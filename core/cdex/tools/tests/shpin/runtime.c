#define COBJMACROS
#include <windows.h>
#include <objbase.h>
#include <shellapi.h>
#include <tlhelp32.h>
#include <urlmon.h>
#include <stdio.h>
#include <string.h>

static const GUID clsid_aclistisf = {0x03c036f1, 0xa186, 0x11d0, {0x82, 0x4a, 0x00, 0xaa, 0x00, 0x5b, 0x43, 0x83}};
static const GUID clsid_autocomplete = {0x00bb2763, 0x6a77, 0x11d0, {0xa5, 0x35, 0x00, 0xc0, 0x4f, 0xd7, 0xd0, 0x62}};
static const GUID clsid_shelllink = {0x00021401, 0x0000, 0x0000, {0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46}};
static const GUID clsid_internet_security_manager = {0x7b8a2d94, 0x0ac9, 0x11d1, {0x89, 0x6c, 0x00, 0xc0, 0x4f, 0xb6, 0xbf, 0xc4}};
static const GUID clsid_missing_server = {0xdeadbeef, 0x1234, 0x5678, {0x90, 0xab, 0xcd, 0xef, 0x01, 0x23, 0x45, 0x67}};
static const GUID clsid_unknown = {0xdeadbeef, 0x1234, 0x5678, {0x90, 0xab, 0xcd, 0xef, 0x01, 0x23, 0x45, 0x68}};
static const GUID clsid_invalid_registry = {0xdeadbeef, 0x1234, 0x5678, {0x90, 0xab, 0xcd, 0xef, 0x01, 0x23, 0x45, 0x69}};
static const GUID clsid_missing_system_server = {0xdeadbeef, 0x1234, 0x5678, {0x90, 0xab, 0xcd, 0xef, 0x01, 0x23, 0x45, 0x6b}};
static const IID iid_iunknown = {0x00000000, 0x0000, 0x0000, {0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46}};
static WCHAR private_dir[MAX_PATH];
typedef HMODULE (WINAPI *shpin_dll_of_clsid_fn)(REFIID);
typedef HRESULT (WINAPI *sh_auto_complete_fn)(HWND, DWORD);

static void print_wide(LPCWSTR value)
{
    char text[MAX_PATH * 4];

    if (!value || !WideCharToMultiByte(CP_UTF8, 0, value, -1, text, sizeof(text), NULL, NULL))
    {
        printf("<unprintable>");
        return;
    }
    printf("%s", text);
}

static BOOL has_basename(LPCWSTR path, LPCWSTR expected)
{
    LPCWSTR base = wcsrchr(path, L'\\');
    base = base ? base + 1 : path;
    return !lstrcmpiW(base, expected);
}

static BOOL is_private_path(LPCWSTR path)
{
    SIZE_T length = lstrlenW(private_dir);
    return length && (SIZE_T)lstrlenW(path) > length &&
           CompareStringOrdinal(path, length, private_dir, length, TRUE) == CSTR_EQUAL &&
           path[length] == L'\\';
}

static BOOL set_private_dir(HMODULE shlwapi)
{
    DWORD length = GetModuleFileNameW(shlwapi, private_dir, ARRAYSIZE(private_dir));
    WCHAR *slash;

    if (!length || length >= ARRAYSIZE(private_dir)) return FALSE;
    slash = wcsrchr(private_dir, L'\\');
    if (!slash) return FALSE;
    *slash = 0;
    return TRUE;
}

static shpin_dll_of_clsid_fn get_shpin(HMODULE shlwapi)
{
    union { FARPROC generic; shpin_dll_of_clsid_fn typed; } symbol;
    symbol.generic = GetProcAddress(shlwapi, MAKEINTRESOURCEA(236));
    return symbol.typed;
}

