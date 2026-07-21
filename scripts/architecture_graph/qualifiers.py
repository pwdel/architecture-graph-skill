from architecture_graph.analysis_types import QualifiedRelation, RelationCandidate
from architecture_graph.nlp import ParsedCorpus


def qualify_relations(candidates: tuple[RelationCandidate, ...], parsed: ParsedCorpus) -> tuple[QualifiedRelation, ...]:
    result = []
    for candidate in candidates:
        words = {token.casefold() for token in candidate.sentence.tokens}
        modality = "required" if words & {"must", "shall", "required"} else "proposed" if words & {"may", "might", "proposed"} else "asserted"
        polarity = "negative" if words & {"not", "never", "no"} else "positive"
        status = candidate.sentence.unit.document_status.casefold()
        applicability = "proposed" if status == "proposed" or modality == "proposed" else "historical" if status in {"deprecated", "superseded", "rejected"} else "current"
        result.append(QualifiedRelation(candidate, modality=modality, polarity=polarity, scope=candidate.sentence.unit.heading_path, applicability=applicability))
    return tuple(result)
