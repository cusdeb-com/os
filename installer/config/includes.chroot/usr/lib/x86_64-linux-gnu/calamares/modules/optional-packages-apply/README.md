# `optional-packages-apply` Calamares job module

A custom Calamares **job module** written in Python. It brings the target
system in line with the user's selection on the `optional-packages` page.

## What it does

1. Reads the list of selected package IDs from `globalStorage["optional-packages"]`.
2. Resolves IDs to Debian package names using the shared catalog.
3. Computes the set of **unselected** packages.
4. Removes unselected packages from `/target` with `apt-get remove -y --purge`.

This is needed because the live squashfs contains all optional packages for the
demo mode, but the installed system should only contain what the user selected.

## Files

| File | Purpose |
|---|---|
| `main.py` | Remove-only apply logic. |
| `module.desc` | Calamares plugin descriptor (`type: job`, `interface: python`). |
| `optional-packages-apply.conf` | Symlink to `optional-packages.conf`; provides the package catalog. |
