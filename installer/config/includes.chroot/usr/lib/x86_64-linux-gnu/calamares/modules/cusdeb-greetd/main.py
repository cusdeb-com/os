#!/usr/bin/env python3
"""Replace live autologin with the installed user's greetd preferences."""

import libcalamares


def run():
    storage = libcalamares.globalstorage
    command = ["/usr/bin/cdex-configure-login"]
    username = storage.value("autoLoginUser")
    if username:
        command += ["--autologin-user", username]
    else:
        command.append("--disable-autologin")
    status = libcalamares.utils.target_env_call(command)
    if status != 0:
        return ("Could not configure the CusDeb login session", f"cdex-configure-login returned {status}")
    return None
