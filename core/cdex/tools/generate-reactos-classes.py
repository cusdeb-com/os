#!/usr/bin/env python3
"""Generate and validate a filtered ReactOS Classes registry fragment.

Processing steps:

- convert ``hivecls.inf`` into a temporary SOFTWARE registry hive;
- export the ``HKLM\\Software\\Classes`` subtree;
- select and normalize the required registry data;
- add compatibility icon values missing from the source;
- write the result as a Wine-compatible ``.reg`` fragment;
- validate the generated fragment.

Included registry data:

- extension association values;
- metadata for classes referenced by extensions;
- selected ``DefaultIcon`` values;
- allow-listed static ``ShellNew`` values.

Validation checks the registry format, allowed icon sources, and preservation
of generated data after importing the fragment into a temporary registry hive.

Other shell commands, ``OpenWith`` entries, protocol registrations, and
unrelated COM registrations are excluded.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

# Registry subtree exported from the ReactOS SOFTWARE hive.
CLASSES_REGISTRY_PREFIX = r"HKEY_LOCAL_MACHINE\SOFTWARE\Classes"

# Header and provenance comments written to generated registry files.
REGISTRY_HEADER = (
    "Windows Registry Editor Version 5.00",
    "",
    "; Generated from ReactOS src/boot/bootdata/hivecls.inf.",
    "; Includes minimal compatibility values missing from that upstream INF.",
    "; Do not edit: regenerate from the source INF.",
    "",
)

# Compatibility icon records added when the upstream export lacks a class icon.
COMPATIBILITY_ICON_RECORDS = {"InternetShortcut": r'@="C:\\reactos\\url.dll,0"'}

# Value names retained for extension association metadata.
ASSOCIATION_VALUES = {"@", "content type", "perceivedtype"}

# Static value names supported by the Windows ShellNew file-creation mechanism.
SHELLNEW_VALUES = {"@", "data", "filename", "nullfile"}

# Matches a quoted registry value name before its equals sign.
VALUE_NAME = re.compile(r'^"((?:\\.|[^"])*)"=', re.ASCII)

# Matches a complete registry section header.
SECTION = re.compile(r"^\[(.*)]$")

# Matches hivexregedit's explicit string type prefix.
TYPE_PREFIX = re.compile(r"=str\(\d+\):(?=\")")

# Matches a registry hexadecimal value and captures its optional subtype.
HEX_VALUE = re.compile(r"hex(?:\((\d+)\))?:(.*)", re.IGNORECASE | re.DOTALL)

# Matches provider paths in DefaultIcon values before they are normalized.
PROVIDER_PATH = re.compile(
    r"(?i)(?:%SystemRoot%|C:\\{1,2}(?:ReactOS|Windows))"
    r"\\{1,2}(?:system32\\{1,2})?([^\\,\"]+\.[^\\,\"]+)"
)

# Matches the concrete provider path emitted by normalization.
NORMALIZED_PROVIDER_PATH = re.compile(
    r"(?i)^C:\\{1,2}reactos\\{1,2}([^\\,\"]+\.[^\\,\"]+)$"
)

# Matches a provider source followed by a numeric icon index.
ICON_REFERENCE = re.compile(r"^(.+),-?\d+$")

# Explicit non-provider icon sources present in the ReactOS Classes hive.
ALLOWED_ICON_SOURCES = {"%1", "msiexec.exe"}

# Provider filenames allowed in generated DefaultIcon values.
KNOWN_ICON_PROVIDERS = frozenset(
    {
        "shell32.dll",
        "shimgvw.dll",
        "wordpad.exe",
        "themeui.dll",
        "msxml3.dll",
        "regedit.exe",
        "ieframe.dll",
        "clipbrd.exe",
        "eventvwr.exe",
        "mstsc.exe",
        "cryptext.dll",
        "mshta.exe",
        "url.dll",
        "hh.exe",
    }
)

# Matches paths to known providers in non-icon registry values.
KNOWN_PROVIDER_PATH_PATTERN = re.compile(
    r"(?i)(?:%SystemRoot%|C:\\{1,2}(?:ReactOS|Windows))"
    r"\\{1,2}(?:system32\\{1,2})?("
    + "|".join(re.escape(provider) for provider in sorted(KNOWN_ICON_PROVIDERS))
    + r")"
)


@dataclass
class _RegistrySection:
    """Represent one section from a ``hivexregedit`` registry export.

    Attributes:
        header: Original section header, including square brackets.
        path: Section path relative to ``HKLM\\Software\\Classes``.
        records: Raw registry value lines belonging to the section.
    """

    header: str
    path: str
    records: list[str] = field(default_factory=list)

    @property
    def parts(self) -> list[str]:
        """Return non-empty components of the section's relative path."""
        return [part for part in self.path.split("\\") if part]