static BOOL report_com(const char *label, REFCLSID clsid, LPCWSTR expected)
{
    IUnknown *object = NULL;
    HRESULT hr = CoCreateInstance(clsid, NULL, CLSCTX_INPROC_SERVER, &iid_iunknown, (void **)&object);
    BOOL result = SUCCEEDED(hr);

    printf("CoCreateInstance %s -> 0x%08lx\n", label, (unsigned long)hr);
    if (object)
    {
        HMODULE provider;
        WCHAR path[MAX_PATH];
        if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                               GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               (LPCWSTR)(ULONG_PTR)object->lpVtbl, &provider) &&
            GetModuleFileNameW(provider, path, ARRAYSIZE(path)))
        {
            BOOL private_provider = is_private_path(path);
            printf("COM provider %s -> ", label); print_wide(path);
            printf(" (%s)\n", private_provider ? "CDEX" : "Wine/system");
            if (expected && (!private_provider || !has_basename(path, expected)))
                result = FALSE;
        }
        else result = FALSE;
        IUnknown_Release(object);
    }
    if (!result) printf("FAIL: COM provider mismatch for %s\n", label);
    return result;
}

static HMODULE report_module(const char *label, shpin_dll_of_clsid_fn pin, REFIID clsid,
                             LPCWSTR expected, BOOL private_expected)
{
    WCHAR guid[40], path[MAX_PATH];
    HMODULE module = pin(clsid);
    DWORD length = module ? GetModuleFileNameW(module, path, ARRAYSIZE(path)) : 0;

    StringFromGUID2(clsid, guid, ARRAYSIZE(guid));
    printf("SHPinDllOfCLSID %s ", label);
    print_wide(guid);
    if (module && length && length < ARRAYSIZE(path))
    {
        BOOL private_provider = is_private_path(path);
        printf(" -> ");
        print_wide(path);
        printf(" (%s)\n", private_provider ? "CDEX" : "Wine/system");
        if (private_provider != private_expected || (expected && !has_basename(path, expected)))
        {
            printf("FAIL: unexpected provider for %s\n", label);
            FreeLibrary(module);
            return NULL;
        }
        return module;
    }

    printf(" -> NULL, error=%lu\n", GetLastError());
    if (module) FreeLibrary(module);
    return NULL;
}

static BOOL register_missing_server_fallback(void)
{
    static const WCHAR key_name[] = L"CLSID\\{deadbeef-1234-5678-90ab-cdef01234567}\\InprocServer32";
    static const WCHAR fallback_path[] = L"C:\\windows\\system32\\shell32.dll";
    HKEY key;
    DWORD disposition, error;

    error = RegCreateKeyExW(HKEY_CLASSES_ROOT, key_name, 0, NULL, 0, KEY_SET_VALUE, NULL, &key, &disposition);
    if (error != ERROR_SUCCESS) return FALSE;
    error = RegSetValueExW(key, NULL, 0, REG_SZ, (const BYTE *)fallback_path,
                           (lstrlenW(fallback_path) + 1) * sizeof(WCHAR));
    RegCloseKey(key);
    return error == ERROR_SUCCESS;
}

static BOOL register_invalid_registry_fallback(void)
{
    static const CHAR key_name[] = "CLSID\\{deadbeef-1234-5678-90ab-cdef01234569}\\InprocServer32";
    static const CHAR path_with_embedded_nul[] = "C:\\windows\\system32\\urlmon.dll\0ignored";
    HKEY key;
    DWORD disposition, error;

    error = RegCreateKeyExA(HKEY_CLASSES_ROOT, key_name, 0, NULL, 0, KEY_SET_VALUE, NULL, &key, &disposition);
    if (error != ERROR_SUCCESS) return FALSE;
    error = RegSetValueExA(key, NULL, 0, REG_SZ, (const BYTE *)path_with_embedded_nul,
                           sizeof(path_with_embedded_nul));
    RegCloseKey(key);
    return error == ERROR_SUCCESS;
}

static BOOL register_missing_system_server_fallback(void)
{
    static const WCHAR key_name[] = L"CLSID\\{deadbeef-1234-5678-90ab-cdef0123456b}\\InprocServer32";
    static const WCHAR fallback_path[] = L"C:\\windows\\system32\\urlmon.dll";
    HKEY key;
    DWORD disposition, error;

    error = RegCreateKeyExW(HKEY_CLASSES_ROOT, key_name, 0, NULL, 0, KEY_SET_VALUE, NULL, &key, &disposition);
    if (error != ERROR_SUCCESS) return FALSE;
    error = RegSetValueExW(key, NULL, 0, REG_SZ, (const BYTE *)fallback_path,
                           (lstrlenW(fallback_path) + 1) * sizeof(WCHAR));
    RegCloseKey(key);
    return error == ERROR_SUCCESS;
}

