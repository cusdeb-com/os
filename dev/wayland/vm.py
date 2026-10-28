#!/usr/bin/env python3
"""Boot the Debian/Wayland/Openbox/CDEX prototype in QEMU."""

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import socket
import struct
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
# The generic image includes DRM and 9p modules; genericcloud's trimmed
# cloud kernel cannot drive the virtual GPU or mount our read-only shares.
BASE = OUT / "debian-13-generic-amd64.qcow2"
IMAGE_URL = "https://cloud.debian.org/images/cloud/trixie/latest"


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def ssh_options(port):
    return [
        "-F", "/dev/null",
        "-p", str(port), "-i", str(OUT / "id_ed25519"),
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"UserKnownHostsFile={OUT / 'known_hosts'}",
    ]


def prepare():
    OUT.mkdir(exist_ok=True)
    if not BASE.exists():
        run("curl", "-fL", "--retry", "3", "-o", f"{BASE}.part", f"{IMAGE_URL}/{BASE.name}")
        Path(f"{BASE}.part").rename(BASE)
    sums = OUT / "SHA512SUMS"
    if not sums.exists():
        run("curl", "-fL", "-o", sums, f"{IMAGE_URL}/SHA512SUMS")
    expected = None
    for line in sums.read_text().splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*").removeprefix("./") == BASE.name:
            expected = fields[0]
            break
    if expected is None:
        raise RuntimeError("Debian checksum list does not include the image")
    with BASE.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha512").hexdigest()
    if actual != expected:
        raise RuntimeError("Debian image checksum mismatch; remove the cached image and sums")
    print(f"Verified Debian image: SHA512 {actual}", flush=True)
    if not (OUT / "id_ed25519").exists():
        run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", OUT / "id_ed25519")


def start(args):
    if not BASE.exists() or not (OUT / "id_ed25519.pub").exists():
        raise RuntimeError("Run prepare first")
    try:
        qmp("query-status")
    except (OSError, ValueError):
        pass
    else:
        raise RuntimeError("The prototype VM is already running")
    disk = OUT / "guest.qcow2"
    if args.fresh and disk.exists():
        backup = OUT / f"guest-{time.time_ns()}.qcow2"
        disk.rename(backup)
        print(f"Preserved previous VM disk: {backup}")
        (OUT / "known_hosts").unlink(missing_ok=True)
    if disk.exists():
        info = json.loads(subprocess.check_output(["qemu-img", "info", "--output=json", str(disk)]))
        if Path(info["full-backing-filename"]) != BASE:
            raise RuntimeError("The VM disk uses another base image; start with --fresh")
    if not disk.exists():
        run("qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", BASE, disk, "20G")
    key = (OUT / "id_ed25519.pub").read_text().strip()
    config = {
        "hostname": "cusdeb-wayland-prototype",
        "users": [{
            "name": "tester", "shell": "/bin/bash",
            "sudo": "ALL=(ALL) NOPASSWD:ALL",
            "groups": ["video", "render"], "ssh_authorized_keys": [key],
        }],
        "ssh_pwauth": False,
        "package_update": True,
        "packages": ["ca-certificates", "curl"],
        "mounts": [
            ["project", "/mnt/cusdeb", "9p", "trans=virtio,version=9p2000.L,ro", "0", "0"],
        ],
        "runcmd": [["bash", "/mnt/cusdeb/dev/wayland/guest/setup.sh"]],
    }
    (OUT / "user-data").write_text("#cloud-config\n" + json.dumps(config, indent=2) + "\n")
    (OUT / "meta-data").write_text("instance-id: cusdeb-wayland-openbox-prototype-v1\n")
    run("cloud-localds", OUT / "seed.img", OUT / "user-data", OUT / "meta-data")
    command = [
        "qemu-system-x86_64", "-name", "cusdeb-wayland-prototype",
        "-machine", "q35", "-accel", args.accel,
        "-cpu", "host" if args.accel == "kvm" else "max",
        "-m", str(args.memory), "-smp", "2",
        "-drive", f"file={disk},if=virtio,format=qcow2",
        "-drive", f"file={OUT / 'seed.img'},if=virtio,format=raw,readonly=on",
        "-netdev", f"user,id=net0,hostfwd=tcp:127.0.0.1:{args.port}-:22",
        "-device", "virtio-net-pci,netdev=net0",
        "-virtfs", f"local,path={ROOT},mount_tag=project,security_model=none,readonly=on",
        "-qmp", f"unix:{OUT / 'qmp.sock'},server=on,wait=off",
        "-vnc", f"unix:{OUT / 'vnc.sock'}",
        "-serial", f"file:{OUT / 'serial.log'}",
        "-pidfile", str(OUT / "qemu.pid"), "-daemonize",
        "-device", "virtio-vga-gl" if args.gl else "virtio-vga",
        "-display", "egl-headless" if args.gl else "none",
    ]
    run(*command)
    with BASE.open("rb") as stream:
        image_sha512 = hashlib.file_digest(stream, "sha512").hexdigest()
    (OUT / "vm-launch.json").write_text(json.dumps({
        "command": command, "session": "weston-rootful-xwayland-openbox", "ssh_port": args.port,
        "image_sha512": image_sha512,
    }, indent=2) + "\n")
    print(f"QEMU started. SSH: python3 {HERE / 'vm.py'} ssh --port {args.port}")


