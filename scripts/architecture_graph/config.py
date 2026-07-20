from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
import math
import unicodedata

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from architecture_graph.canonical import canonical_bytes, sha256_digest


DEFAULT_INCLUDES = (
    "adr/*.md",
    "adr/**/*.md",
    "architecture/*",
    "architecture/**/*",
    "docs/adr/*.md",
    "docs/adr/**/*.md",
    "docs/architecture/*",
    "docs/architecture/**/*",
)
DEFAULT_EXCLUDES = ("**/.git/**", "**/node_modules/**", "**/vendor/**")
ALLOWED_KEYS = {
    "schema_version",
    "include",
    "exclude",
    "untracked",
    "plaintext",
    "source_roles",
    "source_authorities",
    "aliases",
    "max_segment_chars",
    "spacy_model",
    "review_authorities",
}
DOCUMENT_ROLES = frozenset({"adr", "standard", "architecture", "diagram", "narrative"})
AUTHORITY_CLASSES = frozenset(
    {
        "accepted_adr_or_active_standard",
        "approved_policy_or_constraint",
        "maintained_architecture",
        "proposal_or_draft",
        "narrative_note",
    }
)


@dataclass(frozen=True)
class ProjectConfig:
    schema_version: int = 1
    include: tuple[str, ...] = DEFAULT_INCLUDES
    exclude: tuple[str, ...] = DEFAULT_EXCLUDES
    untracked: tuple[str, ...] = ()
    plaintext: tuple[str, ...] = ()
    source_roles: dict[str, str] = field(default_factory=dict)
    source_authorities: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    max_segment_chars: int = 8_000
    spacy_model: str | None = "en_core_web_sm"
    review_authorities: dict[str, float] = field(default_factory=dict)

    def as_digest_input(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "include": sorted(set(self.include)),
            "exclude": sorted(set(self.exclude)),
            "untracked": sorted(set(self.untracked)),
            "plaintext": sorted(set(self.plaintext)),
            "source_roles": dict(sorted(self.source_roles.items())),
            "source_authorities": dict(sorted(self.source_authorities.items())),
            "aliases": dict(sorted(self.aliases.items())),
            "max_segment_chars": self.max_segment_chars,
            "spacy_model": self.spacy_model,
            "review_authorities": dict(sorted(self.review_authorities.items())),
        }


def _relative(value: object, key: str, *, allow_glob: bool) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} entries must be nonempty strings")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise ValueError(f"{key} entries must be normalized relative paths")
    if not allow_glob and any(character in value for character in "*?["):
        raise ValueError(f"{key} entries cannot contain glob syntax")
    return value


def _string_tuple(
    raw: dict[str, object], key: str, default: tuple[str, ...], *, allow_glob: bool
) -> tuple[str, ...]:
    value = raw.get(key, default)
    if not isinstance(value, list) and not isinstance(value, tuple):
        raise ValueError(f"{key} must be an array of strings")
    return tuple(_relative(item, key, allow_glob=allow_glob) for item in value)


def _string_map(raw: dict[str, object], key: str) -> dict[str, str]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    result: dict[str, str] = {}
    for pattern, selected in value.items():
        normalized = _relative(pattern, key, allow_glob=True)
        if not isinstance(selected, str) or not selected:
            raise ValueError(f"{key} values must be nonempty strings")
        result[normalized] = selected
    return result