static void remove_test_registry_keys(void)
{
    RegDeleteTreeW(HKEY_CLASSES_ROOT, L"CLSID\\{deadbeef-1234-5678-90ab-cdef01234567}");
    RegDeleteTreeW(HKEY_CLASSES_ROOT, L"CLSID\\{deadbeef-1234-5678-90ab-cdef01234569}");
    RegDeleteTreeW(HKEY_CLASSES_ROOT, L"CLSID\\{deadbeef-1234-5678-90ab-cdef0123456b}");
    RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Classes\\CLSID\\{deadbeef-1234-5678-90ab-cdef01234567}");
    RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Classes\\CLSID\\{deadbeef-1234-5678-90ab-cdef01234569}");
    RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Classes\\CLSID\\{deadbeef-1234-5678-90ab-cdef0123456b}");
}

static BOOL test_sh_auto_complete(HMODULE shlwapi)
{
    sh_auto_complete_fn auto_complete = (sh_auto_complete_fn)GetProcAddress(shlwapi, "SHAutoComplete");
    HWND edit;
    HRESULT hr;

    if (!auto_complete)
    {
        printf("GetProcAddress(SHAutoComplete) failed: %lu\n", GetLastError());
        return FALSE;
    }

    edit = CreateWindowExW(0, L"EDIT", L"", WS_VISIBLE | WS_OVERLAPPEDWINDOW | ES_AUTOHSCROLL,
                           40, 40, 420, 80, NULL, NULL, GetModuleHandleW(NULL), NULL);
    if (!edit)
    {
        printf("CreateWindow(EDIT) failed: %lu\n", GetLastError());
        return FALSE;
    }

    hr = auto_complete(edit, 0x0f); /* SHACF_FILESYSTEM | SHACF_URLALL | SHACF_USETAB */
    printf("SHAutoComplete -> 0x%08lx\n", (unsigned long)hr);
    if (SUCCEEDED(hr))
    {
        SetFocus(edit);
        SetWindowTextW(edit, L"C:\\win");
        SendMessageW(edit, WM_CHAR, 'd', 1);
        UpdateWindow(edit);
        Sleep(500);
    }
    DestroyWindow(edit);
    return SUCCEEDED(hr);
}

static BOOL sibling_path(LPCWSTR name, LPWSTR path, DWORD size)
{
    DWORD length = GetModuleFileNameW(NULL, path, size);
    WCHAR *slash;
    SIZE_T remaining;

    if (!length || length >= size) return FALSE;
    slash = wcsrchr(path, L'\\');
    if (!slash) return FALSE;
    remaining = size - (slash + 1 - path);
    if ((SIZE_T)lstrlenW(name) >= remaining) return FALSE;
    lstrcpyW(slash + 1, name);
    return TRUE;
}

static BOOL test_nested_actctx(shpin_dll_of_clsid_fn pin)
{
    ACTCTXW actctx;
    HANDLE handle;
    ULONG_PTR cookie;
    WCHAR manifest[MAX_PATH];
    HMODULE module;
    BOOL result;

    if (!sibling_path(L"runtime.manifest", manifest, ARRAYSIZE(manifest))) return FALSE;
    memset(&actctx, 0, sizeof(actctx));
    actctx.cbSize = sizeof(actctx);
    actctx.lpSource = manifest;
    handle = CreateActCtxW(&actctx);
    if (handle == INVALID_HANDLE_VALUE)
    {
        printf("CreateActCtxW failed: %lu\n", GetLastError());
        return FALSE;
    }
    if (!ActivateActCtx(handle, &cookie))
    {
        printf("ActivateActCtx failed: %lu\n", GetLastError());
        ReleaseActCtx(handle);
        return FALSE;
    }
    module = report_module("nested activation context", pin, &clsid_aclistisf,
                           L"browseui.dll", TRUE);
    result = module != NULL;
    if (module) FreeLibrary(module);
    if (!DeactivateActCtx(0, cookie))
    {
        printf("DeactivateActCtx failed: %lu\n", GetLastError());
        result = FALSE;
    }
    ReleaseActCtx(handle);
    printf("Nested activation context: %s\n", result ? "PASS" : "FAIL");
    return result;
}

