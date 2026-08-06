var fso = WScript.CreateObject("Scripting.FileSystemObject");
var shell = WScript.CreateObject("WScript.Shell");
var shellFolders = "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders\\";
var desktop = shell.RegRead(shellFolders + "Desktop");
var startMenu = shell.RegRead(shellFolders + "Start Menu");
var programs = shell.RegRead(shellFolders + "Programs");

function ensureFolder(path) {
  if (fso.FolderExists(path)) {
    return;
  }

  var parent = fso.GetParentFolderName(path);
  if (parent && !fso.FolderExists(parent)) {
    ensureFolder(parent);
  }
  fso.CreateFolder(path);
}

function shortcut(baseDir, relativePath, target, args, workdir, desc, icon) {
  var path = baseDir + "\\" + relativePath + ".lnk";
  ensureFolder(fso.GetParentFolderName(path));

  var link = shell.CreateShortcut(path);
  link.TargetPath = target;
  link.Arguments = args || "";
  link.WorkingDirectory = workdir || "";
  link.Description = desc || fso.GetBaseName(path);
  if (icon) {
    link.IconLocation = icon;
  }
  link.Save();
}

function removeShortcuts(baseDir, names) {
  for (var i = 0; i < names.length; i++) {
    var path = baseDir + "\\" + names[i] + ".lnk";
    if (fso.FileExists(path)) {
      fso.DeleteFile(path);
    }
  }
}

function createShortcuts(baseDir, entries) {
  for (var i = 0; i < entries.length; i++) {
    var target = entries[i][1];
    // Skip shortcuts whose Windows executable is missing from C:\reactos
    if (target.toLowerCase().indexOf("c:\\reactos\\") === 0) {
      var exeName = target.substring(10);
      if (!fso.FileExists("C:\\reactos\\" + exeName)) {
        continue;
      }
    }
    shortcut(baseDir, entries[i][0], entries[i][1], entries[i][2], entries[i][3], entries[i][4], entries[i][5]);
  }
}

var desktopEntries = [
  // No CusDeb-managed desktop shortcuts here. "My Computer" and "Recycle Bin"
  // are rendered as real shell namespace icons by cdex-registry.
];

// Live installer images get a one-time Calamares shortcut on the desktop.
// The entry is always removed first so installed systems drop the shortcut
// after the first non-live login, then it is recreated only while live.
var desktopEntriesToRemove = [];
var calamaresEntry = ["Install CusDeb OS", "C:\\windows\\system32\\cmd.exe", "/c echo calamares > C:\\cusdeb\\launch-request", "C:\\windows\\system32", "Install CusDeb OS", "C:\\windows\\system32\\shell32.dll,188"];
desktopEntriesToRemove.push(calamaresEntry[0]);
if (shell.Environment("PROCESS")("CUSDEB_LIVE") === "1") {
  desktopEntries.push(calamaresEntry);
}

var programsEntries = [
  ["Administrative Tools\\Terminal", "C:\\windows\\system32\\cmd.exe", "/c echo terminal > C:\\cusdeb\\launch-request", "C:\\windows\\system32", "Terminal", "C:\\windows\\system32\\cmd.exe,0"],
  ["Accessories\\Paint", "C:\\reactos\\mspaint.exe", "", "C:\\reactos", "Paint", ""],
  ["Accessories\\Calculator", "C:\\reactos\\calc.exe", "", "C:\\reactos", "Calculator", ""],
  ["Games\\Minesweeper", "C:\\reactos\\winmine.exe", "", "C:\\reactos", "Minesweeper", ""],
  ["Games\\Spider Solitaire", "C:\\reactos\\spider.exe", "", "C:\\reactos", "Spider Solitaire", ""]
];

// Only create the Firefox shortcut if the host firefox-esr binary is installed.
// The session sets CDEX_FIREFOX_AVAILABLE=1 when it detects the binary.
if (shell.Environment("PROCESS")("CDEX_FIREFOX_AVAILABLE") === "1") {
  programsEntries.push(["Firefox", "C:\\windows\\system32\\cmd.exe", "/c echo firefox > C:\\cusdeb\\launch-request", "C:\\windows\\system32", "Firefox", "C:\\reactos\\firefox.ico,0"]);
}

// Remove all CusDeb-managed program shortcuts first so that optional entries
// (e.g. Firefox) disappear when the host application is no longer installed.
var programsEntriesToRemove = [
  "Administrative Tools\\Terminal",
  "Accessories\\Paint",
  "Accessories\\Calculator",
  "Firefox",
  "Games\\Minesweeper",
  "Games\\Spider Solitaire"
];

removeShortcuts(desktop, desktopEntriesToRemove);
createShortcuts(desktop, desktopEntries);
removeShortcuts(programs, programsEntriesToRemove);
createShortcuts(programs, programsEntries);
