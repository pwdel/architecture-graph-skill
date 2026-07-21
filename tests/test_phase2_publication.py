from architecture_graph.indexer import index_corpus
from architecture_graph.project import ProjectPaths
from architecture_graph.snapshot import SnapshotReader
from conftest import ignore_architecture_graph


def test_index_publishes_semantic_records(phase1_repository) -> None:
    ignore_architecture_graph(phase1_repository)
    result = index_corpus([phase1_repository])
    reader = SnapshotReader.open(ProjectPaths.for_corpus(result.selection))
    assert tuple(reader.iter("terms"))
    assert tuple(reader.iter("edges"))
    assert tuple(reader.iter("rankings"))
