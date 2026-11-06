#!/bin/sh
set -eu

mode=${1:-build}
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$test_dir/../../../../.." && pwd)
out=${SH_PIN_TEST_OUT:-/tmp/cdex-shpin-tests}
cc=${CC:-i686-w64-mingw32-gcc}
windres=${WINDRES:-i686-w64-mingw32-windres}
test_files='shpin-actctx-parser.exe shpin-child.exe shpin-runtime.exe shpin-no-context.exe runtime.manifest nested.manifest'

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
		-lole32 -loleaut32 -luuid -lshell32 -ladvapi32 -lurlmon -o "$out/shpin-runtime.exe"
	"$cc" -Wall -Wextra "$test_dir/no_context.c" -ladvapi32 -o "$out/shpin-no-context.exe"
	cp "$test_dir/runtime.manifest" "$out/runtime.manifest"
	cp "$test_dir/nested.manifest" "$out/nested.manifest"
}

check_test_targets_absent()
{
	: "${CDEX_TEST_DIR:?set CDEX_TEST_DIR to the installed CDEX payload directory}"
	for file in $test_files; do
		if [ -e "$CDEX_TEST_DIR/$file" ] || [ -L "$CDEX_TEST_DIR/$file" ]; then
			printf 'Refusing to overwrite existing test file: %s\n' "$CDEX_TEST_DIR/$file" >&2
			return 1
		fi
	done
}

cleanup_tests()
{
	for file in $test_files; do
		rm -f "$CDEX_TEST_DIR/$file"
	done
}

install_tests()
{
	check_test_targets_absent
	install -m 755 "$out/shpin-actctx-parser.exe" "$CDEX_TEST_DIR/shpin-actctx-parser.exe"
	install -m 755 "$out/shpin-child.exe" "$CDEX_TEST_DIR/shpin-child.exe"
	install -m 755 "$out/shpin-runtime.exe" "$CDEX_TEST_DIR/shpin-runtime.exe"
	install -m 755 "$out/shpin-no-context.exe" "$CDEX_TEST_DIR/shpin-no-context.exe"
	install -m 644 "$out/runtime.manifest" "$CDEX_TEST_DIR/runtime.manifest"
	install -m 644 "$out/nested.manifest" "$CDEX_TEST_DIR/nested.manifest"
}

run_tests()
{
	: "${WINEPREFIX:?set WINEPREFIX to a disposable CDEX test prefix}"
	: "${CDEX_TEST_DIR:?set CDEX_TEST_DIR to the installed CDEX payload directory}"
	wine=${WINE:-wine}
	drive=${CDEX_TEST_DRIVE:-C:\\ReactOS}
	timeout_seconds=${SH_PIN_TEST_TIMEOUT:-120}
	log=${SH_PIN_TEST_LOG:-$out/shpin-suite.log}
	if [ "${1:-}" = install ]; then
		check_test_targets_absent
		trap cleanup_tests EXIT
		trap 'exit 130' HUP INT TERM
		install_tests
	fi
	for file in $test_files; do
		if [ ! -f "$CDEX_TEST_DIR/$file" ]; then
			printf 'Test file is missing: %s\n' "$CDEX_TEST_DIR/$file" >&2
			return 1
		fi
	done
	trap cleanup_tests EXIT
	trap 'exit 130' HUP INT TERM
	if ! command -v timeout >/dev/null; then
		printf 'Required command not found: timeout (coreutils)\n' >&2
		return 127
	fi
	case "$timeout_seconds" in
		''|*[!0-9]*) printf 'SH_PIN_TEST_TIMEOUT must be a positive number of seconds\n' >&2; return 2 ;;
	esac
	if [ "$timeout_seconds" -eq 0 ]; then
		printf 'SH_PIN_TEST_TIMEOUT must be greater than zero\n' >&2
		return 2
	fi
	mkdir -p "$(dirname -- "$log")"
	: >"$log"
	run_case() {
		name=$1
		executable=$2
		case_log=${log%.log}-$name.log
		case_status=0
		timeout -k 5 "$timeout_seconds" env WINEDEBUG=${WINEDEBUG:-+loaddll,+actctx,+ole} \
			"$wine" "$drive\\$executable" >"$case_log" 2>&1 || case_status=$?
		if [ "$case_status" -eq 0 ]; then
			printf '%s: PASS (exit=0)\n' "$name" | tee -a "$log"
		elif [ "$case_status" -eq 124 ] || [ "$case_status" -eq 137 ]; then
			printf '%s: TIMEOUT (>%ss)\n' "$name" "$timeout_seconds" | tee -a "$log"
		else
			printf '%s: FAIL (exit=%s)\n' "$name" "$case_status" | tee -a "$log"
		fi
		printf '  full log: %s\n' "$case_log" | tee -a "$log"
		if grep -qvE '^[[:xdigit:]]{4,}:trace:' "$case_log"; then
			grep -vE '^[[:xdigit:]]{4,}:trace:' "$case_log" | tee -a "$log" || true
		fi
		printf '\n' | tee -a "$log"
		return "$case_status"
	}
	status=0
	run_case parser shpin-actctx-parser.exe || status=1
	run_case runtime shpin-runtime.exe || status=1
	run_case no-context shpin-no-context.exe || status=1
	if [ "$status" -eq 0 ]; then
		printf 'SHPin suite: PASS\n' | tee -a "$log"
	else
		printf 'SHPin suite: FAIL; see the failed case log above\n' | tee -a "$log"
	fi
	printf 'Suite summary: %s\n' "$log"
	return "$status"
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
		run_tests install
		;;
	run)
		run_tests
		;;
	*)
		printf 'Usage: %s [build|install|run|all]\n' "$0" >&2
		exit 2
		;;
esac
