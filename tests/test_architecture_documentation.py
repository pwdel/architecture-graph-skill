from pathlib import Path
import re
import subprocess


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
    assert (
        "same project, corpus selection, configuration, pipeline, and analysis history"
        in text
    )


def test_companion_links_to_long_form_reference() -> None:
    text = COMPANION.read_text()
    assert "README/architecture-v0.4.0.md" in text


def test_diagram_exposes_provenance_categories_and_algorithm_registry() -> None:
    text = DIAGRAM.read_text()
    for value in (*PROVENANCE_LABELS, *ALGORITHM_LABELS):
        assert value in text
    assert "v0.4.0 makes no internal LLM calls" in text
    assert 'data-provenance="human optional-external-llm"' in text
    assert text.count('data-provenance="deterministic"') == 8


def test_every_flow_step_declares_provenance_and_method() -> None:
    text = DIAGRAM.read_text()
    flow_source = text.split("const flows = {", 1)[1].split("const SINGLE_MODE", 1)[0]
    step_count = len(re.findall(r'\{\s*from:"', flow_source))
    provenance_count = len(
        re.findall(
            r'provenance:"(?:Deterministic|Optional external LLM|Human/control)"',
            flow_source,
        )
    )
    method_count = len(re.findall(r'method:"[^"]+"', flow_source))
    assert step_count == 25
    assert provenance_count == step_count
    assert method_count == step_count
    assert flow_source.count('provenance:"Human/control"') == 4
    assert flow_source.count('provenance:"Deterministic"') == 21
    assert 'provenance:"Optional external LLM"' not in flow_source


def test_diagram_keeps_existing_topology_and_offline_contract() -> None:
    text = DIAGRAM.read_text()
    assert text.count('<div class="node" data-role=') == 9
    assert len(
        re.findall(r'<button class="flowtab" data-flow="[^"]+" aria-pressed=', text)
    ) == 5
    assert "https://fonts.googleapis.com" not in text
    assert "<script src=" not in text


def test_inline_javascript_parses_and_flow_endpoints_resolve() -> None:
    text = DIAGRAM.read_text()
    script = text.split("<script>", 1)[1].split("</script>", 1)[0]
    result = subprocess.run(
        ["node", "--check", "-"],
        input=script,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    node_ids = set(re.findall(r'data-id="([^"]+)"', text))
    endpoints = re.findall(r'\{\s*from:"([^"]+)",\s*to:"([^"]+)"', script)
    assert len(endpoints) == 25
    assert {value for pair in endpoints for value in pair} <= node_ids

    flow_keys = set(re.findall(r'^  ([a-z_]+): \{\n    name:', script, re.MULTILINE))
    tab_keys = set(
        re.findall(r'class="flowtab" data-flow="([^"]+)" aria-pressed=', text)
    )
    assert flow_keys == tab_keys


def test_panel_bindings_and_external_resource_boundary() -> None:
    text = DIAGRAM.read_text()
    for panel_id in ("panelProvenance", "panelMethod", "stepAnnouncement"):
        assert f'id="{panel_id}"' in text
        assert f'getElementById("{panel_id}")' in text
    assert "panelProvenance.textContent = step.provenance" in text
    assert "panelMethod.textContent = step.method" in text
    assert re.search(
        r'(?:src|href)=["\'](?:https?:)?//|url\(\s*["\']?https?://|fetch\(\s*["\']https?://',
        text,
    ) is None


def test_node_provenance_badges_do_not_change_node_geometry() -> None:
    text = DIAGRAM.read_text()
    rule = re.search(r'\.node \.provenance-badges\{(?P<body>.*?)\n  \}', text, re.DOTALL)
    assert rule is not None
    body = rule.group("body")
    assert "position:absolute" in body
    assert "flex-wrap:nowrap" in body
