#!/usr/bin/env bash

stage_06_write_base_config() {
  # Stage 6: write the baseline guest identity and package source configuration
  # before package installation starts inside the chroot.
  printf '[6/8] Writing base configuration\n'
  cat >"$MNT/etc/hostname" <<EOF
$VM_HOSTNAME
EOF

  # Persist the root filesystem mount so the installed system boots the same UUID
  # we just created on the loop-backed root partition.
  cat >"$MNT/etc/fstab" <<EOF
UUID=$ROOT_UUID / ext4 defaults 0 1
EOF

  # Keep local hostname resolution minimal and deterministic inside the guest.
  cat >"$MNT/etc/hosts" <<EOF
127.0.0.1 localhost
127.0.1.1 $VM_HOSTNAME
EOF

  # Seed the Debian repositories before entering the chroot so all later package
  # installation uses the intended mirror and release channels.
  cat >"$MNT/etc/apt/sources.list" <<EOF
deb $MIRROR $RELEASE main contrib non-free-firmware
deb $MIRROR $RELEASE-updates main contrib non-free-firmware
deb https://security.debian.org/debian-security ${RELEASE}-security main contrib non-free-firmware
EOF

  install_theme_assets_into_rootfs
}
