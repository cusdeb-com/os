To simplify CDEX development and debugging, CusDeb OS provides the **CDEX-over-SPICE** container. It runs CDEX together with all required dependencies—including the custom Wine build—in a container and exposes the desktop through **SPICE**.

SPICE is a remote-access protocol that lets you interact with a graphical environment running inside the container almost like a *local desktop*. Unlike **VNC**, which primarily transmits the screen and input events, SPICE is designed for richer interaction with remote environments, including *clipboard sharing*, *audio*, and *device redirection*.

## Prerequisites

* Docker >= 18.09
* A SPICE client, such as `virt-viewer` or [Remmina](https://remmina.org) with the SPICE plugin, which is usually installed separately

## Build, Run, and Stop

To build the Docker images and start the CDEX-over-SPICE container, run:

```sh
./up.sh
```

The first run builds two images:

* `cusdeb-os:x11spice` — the x11spice base image (compiled from source, slow).
* `cusdeb-os:cdex` — the runtime image with CDEX from the **CusDeb Archive**.

After that, `./up.sh` only starts the container unless an image is missing or you ask for a rebuild.

Useful flags:

| Flag | When to use |
| --- | --- |
| `./up.sh -h`, `./up.sh --help` | Show the full usage message and exit. |
| `./up.sh -r`, `./up.sh --rebuild` | Rebuild both images with the Docker cache (use after local changes to `Dockerfile` or `start-cdex.sh`). |
| `./up.sh -c`, `./up.sh --force-rebuild-cdex` | Rebuild only the runtime image without cache (picks up the latest `cdex-full` from the archive). |
| `./up.sh -f`, `./up.sh --force-rebuild-full` | Rebuild the x11spice base and the runtime image without cache (slow, use for a clean slate). |
| `./up.sh -C NAME`, `./up.sh --container NAME` | Use a custom container name instead of `cdex`. |

Run `./up.sh --help` for the complete list of options and environment variables.

Once the container is running, connect to it with a SPICE client. For example:

```sh
remote-viewer spice://localhost:5900
```

The default password is `secret`. See [Configuration](#configuration) for instructions on how to change it.

When you're done with the container, stop and remove it with:

```sh
CONTAINER=cdex  # replace with the name passed to --container
docker rm -f "$CONTAINER"
```

## Swapping Packages

Once you've played around with the stable version of CDEX, you'll probably want to modify CDEX—or even the Wine build it depends on—and test your changes in the same environment.

Docker also lets you rebuild the [CDEX](https://github.com/cusdeb-com/os/tree/main/core/cdex) and [Wine](https://github.com/cusdeb-com/os/tree/main/core/wine) packages and swap them into the running environment without rebuilding the entire image:

```sh
CONTAINER=cdex  # use the same name as above
docker cp my-package.deb "${CONTAINER}:/tmp/"
docker exec "$CONTAINER" dpkg -i /tmp/my-package.deb
docker restart "$CONTAINER"
```

Reconnect to the SPICE server, and *the change is live*.

## Implementation Details

* Trixie's `xserver-xspice` / `spiceqxl` driver segfaults on Xorg 21, so the session runs on **Xvfb**, with **x11spice** attaching a SPICE server to it. Since `x11spice` isn't packaged in Trixie, it is compiled from source in the separate `Dockerfile.x11spice` base image. The runtime image inherits the compiled binaries from `cusdeb-os:x11spice` and installs only CDEX and its runtime dependencies.
* Wine won't run its session as root, so CDEX runs as the `cusdeb` user. This user has passwordless `sudo`, matching the privileges granted to the desktop user in an installed CusDeb OS system.

## Configuration

`up.sh` / the container honour these env vars:

| Variable           | Default                | Meaning                                             |
| ------------------ | ---------------------- | ----------------------------------------------------|
| `SPICE_PORT`       | `5900`                 | Host port the SPICE server is published on          |
| `SPICE_BIND`       | `127.0.0.1`            | Host address to bind; use `0.0.0.0` to allow remote |
| `SPICE_PASSWORD`   | `secret`               | SPICE connection password                           |
| `RESOLUTION`       | `1280x720x24`          | Xvfb screen geometry                                |
| `IMAGE`            | `cusdeb-os:cdex`       | Runtime image tag                                   |
| `CONTAINER`        | `cdex`                 | Container name                                      |
| `X11SPICE_IMAGE`   | `cusdeb-os:x11spice`   | Base x11spice image tag                             |

Example: `SPICE_PORT=5900 SPICE_PASSWORD=secret ./up.sh`
