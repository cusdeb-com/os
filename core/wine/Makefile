#!/usr/bin/make -f

SHELL := /bin/sh
.SHELLFLAGS := -e -c

REPO_DIR   := $(CURDIR)
WORK_DIR   := $(REPO_DIR)/debian/.wine-build
SRC_DIR    := $(WORK_DIR)/wine-src
BUILD64    := $(WORK_DIR)/build64
BUILD32    := $(WORK_DIR)/build32
PREFIX     := /usr

export CCACHE_DIR := /root/.ccache
export CC         := ccache gcc
export CXX        := ccache g++

.PHONY: configure build install clean

configure: $(BUILD32)/Makefile

$(BUILD32)/Makefile: $(SRC_DIR)/configure
	mkdir -p "$(BUILD64)"
	cd "$(BUILD64)" && "$(SRC_DIR)/configure" \
	  --prefix="$(PREFIX)" \
	  --enable-win64 \
	  --disable-tests

	mkdir -p "$(BUILD32)"
	cd "$(BUILD32)" && "$(SRC_DIR)/configure" \
	  --prefix="$(PREFIX)" \
	  --with-wine64="$(BUILD64)" \
	  --disable-tests

$(SRC_DIR)/configure: $(REPO_DIR)/wine-src/configure
	mkdir -p "$(WORK_DIR)"
	rm -rf "$(SRC_DIR)"
	cp -a "$(REPO_DIR)/wine-src" "$(SRC_DIR)"

build: configure
	@echo "Building 64-bit Wine..."
	$(MAKE) -C "$(BUILD64)" -j$$(nproc)

	@echo "Building 32-bit Wine..."
	$(MAKE) -C "$(BUILD32)" -j$$(nproc)

install: build
	@echo "Installing Wine into $(DESTDIR)$(PREFIX)..."
	$(MAKE) -C "$(BUILD32)" install DESTDIR="$(DESTDIR)"
	$(MAKE) -C "$(BUILD64)" install DESTDIR="$(DESTDIR)"

clean:
	rm -rf "$(WORK_DIR)"
