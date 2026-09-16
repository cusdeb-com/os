#!/usr/bin/make -f

SHELL := /bin/sh
.SHELLFLAGS := -e -c

# Repository and incremental build paths.
REPO_DIR := $(CURDIR)
BUILD_CACHE_DIR := $(REPO_DIR)/.wine-build
BUILD64 := $(BUILD_CACHE_DIR)/build64
BUILD32 := $(BUILD_CACHE_DIR)/build32
CCACHE_DIR := $(BUILD_CACHE_DIR)/ccache
PREFIX := /usr

# Debian package output.
# Relative to the package root; override with PACKAGE_DIR=. in CI.
PACKAGE_DIR ?= .wine-build/packages
PACKAGE_HOST_DIR := $(REPO_DIR)/$(PACKAGE_DIR)

# Container build settings.
DOCKER ?= docker
BUILD_IMAGE ?= wine-buildenv:trixie
# Set REAPPLY_PATCHES=1 to reapply the complete Quilt series before building.
REAPPLY_PATCHES ?= 0

# Wine's generated GNU Makefiles use these tools for native build programs.
export CC := ccache gcc
export CXX := ccache g++
export CCACHE_DIR
export CCACHE_BASEDIR := $(REPO_DIR)
export CCACHE_COMPILERCHECK := content

CONFIGURE := $(REPO_DIR)/src/configure

.PHONY: all build clean image shell ensure-image
.PHONY: build-in-container install-in-container wine-build64 wine-build32

# Public developer interface.
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

# Internal container build interface. These targets are called by
# debian/rules and are not separate developer build steps.
build-in-container:
	$(MAKE) wine-build64
	$(MAKE) wine-build32

wine-build64: $(BUILD64)/Makefile
	@echo "=== Building 64-bit Wine ==="
	$(MAKE) -C "$(BUILD64)" -j$$(nproc)

wine-build32:
	@if [ ! -f "$(BUILD32)/Makefile" ] || [ "$(CONFIGURE)" -nt "$(BUILD32)/Makefile" ]; then \
		echo "=== Configuring 32-bit Wine ==="; \
		mkdir -p "$(BUILD32)"; \
		cd "$(BUILD32)" && "$(CONFIGURE)" \
		  --prefix="$(PREFIX)" \
		  --with-wine64="$(BUILD64)" \
		  --disable-tests; \
	fi
	@echo "=== Building 32-bit Wine ==="
	$(MAKE) -C "$(BUILD32)" -j$$(nproc)

$(BUILD64)/Makefile: $(CONFIGURE)
	@echo "=== Configuring 64-bit Wine ==="
	mkdir -p "$(BUILD64)"
	cd "$(BUILD64)" && "$(CONFIGURE)" \
	  --prefix="$(PREFIX)" \
	  --enable-win64 \
	  --disable-tests

# Internal container install interface. Called by debian/rules after the
# build phase has completed.
install-in-container:
	@echo "=== Installing Wine runtime files ==="
	$(MAKE) -C "$(BUILD32)" install-lib DESTDIR="$(DESTDIR)" INSTALL_PROGRAM_FLAGS="$(INSTALL_PROGRAM_FLAGS)"
	$(MAKE) -C "$(BUILD64)" install-lib DESTDIR="$(DESTDIR)" INSTALL_PROGRAM_FLAGS="$(INSTALL_PROGRAM_FLAGS)"
