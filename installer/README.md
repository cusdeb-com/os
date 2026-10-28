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
2. A Wayland session: Weston drives the screen and input, fullscreen rootful
   XWayland hosts the existing Openbox/CDEX desktop. Xorg is excluded.
3. Calamares installer with CusDeb branding.
4. The CusDeb OS layer: `cdex-full` (Wine, ReactOS Explorer shell, standard GTK theme, Linux-to-Win32 taskbar bridge).
5. A hybrid ISO bootable on both BIOS and UEFI.

## Build overview

`run-iso-build.sh` builds the local CDEX packages and stages the current version
in `installer/out/cdex-packages`. It then builds a Docker image and runs
`build-iso.sh` inside it. `build-iso.sh` compiles the custom Calamares viewmodule,
then runs `lb build`. Published CDEX packages cannot override the local desktop
stack.

`auto/config` sets the main `live-build` options: Debian trixie, amd64, `iso-hybrid`, GRUB for BIOS/UEFI, no apt recommends, firmware controlled via `calamares.list.chroot`.

`package-lists/calamares.list.chroot` installs Calamares, the live-boot stack,
Weston, XWayland, Openbox, greetd/gtkgreet/Cage, bootloader tools, networking,
Mesa and firmware. `010-install-cdex.chroot` installs the locally built CDEX
packages and uses the CusDeb APT repository for Wine and other dependencies.
The final verification hook rejects `xorg`, `xserver-xorg*`, `xinit` and LightDM;
X11 client libraries and `xserver-common` remain available for XWayland.

## Live image architecture

### Live user

Created by `live-config` at boot, not baked into the squashfs. This prevents hardcoded credentials from being copied to every installed system by Calamares `unpackfs`.

- Username: `user`, password: `live`.
- Root is locked by default.
- Default groups are configured in `config/includes.chroot/etc/live/config.conf.d/cusdeb.conf`.
- The `users` group is required for the CusDeb polkit poweroff rule.

### Chroot hooks

Hooks in `config/hooks/live/` run after packages are installed:

- `010-install-cdex.chroot` — adds the CusDeb APT repository and installs local CDEX packages.
- `020-enable-greetd.chroot` — enables greetd and live autologin into the Wayland session.
- `099-verify-wayland.chroot` — fails the build if the Xorg server stack is present.
- `fix-path-utilities.chroot` — symlinks utilities Calamares needs (`blkid`, `smartctl`, `ckbcomp`).

### Boot process

The ISO is `iso-hybrid` with GRUB. `live-boot` mounts `/live/filesystem.squashfs` as the root filesystem via overlay/tmpfs.

greetd starts `cdex-wayland-session` for the live user. On logout, the graphical
gtkgreet screen runs under Cage. Installed systems use the same Wayland entry
point. Openbox manages X11 applications inside rootful XWayland; native Wayland
windows are outside its taskbar. The current session automatically sizes itself
for one output.

## Calamares configuration

Upstream configuration lives in `/usr/share/calamares/` from `calamares-settings-debian`. Calamares treats `/etc/calamares/` as the `local` config tree, so files in `config/includes.chroot/etc/calamares/` override upstream settings.

Key overrides:

- `settings.conf` — module sequence and branding.
- `modules/users.conf` — default groups (`users`, `sudo`), locked root.
- `modules/packages.conf` — live-only packages to remove from target.
- `modules/optional-packages.conf` — catalog for the custom selection page.
- `cusdeb-greetd` job — removes live autologin or replaces it with the installed
  user's selected autologin account using `cdex-configure-login`.

Sequence notes:

- `packages` runs before `sources-final` to remove live-only packages using live media sources.
- `optional-packages-apply` runs after `sources-final` to remove deselected optional packages using target network sources.

## Custom modules

- `optional-packages` (C++ / Qt6) — tree of optional package groups. Built in Docker and copied to `config/includes.chroot/usr/lib/x86_64-linux-gnu/calamares/modules/optional-packages/`.
- `optional-packages-apply` (Python) — removes unselected packages from `/target`.
- `cusdeb-greetd` (Python) — configures `/etc/greetd/cusdeb.toml` in the target.
