# Live image hooks

Hooks in this directory run inside the Live chroot during the `lb chroot` stage, after packages are installed but before the ISO is assembled.

For the live-build configuration layer see [`../../README.md`](../../README.md). For Calamares custom modules, see [`../../../modules/optional-packages/README.md`](../../../modules/optional-packages/README.md).

## `create-live-user.chroot`

Creates the Live session user and sets passwords:

- `user:user` — regular user, added to the `sudo` group.
- `root:root` — root password.

This hook is required so the Live environment can be logged into from console or SSH.

## `enable-serial-getty.chroot`

Enables `serial-getty@ttyS0.service` so the Live image accepts logins over a serial port. Useful for QEMU, VirtualBox, and headless debugging.

## `fix-path-utilities.chroot`

Creates symlinks in `/usr/local/bin` for utilities that Calamares launches via `QProcess`:

- `blkid` — used by the partition/filesystem module.
- `smartctl` — used by the `smartstatus` module.
- `ckbcomp` — used for keyboard layout generation.

Calamares runs commands with a minimal `PATH`, so without these symlinks the utilities may not be found.

## `enable-lightdm.chroot`

Enables the `lightdm.service` systemd unit so the Live image boots straight into the graphical LightDM greeter instead of stopping at a text console.

The autologin configuration is provided by `includes.chroot/etc/lightdm/lightdm.conf`:

- Live user `user` logs in automatically.
- Default session is `openbox`.
- Greeter is `lightdm-gtk-greeter`.

## `setup-ssh.chroot`

Enables the SSH server in the Live image and allows root login with a password. Intended for debugging only.

> **Warning:** For production images this hook should be removed or placed behind an optional debug flag.

## See also

- [`config/README.md`](../../README.md) — live-build configuration, package list, and `includes.chroot`.
- [`modules/optional-packages/README.md`](../../../modules/optional-packages/README.md) — C++ viewmodule built and installed via `includes.chroot`.
