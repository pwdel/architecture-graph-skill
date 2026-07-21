from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict, deque

from architecture_graph.analysis_types import RecordCatalog
from architecture_graph.canonical import stable_id
from architecture_graph.records import Record, finalize_record


@dataclass(frozen=True)
class GraphResult:
    nodes: tuple[Record, ...]
    edges: tuple[Record, ...]
    catalog: RecordCatalog


@dataclass(frozen=True)
class NeighborResult:
    nodes: tuple[Record, ...]
    edges: tuple[Record, ...]


def _edge(edge_type: str, from_id: str, to_id: str, evidence_ids=(), derivation_ids=(), hashes=()) -> Record:
    evidence_ids = sorted(set(str(x) for x in evidence_ids))
    derivation_ids = sorted(set(str(x) for x in derivation_ids))
    hashes = sorted(set(str(x) for x in hashes))
    return finalize_record({"id": stable_id("edge", edge_type, from_id, to_id, evidence_ids, hashes), "kind": "edge", "edge_type": edge_type, "from_id": from_id, "to_id": to_id, "evidence_ids": evidence_ids, "derivation_ids": derivation_ids, "source_content_hashes": hashes})


def build_evidence_graph(catalog: RecordCatalog) -> GraphResult:
    node_kinds = {"source", "segment", "evidence", "term", "entity", "claim", "decision", "warning", "derivation"}
    nodes = tuple(record for record in catalog.all() if record.get("kind") in node_kinds)
    edges: list[Record] = []
    for segment in catalog.iter("segment"):
        edges.append(_edge("CONTAINS", str(segment["source_version_id"]), str(segment["id"]), segment.get("evidence_ids", []), segment.get("derivation_ids", [])))
    for evidence in catalog.iter("evidence"):
        edges.append(_edge("CONTAINS", str(evidence["segment_id"]), str(evidence["id"]), (evidence["id"],), evidence.get("derivation_ids", []), (evidence["source_content_hash"],)))
    for kind in ("term", "entity"):
        for record in catalog.iter(kind):
            for evidence_id in record.get("evidence_ids", []):
                evidence = catalog.get(str(evidence_id))
                edges.append(_edge("MENTIONS", str(evidence_id), str(record["id"]), (evidence_id,), record.get("derivation_ids", []), (evidence["source_content_hash"],)))
    for claim in catalog.iter("claim"):
        evidence_ids = claim.get("evidence_ids", [])
        hashes = [catalog.get(str(e))["source_content_hash"] for e in evidence_ids]
        for evidence_id in evidence_ids:
            edges.append(_edge("ASSERTS", str(evidence_id), str(claim["id"]), (evidence_id,), claim.get("derivation_ids", []), hashes))
        subject = claim.get("subject", {})
        obj = claim.get("object", {})
        if isinstance(subject, dict) and subject.get("entity_id"):
            edges.append(_edge("SUBJECT_OF", str(subject["entity_id"]), str(claim["id"]), evidence_ids, claim.get("derivation_ids", []), hashes))
        if isinstance(obj, dict) and obj.get("entity_id"):
            edges.append(_edge("OBJECT_OF", str(obj["entity_id"]), str(claim["id"]), evidence_ids, claim.get("derivation_ids", []), hashes))
    unique = {str(edge["id"]): edge for edge in edges}
    return GraphResult(tuple(sorted(nodes, key=lambda x: str(x["id"]))), tuple(sorted(unique.values(), key=lambda x: str(x["id"]))), catalog)


def bounded_neighbors(graph: GraphResult, node_id: str, depth: int, limit: int) -> NeighborResult:
    if depth < 0 or depth > 5: raise ValueError("graph depth must be between zero and five")
    if limit < 1: raise ValueError("limit must be positive")
    if graph.catalog.maybe_get(node_id) is None: raise KeyError(node_id)
    adjacency: dict[str, list[tuple[str, Record]]] = defaultdict(list)
    for edge in graph.edges:
        adjacency[str(edge["from_id"])].append((str(edge["to_id"]), edge))
        adjacency[str(edge["to_id"])].append((str(edge["from_id"]), edge))
    seen = {node_id}
    queue = deque([(node_id, 0)])
    nodes: list[Record] = []
    selected_edges: dict[str, Record] = {}
    while queue and len(nodes) < limit:
        current, current_depth = queue.popleft()
        record = dict(graph.catalog.get(current))
        record["depth"] = current_depth
        nodes.append(record)
        if current_depth == depth: continue
        for neighbor, edge in sorted(adjacency[current], key=lambda item: (str(item[1]["edge_type"]), item[0])):
            selected_edges[str(edge["id"])] = edge
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, current_depth + 1))
    emitted = {str(node["id"]) for node in nodes}
    edges = tuple(edge for edge in selected_edges.values() if edge["from_id"] in emitted and edge["to_id"] in emitted)
    return NeighborResult(tuple(nodes), tuple(sorted(edges, key=lambda x: str(x["id"]))))