static BOOL verify_child_log(LPCWSTR filename)
{
    FILE *file = _wfopen(filename, L"rt");
    char contents[4096], private_path[MAX_PATH * 4];
    SIZE_T root_length;
    BOOL result;

    if (!file) return FALSE;
    {
        size_t length = fread(contents, 1, sizeof(contents) - 1, file);
        contents[length] = 0;
        if (!length && ferror(file))
        {
            fclose(file);
            return FALSE;
        }
    }
    if (ferror(file))
    {
        fclose(file);
        return FALSE;
    }
    fclose(file);
    root_length = WideCharToMultiByte(CP_UTF8, 0, private_dir, -1, private_path,
                                     sizeof(private_path), NULL, NULL);
    if (!root_length) return FALSE;
    CharLowerBuffA(contents, lstrlenA(contents));
    CharLowerBuffA(private_path, (DWORD)root_length);
    result = strstr(contents, "shell32.dll ->") && strstr(contents, "shlwapi.dll ->") &&
             strstr(contents, "browseui.dll ->") && !strstr(contents, private_path);
    printf("x86 child DLL map:\n%s", contents);
    printf("x86 child Wine DLL map: %s\n", result ? "PASS" : "FAIL");
    return result;
}

static BOOL test_zonechk(HMODULE shlwapi)
{
    typedef HRESULT (WINAPI *zone_check_fn)(LPCWSTR, PBYTE, DWORD, PBYTE, DWORD,
                                             DWORD, DWORD, IInternetSecurityMgrSite *,
                                             IInternetSecurityManager *);
    zone_check_fn zone_check = (zone_check_fn)GetProcAddress(shlwapi, MAKEINTRESOURCEA(233));
    HRESULT hr;
    HANDLE snapshot;
    MODULEENTRY32W entry;
    WCHAR path[MAX_PATH];

    if (!zone_check)
    {
        printf("GetProcAddress(ZoneCheckUrlExCacheW) failed: %lu\n", GetLastError());
        return FALSE;
    }
    printf("urlmon before zonechk: %s\n", GetModuleHandleW(L"urlmon.dll") ? "loaded" : "not loaded");
    hr = zone_check(L"file:///C:/reactos/explorer.exe", NULL, 0, NULL, 0,
                    URLACTION_SHELL_EXECUTE_HIGHRISK, 0, NULL, NULL);
    printf("ZoneCheckUrlExCacheW(Internet Security Manager) -> 0x%08lx\n", (unsigned long)hr);
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    if (snapshot == INVALID_HANDLE_VALUE)
    {
        printf("FAIL: module snapshot after zonechk failed: %lu\n", GetLastError());
        return FALSE;
    }
    entry.dwSize = sizeof(entry);
    if (!Module32FirstW(snapshot, &entry))
    {
        CloseHandle(snapshot);
        printf("FAIL: module enumeration after zonechk failed: %lu\n", GetLastError());
        return FALSE;
    }
    do
    {
        if (!lstrcmpiW(entry.szModule, L"urlmon.dll"))
        {
            lstrcpynW(path, entry.szExePath, ARRAYSIZE(path));
            CloseHandle(snapshot);
            printf("zonechk cached provider: "); print_wide(path); printf("\n");
            return !is_private_path(path);
        }
    } while (Module32NextW(snapshot, &entry));
    CloseHandle(snapshot);
    printf("FAIL: zonechk did not retain its COM provider\n");
    return FALSE;
}

static BOOL test_pin_performance(shpin_dll_of_clsid_fn pin)
{
    LARGE_INTEGER frequency, before, after;
    WCHAR direct_path[MAX_PATH];
    unsigned int i;
    double resolver_ms, direct_ms;

    if (!QueryPerformanceFrequency(&frequency) ||
        !sibling_path(L"browseui.dll", direct_path, ARRAYSIZE(direct_path)))
        return FALSE;

    QueryPerformanceCounter(&before);
    for (i = 0; i < 500; ++i)
    {
        HMODULE module = pin(&clsid_aclistisf);
        if (!module) return FALSE;
        FreeLibrary(module);
    }
    QueryPerformanceCounter(&after);
    resolver_ms = 1000.0 * (after.QuadPart - before.QuadPart) / frequency.QuadPart;

    QueryPerformanceCounter(&before);
    for (i = 0; i < 500; ++i)
    {
        HMODULE module = LoadLibraryExW(direct_path, NULL, 0);
        if (!module) return FALSE;
        FreeLibrary(module);
    }
    QueryPerformanceCounter(&after);
    direct_ms = 1000.0 * (after.QuadPart - before.QuadPart) / frequency.QuadPart;

    printf("500 pin/free: resolver %.2f ms; direct private LoadLibraryExW %.2f ms; ",
           resolver_ms, direct_ms);
    printf("overhead %.2fx\n", direct_ms ? resolver_ms / direct_ms : 0.0);
    return lstrlenW(private_dir) != 0;
}

