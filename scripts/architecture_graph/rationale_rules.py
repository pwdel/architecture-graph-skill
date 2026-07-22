from __future__ import annotations

from architecture_graph.schemas import load_versioned_resource, resource_digest


def load_rationale_rules():
    return load_versioned_resource("rationale-rules-v1.json")


def rationale_rule_digest() -> str:
    return resource_digest("rationale-rules-v1.json")
