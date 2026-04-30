#!/usr/bin/env bash

stage_02_partition_image() {
  # Stage 2: lay out a simple BIOS/MBR disk with a single bootable Linux root
  # partition. This image intentionally targets the narrow QEMU + GRUB PC path.
  printf '[2/8] Partitioning image\n'
  parted -s "$IMAGE_PATH" mklabel msdos
  parted -s "$IMAGE_PATH" mkpart primary ext4 1MiB 100%
  parted -s "$IMAGE_PATH" set 1 boot on
}
