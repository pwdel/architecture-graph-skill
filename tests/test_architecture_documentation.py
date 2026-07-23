from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README" / "architecture-v0.4.0.md"
DIAGRAM = ROOT / "architecture.html"
COMPANION = ROOT / "architecture.md"

PROVENANCE_LABELS = (
    "Deterministic",
    "Optional external LLM",
    "Human/control",
)

ALGORITHM_LABELS = (
    "Rule Tokenization",
    "Sparse TF-IDF Term Discovery",
    "Controlled SVO Relation Extraction",
    "Exact-Key Entity Resolution",
    "Relation Qualification",
    "Decision Candidate Extraction",
    "Decision Reduction",
    "Typed Evidence Graph Construction",
    "PageRank",
    "Independent Dimension Scoring",
    "Decision-Local Rationale Resolution",
    "Rationale Overlay Contract Validation",
    "Canonical Content-Addressed Publication",
    "Stable Bounded Projection",
    "Cited Report Composition",
)


def test_v040_readme_is_standalone_and_links_companions() -> None:
    text = README.read_text()
    assert text.startswith("# Architecture Graph v0.4.0 Architecture")
    assert "../architecture.html" in text
    assert "../architecture.md" in text
    for heading in (
        "## Purpose and scope",
        "## Provenance boundary",
        "## Components and responsibilities",
        "## End-to-end indexing pipeline",
        "## Algorithm registry",
        "## Typed graph and independent scoring",
        "## Immutable JSONL base snapshots",
        "## Bounded queries",
        "## Rationale overlays",
        "## Cited report composition",
        "## Authorization and engineering review",
        "## Current exclusions",
    ):
        assert heading in text


def test_v040_readme_names_algorithms_and_provenance() -> None:
    text = README.read_text()
    for value in (*PROVENANCE_LABELS, *ALGORITHM_LABELS):
        assert value in text
    for identifier in (
        "`rule_tokenizer`",
        "`sparse_tfidf`",
        "`terms-en-v1`",
        "`predicates-v1`",
        "`extraction-rules-en-v1`",
        "`entity-rules-v1`",
        "`exact_entity_key`",
        "`decision-rules-v1`",
        "`decision_reducer`",
        "`scoring-v1`",
        "`rationale-rules-v1`",
    ):
        assert identifier in text
    assert "does not call an LLM internally" in text
    assert "damping factor of `0.85`" in text
    assert "24 iterations" in text
    assert "rank_eligible: false" in text


def test_companion_links_to_long_form_reference() -> None:
    text = COMPANION.read_text()
    assert "README/architecture-v0.4.0.md" in text
