# Live-build configuration

This directory contains the live-build configuration used to produce the Debian trixie Live ISO.

## `auto/config`

Shell script invoked by `lb config`. It sets the live-build options:

| Option | Meaning |
|---|---|
| `--mode debian` | Build a Debian live image. |
| `--distribution trixie` | Debian 13 (trixie). |
| `--architecture amd64` | 64-bit x86 image. |
| `--binary-images iso-hybrid` | Hybrid ISO image bootable on BIOS and UEFI. |
| `--bootloader "grub-pc grub-efi"` | GRUB bootloader for BIOS (`grub-pc`) and UEFI (`grub-efi`). |
| `--debian-installer none` | Do not include the Debian text/graphical installer. |
| `--win32-loader false` | No Windows loader. |
| `--archive-areas "main contrib non-free non-free-firmware"` | Enable all archive areas. |
| `--updates true` / `--security true` | Include security and updates repositories. |
| `--cache true` | Enable build caching. |
| `--cache-stages "bootstrap chroot"` | Cache the bootstrap and fully configured live chroot. The cache is still used internally by live-build during a single build, but the build script currently performs a full clean rebuild every time. |
| `--apt-indices false` | Do not include apt package indices in the live image. |
| `--apt-recommends false` | Do not install recommended packages by default. |
| `--firmware-chroot false` | Disable live-build's automatic firmware metapackage selection; firmware is controlled via `calamares.list.chroot` instead. |
| `--bootappend-live "boot=live components console=tty0 console=ttyS0,115200n8"` | Kernel command line for live-boot and serial console. |

## `package-lists/calamares.list.chroot`

Packages installed into the Live chroot. Key groups:

- **Calamares installer:** `calamares`, `calamares-settings-debian`. The package
  `calamares-settings-debian` provides upstream modules and helper scripts; our
  sequence and module settings are overridden through `includes.chroot/etc/calamares/`.
- **Password dictionary:** `cracklib-runtime` (required by the Calamares users module; without it password validation prints `error loading dictionary`).
- **Unpackfs tool:** `squashfs-tools` (provides `unsquashfs`, required by the Calamares `unpackfs` module to copy the live filesystem onto the target disk).
- **Partition/filesystem tools:** `dosfstools` (for FAT32/ESP) and `parted` (for disk partitioning), required by Calamares partition and bootloader modules.
- **Minimal X11 desktop:** `xserver-xorg-core` plus a small set of video/input drivers, `openbox`, `lightdm`, `lightdm-gtk-greeter`.
- **GPU firmware:** `firmware-amd-graphics`, `firmware-misc-nonfree` (required for AMD/Intel GPUs on real hardware; QEMU does not need them).
- **Live-boot stack:** `linux-image-amd64`, `live-boot`, `live-boot-doc`, `live-config`, `live-config-doc`, `live-config-systemd`, `live-tools`, `live-task-localisation`, `live-task-recommended`, `firmware-linux-free`. These packages are installed because the upstream `calamares-settings-debian` `packages` module tries to remove all of them; if any are missing, `apt-get remove` fails.
- **Bootloader support:** `grub-pc`, `grub-efi-amd64-bin`, `efibootmgr`, `os-prober` (used by Calamares when installing GRUB on BIOS or UEFI target disks).
- **Networking:** `network-manager`, `wpasupplicant`, `iw`, `wireless-tools`, and firmware packages for Realtek, Intel, Atheros, Broadcom, and MediaTek Wi-Fi adapters.
- **Utilities:** `xterm`, `smartmontools`, `pciutils`, `usbutils`, `sudo`.
- **Debug-only:** `openssh-server` (gated by `setup-ssh.chroot`; should be removed for release images).

### Why `firmware-linux-free`?

The metapackage `firmware-linux` pulls in `firmware-b43-installer`, which tries to download proprietary Broadcom firmware during package installation and fails inside the chroot. `firmware-linux-free` provides free firmware without install-time network downloads.

## `bootloaders/grub-pc/config.cfg`

