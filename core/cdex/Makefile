#!/usr/bin/env make -f

# Repository paths
REPO_DIR := $(CURDIR)
REACTOS_SRC_DIR := $(REPO_DIR)/src

# Incremental build cache
BUILD_CACHE_DIR := $(REPO_DIR)/.cdex-build
BUILD_DIR := $(BUILD_CACHE_DIR)/reactos
OUT_DIR := $(BUILD_DIR)
FONT_BUILD_DIR := $(BUILD_CACHE_DIR)/fonts
WALLPAPER_BUILD_DIR := $(BUILD_CACHE_DIR)/wallpaper
ICON_BUILD_DIR := $(BUILD_CACHE_DIR)/icons

# Generated build inputs
REACTOS_CLASSES_REG := $(BUILD_CACHE_DIR)/reactos-classes.reg

# Build tools and generators
REACTOS_CLASSES_GENERATOR := $(REPO_DIR)/tools/generate_registry_classes.py
HIVEXREGEDIT := /usr/bin/hivexregedit

ASSET_PIPELINE_SCRIPT := $(REPO_DIR)/tools/asset_pipeline.py

# Debian package output
# Relative to the package root; override with PACKAGE_DIR=. in CI.
PACKAGE_DIR ?= .cdex-build/packages
PACKAGE_HOST_DIR := $(REPO_DIR)/$(PACKAGE_DIR)

# Package install destinations
CDEX_DIR := $(DESTDIR)/usr/share/cusdeb/cdex
BIN_DIR := $(DESTDIR)/usr/bin
FONT_DIR := $(DESTDIR)/usr/share/fonts/truetype/cusdeb-ubuntu
DOC_DIR := $(DESTDIR)/usr/share/doc/cdex-base/ubuntu-font

# Container build settings
DOCKER ?= docker
BUILD_IMAGE ?= cdex-buildenv:bookworm
# Set REAPPLY_PATCHES=1 to reapply the complete Quilt series before building.
REAPPLY_PATCHES ?= 0

# Build asset settings
FONT_FACES := R B RI

# Cross-compilation settings
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
	clipbrd \
	eventvwr \
	mshta \
	mstsc \
	regedit \
	wordpad \
	hh \
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
	cryptext \
	ieframe \
	msxml3 \
	shimgvw \
	themeui \
	url \
	mizu.msstyles

REACTOS_ARTIFACTS := \
	explorer.exe \
	filebrowser.exe \
	control.exe \
	calc.exe \
	mspaint.exe \
	winmine.exe \
	spider.exe \
	clipbrd.exe \
	eventvwr.exe \
	mshta.exe \
	mstsc.exe \
	regedit.exe \
	wordpad.exe \
	hh.exe \
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
	cryptext.dll \
	ieframe.dll \
	msxml3.dll \
	shimgvw.dll \
	themeui.dll \
	url.dll \
	mizu.msstyles

.PHONY: all build clean image shell ensure-image prepare-icons
.PHONY: build-in-container install-in-container reactos-build

# Public developer interface
all: build

build: ensure-image
	mkdir -p "$(PACKAGE_HOST_DIR)"
	$(DOCKER) run --rm \
		--mount "type=bind,src=$(REPO_DIR),dst=/workspace" \
		--user "$$(id -u):$$(id -g)" \
		--workdir /workspace \
		--env "REAPPLY_PATCHES=$(REAPPLY_PATCHES)" \
		--env "PACKAGE_DIR=$(PACKAGE_DIR)" \
		"$(BUILD_IMAGE)" \
		sh /workspace/tools/build-in-container.sh

clean:
	rm -rf "$(BUILD_CACHE_DIR)"

image:
	$(DOCKER) build --network=host --tag "$(BUILD_IMAGE)" \
		--file "$(REPO_DIR)/Dockerfile" "$(REPO_DIR)"

ensure-image:
	@if ! $(DOCKER) image inspect "$(BUILD_IMAGE)" >/dev/null 2>&1; then \
		echo "Build the build environment first: make image" >&2; \
		exit 1; \
	fi

shell: ensure-image
	$(DOCKER) run --rm --interactive --tty \
		--mount "type=bind,src=$(REPO_DIR),dst=/workspace" \
		--user "$$(id -u):$$(id -g)" \
		--workdir /workspace \
		"$(BUILD_IMAGE)" /bin/bash

# Internal container build interface.
build-in-container: reactos-build $(REACTOS_CLASSES_REG) $(FONT_BUILD_DIR)/.fonts-stamp $(WALLPAPER_BUILD_DIR)/.wallpaper-stamp

prepare-icons: $(ASSET_PIPELINE_SCRIPT)
	@echo "=== Preparing project-owned shell icons ==="
	@python3 "$(ASSET_PIPELINE_SCRIPT)" prepare \
		--root "$(REPO_DIR)" \
		--build-dir "$(ICON_BUILD_DIR)"