def qmp(command, arguments=None):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(20)
        connection.connect(str(OUT / "qmp.sock"))
        stream = connection.makefile("rwb")
        json.loads(stream.readline())
        for request in ({"execute": "qmp_capabilities"}, {"execute": command, "arguments": arguments or {}}):
            stream.write(json.dumps(request).encode() + b"\n")
            stream.flush()
            while True:
                response = json.loads(stream.readline())
                if "error" in response:
                    raise RuntimeError(response["error"])
                if "return" in response:
                    break
        return response["return"]


def vnc_screenshot(destination):
    """Read the actual virgl scanout through QEMU's local VNC display.

    EGL-headless has no CPU surface for QMP screendump. VNC performs the
    required readback; no TCP VNC listener or external desktop is used.
    """
    from PIL import Image

    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(30)
        connection.connect(str(OUT / "vnc.sock"))

        def receive(length):
            result = bytearray()
            while len(result) < length:
                chunk = connection.recv(length - len(result))
                if not chunk:
                    raise RuntimeError("QEMU closed the VNC connection")
                result.extend(chunk)
            return bytes(result)

        version = receive(12)
        if not version.startswith(b"RFB 003."):
            raise RuntimeError(f"Unexpected VNC protocol: {version!r}")
        connection.sendall(b"RFB 003.008\n")
        security_types = receive(receive(1)[0])
        if 1 not in security_types:
            raise RuntimeError("The local VNC socket requires unsupported authentication")
        connection.sendall(b"\x01")
        if receive(4) != b"\0\0\0\0":
            raise RuntimeError("VNC security negotiation failed")
        connection.sendall(b"\x01")
        width, height = struct.unpack("!HH", receive(4))
        receive(16)
        receive(struct.unpack("!I", receive(4))[0])
        pixel_format = struct.pack("!BBBBHHHBBB3x", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
        connection.sendall(b"\x00\0\0\0" + pixel_format)
        connection.sendall(struct.pack("!BBHi", 2, 0, 1, 0))  # Raw encoding.
        connection.sendall(struct.pack("!BBHHHH", 3, 0, 0, 0, width, height))
        canvas = Image.new("RGB", (width, height))
        while True:
            message_type = receive(1)[0]
            if message_type == 2:  # Bell.
                continue
            if message_type == 3:  # ServerCutText.
                receive(3)
                receive(struct.unpack("!I", receive(4))[0])
                continue
            if message_type != 0:
                raise RuntimeError(f"Unexpected VNC message: {message_type}")
            receive(1)
            count = struct.unpack("!H", receive(2))[0]
            for _ in range(count):
                x, y, w, h, encoding = struct.unpack("!HHHHi", receive(12))
                if encoding != 0:
                    raise RuntimeError(f"Unexpected VNC encoding: {encoding}")
                raw = receive(w * h * 4)
                canvas.paste(Image.frombytes("RGB", (w, h), raw, "raw", "BGRX"), (x, y))
            if count:
                canvas.save(destination)
                return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("prepare")
    boot = sub.add_parser("start")
    boot.add_argument("--accel", choices=["kvm", "tcg"], default="kvm")
    boot.add_argument("--memory", type=int, default=3072)
    boot.add_argument("--port", type=int, default=22227)
    boot.add_argument("--gl", action="store_true")
    boot.add_argument("--fresh", action="store_true", help="Preserve the old overlay and create a clean VM")
    login = sub.add_parser("ssh")
    login.add_argument("--port", type=int, default=22227)
    login.add_argument("command", nargs=argparse.REMAINDER)
    screenshot = sub.add_parser("screenshot")
    screenshot.add_argument("name", default="desktop", nargs="?")
    keyboard = sub.add_parser("key", help="Send QEMU qcode keys to this VM")
    keyboard.add_argument("keys", nargs="+")
    sub.add_parser("stop")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "start":
        start(args)
    elif args.action == "ssh":
        command = args.command
        if command and command[0] == "--":
            command = command[1:]
        remote = [shlex.join(command)] if command else []
        run("ssh", *ssh_options(args.port), "tester@127.0.0.1", *remote)
    elif args.action == "screenshot":
        if Path(args.name).name != args.name:
            raise ValueError("Screenshot name must not contain directories")
        from PIL import Image
        ppm = OUT / f"{args.name}.ppm"
        png = OUT / f"{args.name}.png"
        try:
            qmp("screendump", {"filename": str(ppm)})
        except RuntimeError as error:
            if "no surface" not in str(error):
                raise
            vnc_screenshot(png)
        else:
            with Image.open(ppm) as picture:
                picture.save(png)
            ppm.unlink()
        print(png)
    elif args.action == "stop":
        qmp("system_powerdown")
    elif args.action == "key":
        for key in args.keys:
            qmp("input-send-event", {"events": [
                {"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": key}}},
                {"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": key}}},
            ]})
            time.sleep(0.15)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"vm: {error}", file=sys.stderr)
        sys.exit(1)
