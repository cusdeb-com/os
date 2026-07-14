# CusDeb OS Calamares Installer

This directory builds a bootable Debian trixie Live ISO with a graphical Calamares installer. The live environment is intentionally minimal: Openbox + LightDM, no full desktop environment. Calamares installs a minimal Debian system to disk.

## Quick start

```bash
./installer/run-iso-build.sh
```

Result: `out/cusdeb-os.iso`

> **Note:** the ISO is a **hybrid BIOS/UEFI** image for amd64 (Intel/AMD x86_64).

## High-level layout

```
installer/
├── Dockerfile            # Debian trixie builder image (live-build + Calamares build deps)
├── run-iso-build.sh      # Host wrapper: builds/runs the Docker builder
├── build-iso.sh          # In-container orchestration: builds C++ module + runs live-build
├── auto/config           # live-build distribution/bootloader options
├── config/               # live-build config, package list, hooks, includes.chroot
│   └── includes.chroot/
│       ├── etc/calamares/               # Calamares override configs and branding
│       │   ├── settings.conf
│       │   ├── modules/
│       │   └── branding/cusdeb/
│       └── usr/lib/x86_64-linux-gnu/calamares/modules/
│           └── optional-packages/       # C++ viewmodule (built in Docker)
└── modules/              # Custom Calamares C++ viewmodules
    └── optional-packages/
```

## Documentation

| Document | What it covers |
|---|---|
| [`config/README.md`](config/README.md) | live-build configuration, package list, `includes.chroot` layout, Calamares overrides |
| [`config/hooks/live/README.md`](config/hooks/live/README.md) | Live chroot hooks (live user, serial console, SSH) |
| [`modules/optional-packages/README.md`](modules/optional-packages/README.md) | Custom C++ viewmodule for optional package selection |
| [`config/includes.chroot/usr/lib/x86_64-linux-gnu/calamares/modules/optional-packages-apply/`](config/includes.chroot/usr/lib/x86_64-linux-gnu/calamares/modules/optional-packages-apply/) | Python job module that removes deselected optional packages from the target system |

## Boot process

The ISO is built as `iso-hybrid` with GRUB for both firmware types:

- **BIOS:** El Torito loads the GRUB PC bootloader.
- **UEFI:** The firmware loads `/EFI/BOOT/BOOTX64.EFI` from the EFI System Partition image embedded in the ISO.
- Kernel and initrd are loaded from `/live/vmlinuz-*` and `/live/initrd.img-*`.
- `live-boot` mounts `/live/filesystem.squashfs` as the root filesystem via overlay/tmpfs.

## Calamares module sequence

The full sequence is committed in
[`config/includes.chroot/etc/calamares/settings.conf`](config/includes.chroot/etc/calamares/settings.conf).
It overrides the sequence shipped by `calamares-settings-debian` because Calamares
loads files from `/etc/calamares/` (`local` search path) before `/usr/share/calamares/`.

```yaml
show:
  - welcome
  - locale
  - keyboard
  - partition
  - users
  - optional-packages
  - summary

exec:
  - partition
  - mount
  - unpackfs
  - luksbootkeyfile
  - dpkg-unsafe-io
  - sources-media
  - machineid
  - fstab
  - locale
  - keyboard
  - localecfg
  - users
  - displaymanager
  - networkcfg
  - hwclock
  - services-systemd
  - bootloader-config
  - grubcfg
  - bootloader
  - packages
  - plymouthcfg
  - initramfscfg
  - initramfs
  - dpkg-unsafe-io-undo
  - sources-media-unmount
  - sources-final
  - optional-packages-apply
  - umount

show:
  - finished
```

Improvements over the previous hook-patched sequence:

- `displaymanager` configures LightDM autologin for the installed user.
- `machineid` explicitly writes `/etc/machine-id` and `/var/lib/dbus/machine-id`.
- `dpkg-unsafe-io` speeds up package installation in the target system.
- `bootloader-config` runs the Debian helper that installs the correct `grub-pc`
  or `grub-efi` package set depending on the firmware mode.
- `packages` runs before `sources-final`, so `apt-get remove` of live-only
  packages uses the live media sources.list.
- `optional-packages-apply` runs after `sources-final`, so its `apt-get
  remove` operation uses the target's final network sources.list.

See the per-module READMEs above for details.

## Debug features

The live image currently includes debug helpers that are **not suitable for release builds**:

- SSH server enabled with root password login (`setup-ssh.chroot`).
- Fixed passwords `user:user` and `root:root` (`create-live-user.chroot`).

Remove or gate these hooks before producing a release image.

## Future work

- Integrate Wine + ReactOS Explorer into the live squashfs.
- Add post-install scripts for Wine prefix, registry, and theme setup.
