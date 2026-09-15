#!/bin/sh

set -eu

PACKAGE_DIR=${PACKAGE_DIR:-.cdex-build/packages}
export PACKAGE_DIR

run_quilt() {
	quilt --quiltrc .quiltrc "$@" || {
		status=$?
		[ "$status" -eq 2 ]
	}
}

if [ "${REAPPLY_PATCHES:-0}" = 1 ]; then
	run_quilt pop -a
fi

run_quilt push -a

fakeroot debian/rules binary

dh_clean
