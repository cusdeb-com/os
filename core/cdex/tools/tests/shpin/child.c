#include <windows.h>
#include <stdio.h>
#include <string.h>

static const GUID clsid_private = {
    0x03c036f1, 0xa186, 0x11d0, {0x82, 0x4a, 0x00, 0xaa, 0x00, 0x5b, 0x43, 0x83}
};

static int log_activation_context(FILE *out)
{
    ACTCTX_SECTION_KEYED_DATA data;

    memset(&data, 0, sizeof(data));
    data.cbSize = sizeof(data);
    if (FindActCtxSectionGuid(0, NULL, ACTIVATION_CONTEXT_SECTION_COM_SERVER_REDIRECTION,
                              &clsid_private, &data))
    {
        fprintf(out, "CDEX private COM context: present\n");
        ReleaseActCtx(data.hActCtx);
        return 0;
    }
    fprintf(out, "CDEX private COM context: absent (error=%lu)\n", GetLastError());
    return 1;
}

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
    ok &= log_activation_context(out);
    ok &= log_module(out, L"shell32.dll");
    ok &= log_module(out, L"shlwapi.dll");
    ok &= log_module(out, L"browseui.dll");
    fclose(out);
    return ok ? 0 : 1;
}
