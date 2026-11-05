# SHPinDllOfCLSID tests

`../test_shpin_actctx_abi.py` checks the mirrored Wine COM-redirection record
against both the Wine 11.19 producer and reader. `shpin_actctx_parser.c`
exercises malformed and valid records. `runtime.c` checks real COM providers,
the registry fallback, fail-closed loading, nested activation contexts,
`SHAutoComplete`, `zonechk.c`, repeated pin/free calls, a child Wine process,
and resolver timing. `no_context.c` checks the registry path without a private
process activation context.

Build the PE tests in `cdex-buildenv:bookworm-i386`:

```sh
core/cdex/tools/tests/shpin/run-tests.sh build
```

Install them into an isolated test prefix's CDEX payload directory, then run
them with that prefix's Wine:

```sh
CDEX_TEST_DIR=/usr/share/cusdeb/cdex \
  core/cdex/tools/tests/shpin/run-tests.sh install
WINEPREFIX=/path/to/isolated/prefix wine /usr/share/cusdeb/cdex/shpin-actctx-parser.exe
WINEPREFIX=/path/to/isolated/prefix wine /usr/share/cusdeb/cdex/shpin-runtime.exe
WINEPREFIX=/path/to/isolated/prefix wine /usr/share/cusdeb/cdex/shpin-no-context.exe
```

The runtime executable has an embedded dependency on `CusDeb.ReactOSShell` and
must sit beside that assembly's manifest. The no-context executable has no
manifest resource or sidecar. The tests create only unique HKCU CLSID entries
and remove them on normal completion; run them in a disposable prefix because
a forced process termination can prevent cleanup. `shpin-runtime.exe` starts
the Wine x64 Notepad for a short module-load window; inspect the matching PID
in `WINEDEBUG=+loaddll,+actctx,+ole` output. Its x86 child writes its loaded
module paths to `child.log` and fails if any are from the private CDEX folder.