def _identifier(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{key} entries must be strings")
    normalized = " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
    if not normalized:
        raise ValueError(f"{key} entries must be nonempty strings")
    return normalized


def _alias_map(raw: dict[str, object]) -> dict[str, str]:
    value = raw.get("aliases", {})
    if not isinstance(value, dict):
        raise ValueError("aliases must be an object")
    result: dict[str, str] = {}
    for raw_alias, raw_canonical in value.items():
        alias = _identifier(raw_alias, "aliases")
        canonical = _identifier(raw_canonical, "aliases")
        if alias == canonical:
            raise ValueError(f"alias cannot resolve to itself: {raw_alias}")
        if alias in result:
            raise ValueError(f"duplicate normalized alias: {raw_alias}")
        result[alias] = canonical
    chained = sorted(set(result).intersection(result.values()))
    if chained:
        raise ValueError(
            "alias targets must be terminal canonical identifiers: " + ", ".join(chained)
        )
    return result


def _reject_duplicate_mapping_keys(node: Node, path: str = "$") -> None:
    if isinstance(node, MappingNode):
        seen: set[str] = set()
        for key_node, value_node in node.value:
            if not isinstance(key_node, ScalarNode):
                raise ValueError(f"configuration key at {path} must be a scalar")
            key = key_node.value
            if key in seen:
                raise ValueError(f"duplicate configuration key at {path}: {key}")
            seen.add(key)
            _reject_duplicate_mapping_keys(value_node, f"{path}.{key}")
    elif isinstance(node, SequenceNode):
        for index, child in enumerate(node.value):
            _reject_duplicate_mapping_keys(child, f"{path}[{index}]")


def configuration_digest(config: ProjectConfig) -> str:
    return sha256_digest(canonical_bytes(config.as_digest_input()))


def load_config(root: Path, config_path: Path | None = None) -> ProjectConfig:
    path = config_path or root / ".architecture-graph.yaml"
    if not path.exists():
        return ProjectConfig()
    text = path.read_text(encoding="utf-8")
    try:
        composed = yaml.compose(text, Loader=yaml.SafeLoader)
        if composed is not None:
            _reject_duplicate_mapping_keys(composed)
        raw = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValueError(f"invalid architecture graph YAML: {error}") from error
    if raw is None:
        return ProjectConfig()
    if not isinstance(raw, dict):
        raise ValueError("architecture graph configuration must be an object")
    unknown = sorted(set(raw) - ALLOWED_KEYS)
    if unknown:
        raise ValueError(f"unknown configuration keys: {', '.join(unknown)}")
    schema_version = raw.get("schema_version", 1)
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("only configuration schema_version 1 is supported")
    authority_value = raw.get("review_authorities", {})
    if not isinstance(authority_value, dict):
        raise ValueError("review_authorities must be an object")
    review_authorities: dict[str, float] = {}
    for reviewer, authority in authority_value.items():
        if not isinstance(reviewer, str) or not reviewer:
            raise ValueError("review authority keys must be nonempty strings")
        if isinstance(authority, bool) or not isinstance(authority, (int, float)):
            raise ValueError("review authority values must be numbers")
        normalized_authority = float(authority)
        if not math.isfinite(normalized_authority) or not 0 <= normalized_authority <= 1:
            raise ValueError("review authority values must be finite and between 0 and 1")
        review_authorities[reviewer] = normalized_authority
    spacy_model = raw.get("spacy_model", "en_core_web_sm")
    if spacy_model is not None and (not isinstance(spacy_model, str) or not spacy_model):
        raise ValueError("spacy_model must be a nonempty string or null")
    max_segment_chars = raw.get("max_segment_chars", 8_000)
    if type(max_segment_chars) is not int or max_segment_chars < 256:
        raise ValueError("max_segment_chars must be an integer of at least 256")
    source_roles = _string_map(raw, "source_roles")
    invalid_roles = sorted(set(source_roles.values()) - DOCUMENT_ROLES)
    if invalid_roles:
        raise ValueError(f"invalid source roles: {', '.join(invalid_roles)}")
    source_authorities = _string_map(raw, "source_authorities")
    invalid_authorities = sorted(set(source_authorities.values()) - AUTHORITY_CLASSES)
    if invalid_authorities:
        raise ValueError(f"invalid source authorities: {', '.join(invalid_authorities)}")
    return ProjectConfig(
        include=_string_tuple(raw, "include", DEFAULT_INCLUDES, allow_glob=True),
        exclude=_string_tuple(raw, "exclude", DEFAULT_EXCLUDES, allow_glob=True),
        untracked=_string_tuple(raw, "untracked", (), allow_glob=False),
        plaintext=_string_tuple(raw, "plaintext", (), allow_glob=True),
        source_roles=source_roles,
        source_authorities=source_authorities,
        aliases=_alias_map(raw),
        max_segment_chars=max_segment_chars,
        spacy_model=spacy_model,
        review_authorities=review_authorities,
    )


def path_matches(relative_path: str, patterns: tuple[str, ...]) -> bool:
    path = PurePosixPath(relative_path)
    return any(path.match(pattern) for pattern in patterns)


def source_role(relative_path: str, config: ProjectConfig) -> str:
    matches = [
        (pattern, role)
        for pattern, role in config.source_roles.items()
        if PurePosixPath(relative_path).match(pattern)
    ]
    if not matches:
        path = PurePosixPath(relative_path)
        if "adr" in path.parts or "adrs" in path.parts:
            return "adr"
        if path.suffix.casefold() in {".mmd", ".mermaid", ".puml", ".plantuml"}:
            return "diagram"
        if path.suffix.casefold() == ".txt":
            return "narrative"
        return "architecture"
    return sorted(matches, key=lambda item: (-len(item[0]), item[0]))[0][1]


def source_authority(relative_path: str, config: ProjectConfig) -> tuple[str, str]:
    matches = [
        (pattern, authority)
        for pattern, authority in config.source_authorities.items()
        if PurePosixPath(relative_path).match(pattern)
    ]
    if matches:
        return sorted(matches, key=lambda item: (-len(item[0]), item[0]))[0][1], "configured"
    if source_role(relative_path, config) == "narrative":
        return "narrative_note", "default"
    return "maintained_architecture", "default"