@dataclass(frozen=True)
class GeneratorConfig:
    """Store paths required by the generation and validation pipeline.

    Attributes:
        hivecls: Upstream ReactOS ``hivecls.inf`` source file.
        mkhive: ReactOS host tool that creates a binary registry hive.
        utf16le: ReactOS host tool that converts the INF to UTF-16LE.
        hivexregedit: Host tool used to export and validate registry files.
        output: Destination path for the generated registry fragment.
    """

    hivecls: Path
    mkhive: Path
    utf16le: Path
    hivexregedit: Path
    output: Path


@dataclass
class RegistryArtifact:
    """Describe a generated registry file and its expected section records.

    The expected section records are retained so the validator can check that
    every generated key and value name survives a registry-hive round trip.
    """

    path: Path
    expected_sections: list[tuple[_RegistrySection, list[str]]]


def _fail(message: str) -> NoReturn:
    """Abort generation with the error format expected by build scripts.

    Args:
        message: Human-readable description of the failure, without the
            ``error:`` prefix.

    Raises:
        SystemExit: Always, with a formatted error message.
    """
    raise SystemExit(f"error: {message}")


def _execute(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run an external tool and convert failures to build errors.

    Args:
        command: Executable and arguments to pass to ``subprocess.run``.
        **kwargs: Additional ``subprocess.run`` options, such as
            ``capture_output`` and ``text``.

    Returns:
        The completed process returned by ``subprocess.run``.

    Raises:
        SystemExit: If the executable is missing or exits unsuccessfully.
    """
    try:
        return subprocess.run(command, check=True, **kwargs)
    except FileNotFoundError:
        _fail(f"required command not found: {command[0]}")
    except subprocess.CalledProcessError as error:
        _fail(
            f"command failed with exit status {error.returncode}: {' '.join(command)}"
        )


def _logical_lines(text: str) -> Iterator[str]:
    """Yield logical registry lines after joining backslash continuations.

    ``hivexregedit`` may wrap a registry value over multiple physical lines.
    A trailing backslash joins the next line, and leading whitespace on a
    continuation line is discarded. Empty lines are preserved as logical
    lines because section parsing does not need to reinterpret them.

    Args:
        text: Complete textual registry export.

    Yields:
        Registry lines with continuations represented as one string.
    """
    current = ""
    for line in text.splitlines():
        current += line.lstrip() if current else line
        if current.endswith("\\"):
            current = current[:-1]
            continue
        yield current
        current = ""
    if current:
        yield current


def _parse_export(text: str) -> list[_RegistrySection]:
    """Parse the Classes subtree from a ``hivexregedit`` export.

    Sections outside ``HKLM\\Software\\Classes`` are ignored. Comments and
    records appearing before the first matching section are also ignored.
    Section headers are retained verbatim so the generated file can preserve
    the source export's registry paths.

    Args:
        text: Text produced by ``hivexregedit --export``.

    Returns:
        Parsed Classes sections in their original order.
    """
    sections: list[_RegistrySection] = []
    current: _RegistrySection | None = None
    prefix = CLASSES_REGISTRY_PREFIX.casefold()

    for line in _logical_lines(text):
        match = SECTION.match(line)
        if match:
            path = match.group(1)
            folded_path = path.casefold()
            if folded_path == prefix:
                relative_path = ""
            elif folded_path.startswith(prefix + "\\"):
                relative_path = path[len(CLASSES_REGISTRY_PREFIX) :].lstrip("\\")
            else:
                current = None
                continue
            section = _RegistrySection(line, relative_path)
            current = section
            sections.append(section)
        elif current is not None and line and not line.startswith(";"):
            current.records.append(line)
    return sections


def _value_name(record: str) -> str | None:
    """Extract the name from one textual registry value record.

    The registry's unnamed default value is represented by ``@``. Named
    values are decoded from quoted ``"name"=...`` records so escaped names
    are handled consistently with the registry format.

    Args:
        record: One raw registry value line.

    Returns:
        The decoded value name, ``"@"`` for the default value, or ``None``
        for malformed records.
    """
    if record.startswith("@="):
        return "@"
    match = VALUE_NAME.match(record)
    if not match:
        return None
    return _unescape_registry(match.group(1))


def _unescape_registry(value: str) -> str:
    """Decode the escape sequences used by ``hivexregedit`` registry text.

    Registry backslashes are literal unless they escape a quote or another
    backslash. In particular, sequences such as ``\\t`` and ``\\n`` must not
    be interpreted as JSON control characters.

    Args:
        value: Registry text without its surrounding quotes.

    Returns:
        The decoded registry string.
    """
    result: list[str] = []
    escaped = False
    for char in value:
        if escaped:
            result.append(char if char in {"\\", '"'} else "\\" + char)
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            result.append(char)
    if escaped:
        result.append("\\")
    return "".join(result)


def _escape_registry(value: str) -> str:
    """Escape a registry string for a quoted ``.reg`` value.

    Backslashes and quotes must be escaped so registry importers preserve the
    original string content, including paths and format markers.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _string_value(record: str) -> str | None:
    """Extract and decode a quoted string value from a registry record.

    ``hivexregedit`` can annotate strings with a type prefix such as
    ``str(2):``. The prefix is ignored because the generator only needs the
    decoded text used for class references and metadata filtering.

    Args:
        record: One raw registry value line.

    Returns:
        The decoded string value, or ``None`` for non-string or malformed
        records.
    """
    raw = record.partition("=")[2]
    raw = re.sub(r"^str\(\d+\):", "", raw)
    if not raw.startswith('"') or not raw.endswith('"'):
        return None
    return _unescape_registry(raw[1:-1])


def _value_signature(record: str) -> tuple[str, str, bytes | str] | None:
    """Return a canonical signature for one registry value record.

    String values are compared after registry escaping is decoded. Hexadecimal
    values are compared as bytes so formatting and line wrapping do not affect
    the result. Other values retain their type prefix and normalized text.

    Args:
        record: One raw registry value line.

    Returns:
        A case-folded value name, value kind, and canonical content, or
        ``None`` for malformed records.
    """
    name = _value_name(record)
    if name is None:
        return None

    raw = record.partition("=")[2]
    string = _string_value(record)
    if string is not None:
        return name.casefold(), "string", string

    match = HEX_VALUE.fullmatch(raw)
    if match:
        payload = re.sub(r"[\s,]", "", match.group(2))
        try:
            content = bytes.fromhex(payload)
        except ValueError:
            return name.casefold(), "raw", raw.casefold()
        kind = "hex" if match.group(1) is None else f"hex({match.group(1)})"
        return name.casefold(), kind, content

    value_type, separator, content = raw.partition(":")
    if not separator:
        value_type = "raw"
        content = raw
    return name.casefold(), value_type.casefold(), content.casefold()


def _referenced_classes(sections: list[_RegistrySection]) -> set[str]:
    """Return file classes referenced by top-level extension associations.

    An exported ``Classes`` registry contains entries such as ``.txt`` whose
    unnamed default value points to a class, for example ``@="txtfile"``.
    This function collects those class names so that the caller can later
    retain the corresponding class-level ``DefaultIcon`` and metadata.

    Only one-level extension sections and their unnamed string values are
    considered. Values that are not strings, such as binary registry values,
    are ignored. Class names are case-folded because registry key matching is
    case-insensitive.
    """
    classes: set[str] = set()

    for section in sections:
        if len(section.parts) != 1 or not section.parts[0].startswith("."):
            continue

        for record in section.records:
            if _value_name(record) != "@":
                continue

            value = _string_value(record)
            if value:
                classes.add(value.casefold())

    return classes


def _named_records(records: list[str], names: set[str]) -> list[str]:
    """Return records whose value names belong to an allow-list.

    Registry value names are compared case-insensitively. The caller supplies
    names in their normalized form, including ``"@"`` when the unnamed
    default value should be retained.

    Args:
        records: Raw value records from one registry section.
        names: Allowed case-folded value names.

    Returns:
        Matching records in their original order and spelling.
    """
    return [
        record for record in records if (_value_name(record) or "").casefold() in names
    ]


def _select_records(
    sections: list[_RegistrySection],
) -> list[tuple[_RegistrySection, list[str]]]:
    """Select the safe subset of association and icon registry records.

    The generated fragment contains only:
    - extension association values: the default class, content type, and
      perceived type;
    - static allow-listed ``ShellNew`` values for creating new files;
    - metadata for classes referenced by extensions: the default value and
      ``FriendlyTypeName``;
    - ``DefaultIcon`` values for referenced classes and system associations.

    Other shell commands, ``OpenWith`` entries, protocol registrations, and
    unrelated COM or shell registrations are omitted.

    Args:
        sections: Parsed sections from the complete Classes export.

    Returns:
        Sections paired with the records allowed in the runtime fragment.
    """
    classes = _referenced_classes(sections)
    selected: list[tuple[_RegistrySection, list[str]]] = []

    for section in sections:
        parts = section.parts
        if not parts:
            continue
        first = parts[0]
        first_folded = first.casefold()
        records: list[str] = []

        if first_folded == "systemfileassociations":
            if len(parts) == 2 and parts[1].startswith("."):
                records = _named_records(section.records, ASSOCIATION_VALUES - {"@"})
            elif len(parts) == 3 and parts[2].casefold() == "defaulticon":
                records = _named_records(section.records, {"@"})
        elif first.startswith("."):
            if len(parts) == 1:
                records = _named_records(section.records, ASSOCIATION_VALUES)
            elif len(parts) == 2 and parts[1].casefold() == "shellnew":
                records = _named_records(section.records, SHELLNEW_VALUES)
        elif first_folded in classes:
            if len(parts) == 1:
                records = _named_records(section.records, {"@", "friendlytypename"})
            elif len(parts) == 2 and parts[1].casefold() == "defaulticon":
                records = _named_records(section.records, {"@"})

        if records:
            selected.append((section, records))
    return selected


def _add_compatibility_icons(
    selected: list[tuple[_RegistrySection, list[str]]],
) -> None:
    """Add minimal compatibility icons absent from the upstream export.

    Some Wine/ReactOS integrations expect the ``InternetShortcut`` class to
    have an explicit ``url.dll`` icon even when that class is not emitted by
    the current upstream ``hivecls.inf``. Existing sections are never
    replaced; only missing compatibility sections are appended.

    Args:
        selected: Mutable list of already selected registry sections.
    """
    existing = {section.path.casefold() for section, _ in selected}
    for class_name, record in COMPATIBILITY_ICON_RECORDS.items():
        path = f"{class_name}\\DefaultIcon"
        if path.casefold() not in existing:
            selected.append(
                (
                    _RegistrySection(f"[{CLASSES_REGISTRY_PREFIX}\\{path}]", path),
                    [record],
                )
            )


def _normalize(record: str, provider_pattern: re.Pattern[str]) -> str:
    """Convert an exported registry record to Wine runtime syntax.

    The normalization removes ``hivexregedit`` string type annotations and
    replaces matching ReactOS provider paths with concrete paths under
    ``C:\\reactos``. Concrete paths make icon lookup reliable after the
    generated fragment is imported into a Wine prefix.

    Args:
        record: Raw registry value record from the export.
        provider_pattern: Provider path pattern appropriate for this section.

    Returns:
        The normalized registry record.
    """
    record = TYPE_PREFIX.sub("=", record)
    record = provider_pattern.sub(
        lambda match: f"C:\\\\reactos\\\\{match.group(1)}", record
    )
    value_start = record.find("=") + 1
    raw_value = record[value_start:]
    if raw_value.startswith('"') and raw_value.endswith('"'):
        value = _unescape_registry(raw_value[1:-1])
        record = record[:value_start] + f'"{_escape_registry(value)}"'
    return record


def _icon_providers(
    sections: list[_RegistrySection],
) -> set[str]:
    """Collect and strictly validate providers in DefaultIcon values.

    Args:
        sections: Selected registry sections and their records.

    Returns:
        Case-folded provider filenames referenced by the sections.

    Raises:
        SystemExit: If a DefaultIcon value uses an unsupported or malformed
            icon source.
    """
    providers: set[str] = set()
    for section in sections:
        if not section.parts or section.parts[-1].casefold() != "defaulticon":
            continue
        for record in section.records:
            value = _string_value(record)
            if value is None:
                _fail(f"DefaultIcon is not a string: {section.path}")
            if value.casefold() in ALLOWED_ICON_SOURCES:
                continue
            reference = ICON_REFERENCE.fullmatch(value)
            if reference is None:
                _fail(f"unsupported DefaultIcon value in {section.path}: {value}")
            provider = NORMALIZED_PROVIDER_PATH.fullmatch(reference.group(1))
            if provider is None:
                _fail(f"unsupported DefaultIcon source in {section.path}: {value}")
            providers.add(provider.group(1).casefold())
    return providers


def _check_default_icons(
    sections: list[_RegistrySection],
) -> None:
    """Validate DefaultIcon sources against the CDEX allow-list.

    This is a registry-policy check, not a filesystem check. It prevents a
    provider outside the configured allow-list from entering the output.

    Args:
        sections: Selected and normalized registry sections.

    Raises:
        SystemExit: If a source is malformed or uses an unsupported provider.
    """
    unknown = sorted(_icon_providers(sections) - KNOWN_ICON_PROVIDERS)
    if unknown:
        _fail("unsupported DefaultIcon providers:\n  " + "\n  ".join(unknown))


def _build_software_hive(config: GeneratorConfig, temporary: Path) -> Path:
    """Build a temporary binary SOFTWARE hive from ``hivecls.inf``.

    Args:
        config: Tool and source paths used for the conversion.
        temporary: Existing directory that receives all intermediate files.

    Returns:
        Path to the generated ``SOFTWARE`` hive.

    Raises:
        SystemExit: If a host tool fails or does not produce the hive.
    """
    inf = temporary / "hivecls_utf16.inf"
    hive = temporary / "hive"
    hive.mkdir()
    _execute([str(config.utf16le), str(config.hivecls), str(inf)])
    _execute(
        [
            str(config.mkhive),
            "-h:SOFTWARE",
            "-u",
            f"-d:{hive}",
            str(inf),
        ]
    )
    software = hive / "SOFTWARE"
    if not software.is_file():
        _fail(f"mkhive did not produce {software}")
    return software


class ReactOSClassesGenerator:
    """Generate a filtered ReactOS Classes registry artifact.

    This class owns external tool execution and transformation orchestration.
    Registry parsing, filtering, and normalization remain standalone pure
    functions so they can be tested without creating a hive.
    """

    def __init__(self, config: GeneratorConfig) -> None:
        """Initialize a generator with its source, tools, and output paths.

        Args:
            config: Paths used throughout the generation pipeline.
        """
        self.config = config

    @staticmethod
    def _create_staging_path(destination: Path) -> Path:
        """Create a unique staging filename beside a generated artifact.

        Keeping the staging file beside the destination makes the final
        publish an atomic ``os.replace`` on the same filesystem.

        Args:
            destination: Final artifact path.

        Returns:
            An empty, uniquely named staging path.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".pending",
            dir=destination.parent,
        )
        os.close(descriptor)
        return Path(name)

    def generate(self) -> RegistryArtifact:
        """Build, filter, normalize, and write the registry artifact.

        Returns:
            The output path and the normalized sections expected in that file.

        Raises:
            SystemExit: If a required input or host-tool step fails.
        """
        self._check_required_paths()
        exported = self._export_classes()
        selected = _select_records(_parse_export(exported))
        _add_compatibility_icons(selected)

        normalized = []
        for section, records in selected:
            pattern = (
                PROVIDER_PATH
                if section.parts[-1].casefold() == "defaulticon"
                else KNOWN_PROVIDER_PATH_PATTERN
            )
            normalized_records = [_normalize(record, pattern) for record in records]
            normalized.append((section, normalized_records))

        staging = self._create_staging_path(self.config.output)
        try:
            _write_registry(staging, normalized)
        except BaseException:
            staging.unlink(missing_ok=True)
            raise
        return RegistryArtifact(staging, normalized)

    def _check_required_paths(self) -> None:
        """Verify that source files and host tools exist before generation."""
        required = (
            self.config.hivecls,
            self.config.mkhive,
            self.config.utf16le,
            self.config.hivexregedit,
        )
        for path in required:
            if not path.is_file():
                _fail(f"required input is missing: {path}")

    def _export_classes(self) -> str:
        """Create a temporary hive and export its Classes subtree.

        Returns:
            Text produced by ``hivexregedit --export``.

        Raises:
            SystemExit: If hive construction or export fails.
        """
        with tempfile.TemporaryDirectory(prefix="reactos-classes-") as temporary:
            software = _build_software_hive(self.config, Path(temporary))
            return _execute(
                [
                    str(self.config.hivexregedit),
                    "--export",
                    "--unsafe-printable-strings",
                    "--prefix",
                    CLASSES_REGISTRY_PREFIX.rsplit("\\", 1)[0],
                    str(software),
                    r"\Classes",
                ],
                capture_output=True,
                text=True,
            ).stdout


def _write_registry(
    path: Path, sections: list[tuple[_RegistrySection, list[str]]]
) -> None:
    """Write selected registry sections to an atomically replaced file.

    The output includes a provenance header and is written next to the
    supplied path before ``os.replace`` publishes it. Generation supplies a
    staging path here; the final artifact is published only after validation.

    Args:
        path: Destination path for the generated ``.reg`` file.
        sections: Selected sections and their normalized value records.
    """
    lines = list(REGISTRY_HEADER)
    for section, records in sections:
        lines.extend([section.header, *records, ""])

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            output.write("\n".join(lines))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class ReactOSClassesValidator:
    """Validate a generated registry artifact independently of generation.

    Validation checks the written file's basic registry format and then merges
    it into a disposable SOFTWARE hive using ``hivexregedit``. The second
    layer checks the actual regedit syntax and registry-hive compatibility.
    """

    def __init__(self, config: GeneratorConfig) -> None:
        """Initialize a validator with the tools required for round-trip tests.

        Args:
            config: Paths used to build the disposable validation hive.
        """
        self.config = config

    def validate(self, artifact: RegistryArtifact) -> None:
        """Validate the generated file on disk and through ``hivexregedit``.

        Args:
            artifact: Generated path and expected registry sections.

        Raises:
            SystemExit: If the file is missing, malformed, incomplete, or
                cannot be merged into a hive.
        """
        written_sections = self._read_output(artifact)
        if not artifact.expected_sections:
            _fail("generated registry contains no selected Classes sections")
        self._check_written_sections(artifact.expected_sections, written_sections)
        _check_default_icons(written_sections)
        self._validate_hivex_roundtrip(artifact, written_sections)

    @staticmethod
    def _read_output(artifact: RegistryArtifact) -> list[_RegistrySection]:
        """Read and structurally parse the generated file from disk.

        Args:
            artifact: Artifact whose output path should be checked.

        Returns:
            Parsed Classes sections from the written file.

        Raises:
            SystemExit: If the file is absent, empty, not UTF-8, or contains
                no Classes sections.
        """
        if not artifact.path.is_file():
            _fail(f"generated registry is missing: {artifact.path}")
        if artifact.path.stat().st_size == 0:
            _fail(f"generated registry is empty: {artifact.path}")
        try:
            text = artifact.path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            _fail(f"generated registry is not valid UTF-8: {error}")
        sections = _parse_export(text)
        if not sections:
            _fail(f"generated registry contains no Classes sections: {artifact.path}")
        return sections

    @staticmethod
    def _check_written_sections(
        expected: list[tuple[_RegistrySection, list[str]]],
        actual: list[_RegistrySection],
    ) -> None:
        """Compare the written registry file with the in-memory result.

        The generator writes ``expected`` and then reads the staging file back
        before validation. Comparing section paths and raw value records here
        catches truncated output, unexpected records, and changed value
        contents before the file is merged into a hive that may already
        contain the same registry data.

        Args:
            expected: Sections produced by filtering and normalization.
            actual: Sections parsed from the written staging file.

        Raises:
            SystemExit: If the written file differs from the generated result.
        """
        if len(expected) != len(actual):
            _fail(
                "generated registry differs from in-memory result: expected "
                f"{len(expected)} sections, found {len(actual)}"
            )

        differences: list[str] = []
        actual_by_path = {section.path.casefold(): section for section in actual}
        for expected_section, expected_records in expected:
            actual_section = actual_by_path.get(expected_section.path.casefold())
            if actual_section is None:
                differences.append(f"missing section: {expected_section.path}")
                continue
            if actual_section.records != expected_records:
                differences.append(f"different values: {expected_section.path}")

        expected_paths = {section.path.casefold() for section, _ in expected}
        for section in actual:
            if section.path.casefold() not in expected_paths:
                differences.append(f"unexpected section: {section.path}")

        if differences:
            _fail(
                "generated registry differs from in-memory result:\n  "
                + "\n  ".join(differences)
            )

    def _validate_hivex_roundtrip(
        self,
        artifact: RegistryArtifact,
        expected: list[_RegistrySection],
    ) -> None:
        """Merge the artifact into a disposable hive and export it again.

        The temporary hive starts from the same ReactOS ``hivecls.inf`` used
        during generation. The generated file is merged as an ASCII-compatible
        regedit document, then the Classes subtree is exported to confirm that
        all generated keys and value names survived registry parsing. Exact value
        text is intentionally not compared after export because hivex may rewrite
        registry escaping.

        Args:
            artifact: Generated registry artifact to merge.
            expected: Sections parsed from the generated file on disk.

        Raises:
            SystemExit: If the file cannot be merged or expected data is lost
                during the hive round trip.
        """
        with tempfile.TemporaryDirectory(
            prefix="reactos-classes-validate-"
        ) as temporary:
            temporary = Path(temporary)
            software = _build_software_hive(self.config, Path(temporary))
            prefix = CLASSES_REGISTRY_PREFIX.rsplit("\\", 1)[0]
            parents = temporary / "registry-parents.reg"
            self._write_validation_parents(parents, expected)
            _execute(
                [
                    str(self.config.hivexregedit),
                    "--merge",
                    "--encoding",
                    "ASCII",
                    "--prefix",
                    prefix,
                    str(software),
                    str(parents),
                ]
            )

            _execute(
                [
                    str(self.config.hivexregedit),
                    "--merge",
                    "--encoding",
                    "ASCII",
                    "--prefix",
                    prefix,
                    str(software),
                    str(artifact.path),
                ]
            )

            exported = _execute(
                [
                    str(self.config.hivexregedit),
                    "--export",
                    "--unsafe-printable-strings",
                    "--prefix",
                    prefix,
                    str(software),
                    r"\Classes",
                ],
                capture_output=True,
                text=True,
            ).stdout

            roundtrip = _parse_export(exported)
            self._check_roundtrip_sections(expected, roundtrip)

    @staticmethod
    def _write_validation_parents(
        path: Path,
        sections: list[_RegistrySection],
    ) -> None:
        """Create temporary parent keys required by low-level hive merging.

        ``hivexregedit`` requires parent keys to exist before importing a
        nested key, unlike Windows ``regedit``. The generated artifact must
        remain compatible with the Windows behavior, so these empty parent
        sections are written only to a disposable validation file.

        Args:
            path: Temporary path for the validation-only registry fragment.
            sections: Registry sections whose parent paths are required.
        """
        parent_paths: set[str] = set()
        for section in sections:
            parts = section.parts
            for end in range(1, len(parts)):
                parent_paths.add("\\".join(parts[:end]))

        parents = [
            _RegistrySection(f"[{CLASSES_REGISTRY_PREFIX}\\{parent}]", parent)
            for parent in sorted(
                parent_paths, key=lambda value: (value.count("\\"), value.casefold())
            )
        ]
        _write_registry(path, [(section, []) for section in parents])

    @staticmethod
    def _check_roundtrip_sections(
        expected: list[_RegistrySection],
        actual: list[_RegistrySection],
    ) -> None:
        """Check that generated keys and values survive hive import.

        The source hive already contains upstream Classes data, so the
        round-trip export can contain more sections than the generated file.
        This check therefore verifies that every generated section and value
        is present instead of requiring an exact whole-hive comparison.
        Values are compared using canonical signatures because
        ``hivexregedit`` may rewrite registry escaping during export.

        Args:
            expected: Sections and records from the generated artifact.
            actual: Sections exported after merging the artifact into a hive.

        Raises:
            SystemExit: If a generated key or value is missing after import.
        """
        actual_by_path = {section.path.casefold(): section for section in actual}
        missing: list[str] = []
        for expected_section in expected:
            actual_section = actual_by_path.get(expected_section.path.casefold())
            if actual_section is None:
                missing.append(expected_section.path)
                continue

            expected_values = Counter(
                signature
                for record in expected_section.records
                if (signature := _value_signature(record)) is not None
            )
            actual_values = Counter(
                signature
                for record in actual_section.records
                if (signature := _value_signature(record)) is not None
            )

            for name, kind, _ in (expected_values - actual_values).elements():
                missing.append(f"{expected_section.path}: {name} ({kind})")

        if missing:
            _fail(
                "generated registry lost data during hivex round-trip:\n  "
                + "\n  ".join(missing)
            )


def _generate(config: GeneratorConfig) -> None:
    """Generate and validate the ReactOS Classes registry artifact.

    Args:
        config: Source, tool, artifact, and output paths for the build.

    Raises:
        SystemExit: If generation or any post-generation validation fails.
    """
    artifact = ReactOSClassesGenerator(config).generate()
    try:
        ReactOSClassesValidator(config).validate(artifact)
        os.replace(artifact.path, config.output)
    finally:
        artifact.path.unlink(missing_ok=True)

    values = sum(len(records) for _, records in artifact.expected_sections)
    print(
        f"Generated {config.output} ({len(artifact.expected_sections)} keys, "
        f"{values} values)"
    )


def _main() -> None:
    """Parse command-line arguments and run the generation pipeline.
    Source, tool, and output paths are supplied by the caller. The
    ``hivexregedit`` path has a system default and can be overridden.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hivecls",
        type=Path,
        required=True,
        help="Source hivecls.inf file",
    )
    parser.add_argument(
        "--mkhive",
        type=Path,
        required=True,
        help="Registry hive builder",
    )
    parser.add_argument(
        "--utf16le",
        type=Path,
        required=True,
        help="UTF-16LE converter",
    )
    parser.add_argument(
        "--hivexregedit",
        type=Path,
        default=Path("/usr/bin/hivexregedit"),
        help="Registry hive editor",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Generated registry file",
    )
    args = parser.parse_args()

    _generate(
        GeneratorConfig(
            hivecls=args.hivecls,
            mkhive=args.mkhive,
            utf16le=args.utf16le,
            hivexregedit=args.hivexregedit,
            output=args.output,
        )
    )


if __name__ == "__main__":
    _main()
