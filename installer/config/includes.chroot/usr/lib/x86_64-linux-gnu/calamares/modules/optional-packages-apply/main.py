#!/usr/bin/env python3
"""
Calamares job that makes the installed system match the user's optional
package selection.

All optional packages are pre-installed in the live image, so the target
system already contains every package from the catalog after unpackfs.
This job only removes the packages the user deselected on the
"Optional packages" page.
"""

import subprocess

import libcalamares


def _installed_packages(target_root, package_names):
    """Return the subset of package_names that is installed in /target."""
    if not package_names:
        return []
    try:
        output = subprocess.run(
            ["chroot", target_root, "dpkg-query", "-W", "-f=${Package}\n"]
            + list(package_names),
            check=False,
            capture_output=True,
            text=True,
        ).stdout
        return [line.strip() for line in output.splitlines() if line.strip()]
    except Exception as e:
        libcalamares.utils.warning(f"Failed to query installed packages: {e}")
        return list(package_names)


def _remove_package(target_root, package_name):
    """Remove a single package from the target."""
    libcalamares.utils.debug(f"Removing unselected optional package: {package_name}")
    try:
        subprocess.run(
            ["chroot", target_root, "apt-get", "remove", "-y", "--purge", package_name],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        libcalamares.utils.warning(
            f"Failed to remove unselected package '{package_name}': {e}"
        )


def run():
    gs = libcalamares.globalstorage
    raw_selected = gs.value("optional-packages") or []
    selected_ids = [str(item) for item in raw_selected]

    cfg = libcalamares.job.configuration
    packages = {}
    for group in cfg.get("groups", []):
        for pkg in group.get("packages", []):
            pkg_id = pkg.get("id")
            pkg_name = pkg.get("package")
            if pkg_id and pkg_name:
                packages[pkg_id] = pkg_name
            else:
                libcalamares.utils.warning(
                    f"Skipping malformed optional package entry: {pkg}"
                )

    target_root = gs.value("rootMountPoint")
    if not target_root:
        return (
            "Target root mount point is not set",
            "rootMountPoint is missing from global storage",
        )

    all_ids = set(packages.keys())
    selected = set()
    for pid in selected_ids:
        if pid in packages:
            selected.add(pid)
        else:
            libcalamares.utils.warning(
                f"Ignoring unknown optional package id from viewmodule: {pid}"
            )

    unselected = all_ids - selected
    unselected_pkgs = [packages[pid] for pid in unselected]

    libcalamares.utils.debug(
        f"optional-packages-apply: selected_ids={selected_ids} "
        f"unselected_pkgs={unselected_pkgs}"
    )

    if not unselected_pkgs:
        libcalamares.utils.debug("No packages to remove; nothing to do.")
        return None

    # Remove only the packages that are actually installed in the target.
    installed_unselected = _installed_packages(target_root, unselected_pkgs)
    for package_name in installed_unselected:
        _remove_package(target_root, package_name)

    return None
