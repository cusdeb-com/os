#!/usr/bin/env python3
"""Generate project-owned CDEX shell icons for the ReactOS build."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


# Raster sizes embedded in every ICO, covering shell views from 16px through
# the 256px high-resolution variant.
ICON_SIZES = (256, 128, 96, 64, 48, 40, 32, 24, 20, 16)


@dataclass(frozen=True)
class IconAsset:
    """Describe an SVG master and the legacy resource IDs it replaces."""

    name: str
    source: Path
    resource_ids: tuple[int, ...]


# The catalog intentionally lives beside the transformation code. Each
# semantic SVG master can serve more than one legacy ReactOS resource ID;
# the generated header exposes one path macro per ID.  Keep these source paths
# stable so replacing an SVG master does not require build-logic changes.
ICON_ASSETS = (
    IconAsset(
        name="folder",
        source=Path("assets/icons/folder.svg"),
        resource_ids=(4, 20, 37, 42, 143, 146, 147, 183, 256, 264),
    ),
    IconAsset(
        name="my-computer",
        source=Path("assets/icons/my-computer.svg"),
        resource_ids=(16, 43, 179, 180, 282),
    ),
    IconAsset(
        name="recycle-bin-empty",
        source=Path("assets/icons/recycle-bin-empty.svg"),
        resource_ids=(32, 191, 254),
    ),
    IconAsset(
        name="recycle-bin-full",
        source=Path("assets/icons/recycle-bin-full.svg"),
        resource_ids=(33, 192, 240),
    ),
    IconAsset(
        name="document",
        source=Path("assets/icons/gnome/fullcolor/text-x-generic.svg"),
        resource_ids=(1, 151, 152, 243, 1007),
    ),
    IconAsset(
        name="rich-text",
        source=Path("assets/icons/gnome/fullcolor/x-office-document.svg"),
        resource_ids=(2,),
    ),
    IconAsset(
        name="executable",
        source=Path("assets/icons/gnome/fullcolor/application-x-executable.svg"),
        resource_ids=(3, 154, 278),
    ),
    IconAsset(
        name="folder-open",
        source=Path("assets/icons/gnome/symbolic/status/folder-open-symbolic.svg"),
        resource_ids=(5, 184, 185, 186, 187),
    ),
    IconAsset(
        name="floppy",
        source=Path("assets/icons/gnome/fullcolor/media-floppy.svg"),
        resource_ids=(6, 7, 233, 305),
    ),
    IconAsset(
        name="removable-drive",
        source=Path("assets/icons/gnome/fullcolor/drive-removable-media.svg"),
        resource_ids=(8, 230, 307, 308, 312, 313),
    ),
    IconAsset(
        name="hard-drive",
        source=Path("assets/icons/gnome/fullcolor/drive-harddisk.svg"),
        resource_ids=(9, 13),
    ),
    IconAsset(
        name="network-server",
        source=Path("assets/icons/gnome/fullcolor/network-server.svg"),
        resource_ids=(10, 15, 19, 172, 176, 178, 300, 301, 1003),
    ),
    IconAsset(
        name="network-offline",
        source=Path("assets/icons/gnome/symbolic/status/network-offline-symbolic.svg"),
        resource_ids=(11, 49, 331),
    ),
    IconAsset(
        name="optical-drive",
        source=Path("assets/icons/gnome/fullcolor/drive-optical.svg"),
        resource_ids=(12, 222, 260, 261, 262, 291, 292, 293, 294, 295, 296, 297, 298, 302, 304, 318, 320),
    ),
    IconAsset(
        name="network-workgroup",
        source=Path("assets/icons/gnome/fullcolor/network-workgroup.svg"),
        resource_ids=(14, 18),
    ),
    IconAsset(
        name="printer",
        source=Path("assets/icons/gnome/fullcolor/printer.svg"),
        resource_ids=(17, 38, 138, 139, 141, 168, 170, 196, 197, 245, 252, 1002, 1006, 1008, 1009, 1011),
    ),
    IconAsset(
        name="recent-documents",
        source=Path("assets/icons/gnome/symbolic/actions/document-open-recent-symbolic.svg"),
        resource_ids=(21,),
    ),
    IconAsset(
        name="control-panel",
        source=Path("assets/icons/gnome/symbolic/categories/preferences-system-symbolic.svg"),
        resource_ids=(22, 36, 137, 148, 210, 321),
    ),
    IconAsset(
        name="search",
        source=Path("assets/icons/gnome/symbolic/actions/system-search-symbolic.svg"),
        resource_ids=(23, 281, 337),
    ),
    IconAsset(
        name="help",
        source=Path("assets/icons/gnome/symbolic/categories/system-help-symbolic.svg"),
        resource_ids=(24, 263),
    ),
    IconAsset(
        name="run",
        source=Path("assets/icons/gnome/symbolic/actions/system-run-symbolic.svg"),
        resource_ids=(25, 160),
    ),
    IconAsset(
        name="sleep",
        source=Path("assets/icons/gnome/symbolic/actions/gnome-power-manager-symbolic.svg"),
        resource_ids=(26,),
    ),
    IconAsset(
        name="eject",
        source=Path("assets/icons/gnome/symbolic/actions/media-eject-symbolic.svg"),
        resource_ids=(27,),
    ),
    IconAsset(
        name="shutdown",
        source=Path("assets/icons/gnome/symbolic/actions/system-shutdown-symbolic.svg"),
        resource_ids=(28, 221, 8240),
    ),
    IconAsset(
        name="share",
        source=Path("assets/icons/gnome/symbolic/actions/send-to-symbolic.svg"),
        resource_ids=(29, 244, 265),
    ),
    IconAsset(
        name="folder-wait",
        source=Path("assets/icons/gnome/symbolic/status/folder-visiting-symbolic.svg"),
        resource_ids=(31,),
    ),
    IconAsset(
        name="remote-folder",
        source=Path("assets/icons/gnome/fullcolor/folder-remote.svg"),
        resource_ids=(34, 193),
    ),
    IconAsset(
        name="desktop",
        source=Path("assets/icons/gnome/fullcolor/user-desktop.svg"),
        resource_ids=(35, 181),
    ),
    IconAsset(
        name="font",
        source=Path("assets/icons/gnome/fullcolor/font-x-generic.svg"),
        resource_ids=(39, 155, 156, 157),
    ),
    IconAsset(
        name="start-menu",
        source=Path("assets/icons/gnome/symbolic/places/start-here-symbolic.svg"),
        resource_ids=(40,),
    ),
    IconAsset(
        name="music",
        source=Path("assets/icons/gnome/fullcolor/audio-x-generic.svg"),
        resource_ids=(41, 225, 228, 247, 277),
    ),
    IconAsset(
        name="favorites",
        source=Path("assets/icons/gnome/fullcolor/user-bookmarks.svg"),
        resource_ids=(44, 173),
    ),
    IconAsset(
        name="logout",
        source=Path("assets/icons/gnome/symbolic/actions/system-log-out-symbolic.svg"),
        resource_ids=(45,),
    ),
    IconAsset(
        name="file-manager",
        source=Path("assets/icons/gnome/symbolic/legacy/system-file-manager-symbolic.svg"),
        resource_ids=(46,),
    ),
    IconAsset(
        name="refresh",
        source=Path("assets/icons/gnome/symbolic/actions/view-refresh-symbolic.svg"),
        resource_ids=(47,),
    ),
    IconAsset(
        name="lock",
        source=Path("assets/icons/gnome/symbolic/status/system-lock-screen-symbolic.svg"),
        resource_ids=(48, 194),
    ),
    IconAsset(
        name="not-connected-drive",
        source=Path("assets/icons/gnome/symbolic/devices/drive-harddisk-symbolic.svg"),
        resource_ids=(54, 234),
    ),
    IconAsset(
        name="printer-network",
        source=Path("assets/icons/gnome/fullcolor/printer-network.svg"),
        resource_ids=(140, 169, 198, 199, 311, 1010),
    ),
    IconAsset(
        name="text-script",
        source=Path("assets/icons/gnome/fullcolor/text-x-script.svg"),
        resource_ids=(153,),
    ),
    IconAsset(
        name="image",
        source=Path("assets/icons/gnome/fullcolor/image-x-generic.svg"),
        resource_ids=(226, 249, 251),
    ),
    IconAsset(
        name="video",
        source=Path("assets/icons/gnome/fullcolor/video-x-generic.svg"),
        resource_ids=(224, 227),
    ),
    IconAsset(
        name="folder-documents",
        source=Path("assets/icons/gnome/fullcolor/folder-documents.svg"),
        resource_ids=(235,),
    ),
    IconAsset(
        name="folder-pictures",
        source=Path("assets/icons/gnome/fullcolor/folder-pictures.svg"),
        resource_ids=(236,),
    ),
    IconAsset(
        name="folder-music",
        source=Path("assets/icons/gnome/fullcolor/folder-music.svg"),
        resource_ids=(237,),
    ),
    IconAsset(
        name="folder-videos",
        source=Path("assets/icons/gnome/fullcolor/folder-videos.svg"),
        resource_ids=(238,),
    ),
    IconAsset(
        name="camera",
        source=Path("assets/icons/gnome/fullcolor/camera-web.svg"),
        resource_ids=(248, 309, 317),
    ),
    IconAsset(
        name="display",
        source=Path("assets/icons/gnome/fullcolor/video-display.svg"),
        resource_ids=(250,),
    ),
    IconAsset(
        name="mouse",
        source=Path("assets/icons/gnome/fullcolor/input-mouse.svg"),
        resource_ids=(229, 272),
    ),
    IconAsset(
        name="keyboard",
        source=Path("assets/icons/gnome/fullcolor/input-keyboard.svg"),
        resource_ids=(283,),
    ),
    IconAsset(
        name="scanner",
        source=Path("assets/icons/gnome/fullcolor/scanner.svg"),
        resource_ids=(315, 316),
    ),
    IconAsset(
        name="phone",
        source=Path("assets/icons/gnome/fullcolor/phone.svg"),
        resource_ids=(299, 310, 314),
    ),
    IconAsset(
        name="flash-media",
        source=Path("assets/icons/gnome/fullcolor/media-flash.svg"),
        resource_ids=(303,),
    ),
    IconAsset(
        name="folder-new",
        source=Path("assets/icons/gnome/symbolic/actions/folder-new-symbolic.svg"),
        resource_ids=(319,),
    ),
    IconAsset(
        name="copy",
        source=Path("assets/icons/gnome/symbolic/actions/edit-copy-symbolic.svg"),
        resource_ids=(145,),
    ),
    IconAsset(
        name="delete",
        source=Path("assets/icons/gnome/symbolic/actions/edit-delete-symbolic.svg"),
        resource_ids=(161, 338, 16710, 16715, 16717, 16718, 16721),
    ),
    IconAsset(
        name="users",
        source=Path("assets/icons/gnome/symbolic/legacy/system-users-symbolic.svg"),
        resource_ids=(220, 269, 279),
    ),
    IconAsset(
        name="accessibility",
        source=Path("assets/icons/gnome/symbolic/legacy/preferences-desktop-accessibility-symbolic.svg"),
        resource_ids=(268,),
    ),
    IconAsset(
        name="screen-colors",
        source=Path("assets/icons/gnome/symbolic/legacy/preferences-desktop-color-symbolic.svg"),
        resource_ids=(270,),
    ),
    IconAsset(
        name="display-settings",
        source=Path("assets/icons/gnome/symbolic/legacy/preferences-desktop-display-symbolic.svg"),
        resource_ids=(174, 177),
    ),
    IconAsset(
        name="system",
        source=Path("assets/icons/gnome/symbolic/categories/applications-system-symbolic.svg"),
        resource_ids=(274,),
    ),
    IconAsset(
        name="help-browser",
        source=Path("assets/icons/gnome/symbolic/legacy/help-browser-symbolic.svg"),
        resource_ids=(239, 289, 512, 1004),
    ),
    IconAsset(
        name="go",
        source=Path("assets/icons/gnome/symbolic/actions/go-jump-symbolic.svg"),
        resource_ids=(290,),
    ),
    IconAsset(
        name="network",
        source=Path("assets/icons/gnome/symbolic/devices/network-wired-symbolic.svg"),
        resource_ids=(175, 257, 273),
    ),
    IconAsset(
        name="home",
        source=Path("assets/icons/gnome/fullcolor/user-home.svg"),
        resource_ids=(259,),
    ),
    IconAsset(
        name="public-folder",
        source=Path("assets/icons/gnome/fullcolor/folder-publicshare.svg"),
        resource_ids=(267,),
    ),
    IconAsset(
        name="package",
        source=Path("assets/icons/gnome/fullcolor/package-x-generic.svg"),
        resource_ids=(271,),
    ),
    IconAsset(
        name="window-close",
        source=Path("assets/icons/gnome/symbolic/ui/window-close-symbolic.svg"),
        resource_ids=(200,),
    ),

    # The classic Start menu has dedicated resource IDs and dedicated masters.
    # Their 32px canvases contain smaller artwork, matching ReactOS's layout.
    IconAsset(
        name="favorites-start-menu",
        source=Path("assets/icons/gnome/start-menu/favorites.svg"),
        resource_ids=(322,),
    ),
    IconAsset(
        name="search-start-menu",
        source=Path("assets/icons/gnome/start-menu/search.svg"),
        resource_ids=(323,),
    ),
    IconAsset(
        name="help-start-menu",
        source=Path("assets/icons/gnome/start-menu/help.svg"),
        resource_ids=(324,),
    ),
    IconAsset(
        name="logout-start-menu",
        source=Path("assets/icons/gnome/start-menu/logout.svg"),
        resource_ids=(325,),
    ),
    IconAsset(
        name="folder-start-menu",
        source=Path("assets/icons/gnome/start-menu/folder.svg"),
        resource_ids=(326,),
    ),
    IconAsset(
        name="recent-documents-start-menu",
        source=Path("assets/icons/gnome/start-menu/recent-documents.svg"),
        resource_ids=(327,),
    ),
    IconAsset(
        name="run-start-menu",
        source=Path("assets/icons/gnome/start-menu/run.svg"),
        resource_ids=(328,),
    ),
    IconAsset(
        name="shutdown-start-menu",
        source=Path("assets/icons/gnome/start-menu/shutdown.svg"),
        resource_ids=(329,),
    ),
    IconAsset(
        name="control-panel-start-menu",
        source=Path("assets/icons/gnome/start-menu/control-panel.svg"),
        resource_ids=(330,),
    ),
)


# Generated header consumed by the ReactOS shell32 resource script.
ICON_HEADER_NAME = "cdex_icon_paths.h"

# Treat changes to this pipeline as inputs so generated ICOs are rebuilt.
SCRIPT_PATH = Path(__file__).resolve()


def find_image_converter() -> str:
    """Return an ImageMagick executable available in the build image.

    Returns:
        The executable path suitable for ``subprocess.run``.

    Raises:
        RuntimeError: If neither ``magick`` nor ``convert`` is installed.
    """

    for executable in ("magick", "convert"):
        path = shutil.which(executable)
        if path:
            return path
    raise RuntimeError("ImageMagick is required (expected magick or convert)")


def is_stale(source: Path, output: Path) -> bool:
    """Return whether an icon output is older than one of its inputs.

    The source SVG and this script are both inputs: changing either one must
    cause the generated ICO to be refreshed.

    Args:
        source: SVG master used to generate the output.
        output: Generated ICO whose timestamp is checked.

    Returns:
        ``True`` when the output is missing or an input is newer.
    """
    if not output.is_file():
        return True
    newest_input = max(source.stat().st_mtime_ns, SCRIPT_PATH.stat().st_mtime_ns)
    return newest_input > output.stat().st_mtime_ns


def generate_icon(asset: IconAsset, root: Path, build_dir: Path) -> None:
    """Generate one catalog SVG as a multi-resolution ICO.

    Args:
        asset: Catalog entry describing the SVG source, name, and resource IDs.
        root: Project root containing the asset source.
        build_dir: Directory receiving generated ICO files.

    Raises:
        RuntimeError: If the source is missing or ImageMagick is unavailable.
        subprocess.CalledProcessError: If ImageMagick cannot create the ICO.
    """
    source = root / asset.source
    output = build_dir / f"{asset.name}.ico"

    if not source.is_file():
        raise RuntimeError(f"icon source does not exist: {source}")

    if not is_stale(source, output):
        return

    build_dir.mkdir(parents=True, exist_ok=True)
    converter = find_image_converter()
    with tempfile.NamedTemporaryFile(
        dir=build_dir, prefix=f".{asset.name}.", suffix=".ico", delete=False
    ) as temporary:
        temporary_output = Path(temporary.name)

    try:
        command = [
            converter,
            "-background",
            "none",
            str(source),
            "-alpha",
            "on",
            "-filter",
            "Lanczos",
            "-define",
            f"icon:auto-resize={','.join(map(str, ICON_SIZES))}",
            str(temporary_output),
        ]

        print(f"=== Generating shell icon {asset.name} ===")
        subprocess.run(command, check=True)
        os.replace(temporary_output, output)
    finally:
        temporary_output.unlink(missing_ok=True)


def write_if_changed(path: Path, content: str) -> None:
    """Write generated text without changing its mtime when content is equal.

    Args:
        path: Destination file for the generated text.
        content: Complete text that should be published.
    """

    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", text=True
    )
    temporary = Path(temporary_name)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def generate_icon_header(build_dir: Path) -> Path:
    """Write the resource-header mapping generated ICOs to absolute paths.

    Args:
        build_dir: Directory containing the generated ICO files and receiving
            the header.

    Returns:
        Path to the generated C header.
    """

    lines = [
        "/* Generated by tools/asset_pipeline.py; do not edit. */",
        "#ifndef CDEX_ICON_PATHS_H",
        "#define CDEX_ICON_PATHS_H",
        "",
    ]

    resource_paths: dict[int, Path] = {}
    for asset in ICON_ASSETS:
        output = (build_dir / f"{asset.name}.ico").resolve()
        for resource_id in asset.resource_ids:
            if resource_id in resource_paths:
                raise RuntimeError(
                    f"resource ID {resource_id} is mapped by more than one icon"
                )
            resource_paths[resource_id] = output

    for resource_id, output in sorted(resource_paths.items()):
        lines.append(f"#define CDEX_ICON_{resource_id} {json.dumps(str(output))}")

    lines.extend(("", "#endif /* CDEX_ICON_PATHS_H */", ""))
    header = build_dir / ICON_HEADER_NAME
    write_if_changed(header, "\n".join(lines))
    return header


def prepare_icon_assets(root: Path, build_dir: Path) -> None:
    """Prepare catalog icon assets and their resource-path header.

    Args:
        root: Project root containing the SVG masters.
        build_dir: Directory receiving generated ICO files and the header.

    Raises:
        OSError: If an input or output file cannot be accessed.
        RuntimeError: If icon conversion cannot be started.
        subprocess.CalledProcessError: If ImageMagick conversion fails.
    """
    root = root.resolve()
    build_dir = build_dir.resolve()

    for asset in ICON_ASSETS:
        generate_icon(asset, root, build_dir)

    header = generate_icon_header(build_dir)
    print(f"=== Generated shell icon paths {header} ===")


def make_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the asset pipeline.

    Returns:
        Parser accepting the pipeline command and its directory arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="generate shell icons")
    prepare_parser.add_argument("--root", type=Path, default=Path("."))
    prepare_parser.add_argument("--build-dir", type=Path, required=True)
    return parser


def main() -> int:
    """Run the requested asset-pipeline command and return its exit status.

    Returns:
        ``0`` after successful generation, or ``1`` after a reported build
        error.
    """
    args = make_parser().parse_args()
    try:
        prepare_icon_assets(args.root, args.build_dir)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"asset_pipeline.py: error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