static BOOL launch_probe(LPCWSTR executable, LPCWSTR parameters, BOOL stop_after_load)
{
    SHELLEXECUTEINFOW info;
    DWORD exit_code = (DWORD)-1;

    memset(&info, 0, sizeof(info));
    info.cbSize = sizeof(info);
    info.fMask = SEE_MASK_NOCLOSEPROCESS;
    info.lpVerb = L"open";
    info.lpFile = executable;
    info.lpParameters = parameters;
    info.nShow = SW_HIDE;
    if (!ShellExecuteExW(&info) || !info.hProcess)
    {
        printf("ShellExecuteExW %ls failed: %lu\n", executable, GetLastError());
        return FALSE;
    }

    printf("ShellExecuteExW %ls PID=%lu\n", executable, GetProcessId(info.hProcess));
    if (stop_after_load && WaitForSingleObject(info.hProcess, 3000) == WAIT_TIMEOUT)
    {
        TerminateProcess(info.hProcess, 0);
        WaitForSingleObject(info.hProcess, 5000);
        exit_code = 0;
        printf("Stopped long-running test app after DLL-load trace window\n");
    }
    else
    {
        WaitForSingleObject(info.hProcess, 30000);
        GetExitCodeProcess(info.hProcess, &exit_code);
    }
    CloseHandle(info.hProcess);
    printf("Probe exit code: %lu\n", exit_code);
    return exit_code == 0;
}

