#!/usr/bin/env bash
# ReactOS registry setup helpers.
# Sourced by cdex-win32-session.

reg_add() {
  WINEDEBUG=-all wine reg add "$@" >/dev/null
}

# Build a Windows LOGFONTW as a REG_BINARY value for wine reg add.
# $1 — registry key, $2 — value name, $3 — signed lfHeight, $4 — hex-encoded
# LOGFONTW tail (everything after the lfHeight field).
reg_add_logfont() {
  local key="$1"
  local name="$2"
  local height="$3"
  local tail="$4"
  local b0 b1 b2 b3
  # LOGFONTW.lfHeight is a signed 32-bit little-endian DWORD.
  b0=$(( height & 0xFF ))
  b1=$(( (height >> 8) & 0xFF ))
  b2=$(( (height >> 16) & 0xFF ))
  b3=$(( (height >> 24) & 0xFF ))
  reg_add "$key" /v "$name" /t REG_BINARY /d "$(printf '%02X%02X%02X%02X%s' "$b0" "$b1" "$b2" "$b3" "$tail")" /f
}

add_clsid() {
  local clsid="$1"
  local name="$2"
  local dll="$3"
  reg_add "HKLM\\Software\\Classes\\CLSID\\${clsid}" /ve /t REG_SZ /d "$name" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\${clsid}\\InprocServer32" /ve /t REG_SZ /d "C:\\windows\\system32\\${dll}" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\${clsid}\\InprocServer32" /v ThreadingModel /t REG_SZ /d Apartment /f
}

