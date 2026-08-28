# CusDeb OS Installer

Builds a bootable Debian trixie Live ISO with Calamares. The live environment ships Wine, the ReactOS Explorer-based `cdex` shell, and standard GTK theming.

## Contents

- [Quick start](#quick-start)
- [What the installer builds](#what-the-installer-builds)
- [Build overview](#build-overview)
- [Live image architecture](#live-image-architecture)
- [Calamares configuration](#calamares-configuration)
- [Custom modules](#custom-modules)

## Quick start

```bash
./installer/run-iso-build.sh
```

Result: `out/cusdeb-os.iso` (hybrid BIOS/UEFI, amd64).

Every build is currently a full clean rebuild and takes roughly 10–20 minutes depending on mirror speed and hardware.

## What the installer builds

1. A Debian trixie live image configured by `live-build`.
2. A minimal X11 environment (`openbox`, `lightdm`, selected drivers).
3. Calamares installer with CusDeb branding.
4. The CusDeb OS layer: `cdex-full` (Wine, ReactOS Explorer shell, standard GTK theme, Linux-to-Win32 taskbar bridge).
5. A hybrid ISO bootable on both BIOS and UEFI.

## Build overview

`run-iso-build.sh` builds a Docker image and runs `build-iso.sh` inside it. `build-iso.sh` compiles the custom Calamares viewmodule, then runs `lb build`.

`auto/config` sets the main `live-build` options: Debian trixie, amd64, `iso-hybrid`, GRUB for BIOS/UEFI, no apt recommends, firmware controlled via `calamares.list.chroot`.

`package-lists/calamares.list.chroot` installs Calamares, the live-boot stack, minimal X11, bootloader tools, networking, and firmware. `cdex-full` is installed separately by the `010-install-cdex.chroot` hook, which adds the CusDeb APT repository.

## Live image architecture

### Live user

Created by `live-config` at boot, not baked into the squashfs. This prevents hardcoded credentials from being copied to every installed system by Calamares `unpackfs`.

- Username: `user`, password: `live`.
- Root is locked by default.
- Default groups are configured in `config/includes.chroot/etc/live/config.conf.d/cusdeb.conf`.
- The `users` group is required for the CusDeb polkit poweroff rule.

### Chroot hooks

Hooks in `config/hooks/live/` run after packages are installed:

- `010-install-cdex.chroot` — adds the CusDeb APT repository and installs `cdex-full`.
- `enable-lightdm.chroot` — enables `lightdm.service`.
- `fix-path-utilities.chroot` — symlinks utilities Calamares needs (`blkid`, `smartctl`, `ckbcomp`).

### Boot process

The ISO is `iso-hybrid` with GRUB. `live-boot` mounts `/live/filesystem.squashfs` as the root filesystem via overlay/tmpfs.

## Calamares configuration

Upstream configuration lives in `/usr/share/calamares/` from `calamares-settings-debian`. Calamares treats `/etc/calamares/` as the `local` config tree, so files in `config/includes.chroot/etc/calamares/` override upstream settings.

Key overrides:

- `settings.conf` — module sequence and branding.
- `modules/users.conf` — default groups (`users`, `sudo`), locked root.
- `modules/packages.conf` — live-only packages to remove from target.
- `modules/optional-packages.conf` — catalog for the custom selection page.
- `modules/displaymanager.conf` — LightDM autologin for the installed user.

Sequence notes:

- `packages` runs before `sources-final` to remove live-only packages using live media sources.
- `optional-packages-apply` runs after `sources-final` to remove deselected optional packages using target network sources.

## Custom modules

- `optional-packages` (C++ / Qt6) — tree of optional package groups. Built in Docker and copied to `config/includes.chroot/usr/lib/x86_64-linux-gnu/calamares/modules/optional-packages/`.
- `optional-packages-apply` (Python) — removes unselected packages from `/target`.
