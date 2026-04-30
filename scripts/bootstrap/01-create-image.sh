#!/usr/bin/env bash

stage_01_create_image() {
  # The script creates a brand-new image file; reusing an old path would risk
  # silently overwriting a previous artifact with a partial or incompatible build.
  if [ -e "$IMAGE_PATH" ]; then
    printf 'Refusing to overwrite existing image: %s\n' "$IMAGE_PATH" >&2
    exit 1
  fi

  # Stage 1: allocate an empty raw disk image file of the requested size.
  printf '[1/8] Creating image: %s (%s)\n' "$IMAGE_PATH" "$IMAGE_SIZE"
  truncate -s "$IMAGE_SIZE" "$IMAGE_PATH"
}