Overrides the live-build GRUB template so GRUB loads the font from `/boot/grub/unicode.pf2` directly (`$prefix/unicode.pf2`). The default template uses `font=unicode`, which makes GRUB look under `/boot/grub/fonts/unicode.pf2`; live-build places the font one directory level up, so without this override the graphical menu fails to render on both BIOS and UEFI.

A `fonts/unicode.pf2 -> ../unicode.pf2` symlink is also provided as a fallback.

## `hooks/`

Chroot and binary hooks that configure the live image before ISO creation.

See [`hooks/live/README.md`](hooks/live/README.md).

## `includes.chroot/`

Files placed here are copied into the Live filesystem 1:1 by live-build. The directory structure mirrors the target filesystem.

### Calamares overrides

`calamares-settings-debian` installs its configuration under `/usr/share/calamares/`.
Our `includes.chroot/etc/calamares/settings.conf` sets:

```yaml
modules-search: [ local, /usr/lib/calamares/modules ]
```

Calamares treats `/etc/calamares/` as the `local` config tree, so files placed there
override upstream settings without patching. We use this to:

- provide the full module sequence in `settings.conf`;
- override per-module configs in `modules/*.conf`;
- supply CusDeb branding in `branding/cusdeb/`.

This removes the need for the previous `patch-calamares-settings.*` hooks.

### Why the long Calamares module paths?

Calamares on Debian trixie amd64 loads modules from:

```text
/usr/lib/x86_64-linux-gnu/calamares/modules/
```

To place a custom module at that path in the live image, we store it under:

```text
config/includes.chroot/usr/lib/x86_64-linux-gnu/calamares/modules/<module-name>/
```

### Apt pinning

`etc/apt/preferences.d/99cusdeb` pins the CusDeb repository (`Origin: os-packages`)
above Debian main with `Pin-Priority: 900`. This ensures that packages we ship
(`cdex-base`, patched `wine`, etc.) take precedence over any identically-named
packages in Debian, instead of competing at the default priority 500.

### Important files

```text
includes.chroot/
├── etc/apt/
│   ├── preferences.d/99cusdeb              # Pin CusDeb repo above Debian main
│   ├── sources.list.d/cusdeb.list          # CusDeb package repository
│   └── keyrings/cusdeb.gpg                 # CusDeb repo signing key
├── etc/calamares/
│   ├── settings.conf                       # Full Calamares sequence and branding
│   ├── branding/cusdeb/                    # CusDeb branding assets
│   └── modules/
│       ├── optional-packages.conf          # Package catalog for the viewmodule
│       ├── optional-packages-apply.conf    # Symlink to optional-packages.conf
│       ├── welcome.conf                    # Storage/RAM requirements
│       ├── users.conf                      # Default groups and password policy
│       ├── displaymanager.conf             # LightDM configuration
│       ├── packages.conf                   # Live packages to remove
│       ├── fstab.conf                      # fstab mount options
│       └── partition.conf                  # Partitioning defaults
├── etc/lightdm/lightdm.conf                # Autologin to Openbox via LightDM
└── usr/lib/x86_64-linux-gnu/calamares/modules/
    ├── optional-packages/
    │   ├── module.desc
    │   └── libcalamares_viewmodule_optional-packages.so   # Built in Docker
    └── optional-packages-apply/
        ├── module.desc
        └── main.py
```

## Builds

`run-iso-build.sh` mounts `out/.live-build-cache` as `/tmp/live-build` inside the container and runs `build-iso.sh`. **Every build is currently a full clean rebuild.** Incremental builds were disabled because live-build's cache handling proved unreliable across config/package-list changes.

```bash
./installer/run-iso-build.sh
```

A full build takes roughly 10–20 minutes depending on mirror speed and hardware.

`FORCE_CLEAN` is kept for backward compatibility but is currently ignored.

The build cache directory is still mounted so that leftover bind-mounts can be cleaned up safely inside the container. If a manual cleanup is needed, remove it through a Docker container:

```bash
docker run --rm -v "$(pwd)/out:/out" debian:trixie rm -rf /out/.live-build-cache
mkdir -p out/.live-build-cache
```

See also the top-level [`README.md`](../README.md).
