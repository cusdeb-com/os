#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# Install the basic bootable runtime first: kernel, GRUB, and systemd pieces.
apt-get update
apt-get install -y linux-image-amd64 grub-pc systemd-sysv systemd-resolved wget ca-certificates binfmt-support

# Enable i386 because Wine still requires 32-bit userspace pieces on amd64.
dpkg --add-architecture i386
mkdir -pm755 /etc/apt/keyrings
# Pull WineHQ from the release-matched repository instead of hardcoding a suite
# name, so the external repo follows the image's Debian release setting.
winehq_source_url="https://dl.winehq.org/wine-builds/debian/dists/${RELEASE}/winehq-${RELEASE}.sources"
wget --spider "$winehq_source_url"
wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
wget -NP /etc/apt/sources.list.d/ "$winehq_source_url"
apt-get update
# Install the GUI/session stack, Wine, LightDM, and the tools needed to run
# desktop apps directly after boot without a heavyweight desktop environment.
apt-get install -y --install-recommends winehq-stable openbox lxpanel lightdm lightdm-gtk-greeter xorg spice-vdagent pcmanfm dbus-x11 gtk2-engines-pixbuf x11-xserver-utils xterm

# Register PE binaries with binfmt so Windows executables can be launched more
# naturally inside the image instead of always invoking wine manually.
cat >/usr/share/binfmts/wine <<'BINFMTWINEEOF'
package wine
interpreter /usr/bin/wine
magic MZ
offset 0
credentials no
fix_binary yes
BINFMTWINEEOF
update-binfmts --import wine

# Configure a minimal DHCP-only network so the VM comes up online by default.
# Use a tiny networkd configuration so QEMU virtual NICs come up via DHCP with
# no desktop-specific network manager dependency.
mkdir -p /etc/systemd/network
cat >/etc/systemd/network/20-wired.network <<'NETEOF'
[Match]
Name=en*

[Network]
DHCP=yes
NETEOF

systemctl enable systemd-networkd.service
systemctl enable systemd-resolved.service

# Use the systemd-resolved stub so guest DNS follows the resolver service.
rm -f /etc/resolv.conf
ln -s /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

# Create the login user that will own the desktop session and home directory.
useradd -m -s /bin/bash cusdeb

# Prepare user-owned desktop and config directories before the first GUI start.
# Pre-create .config as cusdeb because cusdeb-session later creates
# $HOME/.config/{openbox,lxpanel}; wrong ownership makes X exit immediately.
install -d -m 755 -o cusdeb -g cusdeb /home/cusdeb/Desktop
install -d -m 755 -o cusdeb -g cusdeb /home/cusdeb/.config
install -d -m 755 -o cusdeb -g cusdeb /home/cusdeb/.config/libfm
install -d -m 755 -o cusdeb -g cusdeb /home/cusdeb/.config/gtk-3.0
install -d -m 755 -o cusdeb -g cusdeb /home/cusdeb/.config/pcmanfm/default
install -d -m 755 -o cusdeb -g cusdeb /home/cusdeb/.config/lxpanel/default/panels
install -d -m 755 -o cusdeb -g cusdeb /home/cusdeb/.config/openbox
install -d -m 755 /usr/local/share/cusdeb
install -d -m 755 /etc/lightdm/lightdm.conf.d
install -d -m 755 /usr/share/themes/Chicago95-Openbox/openbox-3
cat >/home/cusdeb/.config/libfm/libfm.conf <<'LIBFMEOF'
[config]
quick_exec=1
LIBFMEOF

cat >/home/cusdeb/.config/pcmanfm/default/desktop-items-0.conf <<'PCMANFMDESKTOPEOF'
[*]
wallpaper_mode=color
wallpaper_common=1
wallpapers_configured=1
desktop_bg=#5D81AB
desktop_fg=#ffffff
desktop_shadow=#000000
desktop_font=Sans 8
folder=/home/cusdeb/Desktop
show_wm_menu=0
sort=name;ascending;
show_documents=0
show_trash=1
show_mounts=0
PCMANFMDESKTOPEOF

