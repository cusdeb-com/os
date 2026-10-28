#!/usr/bin/env python3
"""Execute a diagnostic command using the running CDEX Wayland environment."""

import json
import os
from pathlib import Path
import subprocess
import sys


arguments = sys.argv[1:]
background = bool(arguments and arguments[0] == "--background")
if background:
    arguments.pop(0)
if arguments and arguments[0] == "--":
    arguments.pop(0)
if not arguments:
    raise SystemExit("Usage: in-session.py [--background] -- COMMAND [ARG ...]")

runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
environment = json.loads((runtime / "cdex-wayland-environment.json").read_text())
environment = {**os.environ, **environment, "WINEDEBUG": "-all"}
if background:
    with (Path.home() / "prototype-apps.log").open("ab") as log:
        process = subprocess.Popen(
            arguments, env=environment, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, start_new_session=True,
        )
    print(process.pid)
else:
    raise SystemExit(subprocess.call(arguments, env=environment))
