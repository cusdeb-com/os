#define COBJMACROS
#include <windows.h>
#include <objbase.h>
#include <oleauto.h>
#include <shellapi.h>
#include <shlobj.h>
#include <tlhelp32.h>
#include <urlmon.h>
#include <stdio.h>
#include <string.h>

static const GUID clsid_aclistisf = {0x03c036f1, 0xa186, 0x11d0, {0x82, 0x4a, 0x00, 0xaa, 0x00, 0x5b, 0x43, 0x83}};
static const GUID clsid_autocomplete = {0x00bb2763, 0x6a77, 0x11d0, {0xa5, 0x35, 0x00, 0xc0, 0x4f, 0xd7, 0xd0, 0x62}};
static const GUID clsid_shelllink = {0x00021401, 0x0000, 0x0000, {0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46}};
static const GUID clsid_shell = {0x13709620, 0xc279, 0x11ce, {0xa4, 0x9e, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00}};
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

static void record_result(const char *scenario, BOOL passed, int *failures)
{
    printf("CASE %s: %s\n", scenario, passed ? "PASS" : "FAIL");
    if (!passed) ++*failures;
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
            {
                printf("FAIL: COM provider mismatch for %s; expected ", label);
                print_wide(expected);
                printf(", got "); print_wide(path); printf("\n");
                result = FALSE;
            }
        }
        else
        {
            printf("FAIL: could not map %s interface vtable to a loaded module (error=%lu)\n",
                   label, GetLastError());
            result = FALSE;
        }
        IUnknown_Release(object);
    }
    else if (expected)
    {
        printf("FAIL: COM activation for %s returned no object; expected provider ", label);
        print_wide(expected); printf("\n");
    }
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
            printf("FAIL: %s expected %s provider ", label,
                   private_expected ? "CDEX" : "Wine/system");
            if (expected) print_wide(expected); else printf("<any>");
            printf(", got "); print_wide(path); printf("\n");
            FreeLibrary(module);
            return NULL;
        }
        return module;
    }

    printf(" -> NULL, error=%lu\n", GetLastError());
    if (private_expected && expected)
    {
        printf("FAIL: %s expected private provider ", label);
        print_wide(expected); printf("\n");
    }
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
    if (FAILED(hr)) printf("FAIL: SHAutoComplete returned HRESULT 0x%08lx\n", (unsigned long)hr);
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

    if (!sibling_path(L"nested.manifest", manifest, ARRAYSIZE(manifest))) return FALSE;
    module = report_module("outer provider before nested context", pin, &clsid_aclistisf,
                           L"browseui.dll", TRUE);
    result = module != NULL;
    if (module) FreeLibrary(module);
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
    module = report_module("nested provider", pin, &clsid_aclistisf, L"shell32.dll", TRUE);
    result = result && module != NULL;
    if (module) FreeLibrary(module);
    if (!DeactivateActCtx(0, cookie))
    {
        printf("DeactivateActCtx failed: %lu\n", GetLastError());
        result = FALSE;
    }
    ReleaseActCtx(handle);
    module = report_module("outer provider after nested context", pin, &clsid_aclistisf,
                           L"browseui.dll", TRUE);
    result = result && module != NULL;
    if (module) FreeLibrary(module);
    printf("Nested provider transition A->B->A: %s\n", result ? "PASS" : "FAIL");
    return result;
}

