#!/usr/bin/env python3
"""Prepare private SxS manifests for the CDEX runtime.

The script provides two commands: "resources" and "assembly".

The "resources" command prepares each module before it is linked. It adds
a dependency on the private CDEX assembly to its manifests, creating a primary
manifest when needed. It preserves the other resources and produces files for
the linker and for later verification.

The "assembly" command checks the resources in the finished modules against
the prepared files, then creates the shared manifest. The manifest lists the
packaged DLLs and CPLs and describes the COM classes and type libraries found
in their resources. Conflicting or inconsistent data stops the build.

Together, these manifests let CDEX components use private libraries
alongside Wine.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from com_registry import COM_PROVIDER_PREFERENCE, collect_com_classes
from manifest import (
    ASSEMBLY_NAME,
    COMMON_CONTROLS_IDENTITY,
    PRIVATE_IDENTITY,
    add_private_dependency,
    manifest_ids,
    merge_manifest_dependencies,
    new_manifest,
    require_linked_resources,
    require_private_dependencies,
    validate_assembly_manifest,
    write_xml,
    xml_tag,
)
from resources import RT_MANIFEST, Resource, read_pe_resources, read_res, write_res
from typelib import collect_type_libraries


# Resource preparation before linking


def create_default_manifest_resource(
    module: str, resource_id: int, compiler: str, work: Path,
) -> list[Resource]:
    """Compile a neutral-language primary manifest using temporary files.

    The manifest identifies ``module`` and depends on the private assembly.
    Return the compiler's RES records for inclusion in the module's resources.
    """
    identity = {**PRIVATE_IDENTITY, "name": f"CusDeb.ReactOS.{module}"}
    root = new_manifest(identity)
    add_private_dependency(root)

    manifest = work / "default.xml"
    write_xml(root, manifest)

    rc_file = work / "default.rc"
    res_file = work / "default.res"
    rc_file.write_text(f'LANGUAGE 0, 0\n{resource_id} {RT_MANIFEST} "{manifest}"\n')

    subprocess.run([
        compiler, "-J", "rc", "-O", "res", str(rc_file), str(res_file),
    ], check=True)

    return read_res(res_file)


def prepare_resources(args: argparse.Namespace) -> None:
    """Handle resources: merge manifests, compile COFF and publish both outputs.

    A missing primary manifest is created. RES and COFF files are prepared in
    a temporary directory; each destination is replaced only after compilation.
    """
    resources = []
    for source in args.inputs:
        resources.extend(read_res(source))

    primary_found = merge_manifest_dependencies(resources, args.kind)

    with tempfile.TemporaryDirectory(dir=args.output.parent) as directory:
        work = Path(directory)

        if not primary_found:
            resources.extend(create_default_manifest_resource(
                args.module, manifest_ids(args.kind)[0], args.compiler, work,
            ))

        res_file = work / "merged.res"
        object_file = work / "merged.obj"
        write_res(res_file, resources, args.module)

        subprocess.run([
            args.compiler, "-J", "res", "-O", "coff", str(res_file), str(object_file),
        ], check=True)

        res_file.replace(args.output)
        object_file.replace(args.object)


# Shared assembly generation during packaging


def load_module_resources(payload: Path, resource_directory: Path) -> dict[str, list[Resource]]:
    """Load and validate the resource catalog for every packaged EXE, DLL and CPL.

    Final PE resources must match the manifest, registry scripts and TypeLibs
    passed to the linker. The linked resources then become the source catalog
    for the shared assembly manifest.
    """
    modules = sorted(
        path for path in payload.iterdir() if path.suffix.lower() in {".exe", ".dll", ".cpl"}
    )
    catalogs = {}

    for module in modules:
        index = resource_directory / f"{module.name}.res-path"
        compiled_resources = read_res(Path(index.read_text()))
        linked_resources = read_pe_resources(module)
        require_linked_resources(module, compiled_resources, linked_resources)
        require_private_dependencies(module, linked_resources)
        catalogs[module.name] = linked_resources

    return catalogs


def prepare_assembly(args: argparse.Namespace) -> None:
    """Write the shared manifest from every packaged DLL/CPL and its resources."""
    catalogs = load_module_resources(args.payload, args.resources)

    assembly = new_manifest(PRIVATE_IDENTITY)
    dependency = ET.SubElement(assembly, xml_tag("dependency"))
    dependent_assembly = ET.SubElement(dependency, xml_tag("dependentAssembly"))
    ET.SubElement(dependent_assembly, xml_tag("assemblyIdentity"), COMMON_CONTROLS_IDENTITY)

    owners: dict[str, tuple[str, dict[str, str]]] = {}
    typelib_owners: dict[tuple[str, int, int], tuple[str, bytes]] = {}

    provider_set = {
        module for module in catalogs
        if Path(module).suffix.lower() in {".dll", ".cpl"}
    }

    providers = [module for module in COM_PROVIDER_PREFERENCE if module in provider_set]
    providers.extend(sorted(provider_set - set(providers)))

    for provider in providers:
        provider_element = ET.SubElement(assembly, xml_tag("file"), name=provider)
        typelibs = collect_type_libraries(provider, catalogs[provider], typelib_owners)
        for key in sorted(typelibs):
            library = typelibs[key]
            ET.SubElement(provider_element, xml_tag("typelib"), {
                "tlbid": library.tlbid,
                "version": f"{library.major}.{library.minor}",
                "helpdir": "",
            })

        classes = collect_com_classes(provider, catalogs[provider], owners)

        for clsid in sorted(classes):
            ET.SubElement(provider_element, xml_tag("comClass"), classes[clsid])

        print(f"Private provider: {provider}, COM classes: {len(classes)}", flush=True)

    manifest = args.payload / f"{ASSEMBLY_NAME}.manifest"
    write_xml(assembly, manifest)
    validate_assembly_manifest(manifest, provider_set, owners, typelib_owners)


def main() -> None:
    """Parse build command arguments and dispatch to the selected stage."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)

    resources = commands.add_parser("resources", help="Embed private dependencies before linking")
    resources.add_argument(
        "--compiler", required=True,
        help="Resource compiler used to generate the default manifest and linker object",
    )
    resources.add_argument(
        "--kind", choices=("exe", "dll"), required=True,
        help="Module type, determining which manifest resource IDs are processed",
    )
    resources.add_argument(
        "--module", required=True,
        help="Final module filename, used for manifest identity and diagnostics",
    )
    resources.add_argument(
        "--output", type=Path, required=True,
        help="Merged RES file retained for packaging-time verification",
    )
    resources.add_argument(
        "--object", type=Path, required=True,
        help="COFF object containing the merged resources, passed to the linker",
    )
    resources.add_argument(
        "--inputs", type=Path, nargs="*", default=[],
        help="Compiled input RES files; modules may have none",
    )
    resources.set_defaults(handler=prepare_resources)

    assembly = commands.add_parser("assembly", help="Generate the shared DLL/COM assembly")
    assembly.add_argument(
        "--payload", type=Path, required=True,
        help="Directory containing the packaged modules and receiving the shared manifest",
    )
    assembly.add_argument(
        "--resources", type=Path, required=True,
        help="Directory of RES path indexes generated for the packaged modules",
    )
    assembly.set_defaults(handler=prepare_assembly)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
