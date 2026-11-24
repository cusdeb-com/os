#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <stdlib.h>
#include <strsafe.h>

#define TRAY_CALLBACK (WM_APP + 1)

static NOTIFYICONDATAW tray_icon;
static HANDLE log_file;
static wchar_t icon_path[MAX_PATH];
static wchar_t control_path[MAX_PATH];
static wchar_t log_path[MAX_PATH];
static UINT tray_slot;
static UINT taskbar_created;

static void log_value(const wchar_t *label, unsigned long value)
{
    wchar_t line[128];
    DWORD written;
    int length = wsprintfW(line, L"%s: %lu\r\n", label, value);

    WriteFile(log_file, line, length * sizeof(wchar_t), &written, NULL);
    FlushFileBuffers(log_file);
}

static void log_context_event(LONG x, LONG y)
{
    wchar_t line[128];
    DWORD written;
    int length = wsprintfW(line, L"Tray context event: %ld,%ld\r\n", x, y);

    WriteFile(log_file, line, length * sizeof(wchar_t), &written, NULL);
    FlushFileBuffers(log_file);
}

static void log_activation_event(UINT event, LONG x, LONG y)
{
    wchar_t line[128];
    DWORD written;
    int length = wsprintfW(line, L"Tray activation event: %u,%ld,%ld\r\n", event, x, y);

    WriteFile(log_file, line, length * sizeof(wchar_t), &written, NULL);
    FlushFileBuffers(log_file);
}

static HICON load_sni_icon(void)
{
    return (HICON)LoadImageW(NULL, icon_path, IMAGE_ICON, 0, 0,
                             LR_LOADFROMFILE | LR_DEFAULTSIZE);
}

static void remove_tray_icon(HWND window)
{
    KillTimer(window, 1);
    log_value(L"NIM_DELETE result", Shell_NotifyIconW(NIM_DELETE, &tray_icon));
    if (tray_icon.hIcon)
    {
        DestroyIcon(tray_icon.hIcon);
        tray_icon.hIcon = NULL;
    }
    DestroyWindow(window);
}

static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam)
{
    if (message == taskbar_created && taskbar_created && tray_icon.hWnd)
    {
        log_value(L"TaskbarCreated NIM_ADD result", Shell_NotifyIconW(NIM_ADD, &tray_icon));
        log_value(L"TaskbarCreated NIM_SETVERSION result", Shell_NotifyIconW(NIM_SETVERSION, &tray_icon));
        return 0;
    }
    if (message == TRAY_CALLBACK)
    {
        UINT event = LOWORD(lparam);
        if (event == 1024 || event == 1025)
            log_activation_event(event, (SHORT)LOWORD(wparam), (SHORT)HIWORD(wparam));
        if (event == WM_CONTEXTMENU)
        {
            POINT point;
            if (GetCursorPos(&point))
                log_context_event(point.x, point.y);
        }
        return 0;
    }

    if (message == WM_TIMER && wparam == 1)
    {
        char command[32] = {0};
        HANDLE file = CreateFileW(control_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                  NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (file != INVALID_HANDLE_VALUE)
        {
            DWORD read;
            ReadFile(file, command, sizeof(command) - 1, &read, NULL);
            CloseHandle(file);
            DeleteFileW(control_path);
            if (!lstrcmpA(command, "DELETE"))
            {
                remove_tray_icon(window);
                return 0;
            }
            if (!lstrcmpA(command, "UPDATE"))
            {
                HICON icon = load_sni_icon();
                if (icon)
                {
                    HICON old_icon = tray_icon.hIcon;
                    tray_icon.hIcon = icon;
                    log_value(L"NIM_MODIFY result", Shell_NotifyIconW(NIM_MODIFY, &tray_icon));
                    if (old_icon)
                        DestroyIcon(old_icon);
                }
            }
        }
        return 0;
    }

    if (message == WM_DESTROY)
    {
        PostQuitMessage(0);
        return 0;
    }

    return DefWindowProcW(window, message, wparam, lparam);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show)
{
    WNDCLASSW window_class = {0};
    wchar_t directory[MAX_PATH];
    DWORD length;
    HWND window;
    MSG message;

    (void)previous;
    (void)show;

    tray_slot = (UINT)wcstoul(command_line, NULL, 10);
    if (!tray_slot)
        return 1;

    length = GetEnvironmentVariableW(L"CDEX_SNI_DIR", directory, ARRAYSIZE(directory));
    if (!length || length >= ARRAYSIZE(directory) ||
        FAILED(StringCchPrintfW(icon_path, ARRAYSIZE(icon_path), L"%s\\icon-%u.ico", directory, tray_slot)) ||
        FAILED(StringCchPrintfW(control_path, ARRAYSIZE(control_path), L"%s\\control-%u.txt", directory, tray_slot)) ||
        FAILED(StringCchPrintfW(log_path, ARRAYSIZE(log_path), L"%s\\host-%u.log", directory, tray_slot)))
        return 1;

    log_file = CreateFileW(log_path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    if (log_file == INVALID_HANDLE_VALUE)
        return 1;

    window_class.lpfnWndProc = window_proc;
    window_class.hInstance = instance;
    window_class.lpszClassName = L"CDEXSniTrayHost";
    if (!RegisterClassW(&window_class))
    {
        log_value(L"RegisterClass error", GetLastError());
        CloseHandle(log_file);
        return 2;
    }

    taskbar_created = RegisterWindowMessageW(L"TaskbarCreated");
    window = CreateWindowW(window_class.lpszClassName, L"CDEX SNI tray host", 0,
                           0, 0, 0, 0, NULL, NULL, instance, NULL);
    if (!window)
    {
        log_value(L"CreateWindow error", GetLastError());
        CloseHandle(log_file);
        return 3;
    }

    tray_icon.cbSize = sizeof(tray_icon);
    tray_icon.hWnd = window;
    tray_icon.uID = tray_slot;
    tray_icon.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP;
    tray_icon.uCallbackMessage = TRAY_CALLBACK;
    tray_icon.hIcon = load_sni_icon();
    length = GetEnvironmentVariableW(L"CDEX_SNI_TOOLTIP", tray_icon.szTip, ARRAYSIZE(tray_icon.szTip));
    if (!length || length >= ARRAYSIZE(tray_icon.szTip))
        lstrcpyW(tray_icon.szTip, L"Linux application");

    if (!tray_icon.hIcon)
    {
        log_value(L"Load SNI icon error", GetLastError());
        DestroyWindow(window);
        CloseHandle(log_file);
        return 4;
    }

    log_value(L"NIM_ADD result", Shell_NotifyIconW(NIM_ADD, &tray_icon));
    tray_icon.uVersion = NOTIFYICON_VERSION_4;
    log_value(L"NIM_SETVERSION result", Shell_NotifyIconW(NIM_SETVERSION, &tray_icon));
    SetTimer(window, 1, 200, NULL);

    while (GetMessageW(&message, NULL, 0, 0) > 0)
    {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }

    CloseHandle(log_file);
    return 0;
}
