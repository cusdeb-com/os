#!/usr/bin/env bash

stage_03_attach_loop_devices() {
  # Stage 3: expose the image as loop devices so the partition can be formatted
  # and mounted like a normal block device.
  printf '[3/8] Attaching loop device\n'
  LOOPDEV="$(losetup --find --show "$IMAGE_PATH")"

  # Ask parted for the exact byte offset instead of guessing a loop offset.
  while IFS=: read -r number start _; do
    if [ "$number" = "1" ]; then
      PART_START_BYTES="${start%B}"
      break
    fi
  done < <(parted -sm "$IMAGE_PATH" unit B print)

  if [ -z "$PART_START_BYTES" ]; then
    printf 'Failed to determine partition offset for %s\n' "$IMAGE_PATH" >&2
    exit 1
  fi

  PART_LOOPDEV="$(losetup --find --show --offset "$PART_START_BYTES" "$IMAGE_PATH")"
}
