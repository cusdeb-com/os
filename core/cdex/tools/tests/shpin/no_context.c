#include <windows.h>
#include <stdio.h>
#include <string.h>

static const GUID clsid_fallback = {0x7b8a2d94, 0x0ac9, 0x11d1, {0x89, 0x6c, 0x00, 0xc0, 0x4f, 0xb6, 0xbf, 0xc4}};
static const GUID clsid_private = {0x03c036f1, 0xa186, 0x11d0, {0x82, 0x4a, 0, 0xaa, 0, 0x5b, 0x43, 0x83}};
typedef HMODULE (WINAPI *shpin_dll_of_clsid_fn)(REFIID);

static shpin_dll_of_clsid_fn get_shpin(HMODULE shlwapi)
{
    union { FARPROC generic; shpin_dll_of_clsid_fn typed; } symbol;
    symbol.generic = GetProcAddress(shlwapi, MAKEINTRESOURCEA(236));
    return symbol.typed;
}

int main(void)
{
    WCHAR path[MAX_PATH], *slash;
    ACTCTX_SECTION_KEYED_DATA data;
    DWORD error;
    HMODULE shlwapi, module;
    shpin_dll_of_clsid_fn pin;

    if (!GetModuleFileNameW(NULL, path, ARRAYSIZE(path))) return 1;
    slash = wcsrchr(path, L'\\');
    if (!slash) return 1;
    lstrcpyW(slash + 1, L"shlwapi.dll");
    shlwapi = LoadLibraryW(path);
    if (!shlwapi) { printf("LoadLibrary ReactOS shlwapi failed: %lu\n", GetLastError()); return 1; }

    memset(&data, 0, sizeof(data));
    data.cbSize = sizeof(data);
    if (FindActCtxSectionGuid(FIND_ACTCTX_SECTION_KEY_RETURN_HACTCTX, NULL,
                              ACTIVATION_CONTEXT_SECTION_COM_SERVER_REDIRECTION,
                              &clsid_private, &data))
    {
        ReleaseActCtx(data.hActCtx);
        printf("FAIL: process unexpectedly has a private CDEX activation context\n");
        FreeLibrary(shlwapi);
        return 1;
    }
    printf("No CDEX COM context: confirmed (error=%lu)\n", GetLastError());

    pin = get_shpin(shlwapi);
    if (!pin) { FreeLibrary(shlwapi); return 1; }
    module = pin(&clsid_fallback);
    if (!module)
    {
        printf("FAIL: registry fallback without activation context failed: %lu\n", GetLastError());
        error = ERROR_FILE_NOT_FOUND;
    }
    else
    {
        WCHAR actual[MAX_PATH];
        DWORD length = GetModuleFileNameW(module, actual, ARRAYSIZE(actual));
        printf("No-context fallback provider: %ls\n", length && length < ARRAYSIZE(actual) ? actual : L"<path-error>");
        error = length && length < ARRAYSIZE(actual) && wcsstr(actual, L"\\windows\\system32\\urlmon.dll")
              ? ERROR_SUCCESS : ERROR_INVALID_DATA;
        FreeLibrary(module);
    }

    FreeLibrary(shlwapi);
    printf("No-context registry fallback: %s\n", error == ERROR_SUCCESS ? "PASS" : "FAIL");
    return error == ERROR_SUCCESS ? 0 : 1;
}