configure_reactos_registry() {
  # REACTOS_REGISTRY_MARKER must be set by the caller (cdex-win32-session).
  if [ -z "${REACTOS_REGISTRY_MARKER:-}" ]; then
    echo "error: REACTOS_REGISTRY_MARKER is not set" >&2
    exit 1
  fi
  # REACTOS_PREFIX must also be set by the caller.
  if [ -z "${REACTOS_PREFIX:-}" ]; then
    echo "error: REACTOS_PREFIX is not set" >&2
    exit 1
  fi
  # Winlogon\Shell, font substitutes and WindowMetrics live in
  # ensure_reactos_ui_settings below and are re-applied on every login because
  # wine.inf (after Wine upgrades) and theme applications clobber them.
  # The desktop background color is different: wine.inf does not touch it, so
  # we set it only once here (on prefix creation) and let the user change it
  # afterwards. #5D81AB == "93 129 171".
  reg_add "HKCU\\Control Panel\\Colors" /v Background /t REG_SZ /d "93 129 171" /f
  # Offer the same color in the ChooseColor custom palette (16 COLORREF slots,
  # little-endian 0x00BBGGRR) so the user can re-select it in desk.cpl.
  reg_add "HKCU\\Control Panel\\Appearance" /v CustomColors /t REG_BINARY /d "5D81AB00$(printf 'FFFFFF00%.0s' $(seq 15))" /f
  reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer" /f
  reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /f
  reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v ListviewShadow /t REG_DWORD /d 1 /f
  # Hide default desktop namespace icons except My Computer and Recycle Bin.
  # My Documents, My Network Places and Internet Explorer are kept hidden on
  # the desktop but their icons are fixed below so they render correctly in
  # File Explorer. The "/" filesystem-root icon is always hidden.
  for panel in NewStartPanel ClassicStartMenu; do
    reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\${panel}" /f
    reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\${panel}" /v "{450D8FBA-AD25-11D0-98A8-0800361B1103}" /t REG_DWORD /d 1 /f
    reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\${panel}" /v "{208D2C60-3AEA-1069-A2D7-08002B30309D}" /t REG_DWORD /d 1 /f
    reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\${panel}" /v "{871C5380-42A0-1069-A2EA-08002B30309D}" /t REG_DWORD /d 1 /f
    reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\HideDesktopIcons\\${panel}" /v "{9D20AAE8-0625-44B0-9CA7-71889C2254D9}" /t REG_DWORD /d 1 /f
  done
  # Make Recycle Bin appear as a real desktop namespace icon (not a .lnk).
  # Wine/ReactOS registers it under HKLM, but Explorer also needs it in HKCU.
  reg_add "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Desktop\\NameSpace\\{645FF040-5081-101B-9F08-00AA002F954E}" /ve /t REG_SZ /d "Recycle Bin" /f
  reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Desktop\\NameSpace\\{645FF040-5081-101B-9F08-00AA002F954E}" /ve /t REG_SZ /d "Recycle Bin" /f
  # Explicit DefaultIcon values for namespace objects. Wine sometimes fails to
  # resolve icons from InprocServer32 for ReactOS shell32, so provide them here.
  reg_add "HKLM\\Software\\Classes\\CLSID\\{20D04FE0-3AEA-1069-A2D8-08002B30309D}\\DefaultIcon" /ve /t REG_SZ /d "C:\\windows\\system32\\shell32.dll,-16" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{450D8FBA-AD25-11D0-98A8-0800361B1103}\\DefaultIcon" /ve /t REG_SZ /d "C:\\windows\\system32\\shell32.dll,-235" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{208D2C60-3AEA-1069-A2D7-08002B30309D}\\DefaultIcon" /ve /t REG_SZ /d "C:\\windows\\system32\\shell32.dll,-18" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{871C5380-42A0-1069-A2EA-08002B30309D}\\DefaultIcon" /ve /t REG_SZ /d "C:\\windows\\system32\\shell32.dll,-512" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{645FF040-5081-101B-9F08-00AA002F954E}\\DefaultIcon" /ve /t REG_SZ /d "C:\\windows\\system32\\shell32.dll,-32" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{645FF040-5081-101B-9F08-00AA002F954E}\\DefaultIcon" /v Empty /t REG_SZ /d "C:\\windows\\system32\\shell32.dll,-32" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{645FF040-5081-101B-9F08-00AA002F954E}\\DefaultIcon" /v Full /t REG_SZ /d "C:\\windows\\system32\\shell32.dll,-33" /f
  # Register Recycle Bin shell extension handlers so Properties and the desktop
  # context menu work. ReactOS's shell32.rgs contains these, but Wine's prefix
  # init does not apply .rgs registration, so do it explicitly here.
  reg_add "HKLM\\Software\\Classes\\CLSID\\{645FF040-5081-101B-9F08-00AA002F954E}\\shellex\\PropertySheetHandlers\\{645FF040-5081-101B-9F08-00AA002F954E}" /ve /t REG_SZ /d "" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{645FF040-5081-101B-9F08-00AA002F954E}\\shellex\\ContextMenuHandlers\\{645FF040-5081-101B-9F08-00AA002F954E}" /ve /t REG_SZ /d "" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{645FF040-5081-101B-9F08-00AA002F954E}\\ShellFolder" /v Attributes /t REG_BINARY /d 40010020 /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{645FF040-5081-101B-9F08-00AA002F954E}\\ShellFolder" /v CallForAttributes /t REG_DWORD /d 0x00000040 /f
  reg_add "HKLM\\Software\\Classes\\Folder\\shell\\open" /v BrowserFlags /t REG_DWORD /d 0x10 /f
  reg_add "HKLM\\Software\\Classes\\Folder\\shell\\open" /v ExplorerFlags /t REG_DWORD /d 0x12 /f
  reg_add "HKLM\\Software\\Classes\\Folder\\shell\\open\\command" /ve /t REG_SZ /d 'C:\\reactos\\filebrowser.exe "%1"' /f
  reg_add "HKLM\\Software\\Classes\\Folder\\shell\\explore" /v ExplorerFlags /t REG_DWORD /d 0x21 /f
  reg_add "HKLM\\Software\\Classes\\Folder\\shell\\explore\\command" /ve /t REG_SZ /d 'C:\\reactos\\filebrowser.exe /E,"%1"' /f
  reg_add "HKLM\\Software\\Classes\\Directory\\shell\\open" /v BrowserFlags /t REG_DWORD /d 0x10 /f
  reg_add "HKLM\\Software\\Classes\\Directory\\shell\\open" /v ExplorerFlags /t REG_DWORD /d 0x12 /f
  reg_add "HKLM\\Software\\Classes\\Directory\\shell\\open\\command" /ve /t REG_SZ /d 'C:\\reactos\\filebrowser.exe "%1"' /f
  reg_add "HKLM\\Software\\Classes\\Directory\\shell\\explore" /v ExplorerFlags /t REG_DWORD /d 0x21 /f
  reg_add "HKLM\\Software\\Classes\\Directory\\shell\\explore\\command" /ve /t REG_SZ /d 'C:\\reactos\\filebrowser.exe /E,"%1"' /f
  reg_add "HKLM\\Software\\Classes\\Drive\\shell\\open" /v BrowserFlags /t REG_DWORD /d 0x10 /f
  reg_add "HKLM\\Software\\Classes\\Drive\\shell\\open" /v ExplorerFlags /t REG_DWORD /d 0x12 /f
  reg_add "HKLM\\Software\\Classes\\Drive\\shell\\open\\command" /ve /t REG_SZ /d 'C:\\reactos\\filebrowser.exe "%1"' /f
  reg_add "HKLM\\Software\\Classes\\Drive\\shell\\explore" /v ExplorerFlags /t REG_DWORD /d 0x21 /f
  reg_add "HKLM\\Software\\Classes\\Drive\\shell\\explore\\command" /ve /t REG_SZ /d 'C:\\reactos\\filebrowser.exe /E,"%1"' /f

  # Register the ReactOS New Object Service (CLSID_NewMenu) so the New submenu
  # appears in desktop and folder context menus.
  reg_add "HKLM\\Software\\Classes\\CLSID\\{D969A300-E7FF-11D0-A93B-00A0C90F2719}" /ve /t REG_SZ /d "ReactOS New Object Service" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{D969A300-E7FF-11D0-A93B-00A0C90F2719}" /v flags /t REG_DWORD /d 0 /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{D969A300-E7FF-11D0-A93B-00A0C90F2719}\\InprocServer32" /ve /t REG_SZ /d "C:\\windows\\system32\\shell32.dll" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{D969A300-E7FF-11D0-A93B-00A0C90F2719}\\InprocServer32" /v ThreadingModel /t REG_SZ /d Apartment /f

  # Attach CLSID_NewMenu to Directory (background), Directory and Folder classes.
  reg_add "HKLM\\Software\\Classes\\Directory\\Background\\shellex\\ContextMenuHandlers\\New" /ve /t REG_SZ /d "{D969A300-E7FF-11D0-A93B-00A0C90F2719}" /f
  reg_add "HKLM\\Software\\Classes\\Directory\\shellex\\ContextMenuHandlers\\New" /ve /t REG_SZ /d "{D969A300-E7FF-11D0-A93B-00A0C90F2719}" /f
  reg_add "HKLM\\Software\\Classes\\Folder\\shellex\\ContextMenuHandlers\\New" /ve /t REG_SZ /d "{D969A300-E7FF-11D0-A93B-00A0C90F2719}" /f

  # Standard ShellNew handlers that CNewMenu enumerates when building the New submenu.
  reg_add "HKLM\\Software\\Classes\\.txt" /ve /t REG_SZ /d "txtfile" /f
  reg_add "HKLM\\Software\\Classes\\.txt\\ShellNew" /f
  reg_add "HKLM\\Software\\Classes\\.txt\\ShellNew" /v NullFile /t REG_SZ /d "" /f
  reg_add "HKLM\\Software\\Classes\\txtfile" /ve /t REG_SZ /d "Text Document" /f

  reg_add "HKLM\\Software\\Classes\\.bmp" /ve /t REG_SZ /d "Paint.Picture" /f
  reg_add "HKLM\\Software\\Classes\\.bmp\\ShellNew" /f
  reg_add "HKLM\\Software\\Classes\\.bmp\\ShellNew" /v NullFile /t REG_SZ /d "" /f
  reg_add "HKLM\\Software\\Classes\\Paint.Picture" /ve /t REG_SZ /d "Bitmap image" /f

  reg_add "HKLM\\Software\\Classes\\.rtf" /ve /t REG_SZ /d "WordPad.Document.1" /f
  reg_add "HKLM\\Software\\Classes\\.rtf\\ShellNew" /f
  reg_add "HKLM\\Software\\Classes\\.rtf\\ShellNew" /v NullFile /t REG_SZ /d "" /f
  reg_add "HKLM\\Software\\Classes\\WordPad.Document.1" /ve /t REG_SZ /d "Rich Text Document" /f

  # Shortcut creation uses the NewLinkHere applet.
  reg_add "HKLM\\Software\\Classes\\.lnk" /ve /t REG_SZ /d "lnkfile" /f
  reg_add "HKLM\\Software\\Classes\\.lnk\\ShellNew" /f
  reg_add "HKLM\\Software\\Classes\\.lnk\\ShellNew" /v Command /t REG_SZ /d "C:\\windows\\system32\\rundll32.exe appwiz.cpl,NewLinkHere %1" /f
  reg_add "HKLM\\Software\\Classes\\lnkfile" /ve /t REG_SZ /d "Shortcut" /f

  add_clsid "{00BB2763-6A77-11D0-A535-00C04FD7D062}" "Shell ReactOS AutoComplete" browseui.dll
  add_clsid "{00BB2764-6A77-11D0-A535-00C04FD7D062}" "ReactOS History AutoComplete List" browseui.dll
  add_clsid "{6935DB93-21E8-4CCC-BEB9-9FE3C77A297A}" "Custom MRU AutoComplete List" browseui.dll
  add_clsid "{EFA24E64-B078-11D0-89E4-00C04FC9E26E}" "Explorer TreeView Band" shdocvw.dll
  add_clsid "{42AEDC87-2188-41FD-B9A3-0C966FEABEC1}" "MruPidlList" shdocvw.dll
  reg_add "HKLM\\Software\\Classes\\CLSID\\{7BA4C740-9E81-11CF-99D3-00AA004AE837}" /ve /t REG_SZ /d "ReactOS SendTo Object Service" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{7BA4C740-9E81-11CF-99D3-00AA004AE837}" /v flags /t REG_DWORD /d 1 /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{7BA4C740-9E81-11CF-99D3-00AA004AE837}\\InprocServer32" /ve /t REG_SZ /d "C:\\windows\\system32\\shell32.dll" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{7BA4C740-9E81-11CF-99D3-00AA004AE837}\\InprocServer32" /v ThreadingModel /t REG_SZ /d Apartment /f
  reg_add "HKLM\\Software\\Classes\\AllFilesystemObjects\\shellex\\ContextMenuHandlers\\SendTo" /ve /t REG_SZ /d "{7BA4C740-9E81-11CF-99D3-00AA004AE837}" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{9E56BE61-C50F-11CF-9A2C-00A0C90A90CE}" /ve /t REG_SZ /d DeskLink /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{9E56BE61-C50F-11CF-9A2C-00A0C90A90CE}" /v NeverShowExt /t REG_SZ /d "" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{9E56BE61-C50F-11CF-9A2C-00A0C90A90CE}\\DefaultIcon" /ve /t REG_EXPAND_SZ /d "%SystemRoot%\\explorer.exe,-103" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{9E56BE61-C50F-11CF-9A2C-00A0C90A90CE}\\InprocServer32" /ve /t REG_SZ /d "C:\\windows\\system32\\sendmail.dll" /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{9E56BE61-C50F-11CF-9A2C-00A0C90A90CE}\\InprocServer32" /v ThreadingModel /t REG_SZ /d Apartment /f
  reg_add "HKLM\\Software\\Classes\\CLSID\\{9E56BE61-C50F-11CF-9A2C-00A0C90A90CE}\\shellex\\DropHandler" /ve /t REG_SZ /d "{9E56BE61-C50F-11CF-9A2C-00A0C90A90CE}" /f
  reg_add "HKLM\\Software\\Classes\\.DeskLink" /ve /t REG_SZ /d "CLSID\\{9E56BE61-C50F-11CF-9A2C-00A0C90A90CE}" /f
  reg_add "HKLM\\Software\\Classes\\.cpl" /ve /t REG_SZ /d "cplfile" /f
  reg_add "HKLM\\Software\\Classes\\cplfile" /ve /t REG_SZ /d "Control Panel Item" /f
  reg_add "HKLM\\Software\\Classes\\cplfile\\shell\\cplopen\\command" /ve /t REG_SZ /d "C:\\windows\\system32\\control.exe %1" /f
  reg_add "HKLM\\Software\\Classes\\cplfile\\shell\\open\\command" /ve /t REG_SZ /d "C:\\windows\\system32\\control.exe %1" /f
  reg_add "HKCU\\Control Panel\\Appearance\\New Schemes\\0" /v DisplayName /t REG_SZ /d "Windows Standard" /f
  reg_add "HKCU\\Control Panel\\Appearance\\New Schemes\\0" /v LegacyName /t REG_SZ /d "Windows Standard" /f
  reg_add "HKCU\\Control Panel\\Appearance\\New Schemes\\0\\Sizes\\0" /v DisplayName /t REG_SZ /d "Normal" /f
  reg_add "HKCU\\Control Panel\\Appearance\\New Schemes\\0\\Sizes\\0" /v LegacyName /t REG_SZ /d "Normal" /f
  if [ -f "$REACTOS_PREFIX/drive_c/windows/Resources/Themes/Mizu/mizu.msstyles" ]; then
    reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\ThemeManager" /v DllName /t REG_SZ /d "C:\\windows\\Resources\\Themes\\Mizu\\mizu.msstyles" /f
    reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\ThemeManager" /v ColorName /t REG_SZ /d "Normal Color" /f
    reg_add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\ThemeManager" /v SizeName /t REG_SZ /d "Normal Size" /f
  fi

  WINEDEBUG=-all wine regsvr32 /s /i browseui.dll >/dev/null 2>&1 || true
  printf '%s\n' "$(date -Is)" >"$REACTOS_REGISTRY_MARKER"
  WINEDEBUG=-all wineserver -k || true
}

