#!/usr/bin/env make -f

REPO_DIR := $(CURDIR)
REACTOS_SRC_DIR := $(REPO_DIR)/src

BUILD_DIR := $(REPO_DIR)/debian/.reactos-build/build
OUT_DIR := $(BUILD_DIR)
FONT_BUILD_DIR := $(REPO_DIR)/debian/.font-build
WALLPAPER_BUILD_DIR := $(REPO_DIR)/debian/.wallpaper-build
CDEX_DIR := $(DESTDIR)/usr/share/cusdeb/cdex
BIN_DIR := $(DESTDIR)/usr/bin
FONT_DIR := $(DESTDIR)/usr/share/fonts/truetype/cusdeb-ubuntu
DOC_DIR := $(DESTDIR)/usr/share/doc/cdex-base/ubuntu-font

FONT_FACES := R B RI

export ROS_ARCH := i386
export CFLAGS := $(CFLAGS) -Wno-error=format-security
export CXXFLAGS := $(CXXFLAGS) -Wno-error=format-security

REACTOS_TARGETS := \
	explorer \
	filebrowser \
	control \
	calc \
	mspaint \
	winmine \
	spider \
	shell32 \
	browseui \
	shlwapi \
	rshell \
	shdocvw \
	uxtheme \
	version \
	sendmail \
	w32time \
	access \
	appwiz \
	desk \
	hdwwiz \
	inetcpl \
	intl \
	joy \
	main \
	mmsys \
	ncpa \
	odbccp32i \
	openglcfg \
	powercfg \
	sysdm \
	telephon \
	timedate \
	usrmgr \
	wined3dcfg \
	mizu.msstyles

REACTOS_ARTIFACTS := \
	explorer.exe \
	filebrowser.exe \
	control.exe \
	calc.exe \
	mspaint.exe \
	winmine.exe \
	spider.exe \
	shell32.dll \
	browseui.dll \
	shlwapi.dll \
	rshell.dll \
	shdocvw.dll \
	uxtheme.dll \
	version.dll \
	sendmail.dll \
	w32time.dll \
	access.cpl \
	appwiz.cpl \
	desk.cpl \
	hdwwiz.cpl \
	inetcpl.cpl \
	intl.cpl \
	joy.cpl \
	main.cpl \
	mmsys.cpl \
	ncpa.cpl \
	odbccp32i.cpl \
	openglcfg.cpl \
	powercfg.cpl \
	sysdm.cpl \
	telephon.cpl \
	timedate.cpl \
	usrmgr.cpl \
	wined3dcfg.cpl \
	mizu.msstyles

.PHONY: all build install clean

all: build

build: $(OUT_DIR)/.build-stamp $(FONT_BUILD_DIR)/.fonts-stamp $(WALLPAPER_BUILD_DIR)/.wallpaper-stamp

$(OUT_DIR)/.build-stamp:
	@echo "=== Configuring ReactOS ==="
	rm -rf "$(OUT_DIR)"
	mkdir -p "$(OUT_DIR)"
	cmake -S "$(REACTOS_SRC_DIR)" -B "$(OUT_DIR)" -G Ninja \
		-DENABLE_CCACHE:BOOL=0 \
		-DENABLE_ROSTESTS=0 \
		-DCMAKE_TOOLCHAIN_FILE:FILEPATH="$(REACTOS_SRC_DIR)/toolchain-gcc.cmake" \
		-DARCH:STRING=i386 \
		-DCMAKE_CXX_STANDARD_LIBRARIES:STRING="-lgcc -lgcc_eh"
	@echo "=== Building ReactOS targets ==="
	ninja -C "$(OUT_DIR)" $(REACTOS_TARGETS)
	@touch "$@"

