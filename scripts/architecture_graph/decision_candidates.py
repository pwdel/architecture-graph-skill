from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from architecture_graph.analysis_types import DecisionCandidate, RecordCatalog, build_analysis_derivation
from architecture_graph.nlp import ParsedCorpus
from architecture_graph.canonical import stable_id
from architecture_graph.records import Record, finalize_record
from architecture_graph.schemas import load_versioned_resource


@dataclass(frozen=True)
class DecisionCandidateResult:
    candidates: tuple[DecisionCandidate, ...]
    warnings: tuple[Record, ...]
    derivations: tuple[Record, ...]


def _unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def collect_decision_candidates(parsed: ParsedCorpus, catalog: RecordCatalog) -> DecisionCandidateResult:
    rules = load_versioned_resource("decision-rules-v1.json")
    roles = {str(value).casefold(): str(value).casefold() for value in rules.get("field_roles", [])}
    groups: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))
    provenance: dict[tuple[str, str], str] = {}
    for sentence in parsed.sentences:
        pointer = sentence.unit.metadata.get("json_pointer")
        if not isinstance(pointer, str) or "/" not in pointer:
            continue
        tokens = pointer.removeprefix("/").split("/")
        field = _unescape(tokens[-1]).casefold()
        role = roles.get(field)
        if role is None:
            continue
        parent = "/" + "/".join(tokens[:-1])
        key = (sentence.unit.source_version_id, parent)
        value = sentence.unit.metadata.get("scalar_value")
        if value is None:
            continue
        groups[key][role].append((str(value), sentence.evidence_id))
        provenance[key] = f"{sentence.format_kind}_structured_parent"
    candidates: list[DecisionCandidate] = []
    derivations: list[Record] = []
    warnings: list[Record] = []
    for (source_id, parent), fields in sorted(groups.items()):
        if "decision" not in fields:
            continue
        field_roles = {role: values[0][0] for role, values in sorted(fields.items())}
        field_evidence = {role: tuple(sorted({item[1] for item in values})) for role, values in sorted(fields.items())}
        evidence_ids = tuple(sorted({item for values in field_evidence.values() for item in values}))
        candidate_id = stable_id("decision-candidate", source_id, parent, field_roles)
        derivation = build_analysis_derivation("structured_decision_candidate", evidence_ids, "decision_candidate", candidate_id)
        derivations.append(derivation)
        status = field_roles.get("status", "unknown").casefold()
        candidates.append(DecisionCandidate(candidate_id, "structured_parent", field_roles, field_evidence, tuple(token for token in parent.split("/") if token), status, provenance[(source_id, parent)], evidence_ids, (str(derivation["id"]),)))
    for claim in catalog.iter("claim"):
        scope = tuple(str(value) for value in (claim.get("qualifiers") or {}).get("scope", []))
        if not any(value.casefold() in {"decision", "decisions", "architecture decision"} for value in scope):
            continue
        statement = f"{claim['subject']['surface']} {claim['predicate']} {claim['object']['surface']}"
        evidence_ids = tuple(str(value) for value in claim.get("evidence_ids", []))
        candidate_id = stable_id("decision-candidate", claim["id"], statement)
        derivation = build_analysis_derivation("claim_decision_candidate", (str(claim["id"]),), "decision_candidate", candidate_id)
        derivations.append(derivation)
        evidence = catalog.get(evidence_ids[0])
        source = catalog.get(str(evidence["source_version_id"]))
        status = str((source.get("adr_metadata") or {}).get("status", "unknown")).casefold()
        candidates.append(DecisionCandidate(candidate_id, "decision_heading", {"decision": statement, "title": statement}, {"decision": evidence_ids}, scope, status, str(claim.get("parser_provenance", "qualified_claim")), evidence_ids, (str(derivation["id"]),), (str(claim["id"]),)))
    return DecisionCandidateResult(tuple(candidates), tuple(warnings), tuple(sorted(derivations, key=lambda item: str(item["id"]))))