static BOOL test_shell_application(void)
{
    IDispatch *shell = NULL;
    VARIANT argument, result;
    DISPPARAMS parameters = {&argument, NULL, 1, 0};
    LPOLESTR name = L"NameSpace";
    DISPID dispid;
    HRESULT hr;
    HMODULE provider;
    WCHAR path[MAX_PATH];
    BOOL ok = FALSE;

    hr = CoCreateInstance(&clsid_shell, NULL, CLSCTX_INPROC_SERVER, &IID_IDispatch,
                          (void **)&shell);
    printf("CoCreateInstance Shell.Application -> 0x%08lx\n", (unsigned long)hr);
    if (FAILED(hr) || !shell) return FALSE;

    if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                           GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCWSTR)(ULONG_PTR)shell->lpVtbl, &provider) &&
        GetModuleFileNameW(provider, path, ARRAYSIZE(path)))
    {
        printf("COM provider Shell.Application -> "); print_wide(path); printf("\n");
        ok = is_private_path(path) && has_basename(path, L"shell32.dll");
    }

    VariantInit(&argument);
    V_VT(&argument) = VT_I4;
    V_I4(&argument) = CSIDL_DESKTOP;
    VariantInit(&result);
    hr = IDispatch_GetIDsOfNames(shell, &IID_NULL, &name, 1, LOCALE_USER_DEFAULT, &dispid);
    if (SUCCEEDED(hr))
        hr = IDispatch_Invoke(shell, dispid, &IID_NULL, LOCALE_USER_DEFAULT,
                              DISPATCH_METHOD, &parameters, &result, NULL, NULL);
    printf("Shell.Application.NameSpace(CSIDL_DESKTOP) -> 0x%08lx\n", (unsigned long)hr);
    ok = ok && SUCCEEDED(hr) && result.vt == VT_DISPATCH && result.pdispVal != NULL;
    VariantClear(&result);
    IDispatch_Release(shell);
    printf("Shell.Application interface call: %s\n", ok ? "PASS" : "FAIL");
    return ok;
}

static BOOL is_wine_system_path(const char *path);

static BOOL verify_child_log(LPCWSTR filename)
{
    FILE *file = _wfopen(filename, L"rt");
    char contents[4096], private_path[MAX_PATH * 4];
    SIZE_T root_length;
    BOOL result;

    if (!file)
    {
        printf("Could not open child DLL map: "); print_wide(filename);
        printf(" (error=%lu)\n", GetLastError());
        return FALSE;
    }
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
    result = strstr(contents, "CDEX private COM context: absent") &&
             strstr(contents, "shell32.dll ->") && strstr(contents, "shlwapi.dll ->") &&
             strstr(contents, "browseui.dll ->") && !strstr(contents, private_path);
    if (!result) printf("FAIL: child retained a private context or its DLL map is incomplete/private\n");
    {
        const char *modules[] = {"shell32.dll", "shlwapi.dll", "browseui.dll"};
        unsigned int index;

        for (index = 0; index < ARRAYSIZE(modules) && result; ++index)
        {
            char needle[80], provider[MAX_PATH * 4];
            const char *line, *path, *line_end;
            SIZE_T path_length;

            snprintf(needle, sizeof(needle), "%s -> ", modules[index]);
            line = strstr(contents, needle);
            if (!line) { result = FALSE; break; }
            path = line + strlen(needle);
            line_end = strchr(path, '\n');
            path_length = line_end ? (SIZE_T)(line_end - path) : strlen(path);
            if (path_length >= sizeof(provider)) { result = FALSE; break; }
            memcpy(provider, path, path_length);
            provider[path_length] = 0;
            result = is_wine_system_path(provider);
        }
    }
    printf("x86 child DLL map:\n%s", contents);
    printf("x86 child context and Wine DLL map: %s\n", result ? "PASS" : "FAIL");
    return result;
}

