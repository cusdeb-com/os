#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
project=/mnt/cusdeb
staging=/var/lib/cdex-prototype
mkdir -p "$staging" /etc/apt/keyrings

dpkg --add-architecture i386
curl --fail --silent --show-error --location \
  https://cusdeb-com.github.io/os/KEY.gpg -o /etc/apt/keyrings/cusdeb.gpg
chmod 644 /etc/apt/keyrings/cusdeb.gpg
cat >/etc/apt/sources.list.d/cusdeb.list <<'SOURCES'
deb [signed-by=/etc/apt/keyrings/cusdeb.gpg] https://cusdeb-com.github.io/os/ stable main
SOURCES
apt-get update

# Exercise the real package dependencies and maintainer scripts, as in the ISO.
version=$(sed -n '1s/.*(\(.*\)).*/\1/p' "$project/core/cdex/debian/changelog")
set -- "$project"/core/cdex/out/*_"$version"_amd64.deb
if [ ! -f "$1" ]; then
  echo 'Build CDEX first: make -C core/cdex image && make -C core/cdex build PACKAGE_DIR=out' >&2
  exit 1
fi
rm -f "$staging"/*.deb
cp "$@" "$staging/"
apt-get install -y --no-install-recommends -o Dpkg::Options::=--force-confold \
  "$staging"/*.deb libgl1-mesa-dri:i386 mesa-utils
/usr/bin/cdex-configure-login --autologin-user tester

# Remove the previous development-only TTY autologin if this VM is reused.
rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
if [ -f /home/tester/.bash_profile ] && grep -q cdex-prototype-login /home/tester/.bash_profile; then
  mv /home/tester/.bash_profile /home/tester/.bash_profile.prototype-backup
fi
systemctl daemon-reload
systemctl enable --force greetd.service
touch "$staging/ready"
systemctl restart greetd.service
