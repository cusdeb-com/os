#include <windows.h>
#include <stdio.h>

static int log_module(FILE *out, const wchar_t *name)
{
    HMODULE module = LoadLibraryW(name);
    WCHAR path[MAX_PATH];
    char module_name[64], module_path[MAX_PATH * 4];
    DWORD length;
    int name_length;

    if (!module)
    {
        fwprintf(out, L"%ls: LoadLibrary failed, error=%lu\n", name, GetLastError());
        return 0;
    }
    length = GetModuleFileNameW(module, path, ARRAYSIZE(path));
    if (!length || length >= ARRAYSIZE(path))
    {
        fwprintf(out, L"%ls: GetModuleFileName failed, error=%lu\n", name, GetLastError());
        FreeLibrary(module);
        return 0;
    }
    name_length = WideCharToMultiByte(CP_UTF8, 0, name, -1, module_name, sizeof(module_name), NULL, NULL);
    if (!name_length || !WideCharToMultiByte(CP_UTF8, 0, path, -1, module_path, sizeof(module_path), NULL, NULL))
    {
        FreeLibrary(module);
        return 0;
    }
    fprintf(out, "%s -> %s\n", module_name, module_path);
    FreeLibrary(module);
    return 1;
}

int main(int argc, char **argv)
{
    FILE *out;
    int ok = 1;

    if (argc != 2) return 2;
    out = fopen(argv[1], "w");
    if (!out) return 3;
    ok &= log_module(out, L"shell32.dll");
    ok &= log_module(out, L"shlwapi.dll");
    ok &= log_module(out, L"browseui.dll");
    fclose(out);
    return ok ? 0 : 1;
}
