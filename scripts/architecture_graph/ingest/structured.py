from __future__ import annotations

import json
import math
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from yaml.tokens import ScalarToken

from architecture_graph.ingest import IngestionContext, IngestionResult
from architecture_graph.ingest.diagrams import (
    derivation_record,
    exact_source_excerpt,
    segment_and_evidence,
    warning_record,
)
from architecture_graph.records import Record, SourceSpan
from architecture_graph.sources import SourceInput


def _safe_message(value: object) -> str:
    return str(value).encode("utf-8", "backslashreplace").decode("utf-8")


def _safe_json_key(key: str) -> str:
    return json.dumps(key, ensure_ascii=True)


def _reject_duplicate_json(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate mapping key: {_safe_json_key(key)}")
        result[key] = value
    return result


def _reject_json_constant(token: str) -> None:
    raise ValueError(f"non-finite JSON number: {token}")


def _finite_json_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"non-finite JSON number: {token}")
    return value


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _pointer_value(root: object, pointer: str) -> object:
    if pointer == "/" and not isinstance(root, (dict, list)):
        return root
    value = root
    for raw in pointer.removeprefix("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise ValueError(f"JSON pointer crosses a scalar: {pointer}")
    return value


def _scalar_type(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "bool"
    if type(value) is int:
        return "int"
    if type(value) is float:
        return "float"
    if isinstance(value, str):
        return "str"
    raise ValueError(
        f"JSON pointer does not resolve to a scalar: {type(value).__name__}"
    )


def _scalar_value(node: ScalarNode) -> object:
    scalar_type = node.tag.rsplit(":", 1)[-1]
    if scalar_type == "null":
        return None
    if scalar_type not in {"bool", "int", "float"}:
        return node.value
    loader = yaml.SafeLoader("")
    try:
        try:
            if scalar_type == "bool":
                value = loader.construct_yaml_bool(node)
            elif scalar_type == "int":
                value = loader.construct_yaml_int(node)
            else:
                value = loader.construct_yaml_float(node)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid {scalar_type} scalar: {node.value}") from error
    finally:
        loader.dispose()
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite numeric scalar: {node.value}")
    return value


def _warning_span(node: Node) -> SourceSpan:
    return SourceSpan(
        node.start_mark.line + 1,
        max(node.start_mark.line + 1, node.end_mark.line + 1),
    )


def _json_mapping_key(source: SourceInput, node: ScalarNode) -> str:
    span = SourceSpan(
        node.start_mark.line + 1,
        node.end_mark.line + 1,
        node.start_mark.column + 1,
        node.end_mark.column + 1,
    )
    token = exact_source_excerpt(source, span)
    key = json.loads(token)
    if not isinstance(key, str):
        raise ValueError("JSON mapping key did not decode to a string")
    try:
        key.encode("utf-8")
    except UnicodeError as error:
        raise ValueError(
            f"unencodable JSON mapping key: {_safe_json_key(key)}"
        ) from error
    return key


def _reject_duplicate_yaml_keys(
    node: Node, visited: frozenset[int] = frozenset()
) -> None:
    identity = id(node)
    if identity in visited:
        return
    descendants = visited | {identity}
    if isinstance(node, MappingNode):
        seen: set[tuple[str, str]] = set()
        for key_node, value_node in node.value:
            if isinstance(key_node, ScalarNode):
                identity_key = (key_node.tag, key_node.value)
                if identity_key in seen:
                    raise ValueError(
                        f"duplicate mapping key: {_safe_message(key_node.value)}"
                    )
                seen.add(identity_key)
            _reject_duplicate_yaml_keys(value_node, descendants)
    elif isinstance(node, SequenceNode):
        for child in node.value:
            _reject_duplicate_yaml_keys(child, descendants)


StructuredIssue = tuple[str, str, SourceSpan]


def _leaves(
    source: SourceInput,
    node: Node,
    pointer: str = "",
    active: frozenset[int] = frozenset(),
) -> tuple[list[tuple[str, ScalarNode]], list[StructuredIssue]]:
    if isinstance(node, ScalarNode):
        if node.start_mark.index == node.end_mark.index:
            return [], [
                (
                    "parse_failed",
                    f"{pointer or '/'}: zero-width implicit YAML scalar",
                    _warning_span(node),
                )
            ]
        return [(pointer or "/", node)], []

    identity = id(node)
    if identity in active:
        return [], [
            (
                "parse_failed",
                f"cyclic YAML alias at {pointer or '/'}",
                _warning_span(node),
            )
        ]
    descendants = active | {identity}
    if isinstance(node, SequenceNode):
        leaves: list[tuple[str, ScalarNode]] = []
        issues: list[StructuredIssue] = []
        for index, child in enumerate(node.value):
            child_pointer = f"{pointer}/{index}"
            try:
                child_leaves, child_issues = _leaves(
                    source, child, child_pointer, descendants
                )
            except (RecursionError, UnicodeError) as error:
                child_leaves = []
                child_issues = [
                    (
                        "parse_failed",
                        f"{child_pointer}: traversal failed: {type(error).__name__}",
                        _warning_span(child),
                    )
                ]
            leaves.extend(child_leaves)
            issues.extend(child_issues)
        return leaves, issues

    if isinstance(node, MappingNode):
        leaves = []
        issues = []
        for key_node, value_node in node.value:
            if not isinstance(key_node, ScalarNode):
                issues.append(
                    (
                        "unsupported_construct",
                        f"{pointer or '/'}: structured mapping keys must be scalar strings",
                        _warning_span(key_node),
                    )
                )
                continue
            if source.source_kind == "json":
                try:
                    key = _json_mapping_key(source, key_node)
                except (TypeError, UnicodeError, ValueError) as error:
                    issues.append(
                        (
                            "parse_failed",
                            _safe_message(error),
                            _warning_span(key_node),
                        )
                    )
                    continue
            else:
                key = key_node.value
                child_pointer = f"{pointer}/{_pointer_token(key)}"
                if key_node.tag == "tag:yaml.org,2002:merge":
                    issues.append(
                        (
                            "unsupported_construct",
                            f"{child_pointer}: YAML merge keys are unsupported",
                            _warning_span(key_node),
                        )
                    )
                    continue
                if key_node.tag != "tag:yaml.org,2002:str":
                    issues.append(
                        (
                            "unsupported_construct",
                            f"{child_pointer}: structured mapping keys must be strings",
                            _warning_span(key_node),
                        )
                    )
                    continue
            child_pointer = f"{pointer}/{_pointer_token(key)}"
            try:
                child_leaves, child_issues = _leaves(
                    source, value_node, child_pointer, descendants
                )
            except (RecursionError, UnicodeError) as error:
                child_leaves = []
                child_issues = [
                    (
                        "parse_failed",
                        f"{child_pointer}: traversal failed: {type(error).__name__}",
                        _warning_span(value_node),
                    )
                ]
            leaves.extend(child_leaves)
            issues.extend(child_issues)
        return leaves, issues

    return [], [
        (
            "unsupported_construct",
            f"{pointer or '/'}: unsupported YAML node: {type(node).__name__}",
            _warning_span(node),
        )
    ]


def _source_position(text: str, index: int) -> tuple[int, int]:
    if not 0 <= index <= len(text):
        raise ValueError("source mark index is out of bounds")
    offset = 0
    for line_number, raw in enumerate(text.splitlines(keepends=True), start=1):
        if raw.endswith("\r\n"):
            terminator_length = 2
        elif raw.endswith(("\r", "\n")):
            terminator_length = 1
        else:
            terminator_length = 0
        content_end = offset + len(raw) - terminator_length
        if offset <= index <= content_end:
            return line_number, index - offset + 1
        if index < offset + len(raw):
            raise ValueError("source mark falls inside a line terminator")
        offset += len(raw)
    raise ValueError("source mark does not address a physical source line")


def _without_final_line_terminator(text: str, end_index: int) -> int:
    if text[:end_index].endswith("\r\n"):
        return end_index - 2
    if text[:end_index].endswith(("\r", "\n")):
        return end_index - 1
    return end_index


def _node_span(source: SourceInput, node: ScalarNode) -> SourceSpan:
    start_index = node.start_mark.index
    end_index = node.end_mark.index
    if source.source_kind == "yaml":
        candidates = (
            token
            for token in yaml.scan(source.text, Loader=yaml.SafeLoader)
            if isinstance(token, ScalarToken)
            and token.start_mark.index >= node.start_mark.index
            and token.end_mark.index == node.end_mark.index
        )
        token = next(candidates, None)
        if token is not None:
            start_index = token.start_mark.index
            end_index = token.end_mark.index
            if token.style in {"|", ">"} and token.end_mark.column == 0:
                end_index = _without_final_line_terminator(
                    source.text, end_index
                )
    start_line, start_column = _source_position(source.text, start_index)
    end_line, end_column = _source_position(source.text, end_index)
    return SourceSpan(
        start_line,
        end_line,
        start_column,
        end_column,
    )


def segment_structured(
    source: SourceInput, context: IngestionContext
) -> IngestionResult:
    if source.source_kind not in {"yaml", "json"}:
        raise ValueError(
            f"structured adapter does not accept source kind: {source.source_kind}"
        )
    derivation = derivation_record(source, "structured_segmenter", context)
    derivation_id = str(derivation["id"])
    if source.decode_error is not None:
        warning = warning_record(
            source,
            code="parse_failed",
            message=_safe_message(source.decode_error),
            span=None,
            possible_role="context",
            derivation_ids=(derivation_id,),
        )
        return IngestionResult(derivations=(derivation,), warnings=(warning,))

    decoded_json: object | None = None
    try:
        if source.source_kind == "json":
            decoded_json = json.loads(
                source.text,
                object_pairs_hook=_reject_duplicate_json,
                parse_constant=_reject_json_constant,
                parse_float=_finite_json_float,
            )
        root = yaml.compose(source.text, Loader=yaml.SafeLoader)
        if root is None:
            leaves: list[tuple[str, ScalarNode]] = []
            issues: list[StructuredIssue] = []
        else:
            if source.source_kind == "yaml":
                _reject_duplicate_yaml_keys(root)
            leaves, issues = _leaves(source, root)
    except (
        RecursionError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
        yaml.YAMLError,
    ) as error:
        warning = warning_record(
            source,
            code="parse_failed",
            message=_safe_message(
                f"structured source parse failed: {type(error).__name__}: {error}"
            ),
            span=SourceSpan(1, max(1, len(source.text.splitlines()))),
            possible_role="context",
            derivation_ids=(derivation_id,),
        )
        return IngestionResult(derivations=(derivation,), warnings=(warning,))

    segments: list[Record] = []
    evidence: list[Record] = []
    warnings: list[Record] = [
        warning_record(
            source,
            code=code,
            message=_safe_message(message),
            span=span,
            possible_role="context",
            derivation_ids=(derivation_id,),
        )
        for code, message, span in issues
    ]
    for pointer, node in leaves:
        try:
            value = (
                _pointer_value(decoded_json, pointer)
                if source.source_kind == "json"
                else _scalar_value(node)
            )
            if isinstance(value, str):
                value.encode("utf-8")
            text = (
                f"{pointer} = "
                f"{json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)}"
            )
            text.encode("utf-8")
            span = _node_span(source, node)
            exact_text = exact_source_excerpt(source, span)
            if max(len(text), len(exact_text)) > context.max_segment_chars:
                warnings.append(
                    warning_record(
                        source,
                        code="segment_too_large",
                        message=f"structured scalar exceeds max_segment_chars: {pointer}",
                        span=span,
                        possible_role="context",
                        derivation_ids=(derivation_id,),
                    )
                )
                continue
            segment, item_evidence = segment_and_evidence(
                source,
                segment_kind="structured_scalar",
                segment_text=text,
                evidence_text=exact_text,
                span=span,
                heading_path=(),
                metadata={
                    "section_role": "context",
                    "json_pointer": pointer,
                    "scalar_type": (
                        _scalar_type(value)
                        if source.source_kind == "json"
                        else node.tag.rsplit(":", 1)[-1]
                    ),
                    "scalar_value": value,
                },
                derivation_ids=(derivation_id,),
                ordinal=len(segments),
            )
        except (
            KeyError,
            OverflowError,
            RecursionError,
            TypeError,
            UnicodeError,
            ValueError,
            yaml.YAMLError,
        ) as error:
            warnings.append(
                warning_record(
                    source,
                    code="parse_failed",
                    message=_safe_message(
                        f"{pointer}: {type(error).__name__}: {error}"
                    ),
                    span=_warning_span(node),
                    possible_role="context",
                    derivation_ids=(derivation_id,),
                )
            )
            continue
        segments.append(segment)
        evidence.append(item_evidence)
    return IngestionResult(
        segments=tuple(segments),
        evidence=tuple(evidence),
        derivations=(derivation,),
        warnings=tuple(warnings),
    )
