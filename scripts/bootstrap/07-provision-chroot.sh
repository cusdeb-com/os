#!/usr/bin/env bash

stage_07_provision_chroot() {
  # Stage 7: prepare a chroot that behaves enough like a running Debian system
  # for package managers, GRUB, and systemd tooling to work correctly.
  # Bind-mount host pseudo-filesystems so package installation and GRUB tooling
  # behave like a normal booted Debian system inside the chroot.
  printf '[7/8] Preparing chroot and installing kernel/bootloader\n'
  mount --rbind /dev "$MNT/dev"
  mount --make-rslave "$MNT/dev"
  mount -t proc proc "$MNT/proc"
  mount --rbind /sys "$MNT/sys"
  mount --make-rslave "$MNT/sys"

  # Copy the chroot provisioning script and runtime payload into the guest, run
  # provisioning there, then remove the temporary root-side helper files so they
  # do not remain in the final image.
  cp "$CHROOT_SCRIPT_SOURCE" "$MNT/root/inside-chroot.sh"
  cp "$CUSDEB_SESSION_SOURCE" "$MNT/root/cusdeb-session"
  install -d "$MNT/usr/local/bin"
  # Repo-side userland/*.exe files are installed into the guest's /usr/local/bin
  # so launchers and desktop entries can keep stable runtime paths.
  install -m 755 "$APP_BIN_SOURCE_DIR"/*.exe "$MNT/usr/local/bin/"
  install -d "$MNT/usr/local/share/cusdeb/icons"
  install -m 644 "$PAINT_ICON_16_SOURCE" "$MNT/usr/local/share/cusdeb/icons/paint_16.png"
  install -m 644 "$PAINT_ICON_48_SOURCE" "$MNT/usr/local/share/cusdeb/icons/paint_48.png"
  chmod +x "$MNT/root/inside-chroot.sh"
  LOOPDEV="$LOOPDEV" ROOT_UUID="$ROOT_UUID" RELEASE="$RELEASE" chroot "$MNT" /bin/bash /root/inside-chroot.sh
  rm -f "$MNT/root/inside-chroot.sh"
  rm -f "$MNT/root/cusdeb-session"
}
