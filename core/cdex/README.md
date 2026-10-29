**CDEX** is a desktop environment for Unix-like operating systems in general, and for **CusDeb OS** in particular. It is based on **ReactOS Explorer** and is specifically aimed at recreating the *classic desktop experience*. Unlike other desktop environments for Unix-like operating systems, CDEX is designed to be built in the **Portable Executable** (PE) binary format and executed using a specialized version of [Wine](https://github.com/cusdeb-com/os/tree/main/core/wine).

The name CDEX is a homage to **CDE** (Common Desktop Environment), the desktop environment that served as the default graphical environment on Solaris, HP-UX, IBM AIX, Digital UNIX, and UnixWare for many years. CDEX is also an acronym that can be interpreted as either *CusDeb Desktop Environment X* or *Common Desktop Environment X*.

The desktop starts through greetd on Wayland. Weston runs fullscreen rootful
XWayland, with Openbox and CDEX inside it. Both `cdex-wayland-session` and direct
invocation of `cdex-win32-session` use this path. The package excludes the Xorg
server and LightDM while retaining the X11 clients and libraries needed by Wine.