cat >/home/cusdeb/.config/lxpanel/default/panels/panel <<'LXPANELEOF'
Global {
  edge=bottom
  align=left
  margin=0
  widthtype=percent
  width=100
  height=28
  transparent=0
  alpha=0
  setdocktype=1
  setpartialstrut=1
  autohide=0
  heightwhenhidden=0
  background=0
  iconsize=20
}
Plugin {
  type=menu
  Config {
    name=Start
    system {
    }
    separator {
    }
    item {
      command=run
    }
    separator {
    }
    item {
      command=logout
    }
  }
}
Plugin {
  type=space
  Config {
    Size=4
  }
}
Plugin {
  type=separator
  Config {
  }
}
Plugin {
  type=launchbar
  Config {
    Button {
      image=/usr/share/icons/SE98/devices/16/computer.png
      tooltip=My Computer
      action=wine explorer
    }
  }
}
Plugin {
  type=space
  Config {
    Size=3
  }
}
Plugin {
  type=launchbar
  Config {
    Button {
      image=/usr/share/icons/SE98/apps/16/system-file-manager.png
      tooltip=File Manager
      action=pcmanfm
    }
  }
}
Plugin {
  type=space
  Config {
    Size=4
  }
}
Plugin {
  type=taskbar
  expand=1
  Config {
    tooltips=1
    IconsOnly=0
    ShowAllDesks=0
    UseMouseWheel=1
    UseUrgencyHint=1
    FlatButton=0
    MaxTaskWidth=180
    spacing=1
  }
}
Plugin {
  type=tray
  Config {
  }
}
Plugin {
  type=dclock
  Config {
    ClockFmt=%R
    TooltipFmt=%A %x
    BoldFont=0
    IconOnly=0
    CenterText=0
  }
}
LXPANELEOF

cat >/usr/share/themes/Chicago95-Openbox/openbox-3/themerc <<'OPENBOXTHEMEOF'
border.width: 1
padding.width: 1
window.handle.width: 4
window.client.padding.width: 0
window.label.text.justify: Left
window.label.text.font: Sans:bold:pixelsize=12
menu.title.text.font: Sans:bold:pixelsize=12
menu.items.font: Sans:pixelsize=12

window.active.border.color: #C0C0C0
window.inactive.border.color: #C0C0C0
window.active.title.bg: Flat Solid
window.active.title.bg.color: #000080
window.inactive.title.bg: Flat Solid
window.inactive.title.bg.color: #808080
window.active.label.bg: Parentrelative
window.active.label.text.color: #FFFFFF
window.inactive.label.bg: Parentrelative
window.inactive.label.text.color: #C0C0C0
window.active.button.unpressed.bg: Raised Solid Bevel1
window.active.button.unpressed.bg.color: #C0C0C0
window.active.button.unpressed.image.color: #000000
window.active.button.pressed.bg: Sunken Solid Bevel1
window.active.button.pressed.bg.color: #C0C0C0
window.active.button.pressed.image.color: #000000
window.inactive.button.unpressed.bg: Raised Solid Bevel1
window.inactive.button.unpressed.bg.color: #C0C0C0
window.inactive.button.unpressed.image.color: #404040
window.inactive.button.pressed.bg: Sunken Solid Bevel1
window.inactive.button.pressed.bg.color: #C0C0C0
window.inactive.button.pressed.image.color: #404040
window.active.client.color: #C0C0C0
window.inactive.client.color: #C0C0C0
menu.border.width: 1
menu.border.color: #000000
menu.separator.color: #808080
menu.title.bg: Flat Solid
menu.title.bg.color: #000080
menu.title.text.color: #FFFFFF
menu.items.bg: Flat Solid
menu.items.bg.color: #C0C0C0
menu.items.text.color: #000000
menu.items.active.bg: Flat Solid
menu.items.active.bg.color: #000080
menu.items.active.text.color: #FFFFFF
OPENBOXTHEMEOF

cat >/usr/share/themes/Chicago95-Openbox/openbox-3/close.xbm <<'CLOSEXBMEOF'
#define close_width 6
#define close_height 6
static unsigned char close_bits[] = {
  0x21, 0x12, 0x0c, 0x0c, 0x12, 0x21
};
CLOSEXBMEOF

cat >/usr/share/themes/Chicago95-Openbox/openbox-3/max.xbm <<'MAXXBMEOF'
#define max_width 6
#define max_height 6
static unsigned char max_bits[] = {
  0x3f, 0x21, 0x21, 0x21, 0x21, 0x3f
};
MAXXBMEOF

cat >/usr/share/themes/Chicago95-Openbox/openbox-3/max_toggled.xbm <<'MAXTOGGLEDXBMEOF'
#define max_toggled_width 6
#define max_toggled_height 6
static unsigned char max_toggled_bits[] = {
  0x1e, 0x12, 0x1f, 0x09, 0x09, 0x0f
};
MAXTOGGLEDXBMEOF

cat >/usr/share/themes/Chicago95-Openbox/openbox-3/iconify.xbm <<'ICONIFYXBMEOF'
#define iconify_width 6
#define iconify_height 6
static unsigned char iconify_bits[] = {
  0x00, 0x00, 0x00, 0x00, 0x3f, 0x00
};
ICONIFYXBMEOF

