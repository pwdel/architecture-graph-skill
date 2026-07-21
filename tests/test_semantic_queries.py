from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.semantic_queries import decisions_query, evidence_query, explain_query, neighbors_query, terms_query
from architecture_graph.snapshot import SnapshotReader
from architecture_graph.paging import page_records
from architecture_graph.views import summarize_record
from conftest import ignore_architecture_graph


def _reader(repo):
    ignore_architecture_graph(repo)
    result = index_corpus([repo])
    return SnapshotReader.open(ProjectPaths.for_corpus(result.selection))


def test_semantic_queries_return_bounded_source_backed_records(phase1_repository) -> None:
    reader = _reader(phase1_repository)
    terms = terms_query(reader, limit=5, max_chars=12_000)
    decisions = decisions_query(reader, score="criticality", limit=5, max_chars=12_000)
    assert terms.items and decisions.items
    decision_id = decisions.items[0]["id"]
    evidence = evidence_query(reader, record_id=decision_id, limit=5, max_chars=12_000)
    explanation = explain_query(reader, record_id=decision_id, limit=20, max_chars=12_000)
    assert evidence.items[0]["path"]
    assert explanation.items[0]["record"]["id"] == decision_id


def test_neighbors_obey_depth_and_include_evidence(phase1_repository) -> None:
    reader = _reader(phase1_repository)
    term = terms_query(reader, limit=1, max_chars=12_000).items[0]
    result = neighbors_query(reader, node_id=term["id"], depth=2, limit=20, max_chars=12_000)
    assert result.items
    assert max(item["depth"] for item in result.items) <= 2


def test_character_fitting_cursor_does_not_skip_removed_items() -> None:
    records = [
        {"id": f"term:{index}", "kind": "term", "text": "x" * 180}
        for index in range(3)
    ]
    binding = {"snapshot_id": "snapshot:one", "command": "terms"}
    first = page_records(records, binding=binding, fields=None, limit=3, max_chars=650)
    assert first.cursor is not None
    second = page_records(records, binding=binding, fields=None, limit=3, max_chars=650, cursor=first.cursor)
    assert first.items[-1]["id"] == "term:0"
    assert second.items[0]["id"] == "term:1"


def test_term_summary_bounds_large_evidence_collections() -> None:
    record = {
        "id": "term:adapter", "kind": "term", "canonical_form": "adapter",
        "tfidf": 3.5, "document_frequency": 12, "occurrence_count": 31,
        "evidence_ids": [f"evidence:{index:04d}" for index in range(2_000)],
        "derivation_ids": ["derivation:term"],
    }
    summary = summarize_record(record)
    assert summary["evidence_count"] == 2_000
    assert summary["top_evidence_ids"] == ["evidence:0000", "evidence:0001"]
    assert "evidence_ids" not in summary
