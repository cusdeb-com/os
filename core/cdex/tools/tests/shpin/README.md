# SHPinDllOfCLSID tests

`../test_shpin_actctx_abi.py` checks the mirrored Wine COM-redirection record
against both the Wine 11.19 producer and reader. `shpin_actctx_parser.c`
exercises malformed and valid records. `runtime.c` checks real COM providers,
the registry fallback, fail-closed loading, nested activation contexts,
`SHAutoComplete`, `zonechk.c`, repeated pin/free calls, a child Wine process,
and resolver timing. `no_context.c` checks the registry path without a private
process activation context.

Run the full regression suite in a disposable Wine prefix. `all` builds the
test PEs, installs them beside the private assembly manifest, runs them, saves
Wine diagnostics, and removes the test files it installed:

```sh
WINEPREFIX=/path/to/disposable/prefix \
CDEX_TEST_DIR=/usr/share/cusdeb/cdex \
core/cdex/tools/tests/shpin/run-tests.sh all
```

The default summary is `/tmp/cdex-shpin-tests/shpin-suite.log`; set
`SH_PIN_TEST_LOG` to choose another path. Each executable gets a separate
`*-parser.log`, `*-runtime.log`, or `*-no-context.log` with full Wine traces.
The summary prints each stage's exit status and test output without the noisy
Wine trace lines. Each process has a 120-second timeout by default; set
`SH_PIN_TEST_TIMEOUT` to change it. A timeout is reported separately and the
full per-case log is retained. The suite enables `+loaddll,+actctx,+ole` unless
`WINEDEBUG` is already set. Separate `build`, `install`, and `run` modes are
available for diagnosis. `run` expects files installed by `install` and removes
them after execution. `install` refuses to overwrite existing test files.

```sh
core/cdex/tools/tests/shpin/run-tests.sh build
CDEX_TEST_DIR=/usr/share/cusdeb/cdex \
  core/cdex/tools/tests/shpin/run-tests.sh install
WINEPREFIX=/path/to/disposable/prefix CDEX_TEST_DIR=/usr/share/cusdeb/cdex \
  core/cdex/tools/tests/shpin/run-tests.sh run
```

The runtime executable has an embedded dependency on `CusDeb.ReactOSShell` and
must sit beside that assembly's manifest. The no-context executable has no
manifest resource or sidecar. The tests create only unique HKCU CLSID entries
and remove them on normal completion; run them in a disposable prefix because
forced process termination can prevent registry cleanup. `shpin-runtime.exe`
starts Wine x64 Notepad for a short module-load window; inspect its PID in the
saved Wine log. Its x86 child records paths for `shell32`, `shlwapi`, and
`browseui` and requires Wine system paths rather than the private CDEX directory.
