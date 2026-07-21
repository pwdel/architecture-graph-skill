from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.snapshot import SnapshotReader
from conftest import ignore_architecture_graph
from architecture_graph.semantic_queries import decisions_query, terms_query


def test_index_publishes_semantic_records(phase1_repository) -> None:
    ignore_architecture_graph(phase1_repository)
    result = index_corpus([phase1_repository])
    reader = SnapshotReader.open(ProjectPaths.for_corpus(result.selection))
    assert tuple(reader.iter("terms"))
    assert tuple(reader.iter("edges"))
    assert tuple(reader.iter("rankings"))
    terms = terms_query(reader)
    assert terms.coverage["eligible_segments"] > 0
    assert terms.coverage["term_records"] > 0


def test_large_structured_plan_returns_terms_and_seven_decisions(architecture_repo) -> None:
    import json
    from conftest import git

    plan = architecture_repo / "architecture" / "large-plan.json"
    plan.parent.mkdir()
    payload = {
        "decision_log": [
            {"title": f"Decision {index}", "status": "accepted", "decision": f"Service {index} must use adapter boundaries.", "rationale": "Keeps contracts explicit."}
            for index in range(7)
        ],
        "architecture_facts": {f"fact_{index}": f"Adapter boundary evidence {index}" for index in range(720)},
    }
    plan.write_text(json.dumps(payload))
    git(architecture_repo, "add", str(plan.relative_to(architecture_repo)))
    git(architecture_repo, "commit", "-m", "add large plan")
    ignore_architecture_graph(architecture_repo)
    result = index_corpus((plan,))
    reader = SnapshotReader.open(ProjectPaths.for_corpus(result.selection))
    assert terms_query(reader, limit=20, max_chars=12_000).items
    decisions = decisions_query(reader, limit=20, max_chars=12_000)
    assert len(decisions.items) == 7
    assert decisions.coverage["eligible_segments"] >= 700