# Re-apply the UI settings that external writers clobber, on every login:
#  - wineboot re-runs wine.inf after every Wine upgrade and resets
#    Winlogon\Shell to "explorer.exe" (reactos-explorer then refuses the
#    desktop role and exits, leaving an empty desktop) and the MS Shell Dlg
#    aliases to Tahoma;
#  - applying a theme (desk.cpl) rewrites the WindowMetrics fonts.
ensure_reactos_ui_settings() {
  # UI font: route the legacy dialog font aliases to our Ubuntu build. The
  # bundled font is GASP-patched (tools/gasp_patch.py) so FreeType renders it
  # antialiased at every size, and renamed per UFL 1.0 clause 2(c)
  # (tools/rename_font.py).
  local ui_font="Ubuntu derivative CusDeb"
  # WindowMetrics LOGFONT binaries: face "Ubuntu derivative CusDeb" (UTF-16LE),
  # weight 400 (normal). Heights (em, ~2pt above the classic Windows metrics):
  # caption/message/status -17, menu/icon/smcaption -14.
  local logfont_tail="0000000000000000000000009001000000000000000001005500620075006E007400750020006400650072006900760061007400690076006500200043007500730044006500620000000000000000000000000000000000"

  reg_add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v Shell /t REG_SZ /d "reactos-explorer.exe" /f

  reg_add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\FontSubstitutes" /v "MS Sans Serif" /t REG_SZ /d "$ui_font" /f
  reg_add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\FontSubstitutes" /v "MS Shell Dlg" /t REG_SZ /d "$ui_font" /f
  reg_add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\FontSubstitutes" /v "MS Shell Dlg 2" /t REG_SZ /d "$ui_font" /f

  reg_add "HKCU\\Software\\Wine\\Fonts\\Replacements" /v Tahoma /t REG_SZ /d "$ui_font" /f
  reg_add "HKCU\\Software\\Wine\\Fonts\\Replacements" /v "Source Sans Pro" /t REG_SZ /d "$ui_font" /f

  local metrics="HKCU\\Control Panel\\Desktop\\WindowMetrics"
  reg_add_logfont "$metrics" CaptionFont -17 "$logfont_tail"
  reg_add_logfont "$metrics" MessageFont -17 "$logfont_tail"
  reg_add_logfont "$metrics" StatusFont -17 "$logfont_tail"
  reg_add_logfont "$metrics" IconFont -14 "$logfont_tail"
  reg_add_logfont "$metrics" MenuFont -14 "$logfont_tail"
  reg_add_logfont "$metrics" SmCaptionFont -14 "$logfont_tail"
}
