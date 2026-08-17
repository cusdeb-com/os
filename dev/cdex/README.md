To simplify CDEX development and debugging, CusDeb OS provides the **CDEX-over-SPICE** container. It runs CDEX together with all required dependencies—including the custom Wine build—in a container and exposes the desktop through **SPICE**.

SPICE is a remote-access protocol that lets you interact with a graphical environment running inside the container almost like a *local desktop*. Unlike **VNC**, which primarily transmits the screen and input events, SPICE is designed for richer interaction with remote environments, including *clipboard sharing*, *audio*, and *device redirection*.

## Prerequisites

* Docker >= 18.09
* A SPICE client, such as `virt-viewer` or [Remmina](https://remmina.org) with the SPICE plugin, which is usually installed separately

## Build, Run, and Stop

To build a Docker image containing the stable version of CDEX from the **CusDeb Archive** and start the CDEX-over-SPICE container, run:

```sh
./up.sh
```

Once the image has been built, this command will only start the container. To force an image rebuild before starting it, run:

```sh
./up.sh --rebuild
```

Once the CDEX-over-SPICE container is running, connect to it using a SPICE client. For example:

```sh
remote-viewer spice://localhost:5900
```

The default password is `secret`. See [Configuration](#configuration) for instructions on how to change it.

When you're done with the CDEX-over-SPICE container, stop and remove it with:

```sh
docker rm -f cdex
```

## Swapping Packages

Once you've played around with the stable version of CDEX, you'll probably want to modify CDEX—or even the Wine build it depends on—and test your changes in the same environment.

Docker also lets you rebuild the [CDEX](https://github.com/cusdeb-com/os/tree/main/core/cdex) and [Wine](https://github.com/cusdeb-com/os/tree/main/core/wine) packages and swap them into the running environment without rebuilding the entire image:

```sh
docker cp my-package.deb cdex:/tmp/
docker exec cdex dpkg -i /tmp/my-package.deb
docker restart cdex
```

Reconnect to the SPICE server, and *the change is live*.

## Implementation Details

* Trixie's `xserver-xspice` / `spiceqxl` driver segfaults on Xorg 21, so the session runs on **Xvfb**, with **x11spice** attaching a SPICE server to it. Since `x11spice` isn't packaged in Trixie, it's compiled from source in a builder stage. The build toolchain remains there, while the runtime image contains only `x11spice` and its runtime libraries.
* Wine won't run its session as root, so CDEX runs as the `cusdeb` user. This user has passwordless `sudo`, matching the privileges granted to the desktop user in an installed CusDeb OS system.

## Configuration

`up.sh` / the container honour these env vars:

| Variable         | Default             | Meaning                                             |
| ---------------- | ------------------- | ----------------------------------------------------|
| `SPICE_PORT`     | `5900`              | Host port the SPICE server is published on          |
| `SPICE_BIND`     | `127.0.0.1`         | Host address to bind; use `0.0.0.0` to allow remote |
| `SPICE_PASSWORD` | `secret`            | SPICE connection password                           |
| `RESOLUTION`     | `1280x720x24`       | Xvfb screen geometry                                |

Example: `SPICE_PORT=5900 SPICE_PASSWORD=secret ./up.sh`