reactos-build: prepare-icons
	@echo "=== Configuring ReactOS ==="
	mkdir -p "$(OUT_DIR)"
	cmake -S "$(REACTOS_SRC_DIR)" -B "$(OUT_DIR)" -G Ninja \
		-DENABLE_CCACHE:BOOL=0 \
		-DENABLE_ROSTESTS=0 \
		-DCMAKE_TOOLCHAIN_FILE:FILEPATH="$(REACTOS_SRC_DIR)/toolchain-gcc.cmake" \
		-DARCH:STRING=i386 \
		-DCDEX_ICON_BUILD_DIR:PATH="$(ICON_BUILD_DIR)" \
		-DCMAKE_CXX_STANDARD_LIBRARIES:STRING="-lgcc -lgcc_eh"
	@echo "=== Building ReactOS targets ==="
	ninja -C "$(OUT_DIR)" host-tools $(REACTOS_TARGETS)

$(REACTOS_CLASSES_REG): $(REACTOS_CLASSES_GENERATOR) \
		$(REACTOS_SRC_DIR)/boot/bootdata/hivecls.inf | reactos-build
	@echo "=== Generating ReactOS Classes registry ==="
	python3 "$(REACTOS_CLASSES_GENERATOR)" \
		--hivecls "$(REACTOS_SRC_DIR)/boot/bootdata/hivecls.inf" \
		--mkhive "$(OUT_DIR)/host-tools/bin/mkhive" \
		--utf16le "$(OUT_DIR)/host-tools/bin/utf16le" \
		--hivexregedit "$(HIVEXREGEDIT)" \
		--output "$@"

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

# Internal container install interface. Called by debian/rules after the build phase.
install-in-container:
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
			clipbrd.exe)     candidate="$(OUT_DIR)/base/applications/clipbrd/clipbrd.exe" ;; \
			eventvwr.exe)    candidate="$(OUT_DIR)/base/applications/mscutils/eventvwr/eventvwr.exe" ;; \
			mshta.exe)       candidate="$(OUT_DIR)/base/applications/mshta/mshta.exe" ;; \
			mstsc.exe)       candidate="$(OUT_DIR)/base/applications/mstsc/mstsc.exe" ;; \
			regedit.exe)     candidate="$(OUT_DIR)/base/applications/regedit/regedit.exe" ;; \
			wordpad.exe)     candidate="$(OUT_DIR)/base/applications/wordpad/wordpad.exe" ;; \
			hh.exe)          candidate="$(OUT_DIR)/base/applications/hh/hh.exe" ;; \
			shell32.dll)     candidate="$(OUT_DIR)/dll/win32/shell32/shell32.dll" ;; \
			*.cpl) \
				cpl_dir="$${artifact%.cpl}"; \
				if [ "$$cpl_dir" = "odbccp32i" ]; then cpl_dir="odbccp32"; fi; \
				candidate="$(OUT_DIR)/dll/cpl/$$cpl_dir/$$artifact" ;; \
			browseui.dll)  candidate="$(OUT_DIR)/dll/win32/browseui/browseui.dll" ;; \
			shlwapi.dll)   candidate="$(OUT_DIR)/dll/win32/shlwapi/shlwapi.dll" ;; \
			rshell.dll)    candidate="$(OUT_DIR)/base/shell/rshell/rshell.dll" ;; \
			shdocvw.dll)   candidate="$(OUT_DIR)/dll/win32/shdocvw/shdocvw.dll" ;; \
			uxtheme.dll)   candidate="$(OUT_DIR)/dll/win32/uxtheme/uxtheme.dll" ;; \
			version.dll)   candidate="$(OUT_DIR)/dll/win32/version/version.dll" ;; \
			sendmail.dll)  candidate="$(OUT_DIR)/dll/shellext/sendmail/sendmail.dll" ;; \
			w32time.dll)   candidate="$(OUT_DIR)/base/services/w32time/w32time.dll" ;; \
			cryptext.dll)  candidate="$(OUT_DIR)/dll/shellext/cryptext/cryptext.dll" ;; \
			ieframe.dll)   candidate="$(OUT_DIR)/dll/win32/ieframe/ieframe.dll" ;; \
			msxml3.dll)    candidate="$(OUT_DIR)/dll/win32/msxml3/msxml3.dll" ;; \
			shimgvw.dll)   candidate="$(OUT_DIR)/dll/win32/shimgvw/shimgvw.dll" ;; \
			themeui.dll)   candidate="$(OUT_DIR)/dll/win32/themeui/themeui.dll" ;; \
			url.dll)       candidate="$(OUT_DIR)/dll/win32/url/url.dll" ;; \
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
	install -m 644 "$(REACTOS_CLASSES_REG)" "$(CDEX_DIR)/reactos-classes.reg"
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