$(FONT_BUILD_DIR)/.fonts-stamp: tools/gasp_patch.py tools/rename_font.py \
		$(wildcard fonts/ubuntu-font-family-0.83/*.ttf)
	@echo "=== Patching Ubuntu fonts (GASP + UFL rename) ==="
	mkdir -p "$(FONT_BUILD_DIR)"
	set -e; for face in $(FONT_FACES); do \
		python3 tools/gasp_patch.py "fonts/ubuntu-font-family-0.83/Ubuntu-$$face.ttf" "$(FONT_BUILD_DIR)/Ubuntu-$$face-gasp.ttf"; \
		python3 tools/rename_font.py "$(FONT_BUILD_DIR)/Ubuntu-$$face-gasp.ttf" "$(FONT_BUILD_DIR)/Ubuntu-$$face.ttf"; \
	done
	@touch "$@"

$(WALLPAPER_BUILD_DIR)/.wallpaper-stamp: wallpapers/cusdeb-race.png
	@echo "=== Converting the CusDeb wallpaper to BMP ==="
	mkdir -p "$(WALLPAPER_BUILD_DIR)"
	convert wallpapers/cusdeb-race.png -alpha off -type TrueColor "BMP3:$(WALLPAPER_BUILD_DIR)/cusdeb-race.bmp"
	@touch "$@"

install: build
	@echo "=== Installing ReactOS artifacts ==="
	install -d "$(CDEX_DIR)"
	for artifact in $(REACTOS_ARTIFACTS); do \
		case "$$artifact" in \
			explorer.exe)    candidate="$(OUT_DIR)/base/shell/explorer/explorer.exe" ;; \
			filebrowser.exe) candidate="$(OUT_DIR)/base/shell/filebrowser/filebrowser.exe" ;; \
			control.exe)     candidate="$(OUT_DIR)/base/applications/control/control.exe" ;; \
			calc.exe)        candidate="$(OUT_DIR)/base/applications/calc/calc.exe" ;; \
			mspaint.exe)     candidate="$(OUT_DIR)/base/applications/mspaint/mspaint.exe" ;; \
			winmine.exe)     candidate="$(OUT_DIR)/base/applications/games/winmine/winmine.exe" ;; \
			spider.exe)      candidate="$(OUT_DIR)/base/applications/games/spider/spider.exe" ;; \
			*.cpl) \
				cpl_dir="$${artifact%.cpl}"; \
				if [ "$$cpl_dir" = "odbccp32i" ]; then cpl_dir="odbccp32"; fi; \
				candidate="$(OUT_DIR)/dll/cpl/$$cpl_dir/$$artifact" ;; \
				shell32.dll)  candidate="$(OUT_DIR)/dll/win32/shell32/shell32.dll" ;; \
				browseui.dll) candidate="$(OUT_DIR)/dll/win32/browseui/browseui.dll" ;; \
				shlwapi.dll)  candidate="$(OUT_DIR)/dll/win32/shlwapi/shlwapi.dll" ;; \
				rshell.dll)   candidate="$(OUT_DIR)/base/shell/rshell/rshell.dll" ;; \
				shdocvw.dll)  candidate="$(OUT_DIR)/dll/win32/shdocvw/shdocvw.dll" ;; \
				uxtheme.dll)  candidate="$(OUT_DIR)/dll/win32/uxtheme/uxtheme.dll" ;; \
				version.dll)  candidate="$(OUT_DIR)/dll/win32/version/version.dll" ;; \
				sendmail.dll) candidate="$(OUT_DIR)/dll/shellext/sendmail/sendmail.dll" ;; \
				w32time.dll)  candidate="$(OUT_DIR)/base/services/w32time/w32time.dll" ;; \
			mizu.msstyles) candidate="$(OUT_DIR)/media/themes/Mizu/mizu.msstyles/mizu.msstyles" ;; \
			esac; \
		if [ -z "$$candidate" ] || [ ! -f "$$candidate" ]; then \
			echo "Artifact not found: $$artifact (looked at $${candidate:-<unknown>})" >&2; \
			exit 1; \
		fi; \
		install -m 755 "$$candidate" "$(CDEX_DIR)/$$artifact"; \
	done

	@echo "=== Installing runtime scripts ==="
	install -d "$(BIN_DIR)"
	install -m 755 runtime/bin/cdex-win32-session runtime/bin/cdex-registry runtime/bin/cdex-taskbar-bridge \
		runtime/bin/cdex-shutdown-helper runtime/bin/cdex-wine-cleanup runtime/bin/poweroff runtime/bin/reboot \
		runtime/bin/cdex-display-properties runtime/bin/cdex-calamares-launcher \
		"$(BIN_DIR)/"
	install -m 755 runtime/bin/cdex-shortcut-helper "$(CDEX_DIR)/cdex-shortcut-helper"
	install -m 644 runtime/bin/create-cusdeb-shortcuts.js "$(CDEX_DIR)/create-cusdeb-shortcuts.js"
	@echo "=== Installing session/config files ==="
	install -D -m 644 runtime/xsessions/cusdeb-win32.desktop "$(DESTDIR)/usr/share/xsessions/cusdeb-win32.desktop"
	install -D -m 644 runtime/config/lightdm/50-cusdeb-greeter.conf "$(DESTDIR)/etc/lightdm/lightdm.conf.d/50-cusdeb-greeter.conf"
	install -D -m 644 runtime/config/lightdm/50-cusdeb-gtk-greeter.conf "$(DESTDIR)/usr/share/lightdm/lightdm-gtk-greeter.conf.d/50-cusdeb.conf"
	install -D -m 644 runtime/config/polkit/50-cusdeb-poweroff.rules "$(DESTDIR)/etc/polkit-1/rules.d/50-cusdeb-poweroff.rules"
	install -D -m 644 runtime/config/systemd/20-wired.network "$(DESTDIR)/etc/systemd/network/20-wired.network"
	install -D -m 644 runtime/config/openbox/rc.xml "$(DESTDIR)/etc/xdg/cusdeb/openbox/rc.xml"
	install -D -m 644 runtime/config/gtk/gtkrc-2.0 "$(DESTDIR)/etc/xdg/cusdeb/gtk-2.0/gtkrc"
	install -D -m 644 runtime/config/gtk/gtk-3.0/settings.ini "$(DESTDIR)/etc/xdg/cusdeb/gtk-3.0/settings.ini"
	@echo "=== Installing Openbox Win10 theme ==="
	install -d "$(DESTDIR)/usr/share/themes"
	cp -a runtime/themes/Win10 "$(DESTDIR)/usr/share/themes/"
	chmod -R a+rX "$(DESTDIR)/usr/share/themes/Win10"

	@echo "=== Installing GASP-patched Ubuntu fonts ==="
	install -d "$(FONT_DIR)"
	set -e; for face in $(FONT_FACES); do \
		install -m 644 "$(FONT_BUILD_DIR)/Ubuntu-$$face.ttf" "$(FONT_DIR)/Ubuntu-$$face.ttf"; \
	done
	install -D -m 644 runtime/config/fontconfig/52-cusdeb-ubuntu.conf "$(DESTDIR)/etc/fonts/conf.d/52-cusdeb-ubuntu.conf"
	install -d "$(DOC_DIR)"
	install -m 644 fonts/ubuntu-font-family-0.83/LICENCE.txt \
		fonts/ubuntu-font-family-0.83/copyright.txt "$(DOC_DIR)/"

	@echo "=== Installing the default wallpaper ==="
	install -D -m 644 "$(WALLPAPER_BUILD_DIR)/cusdeb-race.bmp" "$(CDEX_DIR)/Web/Wallpaper/CusDeb Race.bmp"

	@echo "=== Installing ReactOS Marlett font ==="
	install -D -m 644 "$(REACTOS_SRC_DIR)/media/fonts/Marlett.ttf" "$(CDEX_DIR)/fonts/Marlett.ttf"

clean:
	rm -rf "$(REPO_DIR)/debian/.reactos-build" "$(REPO_DIR)/debian/.font-build" \
		"$(REPO_DIR)/debian/.wallpaper-build"