cat >/home/cusdeb/.config/openbox/rc.xml <<'OPENBOXRCEOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <theme>
    <name>Chicago95-Openbox</name>
    <titleLayout>NLIMC</titleLayout>
    <keepBorder>yes</keepBorder>
    <font place="ActiveWindow">
      <name>Sans</name>
      <size>8</size>
      <weight>bold</weight>
      <slant>normal</slant>
    </font>
    <font place="InactiveWindow">
      <name>Sans</name>
      <size>8</size>
      <weight>bold</weight>
      <slant>normal</slant>
    </font>
    <font place="MenuHeader">
      <name>Sans</name>
      <size>8</size>
      <weight>bold</weight>
      <slant>normal</slant>
    </font>
    <font place="MenuItem">
      <name>Sans</name>
      <size>8</size>
      <weight>normal</weight>
      <slant>normal</slant>
    </font>
  </theme>
</openbox_config>
OPENBOXRCEOF

cat >/home/cusdeb/.gtkrc-2.0 <<'GTK2EOF'
gtk-theme-name="Chicago95"
gtk-icon-theme-name="SE98"
gtk-font-name="Sans 8"
gtk-cursor-theme-name="Chicago95_Standard_Cursors"
gtk-cursor-theme-size=16
gtk-button-images=1
gtk-menu-images=1
GTK2EOF

cat >/home/cusdeb/.config/gtk-3.0/settings.ini <<'GTK3EOF'
[Settings]
gtk-theme-name=Chicago95
gtk-icon-theme-name=SE98
gtk-font-name=Sans 8
gtk-cursor-theme-name=Chicago95_Standard_Cursors
gtk-cursor-theme-size=16
gtk-button-images=1
gtk-menu-images=1
GTK3EOF

# Fix ownership explicitly because the file is created as root during image
# assembly but must be writable/readable by the desktop user at runtime.
chown cusdeb:cusdeb /home/cusdeb/.config/libfm/libfm.conf
chown cusdeb:cusdeb /home/cusdeb/.config/pcmanfm/default/desktop-items-0.conf
chown cusdeb:cusdeb /home/cusdeb/.config/lxpanel/default/panels/panel
chown cusdeb:cusdeb /home/cusdeb/.config/openbox/rc.xml
chown cusdeb:cusdeb /home/cusdeb/.gtkrc-2.0
chown cusdeb:cusdeb /home/cusdeb/.config/gtk-3.0/settings.ini

# Create the desktop shortcut that opens Wine Explorer as the visible shell.
cat >/home/cusdeb/Desktop/explorer.desktop <<'DESKTOPEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=My Computer
Exec=wine explorer
Icon=computer
Terminal=false
Categories=Utility;
DESKTOPEOF

cat >/home/cusdeb/Desktop/terminal.desktop <<'TERMINALEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Terminal
Exec=xterm
Icon=utilities-terminal
Terminal=false
Categories=System;TerminalEmulator;
TERMINALEOF

cat >/home/cusdeb/Desktop/mspaint.desktop <<'MSPAINTEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Paint
Exec=wine /usr/local/bin/mspaint.exe
Icon=/usr/local/share/cusdeb/icons/paint_48.png
Terminal=false
Categories=Graphics;
MSPAINTEOF

cat >/home/cusdeb/Desktop/calculator.desktop <<'CALCULATOREOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Calculator
Exec=wine /usr/local/bin/calc.exe
Icon=/usr/share/icons/SE98/apps/48/accessories-calculator.png
Terminal=false
Categories=Utility;
CALCULATOREOF

cat >/home/cusdeb/Desktop/minesweeper.desktop <<'MINESWEEPEREOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Minesweeper
Exec=wine /usr/local/bin/winmine.exe
Icon=/usr/share/icons/SE98/apps/48/mines.png
Terminal=false
Categories=Game;
MINESWEEPEREOF

cat >/home/cusdeb/Desktop/spider.desktop <<'SPIDEREOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Spider Solitaire
Exec=wine /usr/local/bin/spider.exe
Icon=/usr/share/icons/SE98/apps/48/gnome-aisleriot.png
Terminal=false
Categories=Game;
SPIDEREOF

