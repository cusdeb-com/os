"""Find COM classes declared in the registry scripts of CDEX modules.

ReactOS modules embed RGS scripts that describe registry entries for their
COM classes. This module reads those scripts and selects in-process classes
whose server is the module containing the script. It extracts the class ID,
threading model and programmatic identifier for the shared SxS manifest.

When modules declare the same class, the existing provider preference is used
where applicable; conflicting registrations cause the build to fail. Classes
registered only at runtime or through other mechanisms are outside this scan.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from resources import Resource

# Preserve existing COM mappings when newly included providers repeat a CLSID.
# This ordering affects only duplicate resolution; all payload DLLs/CPLs are included.
COM_PROVIDER_PREFERENCE = (
    "browseui.dll",
    "rshell.dll",
    "sendmail.dll",
    "shell32.dll",
    "shdocvw.dll",
    "shlwapi.dll",
    "version.dll",
    "w32time.dll",
)


# Accept complete brace-delimited CLSIDs before emitting COM class declarations.
GUID_PATTERN = re.compile(r"\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}\Z")

# Match quoted values and GUIDs before braces/words so they remain single tokens.
RGS_TOKEN_PATTERN = re.compile(
    r"'(?:[^']|'')*'"         # Single-quoted string, with doubled quote escapes.
    r'|"[^"]*"'               # Double-quoted string.
    r"|\{[0-9a-fA-F-]{36}\}"  # A GUID is one token, not a nested block.
    r"|[{}=]"
    r"|[^\s{}=]+"
)

# RGS prefixes consumed before the actual registry key or value name.
RGS_MODIFIERS = {"noremove", "forceremove", "delete", "remove", "val"}

# ReactOS and Wine resource compilers use different names for the same RGS data.
COM_REGISTRY_RESOURCE_TYPES = {"REGISTRY", "WINE_REGISTRY"}


# SxS threadingModel values accepted when exporting InprocServer32 metadata.
COM_THREADING_MODELS = {"Apartment", "Both", "Free", "Neutral"}


# ATL registry scripts and COM metadata


@dataclass
class RegistryNode:
    """An RGS registry key or value with its nested entries."""

    name: str
    value: str | None = None
    children: list[RegistryNode] = field(default_factory=list)

    def child(self, name: str) -> RegistryNode | None:
        """Find the first direct child by case-insensitive registry name."""
        for node in self.children:
            if node.name.casefold() == name.casefold():
                return node

        return None


class RegistryParser:
    """Parse ATL RGS resources into registry nodes using a token cursor.

    Registration modifiers and value type tokens are consumed; key names,
    values and nesting are retained for COM class extraction.
    """

    def __init__(self, data: bytes):
        """Decode UTF-8 or BOM-marked UTF-16 input and tokenize its RGS text."""
        encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        text = data.decode(encoding).rstrip("\x00")
        text = re.sub(r"(?m)^\s*//.*$", "", text)

        self.tokens = RGS_TOKEN_PATTERN.findall(text)
        self.position = 0

    def parse(self) -> list[RegistryNode]:
        """Consume the whole script and return its top-level registry nodes."""
        nodes = self._entries()
        if self.position != len(self.tokens):
            raise ValueError("Unexpected trailing RGS tokens")

        return nodes

    def _take(self) -> str:
        """Advance one token, unquote strings and reject premature EOF."""
        if self.position == len(self.tokens):
            raise ValueError("Truncated RGS resource")

        token = self.tokens[self.position]
        self.position += 1

        if token.startswith(("'", '"')):
            return token[1:-1].replace("''", "'")

        return token

    def _entries(self, nested: bool = False) -> list[RegistryNode]:
        """Read sibling entries and consume the closing brace of a nested block."""
        nodes = []

        while self.position < len(self.tokens) and self.tokens[self.position] != "}":
            name = self._take()
            if name.casefold() in RGS_MODIFIERS:
                name = self._take()

            node = RegistryNode(name)

            if self.position < len(self.tokens) and self.tokens[self.position] == "=":
                self._take()  # Equals sign.
                self._take()  # Registry value type.
                node.value = self._take()

            if self.position < len(self.tokens) and self.tokens[self.position] == "{":
                self._take()
                node.children = self._entries(nested=True)

            nodes.append(node)

        if nested and self._take() != "}":
            raise ValueError("Unbalanced RGS resource")

        return nodes


def com_classes(nodes: list[RegistryNode]) -> Iterator[dict[str, str]]:
    """Yield manifest attributes for COM classes implemented by this module.

    Only InprocServer32 entries referring to the RGS module placeholder are
    included. Invalid CLSIDs and unsupported threading models raise ValueError.
    """
    for node in nodes:
        if node.name.casefold() == "clsid":
            for cls in node.children:
                server = cls.child("InprocServer32")
                if server is None or server.value not in {"%MODULE%", "%MODULE_RAW%"}:
                    continue

                if not GUID_PATTERN.fullmatch(cls.name):
                    raise ValueError(f"Unresolved COM class: {cls.name}")

                attributes = {"clsid": cls.name.upper()}

                model = server.child("ThreadingModel")
                if model is not None:
                    if model.value not in COM_THREADING_MODELS:
                        raise ValueError(f"Unsupported threading model: {model.value}")
                    attributes["threadingModel"] = model.value

                progid = cls.child("ProgID")
                if progid is not None and progid.value:
                    attributes["progid"] = progid.value

                yield attributes

        yield from com_classes(node.children)


def collect_com_classes(
    provider: str,
    resources: list[Resource],
    owners: dict[str, tuple[str, dict[str, str]]],
) -> dict[str, dict[str, str]]:
    """Collect one provider's COM classes, keyed by CLSID.

    ``owners`` is shared across providers and updated in place. Existing
    providers keep identical mappings when new modules repeat a CLSID;
    conflicting mappings and duplicates among new providers are rejected.
    """
    classes = {}
    for resource in resources:
        if resource.type not in COM_REGISTRY_RESOURCE_TYPES:
            continue

        nodes = RegistryParser(resource.data).parse()
        for attributes in com_classes(nodes):
            clsid = attributes["clsid"]
            owner = owners.get(clsid)

            if owner is not None and owner[0] != provider:
                if (owner[0] in COM_PROVIDER_PREFERENCE
                        and provider not in COM_PROVIDER_PREFERENCE
                        and owner[1] == attributes):
                    print(f"Duplicate COM class {clsid}: keeping {owner[0]}", flush=True)
                    continue

                raise ValueError(
                    f"COM class {clsid} is supplied by both {owner[0]} and {provider}"
                )
            if owner is not None and owner[1] != attributes:
                raise ValueError(f"Conflicting COM metadata for {clsid}")

            owners[clsid] = (provider, attributes)
            classes[clsid] = attributes
    return classes
