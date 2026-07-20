from pathlib import Path

import pytest

from architecture_graph.ingest import IngestionContext
from architecture_graph.ingest.diagrams import segment_diagram
from architecture_graph.ingest.markdown import segment_markdown
from architecture_graph.sources import SourceInput


FIXTURES = Path(__file__).parent / "fixtures" / "phase1_repo"
CONTEXT = IngestionContext(
    "sha256:" + ("a" * 64),
    "sha256:" + ("b" * 64),
    "0.1.0",
)


def source(relative_path: str, source_kind: str, text: str | None = None) -> SourceInput:
    path = FIXTURES / relative_path
    content = path.read_text(encoding="utf-8") if text is None else text
    return SourceInput(
        relative_path=relative_path,
        absolute_path=path,
        source_kind=source_kind,
        document_role="architecture",
        authority_class="maintained_architecture",
        authority_basis="default",
        tracked=True,
        git_blob="fixture-blob",
        content_hash=f"sha256:{relative_path}",
        text=content,
        decode_error=None,
    )


def test_standalone_plantuml_emits_only_directional_statements() -> None:
    result = segment_diagram(
        source("architecture/deployment.puml", "plantuml"), CONTEXT, "plantuml"
    )
    assert [item["text"] for item in result.segments] == [
        "Checkout -> Orders : writes orders",
        "Orders --> Warehouse : publishes OrderPlaced",
    ]
    assert all(
        item["metadata"]["diagram_language"] == "plantuml"
        for item in result.segments
    )
    assert len(result.derivations) == 1


def test_fenced_plantuml_inherits_markdown_section() -> None:
    markdown = source(
        "docs/architecture/embedded.md",
        "markdown",
        "# Runtime\n\n## Decision\n\n```plantuml\nAPI -> Queue : publishes Job\n```\n",
    )
    result = segment_markdown(markdown, CONTEXT)
    statement = next(
        item for item in result.segments if item["segment_kind"] == "diagram_statement"
    )
    assert statement["heading_path"] == ["Runtime", "Decision"]
    assert statement["metadata"] == {
        "diagram_language": "plantuml",
        "content_role": "diagram",
        "section_role": "decision",
    }


PLANTUML_WITH_IGNORED_ARROWS = """\
@startuml
/' same-line comment -> Fake '/
/'
multiline comment -> Fake
'/
!define FAKE A -> B
  !include fake -> target
Checkout -> Orders : writes orders /' trailing comment -> Fake '/
@enduml
"""


@pytest.mark.parametrize(
    "relative_path", ["architecture/comments.puml", "architecture/comments.plantuml"]
)
def test_standalone_plantuml_ignores_comments_and_directives(
    relative_path: str,
) -> None:
    result = segment_diagram(
        source(relative_path, "plantuml", PLANTUML_WITH_IGNORED_ARROWS), CONTEXT
    )

    assert [item["text"] for item in result.segments] == [
        "Checkout -> Orders : writes orders"
    ]
    assert [item["text"] for item in result.evidence] == [
        "Checkout -> Orders : writes orders"
    ]


@pytest.mark.parametrize("language", ["plantuml", "puml"])
def test_fenced_plantuml_ignores_comments_and_directives(language: str) -> None:
    result = segment_markdown(
        source(
            "docs/architecture/comments.md",
            "markdown",
            f"# Runtime\n\n```{language}\n{PLANTUML_WITH_IGNORED_ARROWS}```\n",
        ),
        CONTEXT,
    )

    statements = [
        item
        for item in result.segments
        if item["segment_kind"] == "diagram_statement"
    ]
    assert [item["text"] for item in statements] == [
        "Checkout -> Orders : writes orders"
    ]
    statement_evidence = next(
        item for item in result.evidence if item["segment_id"] == statements[0]["id"]
    )
    assert statement_evidence["text"] == "Checkout -> Orders : writes orders"