# Make the launcher visible and executable for the runtime desktop session.
chown cusdeb:cusdeb /home/cusdeb/Desktop/explorer.desktop
chmod 755 /home/cusdeb/Desktop/explorer.desktop
chown cusdeb:cusdeb /home/cusdeb/Desktop/terminal.desktop
chmod 755 /home/cusdeb/Desktop/terminal.desktop
chown cusdeb:cusdeb /home/cusdeb/Desktop/mspaint.desktop
chmod 755 /home/cusdeb/Desktop/mspaint.desktop
chown cusdeb:cusdeb /home/cusdeb/Desktop/calculator.desktop
chmod 755 /home/cusdeb/Desktop/calculator.desktop
chown cusdeb:cusdeb /home/cusdeb/Desktop/minesweeper.desktop
chmod 755 /home/cusdeb/Desktop/minesweeper.desktop
chown cusdeb:cusdeb /home/cusdeb/Desktop/spider.desktop
chmod 755 /home/cusdeb/Desktop/spider.desktop

install -m 755 /root/cusdeb-session /usr/local/bin/cusdeb-session
chown cusdeb:cusdeb /usr/local/bin/cusdeb-session

cat >/usr/share/xsessions/cusdeb.desktop <<'XSESSIONEOF'
[Desktop Entry]
Name=CusDeb
Comment=CusDeb Openbox desktop session
Exec=/usr/local/bin/cusdeb-session
Type=Application
DesktopNames=CusDeb;Openbox
XSESSIONEOF

cat >/etc/lightdm/lightdm.conf.d/50-cusdeb-autologin.conf <<'LIGHTDMEOF'
[Seat:*]
autologin-user=cusdeb
autologin-user-timeout=0
user-session=cusdeb
autologin-session=cusdeb
greeter-session=lightdm-gtk-greeter
LIGHTDMEOF

cat >/etc/lightdm/lightdm-gtk-greeter.conf <<'GREETEREOF'
[greeter]
theme-name=Chicago95
icon-theme-name=SE98
cursor-theme-name=Chicago95_Standard_Cursors
GREETEREOF

# Pre-initialize Wine in the image so first boot does not block on prefix setup.
rm -rf /home/cusdeb/.wine
CUSDEB_UID="$(id -u cusdeb)"

# Create the runtime directory Wine expects for the desktop user before we run
# wineboot during image creation.
install -d -m 700 -o cusdeb -g cusdeb "/run/user/$CUSDEB_UID"
su -s /bin/bash -l cusdeb -c "export WINEDEBUG=-all; export XDG_RUNTIME_DIR=/run/user/$CUSDEB_UID; wineboot --init; wineserver -w || true; wineserver -k || true"

# Use LightDM as the only graphical entrypoint for the desktop session.
systemctl enable lightdm.service

# Install GRUB into the image disk itself, then resolve the kernel and initrd
# through the canonical symlinks to avoid brittle file-name guessing.
grub-install --target=i386-pc --modules="biosdisk part_msdos ext2 normal search search_fs_uuid" "$LOOPDEV"

# Validate the canonical /vmlinuz and /initrd.img links before writing grub.cfg
# so the boot menu always points at real files under /boot.
if [ ! -e /vmlinuz ] || [ ! -e /initrd.img ]; then
  printf 'Missing /vmlinuz or /initrd.img after kernel installation\n' >&2
  exit 1
fi
KERNEL_TARGET="$(readlink -f /vmlinuz)"
INITRD_TARGET="$(readlink -f /initrd.img)"

case "$KERNEL_TARGET" in
  /boot/vmlinuz-*) ;;
  *)
    printf 'Unexpected kernel target: %s\n' "$KERNEL_TARGET" >&2
    exit 1
    ;;
esac

case "$INITRD_TARGET" in
  /boot/initrd.img-*) ;;
  *)
    printf 'Unexpected initrd target: %s\n' "$INITRD_TARGET" >&2
    exit 1
    ;;
esac

if [ ! -f "$KERNEL_TARGET" ] || [ ! -f "$INITRD_TARGET" ]; then
  printf 'Resolved kernel/initrd targets are missing regular files\n' >&2
  exit 1
fi

KERNEL_PATH="$(basename "$KERNEL_TARGET")"
INITRD_PATH="$(basename "$INITRD_TARGET")"
mkdir -p /boot/grub

# Write a minimal GRUB menu that boots the generated root filesystem by UUID and
# keeps the serial console enabled for easier debugging in QEMU.
cat >/boot/grub/grub.cfg <<GRUBEOF
set timeout=5
set default=0
insmod biosdisk
insmod part_msdos
insmod ext2

menuentry 'CusDeb OS' {
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    linux /boot/$KERNEL_PATH root=UUID=$ROOT_UUID ro console=ttyS0
    initrd /boot/$INITRD_PATH
}
GRUBEOF