static BOOL is_wine_system_path(const char *path)
{
    static const char system32[] = "c:\\windows\\system32\\";
    static const char syswow64[] = "c:\\windows\\syswow64\\";

    return !strncmp(path, system32, sizeof(system32) - 1) ||
           !strncmp(path, syswow64, sizeof(syswow64) - 1) ||
           strstr(path, "\\usr\\lib\\wine\\") != NULL ||
           strstr(path, "/usr/lib/wine/") != NULL;
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
    printf("ZoneCheckUrlExCacheW call HRESULT: %s\n", SUCCEEDED(hr) ? "success" : "failure");
    printf("ZoneCheckUrlExCacheW HRESULT status: %s\n", SUCCEEDED(hr) ? "success" : "failure");
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

    if (!QueryPerformanceFrequency(&frequency))
    {
        printf("QueryPerformanceFrequency failed: %lu\n", GetLastError());
        return FALSE;
    }
    if (!sibling_path(L"browseui.dll", direct_path, ARRAYSIZE(direct_path)))
    {
        printf("Could not form the private browseui.dll path for the timing comparison\n");
        return FALSE;
    }

    QueryPerformanceCounter(&before);
    for (i = 0; i < 500; ++i)
    {
        HMODULE module = pin(&clsid_aclistisf);
        if (!module)
        {
            printf("SHPinDllOfCLSID failed during timing probe at iteration %u: %lu\n", i, GetLastError());
            return FALSE;
        }
        FreeLibrary(module);
    }
    QueryPerformanceCounter(&after);
    resolver_ms = 1000.0 * (after.QuadPart - before.QuadPart) / frequency.QuadPart;

    QueryPerformanceCounter(&before);
    for (i = 0; i < 500; ++i)
    {
        HMODULE module = LoadLibraryExW(direct_path, NULL, 0);
        if (!module)
        {
            printf("LoadLibraryExW failed during timing baseline at iteration %u: %lu\n", i, GetLastError());
            return FALSE;
        }
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
    BOOL passed;
    WCHAR child[MAX_PATH], child_temp[MAX_PATH], child_source[MAX_PATH];
    WCHAR child_log[MAX_PATH], temp_path[MAX_PATH], child_args[MAX_PATH + 4];
    DWORD temp_length;
    BOOL child_temp_created = FALSE, child_created = FALSE, child_log_created = FALSE;

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
    passed = test_sh_auto_complete(shlwapi);
    record_result("SHAutoComplete call", passed, &failures);

    passed = report_com("ACListISF", &clsid_aclistisf, L"browseui.dll");
    record_result("COM activation ACListISF", passed, &failures);
    module = report_module("ACListISF", pin, &clsid_aclistisf, L"browseui.dll", TRUE);
    record_result("SHPin provider ACListISF", module != NULL, &failures);
    if (module) FreeLibrary(module);
    passed = report_com("AutoComplete", &clsid_autocomplete, L"browseui.dll");
    record_result("COM activation AutoComplete", passed, &failures);
    module = report_module("AutoComplete", pin, &clsid_autocomplete, L"browseui.dll", TRUE);
    record_result("SHPin provider AutoComplete", module != NULL, &failures);
    if (module) FreeLibrary(module);
    passed = report_com("ShellLink", &clsid_shelllink, L"shell32.dll");
    record_result("COM activation ShellLink", passed, &failures);
    module = report_module("ShellLink", pin, &clsid_shelllink, L"shell32.dll", TRUE);
    record_result("SHPin provider ShellLink", module != NULL, &failures);
    if (module) FreeLibrary(module);
    record_result("Shell.Application interface call", test_shell_application(), &failures);

    module = report_module("InternetSecurityManager registry fallback", pin,
                           &clsid_internet_security_manager, L"urlmon.dll", FALSE);
    passed = module != NULL;
    record_result("Wine registry fallback urlmon", passed, &failures);
    if (module) FreeLibrary(module);

    module = report_module("unknown CLSID", pin, &clsid_unknown, NULL, FALSE);
    passed = module == NULL;
    if (module)
    {
        printf("FAIL: unknown CLSID unexpectedly resolved\n");
        FreeLibrary(module);
    }
    record_result("Unknown CLSID rejected", passed, &failures);

    passed = register_invalid_registry_fallback();
    if (!passed)
    {
        printf("FAIL: could not register malformed test-only value, error=%lu\n", GetLastError());
    }
    else if ((module = report_module("malformed registry string", pin,
                                    &clsid_invalid_registry, NULL, FALSE)) != NULL)
    {
        printf("FAIL: malformed registry string loaded a DLL\n");
        FreeLibrary(module);
        passed = FALSE;
    }
    else if (GetLastError() != ERROR_INVALID_DATA)
    {
        printf("FAIL: malformed registry string returned error=%lu, expected %lu\n",
               GetLastError(), ERROR_INVALID_DATA);
        passed = FALSE;
    }
    else
        printf("PASS: malformed registry string failed with ERROR_INVALID_DATA\n");
    record_result("Malformed registry value rejected", passed, &failures);

    passed = register_missing_server_fallback();
    if (!passed)
    {
        printf("FAIL: could not register test-only fallback key, error=%lu\n", GetLastError());
    }
    else if ((module = report_module("SxS class with missing provider", pin,
                                    &clsid_missing_server, NULL, FALSE)) != NULL)
    {
        printf("FAIL: missing SxS provider fell back to the registry\n");
        FreeLibrary(module);
        passed = FALSE;
    }
    else
        printf("PASS: missing SxS provider failed closed despite registry fallback\n");
    record_result("Missing SxS provider fails closed", passed, &failures);

    passed = register_missing_system_server_fallback();
    if (!passed)
    {
        printf("FAIL: could not register same-name Wine DLL fallback, error=%lu\n", GetLastError());
    }
    else if ((module = report_module("missing private urlmon with Wine fallback", pin,
                                    &clsid_missing_system_server, L"urlmon.dll", FALSE)) != NULL)
    {
        printf("FAIL: missing private provider loaded the existing Wine urlmon.dll\n");
        FreeLibrary(module);
        passed = FALSE;
    }
    else
        printf("PASS: missing private urlmon did not fall back to the existing Wine DLL\n");
    record_result("Missing private provider does not load Wine DLL", passed, &failures);

    record_result("Nested activation-context transition", test_nested_actctx(pin), &failures);
    record_result("ZoneCheck COM provider resolution", test_zonechk(shlwapi), &failures);

    if (!sibling_path(L"shpin-child.exe", child_source, ARRAYSIZE(child_source)) ||
        !(temp_length = GetTempPathW(ARRAYSIZE(temp_path), temp_path)) ||
        temp_length >= ARRAYSIZE(temp_path) ||
        !GetTempFileNameW(temp_path, L"shp", 0, child_temp))
    {
        printf("Could not locate child test files\n");
        ++failures;
    }
    else
    {
        WCHAR *extension;
        child_temp_created = TRUE;
        lstrcpynW(child, child_temp, ARRAYSIZE(child));
        extension = wcsrchr(child, L'.');
        if (!extension || lstrcmpiW(extension, L".tmp"))
        {
            printf("GetTempFileNameW returned an unexpected path\n");
            ++failures;
        }
        else
        {
            lstrcpyW(extension, L".exe");
            if (!MoveFileW(child_temp, child))
            {
                printf("Could not reserve unique child path: %lu\n", GetLastError());
                ++failures;
            }
            else
            {
                child_temp_created = FALSE;
                child_created = TRUE;
                if (!GetTempFileNameW(temp_path, L"shl", 0, child_log))
                {
                    printf("Could not reserve unique child log path: %lu\n", GetLastError());
                    ++failures;
                }
                else
                {
                    child_log_created = TRUE;
                    child_args[0] = L'"';
                    lstrcpynW(child_args + 1, child_log, ARRAYSIZE(child_args) - 2);
                    lstrcatW(child_args, L"\"");
                    if (!CopyFileW(child_source, child, FALSE))
                    {
                        printf("CopyFileW child image failed: %lu\n", GetLastError());
                        ++failures;
                    }
                    else
                    {
                        passed = launch_probe(child, child_args, FALSE);
                        record_result("x86 child launched via ShellExecuteEx", passed, &failures);
                        if (passed)
                            record_result("x86 child has no CDEX context and uses Wine DLLs",
                                          verify_child_log(child_log), &failures);
                        else
                            printf("CASE x86 child DLL map: SKIP (child did not exit cleanly)\n");
                    }
                }
            }
        }
        if (child_temp_created) DeleteFileW(child_temp);
        if (child_created) DeleteFileW(child);
        if (child_log_created) DeleteFileW(child_log);
    }
    record_result("x64 Wine process launched via ShellExecuteEx",
                  launch_probe(L"C:\\windows\\sysnative\\notepad.exe", NULL, TRUE), &failures);

    module = pin(&clsid_aclistisf);
    passed = module != NULL;
    if (!module)
    {
        printf("FAIL: initial repeat-test pin failed, error=%lu\n", GetLastError());
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
                passed = FALSE;
                if (module) FreeLibrary(module);
                break;
            }
            FreeLibrary(module);
        }
        FreeLibrary(expected);
        if (i == 32) printf("PASS: 32 repeated pin/free calls returned the same module\n");
    }
    record_result("Repeated pin/free stability", passed, &failures);

    record_result("Resolver timing probe", test_pin_performance(pin), &failures);

    remove_test_registry_keys();
    FreeLibrary(shlwapi);
    CoUninitialize();
    printf("Harness result: %s (%d failure(s))\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 4 : 0;
}