int main(void)
{
    HMODULE shlwapi, module;
    shpin_dll_of_clsid_fn pin;
    unsigned int i;
    int failures = 0;
    WCHAR child[MAX_PATH], child_source[MAX_PATH], child_log[MAX_PATH], child_args[MAX_PATH + 4];
    DWORD temp_length;

    CoInitialize(NULL);
    shlwapi = LoadLibraryW(L"shlwapi.dll");
    if (!shlwapi)
    {
        printf("LoadLibrary(shlwapi.dll) failed: %lu\n", GetLastError());
        return 1;
    }
    pin = get_shpin(shlwapi);
    if (!pin)
    {
        printf("GetProcAddress(SHPinDllOfCLSID) failed: %lu\n", GetLastError());
        return 2;
    }
    if (!set_private_dir(shlwapi))
    {
        printf("Could not determine the loaded ReactOS shlwapi directory\n");
        return 3;
    }
    {
        WCHAR path[MAX_PATH];
        if (GetModuleFileNameW(shlwapi, path, ARRAYSIZE(path)))
        {
            printf("Harness shlwapi: ");
            print_wide(path);
            printf("\n");
        }
    }

    remove_test_registry_keys();
    if (!test_sh_auto_complete(shlwapi)) ++failures;

    failures += !report_com("ACListISF", &clsid_aclistisf, L"browseui.dll");
    module = report_module("ACListISF", pin, &clsid_aclistisf, L"browseui.dll", TRUE);
    if (!module) ++failures;
    if (module) FreeLibrary(module);
    failures += !report_com("AutoComplete", &clsid_autocomplete, L"browseui.dll");
    module = report_module("AutoComplete", pin, &clsid_autocomplete, L"browseui.dll", TRUE);
    if (!module) ++failures;
    if (module) FreeLibrary(module);
    failures += !report_com("ShellLink", &clsid_shelllink, L"shell32.dll");
    module = report_module("ShellLink", pin, &clsid_shelllink, L"shell32.dll", TRUE);
    if (!module) ++failures;
    if (module) FreeLibrary(module);

    module = report_module("InternetSecurityManager registry fallback", pin,
                           &clsid_internet_security_manager, L"urlmon.dll", FALSE);
    if (module) FreeLibrary(module);
    else ++failures;

    module = report_module("unknown CLSID", pin, &clsid_unknown, NULL, FALSE);
    if (module)
    {
        printf("FAIL: unknown CLSID unexpectedly resolved\n");
        FreeLibrary(module);
        ++failures;
    }

    if (!register_invalid_registry_fallback())
    {
        printf("FAIL: could not register malformed test-only value, error=%lu\n", GetLastError());
        ++failures;
    }
    else if ((module = report_module("malformed registry string", pin,
                                    &clsid_invalid_registry, NULL, FALSE)) != NULL)
    {
        printf("FAIL: malformed registry string loaded a DLL\n");
        FreeLibrary(module);
        ++failures;
    }
    else if (GetLastError() != ERROR_INVALID_DATA)
    {
        printf("FAIL: malformed registry string returned error=%lu, expected %lu\n",
               GetLastError(), ERROR_INVALID_DATA);
        ++failures;
    }
    else
        printf("PASS: malformed registry string failed with ERROR_INVALID_DATA\n");

    if (!register_missing_server_fallback())
    {
        printf("FAIL: could not register test-only fallback key, error=%lu\n", GetLastError());
        ++failures;
    }
    else if ((module = report_module("SxS class with missing provider", pin,
                                    &clsid_missing_server, NULL, FALSE)) != NULL)
    {
        printf("FAIL: missing SxS provider fell back to the registry\n");
        FreeLibrary(module);
        ++failures;
    }
    else
        printf("PASS: missing SxS provider failed closed despite registry fallback\n");

    if (!register_missing_system_server_fallback())
    {
        printf("FAIL: could not register same-name Wine DLL fallback, error=%lu\n", GetLastError());
        ++failures;
    }
    else if ((module = report_module("missing private urlmon with Wine fallback", pin,
                                    &clsid_missing_system_server, L"urlmon.dll", FALSE)) != NULL)
    {
        printf("FAIL: missing private provider loaded the existing Wine urlmon.dll\n");
        FreeLibrary(module);
        ++failures;
    }
    else
        printf("PASS: missing private urlmon did not fall back to the existing Wine DLL\n");

    if (!test_nested_actctx(pin)) ++failures;
    if (!test_zonechk(shlwapi)) ++failures;

    if (!sibling_path(L"shpin-child.exe", child_source, ARRAYSIZE(child_source)) ||
        !(temp_length = GetTempPathW(ARRAYSIZE(child), child)) ||
        temp_length + (DWORD)lstrlenW(L"shpin-child.exe") >= ARRAYSIZE(child) ||
        !(temp_length = GetTempPathW(ARRAYSIZE(child_log), child_log)) ||
        temp_length + (DWORD)lstrlenW(L"shpin-child.log") >= ARRAYSIZE(child_log))
    {
        printf("Could not locate child test files\n");
        ++failures;
    }
    else
    {
        lstrcatW(child, L"shpin-child.exe");
        lstrcatW(child_log, L"shpin-child.log");
        child_args[0] = L'"';
        lstrcpynW(child_args + 1, child_log, ARRAYSIZE(child_args) - 2);
        lstrcatW(child_args, L"\"");
        if (!CopyFileW(child_source, child, FALSE) ||
            !launch_probe(child, child_args, FALSE) || !verify_child_log(child_log)) ++failures;
        DeleteFileW(child);
        DeleteFileW(child_log);
    }
    if (!launch_probe(L"C:\\windows\\sysnative\\notepad.exe", NULL, TRUE)) ++failures;

    module = pin(&clsid_aclistisf);
    if (!module)
    {
        printf("FAIL: initial repeat-test pin failed, error=%lu\n", GetLastError());
        ++failures;
    }
    else
    {
        HMODULE expected = module;
        for (i = 0; i < 32; ++i)
        {
            module = pin(&clsid_aclistisf);
            if (!module || module != expected)
            {
                printf("FAIL: repeat %u returned %p, expected %p, error=%lu\n", i, module, expected, GetLastError());
                ++failures;
                if (module) FreeLibrary(module);
                break;
            }
            FreeLibrary(module);
        }
        FreeLibrary(expected);
        if (i == 32) printf("PASS: 32 repeated pin/free calls returned the same module\n");
    }

    if (!test_pin_performance(pin)) ++failures;

    remove_test_registry_keys();
    FreeLibrary(shlwapi);
    CoUninitialize();
    printf("Harness result: %s (%d failure(s))\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 4 : 0;
}
