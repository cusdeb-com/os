"""Create and check XML manifests for the private CDEX runtime.

Module manifests declare a dependency on the shared CDEX assembly. This
module adds that dependency while preserving other manifest content and checks
that linked EXE, DLL and CPL files contain the expected assembly identity.

It also provides helpers for writing the shared manifest and validates its
file list, COM classes and type libraries against the collected module data.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from resources import RT_MANIFEST, Resource

# Windows assembly schema namespace used for manifest elements.
XML_NAMESPACE = "urn:schemas-microsoft-com:asm.v1"

# ElementTree search alias; manifest serialization uses the default namespace.
XML_NAMESPACES = {"asm": XML_NAMESPACE}

# Shared SxS assembly referenced by every packaged ReactOS module.
ASSEMBLY_NAME = "CusDebOS.CDEX.Runtime"

# Module dependencies and the shared manifest must use this exact identity.
PRIVATE_IDENTITY = {
    "type": "win32",
    "name": ASSEMBLY_NAME,
    "version": "1.0.0.0",
    "processorArchitecture": "x86",
}

# Request themed Common Controls v6 from Wine for the private shell assembly.
COMMON_CONTROLS_IDENTITY = {
    "type": "win32",
    "name": "Microsoft.Windows.Common-Controls",
    "version": "6.0.0.0",
    "processorArchitecture": "*",
    "publicKeyToken": "6595b64144ccf1df",
    "language": "*",
}


ET.register_namespace("", XML_NAMESPACE)


# Manifest XML


def xml_tag(name: str) -> str:
    """Qualify an element name with the Windows assembly XML namespace."""
    return f"{{{XML_NAMESPACE}}}{name}"


def new_manifest(identity: dict[str, str]) -> ET.Element:
    """Create an assembly root containing the supplied assembly identity."""
    root = ET.Element(xml_tag("assembly"), manifestVersion="1.0")
    ET.SubElement(root, xml_tag("assemblyIdentity"), identity)
    return root


def private_dependencies(root: ET.Element) -> list[ET.Element]:
    """Return the direct dependency identities referring to our private assembly."""
    identities = root.findall(
        "asm:dependency/asm:dependentAssembly/asm:assemblyIdentity", XML_NAMESPACES,
    )

    return [identity for identity in identities if identity.get("name") == ASSEMBLY_NAME]


def add_private_dependency(root: ET.Element) -> None:
    """Add the private dependency in place, accepting an existing matching one.

    An existing dependency with conflicting identity attributes raises
    ValueError. Unrelated manifest elements are preserved.
    """
    for identity in private_dependencies(root):
        if identity.attrib != PRIVATE_IDENTITY:
            raise ValueError("Conflicting private assembly identity")

        return

    dependency = ET.SubElement(root, xml_tag("dependency"))
    dependent_assembly = ET.SubElement(dependency, xml_tag("dependentAssembly"))
    ET.SubElement(dependent_assembly, xml_tag("assemblyIdentity"), PRIVATE_IDENTITY)


def manifest_ids(kind: str) -> tuple[int, ...]:
    """Return relevant manifest IDs, primary first: EXE 1 or DLL 2 and 123."""
    return (1,) if kind == "exe" else (2, 123)


def merge_manifest_dependencies(resources: list[Resource], kind: str) -> bool:
    """Attach the dependency and report whether a primary manifest was present."""
    ids = manifest_ids(kind)
    primary_found = False

    for resource in resources:
        if resource.type != RT_MANIFEST or resource.name not in ids:
            continue

        root = ET.fromstring(resource.data)
        add_private_dependency(root)
        resource.data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        if resource.name == ids[0]:
            primary_found = True

    return primary_found


def require_private_dependencies(module: Path, resources: list[Resource]) -> None:
    """Require exactly one matching private dependency in each relevant manifest.

    Reject modules without a relevant manifest and manifests with missing,
    duplicate or conflicting private dependency identities.
    """
    kind = "exe" if module.suffix.lower() == ".exe" else "dll"
    manifests = [
        resource for resource in resources
        if resource.type == RT_MANIFEST and resource.name in manifest_ids(kind)
    ]
    if not manifests:
        raise ValueError(f"Private dependency missing: {module.name}")

    for manifest in manifests:
        identities = private_dependencies(ET.fromstring(manifest.data))
        if len(identities) != 1 or identities[0].attrib != PRIVATE_IDENTITY:
            raise ValueError(f"Private dependency missing: {module.name}")


def require_linked_resources(
    module: Path,
    compiled_resources: list[Resource],
    linked_resources: list[Resource],
) -> None:
    """Require every linked PE resource to match the RES records passed to the linker."""
    expected = Counter((resource.key, resource.data) for resource in compiled_resources)
    actual = Counter((resource.key, resource.data) for resource in linked_resources)
    if expected == actual:
        return

    missing_records = expected - actual
    unexpected_records = actual - expected

    def key_counts(records: Counter) -> Counter:
        counts = Counter()
        for (key, _), count in records.items():
            counts[key] += count
        return counts

    missing = key_counts(missing_records)
    unexpected = key_counts(unexpected_records)
    changed = sorted(missing.keys() & unexpected.keys(), key=repr)
    missing_only = sorted(missing.keys() - unexpected.keys(), key=repr)
    unexpected_only = sorted(unexpected.keys() - missing.keys(), key=repr)
    raise ValueError(
        f"PE resources differ between RES and linked PE for {module.name}: "
        f"missing={[(key, missing[key]) for key in missing_only]}, "
        f"unexpected={[(key, unexpected[key]) for key in unexpected_only]}, "
        f"changed={[(key, missing[key], unexpected[key]) for key in changed]}"
    )


def write_xml(root: ET.Element, path: Path) -> None:
    """Write a UTF-8 manifest with an XML declaration."""
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def validate_assembly_manifest(
    path: Path,
    expected_providers: set[str],
    class_owners: dict[str, tuple[str, dict[str, str]]],
    typelib_owners: dict[tuple[str, int, int], tuple[str, bytes]],
) -> None:
    """Check the written assembly identity, payload list and COM metadata."""
    root = ET.parse(path).getroot()
    identities = root.findall("asm:assemblyIdentity", XML_NAMESPACES)
    if root.tag != xml_tag("assembly") or len(identities) != 1:
        raise ValueError("Invalid private assembly manifest root")
    if identities[0].attrib != PRIVATE_IDENTITY:
        raise ValueError("Private assembly identity does not match payload dependencies")

    files = root.findall("asm:file", XML_NAMESPACES)
    names = [entry.get("name", "") for entry in files]
    folded_names = [name.casefold() for name in names]
    expected_names = {name.casefold() for name in expected_providers}
    if len(folded_names) != len(set(folded_names)) or set(folded_names) != expected_names:
        raise ValueError("Private assembly file list does not match packaged DLL/CPL files")

    actual_classes = {}
    actual_typelibs = {}
    for entry in files:
        provider = entry.get("name", "").casefold()
        for declaration in entry.findall("asm:comClass", XML_NAMESPACES):
            clsid = declaration.get("clsid", "").casefold()
            if not clsid or clsid in actual_classes:
                raise ValueError(f"Duplicate or missing COM class in private manifest: {clsid}")
            actual_classes[clsid] = (
                provider,
                {key: value for key, value in declaration.attrib.items() if key != "clsid"},
            )

        for declaration in entry.findall("asm:typelib", XML_NAMESPACES):
            tlbid = declaration.get("tlbid", "").casefold()
            version = declaration.get("version", "")
            key = (tlbid, version)
            if not tlbid or key in actual_typelibs:
                raise ValueError(f"Duplicate or missing TypeLib in private manifest: {key}")
            actual_typelibs[key] = provider

    expected_classes = {
        clsid.casefold(): (
            provider.casefold(),
            {key: value for key, value in attributes.items() if key != "clsid"},
        )
        for clsid, (provider, attributes) in class_owners.items()
    }
    expected_typelibs = {
        (tlbid.casefold(), f"{major}.{minor}"): provider.casefold()
        for (tlbid, major, minor), (provider, _) in typelib_owners.items()
    }
    if actual_classes != expected_classes:
        raise ValueError("Private manifest COM classes do not match linked PE registrations")
    if actual_typelibs != expected_typelibs:
        raise ValueError("Private manifest TypeLibs do not match linked PE resources")
