# `optional-packages` Calamares viewmodule

A custom Calamares **view module** written in C++ / Qt6. It presents a tree of optional package groups. The user can select individual packages or whole groups; the selected package IDs are stored in Calamares global storage so that a later job module can remove the unselected ones.

## What it does

- Reads the catalog from `/etc/calamares/modules/optional-packages.conf`.
- Renders a `QTreeWidget` with collapsible groups.
- Group checkboxes are tri-state:
  - empty = no package selected,
  - checkmark = all packages selected,
  - square = some packages selected.
- Clicking a group toggles all its children.
- When the user leaves the page, the list of selected package IDs is written to `globalStorage["optional-packages"]`.

## Files

| File | Purpose |
|---|---|
| `OptionalPackagesPage.h` / `OptionalPackagesPage.cpp` | Qt6 UI: tree widget, checkbox state synchronization, selection extraction. |
| `ViewStep.h` / `ViewStep.cpp` | Calamares `ViewStep` implementation. Parses config, owns the page, writes selected IDs to global storage. |
| `CMakeLists.txt` | Builds the plugin without `find_package(Calamares)` because Debian trixie does not ship `calamares-dev`. Links `libcalamares.so` and `libcalamaresui.so` directly. |
| `module.desc` | Calamares plugin descriptor (`type: view`, `interface: qtplugin`). |

## Configuration format

`/etc/calamares/modules/optional-packages.conf`:

```yaml
---
groups:
  - id: terminal-tools
    name: Terminal utilities
    description: Useful command-line tools
    selected: false
    packages:
      - id: htop
        name: htop
        description: Interactive process viewer
        package: htop
      - id: mc
        name: Midnight Commander
        description: Two-panel file manager
        package: mc
```

Fields:

- `id` — internal identifier used in global storage and by the apply job.
- `name` / `description` — shown in the UI.
- `package` — Debian package name resolved by the apply job.
- `selected` — initial group state (`true` = fully checked).

## Build process

The module is built inside the Docker builder before `lb build`:

```bash
# From build-iso.sh
cmake modules/optional-packages
make -j$(nproc)
```

The resulting artifacts are copied into the live-build `includes.chroot` tree:

```text
config/includes.chroot/usr/lib/x86_64-linux-gnu/calamares/modules/optional-packages/
├── module.desc
└── libcalamares_viewmodule_optional-packages.so
```

live-build then copies this tree into the Live filesystem at the same path.

## Why the custom CMakeLists.txt

Debian trixie ships the runtime package `calamares` but not `calamares-dev`. The upstream `CalamaresConfig.cmake` (which would normally be used via `find_package(Calamares)`) depends on Qt6 development packages that are runtime-only in trixie. Therefore this module:

- Manually sets `CALAMARES_INCLUDE_DIR` and `CALAMARES_LIB_DIR`.
- Links directly to `${CALAMARES_LIB_DIR}/libcalamares.so` and `libcalamaresui.so`.
- Defines the same export macros (`PLUGINDLLEXPORT_PRO`, `DLLEXPORT_PRO`, `UIDLLEXPORT_PRO`) that upstream uses.

## Adding a new group or package

1. Edit `/etc/calamares/modules/optional-packages.conf` (i.e. `config/includes.chroot/etc/calamares/modules/optional-packages.conf`).
2. Add the group and package entries with all required fields.
3. Rebuild the ISO.

No C++ code changes are needed unless you want to change the UI behavior.

## Adding a new viewmodule

If you want a completely separate selection page:

1. Create a new directory under `modules/`:

   ```text
   modules/my-choice/
   ├── CMakeLists.txt
   ├── module.desc
   ├── MyChoicePage.cpp/.h
   └── ViewStep.cpp/.h
   ```

2. Inherit `Calamares::ViewStep` and declare the plugin factory with `CALAMARES_PLUGIN_FACTORY_DECLARATION` / `DEFINITION`.
3. Update `build-iso.sh` to build the new module and copy the artifacts to `config/includes.chroot/.../calamares/modules/my-choice/`.
4. Add the module name to the Calamares sequence in `config/hooks/live/patch-calamares-settings.chroot`.

See also [`config/hooks/live/README.md`](../../config/hooks/live/README.md) and [`config/README.md`](../../config/README.md).
