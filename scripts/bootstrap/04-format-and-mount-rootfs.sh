#!/usr/bin/env bash

stage_04_format_and_mount_rootfs() {
  # Stage 4: create the filesystem that will become the guest rootfs and mount it
  # into the temporary workspace.
  printf '[4/8] Formatting and mounting root filesystem\n'
  mkfs.ext4 -F "$PART_LOOPDEV"
  ROOT_UUID="$(blkid -s UUID -o value "$PART_LOOPDEV")"
  mount "$PART_LOOPDEV" "$MNT"
}
