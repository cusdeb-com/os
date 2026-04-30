#!/usr/bin/env bash

stage_08_finalize_image() {
  # Configure root access only after the guest filesystem is fully provisioned.
  if [ -n "$ROOT_PASSWORD" ]; then
    printf '%s\n' "root:$ROOT_PASSWORD" | chroot "$MNT" chpasswd
  else
    chroot "$MNT" passwd -l root
  fi

  # Optionally hand the output artifact back to the invoking host user so Docker
  # builds do not leave a root-owned image behind.
  if [ -n "$HOST_UID" ] && [ -n "$HOST_GID" ]; then
    chown "$HOST_UID:$HOST_GID" "$IMAGE_PATH"
  fi

  # Stage 8: all provisioning is complete and the raw image is ready to boot.
  printf '[8/8] Image is ready: %s\n' "$IMAGE_PATH"
}
