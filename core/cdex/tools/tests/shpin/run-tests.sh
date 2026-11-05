#!/bin/sh
set -eu

mode=${1:-build}
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$test_dir/../../../../.." && pwd)
out=${SH_PIN_TEST_OUT:-/tmp/cdex-shpin-tests}
cc=${CC:-i686-w64-mingw32-gcc}
windres=${WINDRES:-i686-w64-mingw32-windres}

build_tests()
{
	command -v "$cc" >/dev/null
	command -v "$windres" >/dev/null
	python3 "$repo/core/cdex/tools/tests/test_shpin_actctx_abi.py"
	mkdir -p "$out"
	"$cc" -Wall -Wextra "$test_dir/../shpin_actctx_parser.c" -o "$out/shpin-actctx-parser.exe"
	"$cc" -Wall -Wextra "$test_dir/child.c" -o "$out/shpin-child.exe"
	(cd "$test_dir" && "$windres" runtime.rc "$out/runtime-resource.o")
	"$cc" -Wall -Wextra "$test_dir/runtime.c" "$out/runtime-resource.o" \
		-lole32 -lshell32 -ladvapi32 -lurlmon -o "$out/shpin-runtime.exe"
	"$cc" -Wall -Wextra "$test_dir/no_context.c" -ladvapi32 -o "$out/shpin-no-context.exe"
	cp "$test_dir/runtime.manifest" "$out/runtime.manifest"
}

install_tests()
{
	: "${CDEX_TEST_DIR:?set CDEX_TEST_DIR to the installed CDEX payload directory}"
	install -m 755 "$out/shpin-actctx-parser.exe" "$CDEX_TEST_DIR/shpin-actctx-parser.exe"
	install -m 755 "$out/shpin-child.exe" "$CDEX_TEST_DIR/child.exe"
	install -m 755 "$out/shpin-runtime.exe" "$CDEX_TEST_DIR/shpin-runtime.exe"
	install -m 755 "$out/shpin-no-context.exe" "$CDEX_TEST_DIR/shpin-no-context.exe"
	install -m 644 "$out/runtime.manifest" "$CDEX_TEST_DIR/runtime.manifest"
}

run_tests()
{
	: "${WINEPREFIX:?set WINEPREFIX to a disposable CDEX test prefix}"
	: "${CDEX_TEST_DIR:?set CDEX_TEST_DIR to the installed CDEX payload directory}"
	wine=${WINE:-wine}
	drive=${CDEX_TEST_DRIVE:-C:\\ReactOS}
	cleanup() {
		rm -f "$CDEX_TEST_DIR/shpin-actctx-parser.exe" "$CDEX_TEST_DIR/shpin-child.exe" \
			"$CDEX_TEST_DIR/shpin-runtime.exe" "$CDEX_TEST_DIR/shpin-no-context.exe" \
			"$CDEX_TEST_DIR/runtime.manifest"
	}
	trap cleanup EXIT HUP INT TERM
	install_tests
	"$wine" "$drive\\shpin-actctx-parser.exe"
	"$wine" "$drive\\shpin-runtime.exe"
	"$wine" "$drive\\shpin-no-context.exe"
}

case "$mode" in
	build)
		build_tests
		printf 'Built SHPin tests in %s\n' "$out"
		;;
	install)
		install_tests
		;;
	all)
		build_tests
		install_tests
		;;
	run)
		run_tests
		;;
	*)
		printf 'Usage: %s [build|install|run|all]\n' "$0" >&2
		exit 2
		;;
esac
