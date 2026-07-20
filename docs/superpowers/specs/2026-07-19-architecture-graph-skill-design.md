# Architecture Graph Skill Design

Status: approved design

Date: 2026-07-19
Reference sibling: codebase-graph-skill v0.2.0

## Goal

Build a deterministic-first Codex and Claude skill that converts a versioned architecture corpus into:

1. a source-backed dictionary of architectural terms;
2. an immutable ledger of qualified design claims;
3. a typed graph of decisions, concerns, consequences, and evidence;
4. an explainable ranking of the decisions engineers need to understand;
5. a human-readable brief that engineers can review with the architect.

The skill serves as a defense against over-specified software. It should expose prescriptions that lack a documented driver, scope, consequence, or current decision status. It should not decide that a specific implementation is wrong merely because it is specific.

## Context

Architecture knowledge arrives as ADRs, diagrams, standards, proposals, interface descriptions, deployment notes, and narrative text. These sources vary in authority, age, scope, and precision. They also contradict or supersede each other.

A term-frequency list cannot identify which constraints will shape future engineering work. A raw graph cannot do so either. Repeated boilerplate creates high-degree hubs, while an important cross-cutting constraint may appear in only one accepted ADR.

The system therefore ranks provenance-bearing decisions rather than nouns. Term discovery and graph structure contribute evidence to the rank. They do not stand in for architectural importance.

## V1 Boundaries

V1 ingests text-native artifacts selected from a Git working tree. Tracked files are included by default; configuration may include specific untracked files:

- Markdown ADRs and architecture notes;
- Mermaid diagrams and Mermaid blocks embedded in Markdown;
- PlantUML files and blocks;
- YAML and JSON architecture metadata;
- plain text files selected by configuration.

The first language adapter targets English architecture prose. Language-specific tokenization, parsing, stop terms, and modality tables are versioned adapters rather than hidden fallbacks.

V1 does not ingest PDF, DOCX, draw.io binaries, screenshots, or other image diagrams. Later adapters may add those formats without changing the claim ledger or graph schema.

V1 does not:

- replace an architect or approve a design;
- promise that a rank predicts the future;
- treat centrality, TF-IDF, or extraction confidence as truth;
- allow an LLM to create an uncited report claim;
- merge ambiguous entities without traceable evidence;
- implement a user-facing mini-language.

The first control surface is a typed configuration file plus a bounded CLI. A later DSL may compile to the same configuration only after repeated workflows justify another language.

## Design Principles

### Evidence before interpretation

Every term, claim, decision, edge, rank explanation, and report sentence points to source evidence. The system preserves the original wording and source location.

### Deterministic baseline

The default index command runs without an LLM or network access. It produces a useful term dictionary, claim ledger, graph, ranking, and report.

### Visible derivation

Every generated record identifies whether a deterministic script, an LLM, or a human produced it. The record also identifies the method, tool or model version, configuration digest, inputs, and confidence.

### Independent dimensions

The system stores these dimensions separately:

- what the source claims;
- how the system derived the claim;
- how confident the extraction is;
- whether a human verified it;
- how critical the decision appears;
- how urgently an architect should review it.

### Immutable history

Finalized snapshots never change. A new extraction, LLM enrichment, or source update creates a new content-addressed snapshot.

### Bounded retrieval

Agent commands return a small, relevant context pack instead of printing the corpus. Every list, graph traversal, and evidence command enforces result and character limits.

### Specificity requires rationale

A concrete technology or implementation choice becomes a possible over-specification when the corpus provides no traceable path from driver or concern to decision and consequence. Specificity alone does not trigger the warning.

### Generated and human-owned files remain separate

Snapshot generation owns machine artifacts. Human review records live outside generated snapshot directories and snapshot publication never overwrites them.

## Approaches Considered

### Claim ledger with generated graph projections

Selected.

The system stores immutable claims and derivations, then builds filtered graph and report projections. Deterministic, LLM-derived, and human-authored records can coexist without overwriting one another. This supports audit, conflict tracking, historical comparison, and derivation-specific views.

### One mutable graph with provenance tags

This has fewer record types, but mutation obscures which extraction or interpretation changed. Historical comparisons become reconstruction work, and later enrichment can overwrite the deterministic baseline.

### Separate deterministic and LLM graphs

This provides strong isolation, but duplicates entity identity and complicates reconciliation. A shared claim ledger gives the same isolation through derivation filters while preserving one identity model.

### SQLite storage

The sibling codebase graph uses SQLite because source traversal and caller or callee queries benefit from indexed relational access. This skill values inspectable snapshots, Git-style diffs, and bounded reports more than low-latency arbitrary graph queries. SQLite would also hide record-level changes behind a binary artifact.

### One nested JSON snapshot

A single JSON document is portable, but large arrays require broad parsing and encourage agents to print too much. Record-oriented JSON Lines supports streaming, targeted selection, stable diffs, and append-only staging.

## Terminology

| Term | Definition |
|---|---|
| Term | A discovered noun phrase, acronym, identifier, quality attribute, technology name, or other corpus expression. |
| Entity | A normalized architectural concept such as a service, database, team, platform, capability, interface, or concern. |
| Claim | A source-backed assertion represented as a qualified subject, predicate, and object tuple. |
| Decision | A group of claims that records a choice or constraint together with its drivers, options, rationale, consequences, and status. |
| Modality | The force of a claim: must, should, may, planned, indicative, or unknown. |
| Polarity | Whether a claim affirms or negates the relationship. Must not is encoded as modality must plus negative polarity. |
| Condition | The event or state under which the claim applies. |
| Scope | The system, component, environment, tenant, stakeholder, time window, or other boundary to which the claim applies. |
| Decision status | The architecture lifecycle state: proposed, accepted, rejected, deprecated, superseded, or absent when the source states no status. |
| Review status | The human assessment of the extracted record: unreviewed, verified, disputed, or rejected. |
| Provenance | The exact source file, section, line or diagram coordinates, Git blob or content hash, linked Git observation, and evidence text. |
| Derivation | The producer, method, tool or model version, inputs, configuration, time, and confidence that created a record. |
| Assertion kind | Whether the system extracted a statement from evidence or inferred a new relationship from other claims. |

Modality borrows the familiar requirement levels must, should, and may, while preserving the source wording. RFC 2119 also warns authors to use imperative language only when it supports a concrete interoperability or harm-avoidance requirement. That warning supports the over-specification review lens.

## Architecture

~~~text
Selected architecture sources from a Git working tree
  → source manifest and structural segmentation
  → deterministic term discovery
  → deterministic qualified-claim extraction
  → immutable claim ledger
  → entity, predicate, and decision normalization
  → typed decision graph
  → explainable decision ranking
  → bounded engineer review brief
  → optional LLM enrichment
  → optional human review
~~~

The LLM stage follows the deterministic report. It can propose aliases, qualifiers, decision clusters, conflict explanations, or clearer summaries. It writes new records and references the deterministic inputs it used. It cannot edit or delete earlier records.

### 1. Source manifest

The indexer locates eligible files and records:

- path relative to the repository root;
- source kind and configured authority class;
- Git-object hash of the exact selected working-tree bytes for tracked files, never a stale index-entry blob;
- content hash for every selected file, including dirty and untracked inputs;
- ADR metadata such as identifier, title, date, and status;
- parser and extractor versions;
- deterministic pipeline digest;
- configuration digest.

The source manifest provides the input to the snapshot digest. Relative paths keep snapshots portable across checkouts. A project-level observation ledger links each index run and snapshot to the current branch, commit, dirty-worktree fingerprint, and observation time without placing volatile Git-run metadata inside the content-addressed snapshot.

### 2. Structural segmentation

The indexer segments sources by architecture-bearing structure rather than fixed character windows:

- ADR sections;
- Markdown headings and bounded paragraphs;
- list items that share a heading and modality;
- Mermaid or PlantUML statements;
- YAML or JSON objects;
- bounded token chunks that retain their heading path.

Each segment receives a stable identifier and exact source span.

### 3. Term discovery

The deterministic term stage creates the architectural dictionary through:

- noun phrase and named-entity candidates;
- identifiers, acronyms, and capitalization patterns;
- glossary and heading terms;
- normalized n-grams;
- section-, document-, repository-, and corpus-level TF-IDF;
- configured stop terms and generic-hub detection;
- conservative alias candidates.

TF-IDF measures lexical distinctiveness within the selected corpus. It supports candidate discovery and contributes a small ranking feature. It does not determine importance.

Each dictionary entry stores surface forms, normalized form, term type, frequency at each corpus level, TF-IDF values, alias evidence, and source spans.

### 4. Deterministic qualified-claim extraction

The claim extractor starts with deterministic rules and pinned classical NLP models. It recognizes:

- active subject, predicate, and object patterns;
- passive constructions;
- copular claims;
- modal and imperative language;
- negation;
- conditional clauses;
- coordinated subjects and objects;
- architecture predicate phrases;
- explicit ADR status, rationale, option, and consequence sections;
- typed Mermaid and PlantUML relationships.

SVO provides the core tuple. Architecture prose often encodes the actor through passive voice, nominalization, or context, so the extractor targets typed semantic relationships rather than accepting a grammatical subject as the final semantic actor.

A pinned statistical parser counts as deterministic for this design because the same source, parser version, model version, and configuration reproduce its output. Its derivation method still states dependency_parse or statistical_nlp instead of rule.

### 5. Qualification

The qualifier stage adds:

- modality;
- polarity;
- conditions;
- scope;
- effective time when stated;
- claim role and decision linkage;
- source authority;
- extraction confidence.

Decision status belongs to the decision record. The reducer applies it only to the selected decision or constraint claims. It does not turn rejected options, context, or consequences from an accepted ADR into active assertions.

The stage leaves missing qualifiers empty and records a warning or review reason when the omission can change meaning. It does not invent a default scope or rationale.

### Claim invariants

A canonical claim follows these rules:

- subject, canonical predicate, object, evidence, and derivation are required;
- subject and object use a ClaimArgument union with kind entity_ref, literal, unresolved_span, or implicit_context;
- every argument records origin as explicit, dependency_resolved, coreference_resolved, heading_context, or unresolved;
- an imperative such as Use PostgreSQL uses an implicit_context subject tied to the nearest explicit component or system scope;
- a value such as 30 days uses a literal argument with datatype and unit;
- extraction that cannot form an object remains an extraction candidate and warning rather than a canonical claim;
- the predicate stores a positive canonical relation and the source verb phrase without modal or negation tokens;
- modality stores must, should, may, planned, indicative, or unknown;
- polarity stores positive or negative, so must not has one canonical representation;
- claim_role stores decision, constraint, option, rationale, consequence, context, or observation;
- applicability stores active, considered, rejected, contextual, or unknown;
- extracted claims require at least one evidence ID;
- inferred claims require at least one input claim ID and inherit their transitive evidence;
- conditions, scope sets, evidence IDs, derivation IDs, and decision IDs use canonical sorted order.

Effective time distinguishes an unspecified interval from an explicit open interval. Its basis field is explicit, source_default, or unknown.

### 6. Normalization and resolution

The normalizer maps surface predicates to a controlled architecture vocabulary while retaining the original phrase. Initial predicates include:

- depends_on;
- calls;
- reads_from;
- writes_to;
- publishes_to;
- subscribes_to;
- owned_by;
- deployed_on;
- constrains;
- requires;
- prohibits;
- replaces;
- supersedes;
- addresses;
- causes;
- trades_off_with;
- justified_by.

Entity resolution uses exact identifiers, declared aliases, acronym evidence, structural context, and conservative similarity. Unresolved aliases remain separate candidates. An LLM may propose a merge, but the proposal stays visible and cannot collapse deterministic entities until a versioned merge cascade exists. V1 human review may discuss or reject that proposal; it cannot materialize it by acceptance.

### 7. Decision construction

The deterministic V1 reducer groups claims with explicit source structure and exact canonical keys. It does not use embedding similarity or an LLM.

The reducer applies these rules in order:

1. An ADR identifier plus a Decision heading creates an explicit decision anchor.
2. An ADR with no Decision heading creates one anchor from the ADR identifier and document root.
3. A non-ADR heading creates a decision anchor only when its segment contains a prescriptive claim with must, must not, should, requires, prohibits, or an explicit decision phrase.
4. The first prescriptive claim under the anchor becomes the primary claim. The reducer attaches other claims under the same heading according to section role.
5. Context, Driver, and Rationale sections attach driver or justification claims.
6. Options or Alternatives sections attach option claims.
7. Consequences, Tradeoffs, Risks, and Outcomes sections attach consequence claims.
8. Status and supersession metadata attach to the decision record. Selected decision and constraint claims become active, options become considered or rejected, and rationale, context, and consequence claims become contextual.
9. Cross-source records merge into one decision only when they share a unique exact explicit-identifier/local-anchor key, or when their canonical primary claim keys and normalized scopes match exactly with at most one candidate anchor per logical source. Ambiguous many-to-many clusters do not merge. A valid cluster keeps the lexicographically smallest full candidate identity and records the others as aliases. One ADR with two distinct local Decision headings therefore remains two decisions despite the shared ADR identifier.
10. Other similar decisions remain separate and receive SUPPORTS, CONTRADICTS, or ALIAS_CANDIDATE edges when deterministic rules can establish those relationships.

A decision can connect:

- drivers and concerns;
- considered options;
- chosen constraints;
- rationale;
- positive and negative consequences;
- supersession links;
- affected components and stakeholders.

An ADR can yield one decision or several scoped decisions. The reducer does not assume one file equals one decision. Descriptive topology claims remain graph claims and do not become decisions unless a source anchor or prescriptive claim establishes a choice or constraint.

A decision record requires its stable ID, source anchor, primary claim IDs, all member claim IDs, decision status and status evidence, source-version IDs, derivation IDs, and predecessor identity when one exists.

### 8. Claim ledger

The ledger stores claims and their derivation records before graph projection. It is the audit source for every later artifact.

Example claim:

~~~json
{
  "id": "claim:7f1d...",
  "subject": {
    "kind": "entity_ref",
    "entity_id": "service:checkout",
    "surface": "Checkout Service",
    "origin": "explicit"
  },
  "predicate": {
    "canonical": "publishes_to",
    "surface": "publish"
  },
  "object": {
    "kind": "entity_ref",
    "entity_id": "event:order-placed",
    "surface": "OrderPlaced events",
    "origin": "explicit"
  },
  "qualifiers": {
    "modality": "must",
    "polarity": "positive",
    "conditions": [],
    "scope": {
      "environments": ["production"]
    },
    "effective_time": {
      "valid_from": null,
      "valid_to": null,
      "basis": "unknown"
    }
  },
  "claim_role": "constraint",
  "applicability": "active",
  "claim_anchor": {
    "logical_source_id": "logical-source:adr-0012",
    "normalized_heading_path": ["decision"],
    "canonical_tuple_ordinal": 0
  },
  "source_lineage": ["logical-source:adr-0012"],
  "source_version_ids": ["source:4c2a..."],
  "segment_id": "segment:1a9b...",
  "decision_ids": ["decision:adr-0012:publishing"],
  "assertion_kind": "extracted",
  "extraction_confidence": 0.91,
  "evidence_ids": ["evidence:31aa..."],
  "derivation_ids": ["derivation:2e15..."]
}
~~~

Example derivation, with illustrative version values rather than prescribed dependencies:

~~~json
{
  "id": "derivation:2e15...",
  "producer_kind": "deterministic",
  "method": "dependency_parse",
  "tool": "spacy",
  "tool_version": "3.8.7",
  "model": "configured-english-pipeline",
  "model_version": "3.8.0",
  "model_artifact_digest": "sha256:42b0...",
  "configuration_digest": "sha256:918f...",
  "input_ids": ["segment:adr-0012:persistence"],
  "output_kind": "claim",
  "output_identity_key": "checkout|publishes_to|order-placed|production",
  "created_at": null
}
~~~

Canonical deterministic records do not contain wall-clock run time. current.json stores publication time outside the snapshot digest. LLM and human derivations store creation time because the time forms part of those events.

The implementation records the installed package version and model artifact SHA-256 observed at index time. A lockfile entry alone does not satisfy the derivation record.

Producer kind and assertion kind remain independent:

~~~yaml
producer_kind: deterministic | llm | human
method: rule | tfidf | dependency_parse | openie | graph_rule | llm_extract | llm_summarize | human_review
assertion_kind: extracted | inferred
review_status: unreviewed | verified | disputed | rejected
~~~

This permits a deterministic inference, an LLM extraction, or a human-authored correction without conflating them.

review_status is computed by a frozen review projection; it is not an authored field on an immutable base claim.

### Proposals and field-level origin

LLM and human enrichers write immutable proposal records. They do not copy and relabel an entire deterministic claim.

A proposal contains:

~~~text
proposal_id
target_kind
target_id
target_content_digest
proposal_kind
field_path
proposed_value
evidence_ids
derivation_id
~~~

proposal_kind is create_record, replace_field, add_alias, merge_entities, split_entity, link_decision, or rewrite_report_text. target_id and target_content_digest may be null only for create_record. field_path uses a JSON Pointer when the proposal changes one field and is null for whole-record, merge, and split proposals. A proposal identity hashes its derivation ID, target identity and content digest, proposal kind, field path, and canonical proposed-value digest.

V1 validates and preserves all seven proposal shapes for diagnosis, but automated accepted-successor materialization supports only `replace_field`. The other kinds may be rejected or discussed in review; `accept_proposal` for one of them fails validation until a versioned cascade rule exists. This prevents an unknown merge, split, record creation, decision link, alias, or report rewrite from acquiring semantics by accident.

Automated correction is narrower still. `correctable_fields_v1` permits only claim subject/object entity, context, or literal values; canonical predicate; modality, polarity, conditions, scope, and effective time; claim role and applicability; and entity type, canonical key, or declared scope. Exact JSON Pointers are versioned in the schema. IDs, kinds, digests, evidence, derivations, origins, ranks, source anchors, and all decision/ranking/term/warning/review/proposal fields are not directly correctable in V1. A corrected claim or entity is fully revalidated, records the field origin, and, when an identity input changes, receives a new ID and cascades through claims, decisions, and edges with explicit lineage.

An accepted V1 `replace_field` proposal creates a successor record in a new snapshot. A change to a content-only field keeps the stable identity key and records predecessor_content_digest. A change to an identity field creates a new stable ID and a predecessor-to-successor entry in lineage.jsonl. If a later version implements entity merge/split acceptance, it must create new entity identities and cascade affected claim identities when canonical subject, predicate, object, or scope changes.

For claims, subject, predicate, object, normalized scope, logical source lineage, and a stable local claim anchor are identity fields. The claim anchor contains the logical source ID, normalized heading path, and the source-order occurrence among claims with the same canonical subject-predicate-object-scope key under that heading. It lets simultaneous positive/negative or conditional assertions coexist without making surface wording or parser origin part of identity. Modality, polarity, conditions, effective time, role, applicability, confidence, evidence, derivation, and field origins are content fields. Effective review status is a separate projection and is never an identity input. Each other record schema declares the same boundary: the identity inputs listed below are identity fields and every other field is content unless its schema says otherwise.

The successor carries field_origins that map each JSON Pointer to origin references of the form `{kind: derivation | review, id: ...}`. Copied deterministic fields therefore remain labeled deterministic, while an accepted LLM qualifier records both the LLM proposal derivation and the human acceptance review.

Each snapshot is a self-contained materialization with at most one record version per stable ID. A same-ID successor replaces its predecessor only in the new snapshot; the parent snapshot retains the prior version. Historical queries traverse snapshot parents and lineage instead of placing two versions with one ID in a JSONL file.

Unaccepted proposals appear only in the enriched provenance layer with the review lifecycle lens. They cannot participate in the current graph or criticality score.

### Stable identity and content digests

Every record has a stable identity key and a separate content digest. Diffs match identity keys and classify a changed content digest as a modification.

- An evidence identity hashes the relative source path, source content hash, source span, and segment ID. YAML aliases may attach one exact source span to several semantic paths, so each segment keeps a distinct evidence link without changing the quoted bytes.
- A term identity hashes its normalized form and term kind.
- An entity identity hashes its entity type, canonical key, and declared scope.
- A claim identity hashes canonical subject, predicate, object, scope, logical source lineage, and the stable local claim anchor. Argument surface text and extraction origin are excluded. Its content digest also covers qualifiers, evidence, confidence, and derivation.
- An explicit decision identity uses the ADR or source decision identifier plus its local decision anchor.
- A non-ADR decision identity hashes the persistent logical source ID, heading anchor, and primary prescriptive claim key. Relative path remains provenance/content, not identity, so a verified rename can preserve the decision lineage.
- Exact cross-source explicit-ID/local-anchor matches already share one identity. A merged non-ADR cross-source decision keeps the lexicographically smallest candidate identity and records the other distinct identities as aliases.
- A derivation identity hashes producer kind, method, actual tool or model artifact identity, configuration digest, input IDs, output kind, and output identity key.
- A review identity hashes reviewer ID, exact target kind/ID/content digest, field path, verdict, canonical replacement-value digest, sorted evidence IDs, authority-policy digest, superseded review ID, and canonical UTC event time. Exact duplicate events deduplicate; distinct times or explicit supersession remain separate ledger events.

One versioned `decision_identity_payload` implements the two conditional decision branches above. Stable-ID construction, review successor classification, lineage, and diff all call it; none hashes the whole source-anchor object or its relative path.

The snapshot digest hashes the canonical manifest core, the digests of every finalized JSONL file, and report.md. It excludes current.json, wall-clock publication metadata, and the manifest field that stores the completed digest. This avoids circular identifiers and preserves reproducible deterministic snapshots.

## Graph Model

The graph reifies claims and decisions as nodes. It does not collapse all evidence into direct entity-to-entity edges.

Core node kinds:

- entity;
- term;
- claim;
- decision;
- concern or driver;
- consequence;
- evidence span;
- source version;
- derivation;
- proposal;
- review.

Snapshot identity remains manifest/query provenance, not a graph node. V1 constructs graph nodes only from durable JSONL record families and never invents a synthetic snapshot node.

Core edge kinds:

- CLAIM_SUBJECT;
- CLAIM_PREDICATE;
- CLAIM_OBJECT;
- BELONGS_TO_DECISION;
- EVIDENCED_BY;
- DERIVED_FROM;
- SUPPORTS;
- CONTRADICTS;
- SUPERSEDES;
- ADDRESSES;
- JUSTIFIED_BY;
- GOVERNS;
- HAS_CONSEQUENCE;
- TRADES_OFF_WITH;
- CONSTRAINS;
- AFFECTS;
- ALIAS_CANDIDATE.

Graph projections have two independent selectors.

The lifecycle lens is:

- current: accepted decisions, active selected claims, and maintained observations;
- review: current material plus status-absent, proposed, deprecated, disputed, conflicting, incomplete, and stale material;
- historical: all lifecycle records captured by a requested immutable snapshot, including rejected and superseded records as records rather than current assertions. V1 does not expose an arbitrary effective-time `as_of` selector; time-point projection is deferred until its ranking and cursor semantics can be specified end to end.

The provenance layer is:

- deterministic: deterministic records only;
- enriched: deterministic records plus labeled, unaccepted proposal nodes;
- reviewed: deterministic records plus accepted successor records and the frozen human review projection.

Every command declares both selectors. An unaccepted LLM proposal can appear as a proposal node in the enriched review lens, but it cannot become a semantic assertion or enter current critical commitments.

### Semantic ranking projection

The evidence graph above remains the source of truth. The ranker creates a deterministic semantic projection for graph metrics from a lifecycle lens and provenance layer:

1. The deterministic layer starts with deterministic claims. The reviewed layer may substitute human-accepted successor records. The enriched layer adds proposals only as non-semantic review nodes.
2. A rejected or disputed claim never emits a semantic assertion edge. The review lens retains its reified claim, conflict, and review edges for diagnosis.
3. The current candidate set contains only accepted decisions whose effective review status is verified or unreviewed. It emits active decision and constraint claims. Maintained observation claims also emit edges when extraction confidence is at least 0.50 or a human verified the claim.
4. The review candidate set contains current candidates plus decisions whose source status is absent, proposed, or deprecated, and decisions whose effective review status is disputed. Non-rejected, non-disputed active claims may emit status-weighted edges; disputed and rejected claims remain diagnostic nodes only.
5. The historical candidate set contains every decision record in the selected immutable snapshot. Non-rejected, non-disputed assertion claims may emit edges while preserving their effective-time interval as metadata. Rejected options, rationale, and consequences remain contextual nodes rather than assertions.
6. For a positive claim with entity_ref subject and object, the projector emits a directed semantic edge from subject to object using the canonical predicate. A native positive `prohibits` relationship uses `prohibited_predicate: prohibits`. A negative must/should claim whose predicate is not already `prohibits` emits `PROHIBITS` and retains the original canonical predicate as `prohibited_predicate`; other negative claims remain reified without emitting the negated positive relationship.
7. For a claim with a literal, unresolved, or implicit argument, it retains the reified claim but excludes that relationship from centrality.
8. It connects each decision to the primary subject through GOVERNS, to concerns or drivers through ADDRESSES or JUSTIFIED_BY, to consequences through HAS_CONSEQUENCE, and to other affected entities through AFFECTS.
9. It aggregates semantic edges only when from, type, to, normalized scope, effective-time interval, and any edge-type discriminator such as `prohibited_predicate` match. The aggregate retains every claim, evidence, and derivation ID.

Canonical predicate direction follows subject to object. The implementation does not add inverse edges. Each semantic edge stores scope, effective time, status factor, extraction confidence, independent source count, and provenance IDs.

An independent source is a distinct source-content hash, not a path or source-version ID. Byte-identical copies can add mentions and evidence locations but never increase IDF document count, corroboration, evidence breadth, transition strength, decision-status authority, persistence, churn, or ranking features.

When byte-identical paths share one explicit logical-source ID, relation candidates with the same normalized heading, canonical tuple, content hash, and source-relative evidence span are one claim occurrence. The claim builder collapses them before assigning tuple ordinals, preserves one claim identity, and unions their evidence, source-version, derivation, surface, and field-origin provenance. Path or candidate IDs never choose the ordinal.

Authority is aggregated once per content-hash group. The group's effective authority is the least authoritative occurrence under the versioned authority order, and every status reducer and scoring feature uses that value rather than a path-level maximum. Independent byte groups may still contribute their own authority. This conservative rule ensures that copying narrative bytes into an accepted-ADR path cannot increase status precedence or any score; adding a lower-authority duplicate may lower confidence in the attribution, but never manufacture importance.

The effective review status comes from the frozen review projection. Rejected records leave current and review semantic edges, disputed records enter the review lens as diagnostics only, verified records receive review assurance, and unreviewed deterministic records retain their extraction status.

## Decision Ranking

The ranker scores decisions and claim clusters. It does not rank the noun dictionary and declare the top nouns to be the top decisions. Each ranking record names its lifecycle lens, provenance layer, and semantic-projection digest; normalization and ordering occur within that projection. Current commitments use the current lens. The review report uses review-lens scores, and historical scores are never substituted into current output.

All feature values are normalized to the interval zero through one. The snapshot stores the scoring configuration and each decision stores its feature explanation.

### Criticality

The initial versioned score is:

~~~text
criticality =
  decision_status_factor × (
    0.25 × authority_and_commitment
  + 0.20 × impact_and_irreversibility
  + 0.15 × cross_cutting_scope
  + 0.15 × structural_leverage
  + 0.10 × independent_evidence_breadth
  + 0.10 × persistence_across_snapshots
  + 0.05 × lexical_salience
  )
~~~

The status factor lowers the score of unsettled or retired decisions and is zero for rejected and superseded decisions. Projection filters remain separate: current critical commitments contain accepted decisions only, while proposed, status-absent, and deprecated decisions remain ranked in review or historical sections.

The initial status factors are:

| Decision status | Ranking factor |
|---|---:|
| Accepted | 1.00 |
| Absent in a maintained current source | 0.65 |
| Proposed | 0.35 |
| Deprecated | 0.10 |
| Rejected or superseded | 0.00 |

Items without explicit status remain visible in review output. The system does not silently relabel them as accepted.

Authority and commitment use:

~~~text
authority_and_commitment =
    0.60 × maximum_supporting_independent_content_group_authority
  + 0.40 × primary_claim_modality_weight
~~~

The initial source-authority defaults are:

| Source class | Weight |
|---|---:|
| Accepted ADR or active architecture standard | 1.00 |
| Approved policy or constraint | 0.90 |
| Current architecture description or maintained diagram | 0.75 |
| Proposal or draft ADR | 0.45 |
| Undated narrative note | 0.35 |

Producer policy is applied after source authority. An unverified LLM-only proposal receives no current-view authority even when it cites an authoritative source.

The initial modality weights are:

| Modality | Weight |
|---|---:|
| must | 1.00 |
| should | 0.75 |
| indicative | 0.50 |
| planned | 0.40 |
| may | 0.35 |
| unknown | 0.25 |

Impact and irreversibility use deterministic category flags:

~~~text
impact_and_irreversibility = min(1,
    0.20 × system_structure
  + 0.15 × quality_attribute
  + 0.15 × public_interface_or_boundary
  + 0.15 × data_ownership_or_persistence
  + 0.15 × trust_or_security_boundary
  + 0.10 × shared_dependency
  + 0.10 × migration_or_lock_in
)
~~~

Each category is one when the decision has an evidence-backed edge to an entity, concern, consequence, or controlled term tagged with that category. Otherwise it is zero. The configuration versions the controlled term and predicate mappings. These categories follow the original ADR motivation described by Michael Nygard.

Cross-cutting scope counts distinct canonical identifiers:

~~~text
cross_cutting_scope =
    0.50 × min(1, affected_components / 5)
  + 0.20 × min(1, affected_concerns / 3)
  + 0.15 × min(1, affected_environments / 3)
  + 0.15 × min(1, affected_stakeholders / 3)
~~~

Repeated mentions and duplicate source text count once.

Structural leverage uses:

~~~text
structural_leverage =
    0.60 × typed_personalized_pagerank
  + 0.25 × capped_bridge_score
  + 0.15 × confidence_weighted_degree
~~~

Structural metrics operate on the decision, concern, and entity projection. Evidence, derivation, term, containment, and alias edges do not participate.

The initial edge base weights are:

| Edge class | Weight |
|---|---:|
| CONSTRAINS, REQUIRES, PROHIBITS, SUPERSEDES | 1.00 |
| GOVERNS | 1.00 |
| DEPENDS_ON, CAUSES, TRADES_OFF_WITH, ADDRESSES, JUSTIFIED_BY, REPLACES | 0.90 |
| CALLS, READS_FROM, WRITES_TO, PUBLISHES_TO, SUBSCRIBES_TO | 0.80 |
| HAS_CONSEQUENCE | 0.80 |
| OWNED_BY, DEPLOYED_ON, AFFECTS | 0.50 |

Each transition weight is the base weight multiplied by the evidence-weighted mean extraction confidence of its supporting claims, the decision-status factor, and min(1, independent source count / 3). Synthetic decision edges use the claims that established that exact decision relationship. A maintained observation claim that is not attached to a decision uses 0.65 as its status factor. The algorithm normalizes outgoing transitions for PageRank.

Review traversal edges do not participate in PageRank, degree, or betweenness. Their context-traversal weights are 1.00 for CONTRADICTS and SUPERSEDES, 0.70 for SUPPORTS, and 0.25 for proposal links. Reified containment, evidence, derivation, alias-candidate, and claim-argument edges have no semantic transition weight.

The PageRank personalization set contains concerns and constraints attached to accepted decisions, plus interfaces, data boundaries, and shared infrastructure present in the current projection, with equal seed mass. If no seed exists, the algorithm uses a uniform vector. V1 uses fixed tolerance and iteration settings from the scoring configuration.

For graphs with at most 5,000 ranking nodes, the bridge score uses exact normalized betweenness centrality. Above that limit, it uses a deterministic approximation whose source and target sample contains the first 256 hash-sorted stable node IDs. Raw confidence-weighted degree for node v is the sum, over each distinct adjacent canonical node u, of the maximum transition weight on any semantic edge connecting v and u; direction is ignored for this degree feature. The raw value is then normalized as described below.

PageRank and degree are min-max normalized within the lifecycle-lens and provenance-layer projection; a constant metric maps to zero. Betweenness uses its normalized value. All metrics are clamped to zero through one before combination. Final decision ordering uses descending score and stable decision ID as the tie-breaker.

Independent evidence breadth uses:

~~~text
independent_evidence_breadth =
  min(1, log(1 + distinct_independent_sources) / log(6))
~~~

Sources with the same content hash count once.

Persistence starts at 0.50 in the first deterministic source revision and adds 0.10 for each prior consecutive source-revision group in which decision_semantic_digest_v1 remained active and unchanged along the recorded decision lineage, capped at 1.00. Adjacent deterministic snapshots with the same `source_revision_digest_v1` form one group; the newest snapshot is its analysis representative, but a rebuild inside the group inherits the previous representative's history features and creates no transition. Re-indexing unchanged source inputs creates an observation, while parser/configuration-only rebuilds create no architectural revision. Age alone does not imply importance. A semantic change across two distinct source-revision groups contributes to churn instead.

decision_semantic_digest_v1 hashes decision status, status resolution, the distinct candidate status values, supersession targets, and the sorted set of unique role-tagged semantic payloads from member claims: canonical argument type, key, and scope rather than record ID; canonical predicate; modality; polarity; normalized conditions and scope; effective time; claim role; and applicability. It excludes candidate-status evidence/source IDs, record and content IDs, duplicate corroborating claims, surface wording, source paths, evidence, confidence, derivations, field origins, human review state, graph metrics, ranks, and report text. Added corroborating evidence or a parser-confidence change therefore does not reset persistence; a changed commitment, boundary, qualifier, rationale, consequence, option, applicability, lifecycle status, or status ambiguity does.

Lexical salience is the mean across primary claims of 0.40 times normalized subject TF-IDF, 0.20 times predicate TF-IDF, and 0.40 times object TF-IDF. Its five-percent criticality weight prevents unusual vocabulary from dominating accepted cross-cutting decisions.

Missing feature evidence contributes zero unless a table above defines an explicit absent-state value. V1 uses sorted inputs, exact graph algorithms, fixed solver settings, and scores rounded to eight decimal places before serialization.

### Review priority

Review priority remains separate from criticality:

~~~text
review_priority =
    0.25 × conflict
  + 0.20 × churn
  + 0.20 × missing_rationale
  + 0.15 × stale_or_ambiguous_status
  + 0.10 × scope_ambiguity
  + 0.10 × derivation_risk
~~~

Contradiction increases review priority. It does not convert a disputed claim into accepted truth.

V1 calculates the review features as follows:

- conflict is 1.00 when claims share canonical subject and predicate, have overlapping scope and effective time, and contain incompatible polarity, object, or active status; otherwise it is zero;
- churn is min(1, semantic decision changes across the last three distinct source-revision-group transitions / 3);
- missing_rationale is 1.00 when both driver and consequence paths are missing, 0.50 when one is missing, and zero when both exist;
- stale_or_ambiguous_status is 1.00 for conflicting active statuses, 0.75 for absent status, 0.50 for proposed, 0.25 for deprecated, and zero for accepted;
- scope_ambiguity is 1.00 when the source contains a scope marker that extraction could not resolve, 0.50 when a prescriptive claim has no scope and its subject occurs in multiple known scopes, and zero otherwise;
- derivation_risk is 1.00 for an unverified LLM-only record, 0.50 for an unsupported inference, 0.35 for a single-source statistical extraction, 0.15 for a single-source rule extraction, and zero after human verification.

### Confidence

Confidence also remains separate:

~~~text
confidence =
    0.40 × extraction_confidence
  + 0.25 × provenance_completeness
  + 0.20 × independent_corroboration
  + 0.15 × review_assurance
~~~

The report may surface a low-confidence decision with high potential impact in the review section. It labels the uncertainty instead of hiding the item.

V1 calculates the confidence features as follows:

- extraction_confidence is the evidence-weighted mean confidence of the decision's primary and constraint claims;
- provenance_completeness is the fraction present among relative path, source content hash, source span, evidence excerpt, source kind, and derivation ID;
- independent_corroboration is min(1, distinct independent sources / 3);
- review_assurance is 1.00 for verified, 0.25 for unreviewed, and zero for disputed or rejected.

### Over-specification review

The over-specification evaluator returns flagged, not_flagged, or unknown.

It evaluates only prescriptive decisions containing modality must or should, or predicates requires or prohibits. It searches links inside the same decision and requires compatible normalized scope, applicability, and decision status.

The evaluator first assigns satisfied, missing, or unknown to driver, consequence, scope, and status:

- driver is satisfied by an evidence-backed ADDRESSES or JUSTIFIED_BY path connecting a driver, concern, or rationale to the prescription;
- consequence is satisfied by an evidence-backed HAS_CONSEQUENCE or TRADES_OFF_WITH path documenting a consequence, tradeoff, or avoided harm;
- scope is satisfied by a compatible explicit scope, or when the canonical subject has only one known scope in the corpus;
- status is satisfied by an accepted, non-conflicting decision status.

For each dimension, absence is missing when the source adapter completed every relevant region under that decision anchor without finding the required link or value. It is unknown only when a persisted, overlapping coverage warning names that dimension: parse_failed or unsupported_construct with possible_role driver, rationale, consequence, or status; unresolved_scope_marker for scope; or unresolved_status_marker for status. A warning elsewhere in the file does not affect the decision. Each source adapter emits covered regions and role-specific warnings, so there is no numeric coverage threshold.

The four values combine as a three-valued OR: the overall result is flagged when any dimension is missing; otherwise it is unknown when at least one dimension is unknown; otherwise it is not_flagged. Unknown items enter the architect-question queue and remain labeled unassessed.

Missing both driver and consequence produces high review severity. One missing element, scope ambiguity, or status ambiguity produces medium severity. Vendor or version specificity, churn, and weak independent support order items within a severity band. They cannot trigger the flag alone.

The system asks a concrete architect question, for example:

- Which quality attribute or constraint requires this database engine?
- Does this rule apply to every environment or only production?
- Which accepted decision supersedes the earlier interface choice?
- What failure or interoperability risk justifies the must-level language?

## Engineer Report

The Markdown report contains four ranked sections:

1. Current critical commitments.
2. Cross-cutting consequences and risks.
3. Contested, stale, or changing decisions.
4. Possible over-specification and questions for the architect.

Each item follows this shape:

~~~text
Decision: <human-readable statement>
Status and scope: <accepted/proposed/etc. and boundaries>
Why it ranks: <top score features>
Consequence: <documented tradeoff or effect>
Evidence: <bounded source links and excerpts>
Derivation: <deterministic, LLM-derived, and human-reviewed labels>
Confidence: <score and missing evidence>
Architect question: <one focused question when review is needed>
~~~

Every source-facing architectural assertion in generated prose maps to one or more claim and evidence identifiers. Assertions about a score, conflict, omission, or derivation map to the responsible input records and derivation instead of pretending to be source text.

## JSONL Snapshot Storage

The skill uses JSON and JSON Lines flat files. It does not require a database.

Default durable memory layout:

~~~text
~/.codex/memories/architecture-graph/projects/<project-id>/
  PROJECT.json
  current.json
  observations.jsonl
  snapshots/
    <content-digest>/
      manifest.json
      sources.jsonl
      segments.jsonl
      terms.jsonl
      entities.jsonl
      claims.jsonl
      decisions.jsonl
      edges.jsonl
      rankings.jsonl
      derivations.jsonl
      evidence.jsonl
      proposals.jsonl
      reviews.jsonl
      lineage.jsonl
      warnings.jsonl
      report.md
  reviews/
    reviews.jsonl
~~~

The project identifier hashes the normalized remote URL and repository root so same-named repositories do not collide. Every stable repository capture includes both the normalized remote and derived project identifier. Project storage is selected from that captured identity, not from a second remote read, and the final repository guard rederives both values; a remote change therefore fails the run instead of forking one repository into disconnected project histories. Each Git observation also reads branch and commit both before and after its stable dirty-state capture and rejects a changed HEAD, so those fields always describe one coherent repository window.

The resolved project directory must remain beneath the resolved memory root and outside the resolved source repository, whether the memory root came from an argument, environment, or default. Existing project, staging, snapshots, reviews, and cache entries must be actual directories. Existing lock, current-pointer, observation-ledger, and project-metadata entries must be regular files. Symlinks and all other path types fail before project-state access. Phase 1 enforces this with one POSIX project-directory context anchored by directory descriptors: it walks actual directories with `O_DIRECTORY | O_NOFOLLOW`, opens regular files with `O_NOFOLLOW | O_NONBLOCK` followed by an `fstat` type check, and performs temporary creation, replacement, staging install, cleanup, and locking by relative name with `dir_fd`. This is a narrow storage boundary for project-owned files, not a general virtual filesystem, and adds no dependency.

Each manifest identifies:

- snapshot_kind: deterministic, enriched, or reviewed;
- analysis_parent_snapshot_id for a deterministic snapshot created after a material input change;
- parent_snapshot_id for an enriched or reviewed snapshot;
- base_deterministic_snapshot_id for enriched and reviewed snapshots;
- material_input_digest;
- source_revision_digest inherited by layered snapshots;
- deterministic_pipeline_digest inherited by every snapshot, plus enrichment_pipeline_digest or review_pipeline_digest when those stages ran;
- the canonical fingerprint preimage for every non-null pipeline digest;
- review_authority_policy_digest for reviewed snapshots;
- input_digest;
- content_digest;
- frozen review-set digest;
- LLM configuration and prompt digests when enrichment ran.

deterministic_pipeline_digest covers every deterministic implementation artifact that can change canonical output: schema versions, structural segmenters, parser and model artifacts, extraction rules, qualifier rules, normalizers and ontology, decision reducer, canonical serializer, graph projector and algorithms, score configuration, and report templates. enrichment_pipeline_digest covers proposal schemas, bounded-prompt assembly, response validation, and materialization code. review_pipeline_digest covers review schemas, authority reduction, proposal acceptance, successor materialization, and reviewed-report templates. Each canonical fingerprint preimage also records the Python runtime and installed versions of output-affecting dependencies and is persisted in the manifest; publication and reuse verify that its hash equals the corresponding digest. A packaged release hashes its installed package artifact and stage manifest; a development checkout hashes the selected implementation files, so an uncommitted rule or template change cannot reuse an older snapshot.

A reviewed build may rerun deterministic reducers, diagnostics, graph projection, ranking, and report generation. Before doing so, the finalizer computes the current deterministic pipeline fingerprint with the parent's recorded runtime/model configuration and requires it to equal the parent's `deterministic_pipeline_digest`. A mismatch fails closed and asks for a new deterministic base; reviewed output is never labeled with an inherited digest for different code. The review fingerprint also hashes the inherited deterministic digest and every review-specific schema, reducer, materializer, orchestrator, reviewed-report template, runtime, and output-affecting dependency.

For deterministic indexing, material_input_digest hashes selected relative source paths, source content hashes, source-role metadata, deterministic_pipeline_digest, ontology, scoring configuration, and deterministic configuration. A separate `source_revision_digest_v1` identifies architecture-document revisions for history by hashing only the sorted set of unique selected `source.content_hash` values. Paths, multiplicity, source kind/role/authority, parser, model, ontology, scoring, aliases, report code, runtime, and all other configuration are excluded. Adding or moving a byte-identical copy therefore never advances history, including when the copy has different path-derived authority; adding, removing, or changing a unique byte group does. Metadata and pipeline changes may still require a deterministic rebuild through `material_input_digest`, but adjacent rebuilds with the same source-revision key collapse to one history position. Before building, the indexer compares material input with the current base deterministic snapshot:

- when the value is unchanged, it reuses that snapshot and records a new observation;
- when the value changed, it creates a snapshot whose analysis_parent_snapshot_id is the current base deterministic snapshot, or null at genesis.

If current.json selects an enriched or reviewed snapshot derived from the unchanged base, indexing preserves that selected layer and points the new observation to it. A material deterministic change selects the new deterministic snapshot; proposals and reviews against the prior base remain in history and must be re-evaluated against new target content digests.

The deterministic input_digest hashes exactly material_input_digest, source_revision_digest, analysis_parent_snapshot_id, and the canonical Git rename-resolution input used to assign fallback logical-source identities and ambiguous-rename warnings. Rename resolution affects snapshot content but not freshness: once a material build records a completed rename, unchanged material reuses that snapshot instead of rebuilding with a newly empty Git diff. The analysis-parent chain may contain deterministic rebuilds for pipeline/configuration changes; history collapses adjacent entries with the same source-revision digest. If the current build has the same source-revision digest as its parent, matched decisions inherit the parent's persistence and churn exactly rather than resetting or advancing them because extraction changed. An enriched input_digest hashes its base deterministic snapshot, parent snapshot, enrichment pipeline digest, LLM configuration, prompt, provider, and model identity. A reviewed input_digest hashes its parent snapshot, base deterministic snapshot, review pipeline digest, frozen review set, and review-authority configuration.

observations.jsonl stores observation ID, selected snapshot ID, previous current snapshot ID, base deterministic snapshot ID, branch, commit, dirty-worktree fingerprint, material input digest, source revision digest, and observation time. It lives outside immutable snapshots and is excluded from their content digest. An unrelated commit that leaves every selected architecture input unchanged therefore reuses the same deterministic snapshot while gaining a new observation record.

The content digest hashes:

- the canonical manifest core, excluding content_digest and publication metadata;
- every finalized JSONL file, including proposals and frozen reviews;
- report.md.

snapshot_id is the content digest with a snapshot type prefix; the on-disk directory uses the hexadecimal digest. The manifest's payload file-digest table covers the JSONL files and report, not manifest.json itself. The canonical manifest core includes that payload table, input identifiers, schema versions, and snapshot-kind fields before the snapshot digest is calculated.

Records do not embed the containing snapshot ID. The directory and manifest provide that context, which prevents a self-hash cycle. LLM and human records affect the JSONL file hashes and therefore affect the enriched or reviewed content digest.

The persisted report contains only content-derived facts. It excludes its containing snapshot digest, current-pointer state, branch, commit, observation ID, publication time, and other run metadata. Read commands may display that metadata as a separate, non-persisted banner.

Canonical serialization uses:

- UTF-8 with Unicode normalized to NFC;
- sorted object keys;
- compact JSON separators;
- one LF-terminated JSON object per line;
- stable record-ID ordering;
- schema-defined ordering for set-like arrays;
- preserved ordering for semantically ordered arrays;
- rejection of NaN and infinity;
- decimal scores rounded to eight places;
- no wall-clock fields in deterministic canonical records.

JSON Lines supports record-at-a-time processing and Unix-style pipelines.

PROJECT.json, current.json, and manifest.json remain small standard JSON documents. current.json contains exactly schema version, selected snapshot identifier, latest observation identifier, and publication time. Readers require canonical bytes and `type(schema_version) is int` with value 1. The selected state consists of both the complete canonical pointer image and the exact canonical observation row it selects. Readers require exactly one matching row and validate its snapshot and publication time against the pointer. Publication revalidates both tokens under the project lock; changing only the selected row, observation identifier, or publication time for the same snapshot conflicts with a writer that captured the prior state.

Human review files remain outside generated snapshots. A reviewed-snapshot finalization freezes the complete validated review ledger into reviews.jsonl and separately computes which records apply. Deterministic and enriched snapshots contain canonical empty review files. The reviewed manifest records the digest of that frozen review set; report.md remains content-only and does not repeat snapshot identity metadata.

### Initial Python toolset

The implementation keeps the dependency boundary small and records the installed version and relevant model artifact digest for each generated record:

- jsonlines reads and writes record-oriented durable state;
- PyYAML safely parses the supported YAML configuration and source documents;
- spaCy supplies English tokenization, noun chunks, and dependency parses;
- scikit-learn supplies sparse TF-IDF vectors and cosine similarity;
- NetworkX supplies the versioned PageRank, degree, and betweenness implementations;
- jmespath filters only already bounded command results;
- the Python standard library supplies hashing, canonical JSON serialization hooks, paths, temporary staging, and publication locks.

The CLI, not an agent prompt, performs corpus scans, joins, graph traversal, scoring, and truncation. pandas, a database engine, and an unrestricted whole-snapshot query dependency are unnecessary for V1. Model packages must already be installed for deterministic indexing; the default command does not download them.

## Snapshot Writer and Reader

The Python storage toolset exposes:

~~~text
SnapshotReader.iter(record_type)
SnapshotReader.get(record_type, id)
SnapshotReader.select(record_type, filters, fields, limit)
SnapshotWriter.append(record_type, record)
SnapshotWriter.extend(record_type, records)
SnapshotFinalizer.validate()
SnapshotFinalizer.publish()
AtomicJsonlLedger.append(path, record)
~~~

SnapshotReader has no hidden descriptor ownership. Indexing explicitly lends it
the live anchored project-storage context, which the reader never closes; use
after that context closes is a deliberate error. Compatibility calls that omit
the context open a one-shot anchored context for the complete open operation or
JSONL-generator lifetime and close it before returning or exhausting the
generator. `iter`, `get`, and `select` open snapshot payloads relative to the
held project descriptor and never reopen a project-owned path by pathname.

The implementation uses the small jsonlines package for record framing and streaming reads/writes; the canonical serializer supplies validation and deterministic key ordering. The Python standard library handles small manifest files. The ijson package remains an adapter dependency only if a future source format requires streaming a large nested JSON document.

Writers target a temporary staging directory. Finalization:

1. validates each record against its type schema;
2. verifies referenced identifiers;
3. rejects duplicate stable IDs with different content;
4. deduplicates exact repeated records;
5. sorts records by stable ID;
6. acquires the project publication lock;
7. rereads and validates current.json plus its uniquely selected observation row, then compares both complete canonical tokens and their absent/present shape with the expected selected state;
8. for a reviewed snapshot, reads one locked byte image of the complete review ledger, validates it, sorts its records by stable ID, and freezes those exact canonical JSONL bytes plus their digest into staging;
9. renders report.md from frozen, content-derived inputs;
10. calculates the payload file-digest table;
11. assembles the manifest core and calculates the snapshot content digest;
12. writes manifest.json with the completed digest;
13. performs the collision check and atomically renames the staging directory;
14. publishes the observation record through the atomic ledger writer;
15. atomically updates current.json with compare-and-swap semantics, selecting the snapshot and observation.

Phase 1 deterministic indexing tightens that generic sequence at its repository boundary. It validates the initial observation before staging. For changed material it completes and synchronizes staging, performs immutable collision verification, and removes a redundant collision stage before the final repository-token guard. For reuse it computes every result count first and revalidates the complete immutable snapshot under lock before the guard. Both branches parse, validate, and ID-index the complete observation ledger and copy its validated bytes to a synchronized anchored temporary file before the guard. The guard then rechecks source/configuration/Git/project-identity state and returns the final observation. After it, the publisher validates and serializes only that bounded row, appends it to the prepared file, installs a new snapshot when needed, and performs the project-metadata, ledger, and pointer replacements. No corpus or ledger parse/copy occurs after the guard.

Pre-publication containment, count, read, validation, selected-state CAS, ledger-preparation, and final-guard failures leave both the observation ledger and current pointer unchanged. Once durable writes begin, an installed immutable snapshot or a failure after step 14 may leave an unselected snapshot or observation, which is safe because current.json remains authoritative. The `os.replace()` that installs `current.json` is the flat-file commit point. A failure before it preserves the old selection; a directory-sync or lock-release failure after a successful replace has an explicitly indeterminate committed/durability outcome, may already expose the new selection, and must not be blindly retried. `PublicationCommitUncertain` reports that uncertainty in the active command. A later status command can validate the state and report the selected pointer and any orphans it actually observes, but without a durable transaction marker it cannot reconstruct whether an earlier sync completed. The flat files do not pretend to provide a multi-file database transaction.

Finalized snapshots are immutable. Indexing, LLM enrichment, and changed human review sets create new snapshots.

If a content-digest directory already exists, the publisher compares its manifest file-digest table with staging. An identical bundle is reused. Any byte mismatch under the same digest is a fatal integrity error. A project-scoped operating-system file lock prevents concurrent writers from publishing, appending a review or observation, or changing current.json at the same time.

The two append-only ledgers are append-only at the record level, not by unsafe raw file append. AtomicJsonlLedger validates the existing file, writes its canonical records plus the new record to a sibling temporary file, synchronizes the file, atomically replaces the old path, and synchronizes the parent directory while holding the project lock. A crash therefore exposes either the old complete ledger or the new complete ledger, never a partial final JSON line. Snapshot freezing parses exactly one locked byte image, rejects invalid framing or authority values, then stable-ID-sorts the validated records with the shared canonical JSONL writer. `frozen_review_set_digest` hashes those exact canonical snapshot bytes, not the external ledger's append order. The raw-image digest is transient consistency evidence only and is not snapshot identity.

## Human Review Records

reviews/reviews.jsonl is an append-only human-owned ledger. V1 reviews target durable claims, decisions, proposals, entities, terms, derivations, rankings, or decision-diagnostic warnings. A qualifier correction may target an allowlisted claim field. Alias and report feedback targets the underlying entity, decision, ranking, or diagnostic record for verification/dispute/rejection or a diagnostic proposal; V1 does not materialize alias or report-text corrections, and report prose has no separate review identity.

Each review stores:

~~~text
review_id
target_kind
target_id
target_content_digest
field_path
verdict
replacement_value
evidence_ids
reviewer_id
reviewer_authority
authority_policy_digest
supersedes_review_id
created_at
~~~

verdict is verify, dispute, reject, accept_proposal, reject_proposal, or correct. reviewer_authority is resolved from the project authority policy for reviewer_id, copied into the record by the review command, and validated against authority_policy_digest; it is not a free-form assertion by the reviewer. reject requires a whole-record target; correct requires an exact `correctable_fields_v1` claim/entity path and replacement value; and proposal verdicts require a proposal target. A review becomes stale when target_content_digest no longer matches the target record version. The report shows stale reviews but does not apply them.

Review append is a locked transaction, not an unchecked line append. While holding the project lock, it resolves the exact target and every supplied evidence ID against the selected immutable snapshot and requires the latter to be evidence records. It validates the complete existing homogeneous review ledger, then preflights any supersedes link: the ancestor must exist, have the same reviewer, name the same target kind/stable ID and field path, and leave the supersession graph acyclic. Only then does the crash-safe ledger replacement occur. A missing or wrong-kind evidence reference, missing/cross-reviewer/incompatible supersession, cycle, or malformed existing ledger leaves the original bytes unchanged.

For several active reviews, the projection uses the highest validated reviewer authority. Equal-authority incompatible verdicts produce disputed status. A later review from the same reviewer affects the projection only when it explicitly supersedes that reviewer's earlier record. The frozen snapshot contains the complete review ledger, including superseded ancestors, so every supersedes_review_id resolves inside reviews.jsonl.

Review status is a materialized projection field. Base claims and decisions do not mutate when a reviewer acts. Accepted corrections and proposals create successor record versions in a reviewed snapshot with field-level origin and review IDs.

A later reviewed snapshot may use the selected reviewed snapshot as its parent. It preserves previously materialized successors once, freezes the complete append-only ledger, and applies new events only to exact record versions in that parent. Reviews against displaced predecessor digests are stale; follow-up review targets the current successor digest. The chain retains one immutable base deterministic snapshot and never counts review rounds as source revisions.

Finalizing a selected reviewed snapshot again with the same frozen ledger, authority-policy digest, proposal payload, inherited deterministic digest, review-pipeline digest, and already-materialized review set reuses that snapshot. The finalizer first verifies the current deterministic fingerprint against the base, before reading the review ledger or considering reuse, so code drift cannot hide behind a no-op path. A reuse result returns the existing snapshot ID with `observation_id: null`; it does not create a no-op reviewed child, observation, or current-pointer write. Only a changed review input or pipeline can create the next reviewed snapshot.

The frozen projection first reduces non-stale reviews for each target. At the highest reviewer-authority level, a whole-record verify yields verified, a whole-record reject yields rejected, and a whole-record dispute or incompatible verdicts yield disputed. A field-level verify does not verify the whole record; a field-level dispute makes the record disputed until corrected. An accepted correction or proposal is not represented as verified content: it materializes a successor record, and reviews then target that successor digest.

A decision's effective review status is reduced conservatively from its direct status and primary claims:

1. a direct rejected decision is rejected;
2. a direct disputed decision is disputed;
3. when every primary claim is rejected, the decision is rejected;
4. when any primary claim is disputed, or rejected while another remains active, the decision is disputed;
5. a directly verified decision, or one whose primary claims are all verified, is verified when no earlier rule applies;
6. every other decision is unreviewed.

Reviews of rationale, option, context, or consequence claims affect those claims and the review report, but do not by themselves verify or reject the decision.

## Bounded Query Toolset

The public CLI follows the sibling's status-first workflow:

~~~text
architecture-graph memory status .
architecture-graph index .
architecture-graph report .
architecture-graph get claims <id> --root .
architecture-graph find claims --root . --contains checkout --limit 20
architecture-graph decisions . --score criticality --limit 10
architecture-graph neighbors . <entity-id> --depth 2 --limit 30
architecture-graph evidence . <decision-id>
architecture-graph explain . <decision-id>
architecture-graph context . "payment dependencies" --max-chars 12000
architecture-graph diff . <snapshot-a> <snapshot-b>
~~~

Commands stream the relevant JSONL files and build temporary in-memory maps only for the requested operation.

Every read command supports selected fields, a maximum-character budget, and Markdown or JSON output. Multi-record commands add record limits and cursors; graph-traversal commands add a maximum depth; evidence-bearing commands add a maximum excerpt count. Unsupported bounds are not accepted as decorative no-op flags.

Default agent-facing limits are:

| Limit | Default |
|---|---:|
| Records | 20 |
| Graph depth | 2 |
| Evidence excerpts per item | 3 |
| Characters | 12,000 |

All read commands apply their applicable limits after selecting a stable command-specific order:

- get resolves one exact ID. If the selected fields cannot fit, it returns a schema-valid summary with omitted_fields and directs the caller to request narrower fields;
- find sorts scored matches by descending score and stable ID, or unscored filtered matches by stable ID;
- neighbors uses breadth-first depth, then descending edge weight, edge type, source ID, and target ID;
- evidence uses descending source authority, then relative path, source span, and evidence ID;
- explain renders summary, score features, graph reasons, evidence, and architect question in that fixed priority;
- decisions and report use their stored lens rank followed by stable decision ID.

Each command constructs complete result-item envelopes. It first removes optional evidence excerpts and verbose explanations, then removes the lowest-priority complete item until the result fits; it never slices serialized JSON. Multi-item commands return truncated, omitted_count, and a cursor that binds snapshot ID, command, normalized arguments and filters, configuration digest, and last emitted sort tuple. Markdown follows the same item boundary. V1 has no unbounded export command: callers request narrower fields or continue through bound cursors. A full canonical export may be added after V1 as an explicit machine-to-machine interface.

At index time, each decision receives a deterministic search document formed from its normalized title, sorted identifiers and aliases, canonical and surface subject-predicate-object terms from primary and constraint claims, and linked concern or driver labels. Full evidence prose is not placed in that TF-IDF document. The bounded evidence set used for query overlap contains at most three primary-or-constraint evidence spans per decision, sorted by source authority, relative path, span, and evidence ID, with each excerpt clipped to 400 characters at a sentence or source-line boundary.

The context command uses a deterministic selection algorithm:

1. It normalizes query tokens with the snapshot's term normalizer and rejects a query with no remaining identifier or lexical token.
2. It scores decisions eligible for the selected lifecycle lens as 0.55 times TF-IDF cosine similarity, 0.25 times identifier and alias match, 0.10 times the selected lens score, and 0.10 times evidence-term overlap. TF-IDF cosine uses the stored snapshot vocabulary and decision search document. Identifier and alias match is 1.00 for an exact normalized match, 0.70 for a token-boundary prefix match, and zero otherwise. Evidence-term overlap is the fraction of distinct normalized query tokens found in the bounded evidence set. The lens feature is the decision's normalized criticality, review-priority, or confidence score.
3. It sorts by descending seed score and stable ID, then selects at most eight seeds.
4. It traverses only semantic ranking edges allowed by the lens. Current uses decision edges GOVERNS, ADDRESSES, HAS_CONSEQUENCE, and AFFECTS plus semantic predicates constrains, requires, prohibits, depends_on, calls, reads_from, writes_to, publishes_to, and subscribes_to. Review also allows CONTRADICTS, SUPERSEDES, SUPPORTS, and proposal links.
5. Traversal priority is seed score times semantic edge weight times 0.5 to the traversal depth. Each queued path carries path-local visited node and edge sets and cannot revisit either; the reducer retains only the highest-value path per internal node.
6. It deduplicates final decisions to their best path and sorts them by traversal score, lens score, and stable ID.

The output budget counts Unicode scalar values after rendering. It reserves 10 percent for query and truncation metadata, 55 percent for decision summaries and score explanations, 30 percent for evidence, and 5 percent for omission metadata. Evidence clips at sentence or source-line boundaries. If one record exceeds its allocation, the command emits its ID and bounded summary without the full excerpt.

The context cursor additionally binds the normalized-query digest, lifecycle lens, provenance layer, and scoring-configuration digest. It is invalid after any of those values changes.

The context command selects terms and decisions, traverses bounded typed edges, and returns only:

- relevant ranked decisions;
- score explanations;
- derivation labels;
- short evidence excerpts;
- unresolved architect questions.

It never emits a complete snapshot. Full machine-to-machine export is post-V1; current callers page through bounded canonical results.

JMESPath may filter an already bounded JSON result. The CLI does not run an unrestricted in-memory JMESPath query over the entire corpus. jq remains an optional shell tool, including its streaming mode, and is not a runtime requirement.

## Incremental Updates and Diffs

The update process compares source manifests rather than trusting the Git commit alone. It detects:

- added files;
- changed files;
- renames;
- deletions;
- dirty tracked files;
- selected untracked files;
- parser, ontology, or configuration changes.

The cache separates path-independent parsing from provenance-bound extraction:

- a parser cache keyed by source content hash, parser and model artifact digest, and parser configuration may reuse tokens, sentence boundaries, and dependency output;
- every run rebinds relative path, heading structure, source role, authority, ADR metadata, and evidence spans;
- complete extraction records may be reused only when content, relative path, source metadata, and extractor configuration all match;
- a rename may reuse path-independent parser output but must create new source-version and evidence records.

The indexer removes claims whose evidence disappeared.

After local extraction, the indexer reruns every corpus-global stage: TF-IDF, entity resolution, decision merging, contradiction and supersession detection, over-specification evaluation, semantic graph projection, ranking, and report generation. One changed document can affect another decision's IDF, entity identity, conflict state, centrality, or rank.

### Logical lineage

Source-version identity and logical-source identity remain separate:

- source_version_id hashes relative path and content hash;
- logical_source_id uses an explicit ADR or document identifier when present;
- repeated occurrences of one explicit identifier share that logical ID only when their content hashes match; the same identifier on different bytes fails before publication;
- otherwise genesis hashes project identity, prior snapshot/genesis marker, relative path, and content hash, while each immutable source record carries the resulting logical ID;
- the next index resolves the selected layer to its base deterministic analysis parent, reads path-to-logical-ID and exact content-digest state only from that immutable parent, and obtains its Git baseline only from the observation selected by authoritative `current.json`; orphan observations never participate;
- Phase 1 derives current added/changed targets and prior deleted/changed origins authoritatively from the parent/current selected-manifest path and content-digest deltas. Git `A`, `D`, rename, and untracked facts may confirm only paths already present in those actual manifest deltas; they never promote an unchanged continuous path into the candidate graph. This still admits genuine configured-untracked and staged dirty additions when they are absent from the selected parent. A changed same-path target has a continuity edge to its prior path; every eligible cross-path exact-digest match adds an edge based only on persisted parent source-record digests;
- an isolated continuity edge retains the logical ID and an isolated cross-path exact edge moves it. Every target in any non-isolated competing component is ambiguous with its complete sorted set of direct origins; except for an independently authoritative explicit document ID, none of those targets inherits a parent logical ID;
- an added target with no exact edge is unresolved only when deleted origins exist; Phase 1 has no similarity fallback because snapshots do not persist parent raw bytes. Ambiguous and unresolved cases use removal/addition semantics plus warnings, and canonical unique-pair, complete ambiguity, and unresolved maps all enter deterministic `input_digest`.

`PROJECT.json` stores only immutable project identity/root metadata. It is never an append-only path history, so an orphaned failed publication cannot poison later logical-source resolution and a path reused after a rename receives a new logical ID.

Decision-anchor lineage matches in this order:

1. exact explicit decision or ADR identifier;
2. exact logical source ID plus normalized heading anchor;
3. unique exact primary-claim key within the same logical source;
4. unique predecessor candidate with at least 0.80 Jaccard overlap across canonical claim keys.

If the best match is tied, V1 records removal and addition rather than guessing.

lineage.jsonl records predecessor and successor identity keys for source renames, moved anchors, changed decision clusters, and accepted identity-field corrections. A future versioned entity merge/split cascade uses the same ledger. Evidence version IDs may change after an edit while claim and decision lineage remains stable.

Persistence and churn follow byte-deduplicated deterministic source-revision groups only. Consecutive deterministic rebuilds with the same source-revision digest collapse to one position, and adding only another path for already selected bytes creates no position. An enriched or reviewed snapshot points to base_deterministic_snapshot_id and inherits its position in that lineage rather than counting as another source revision.

Snapshot diff reports:

- added, removed, and modified terms;
- added, removed, and modified claims;
- entity merges and splits;
- decision status transitions;
- new and resolved conflicts;
- new and resolved over-specification questions;
- rank movement with feature-level explanations;
- derivation changes;
- source coverage changes.

Git diff helps identify changed inputs. The claim and decision diff remains the primary engineering output.

## LLM Enrichment

The LLM stage is optional and runs only after deterministic indexing.

The enricher receives bounded source excerpts and deterministic records. It can propose:

- unresolved entity aliases;
- missing qualifier interpretations;
- candidate decision clusters;
- contradiction explanations;
- report wording;
- architect questions.

Every LLM proposal references a derivation record that stores:

- provider and model identifier;
- model configuration;
- prompt or prompt-template digest;
- input record and evidence identifiers;
- output schema version;
- proposal confidence or uncertainty when the output schema provides it;
- creation time;
- producer_kind set to llm.

The LLM cannot:

- modify deterministic records;
- remove conflicts;
- invent evidence;
- place an unverified LLM-only claim in current critical commitments;
- send the full corpus by default.

The deterministic report remains available when enrichment fails.

## Error Handling

- A source parser failure creates a persisted warning and does not stop unrelated sources.
- Unsupported constructs appear in the ingestion report with file and section context.
- Invalid JSONL records fail staging validation.
- Broken record references prevent snapshot publication.
- Duplicate IDs with different content fail finalization.
- Ambiguous entities remain separate.
- Conflicting claims remain present with their scope and time.
- A missing source span prevents a claim from appearing in generated prose.
- An LLM timeout or schema error leaves the deterministic snapshot unchanged.
- Query commands truncate at declared limits and state the truncation.
- Fetch, Git, and model-loading errors remain visible; the implementation does not swallow them.

## Testing

### Unit tests

Unit tests cover:

- source manifest hashing;
- Markdown and ADR segmentation;
- Mermaid and PlantUML extraction;
- term discovery and TF-IDF;
- active and passive relation rules;
- ClaimArgument variants, implicit subjects, and typed literals;
- modality, negation, condition, scope, and the canonical must-not representation;
- entity and predicate normalization;
- deterministic decision grouping and decision-status propagation;
- identity-preserving and identity-changing proposal successors, one version per stable ID, and field-level origin;
- review precedence, stale reviews, and decision review aggregation;
- authority-policy validation and atomic ledger replacement;
- lifecycle-lens and provenance-layer eligibility;
- decision semantic digests, persistence, and churn;
- over-specification three-valued coverage rules;
- score components;
- JSONL schemas, canonical serialization, and stable ordering;
- semantic projection inclusion and edge aggregation;
- bounded query seed scoring, traversal, truncation, and cursor validation.

### Golden tests

Repeated deterministic runs over the same fixture corpus must produce identical:

- snapshot digests;
- JSONL records;
- ranks;
- score explanations;
- reports.

The fixture fixes the analysis parent. Observation IDs and times are tested separately because observations are intentionally outside the canonical bundle.

### Adversarial fixtures

Fixtures include:

- repeated boilerplate;
- generic terms such as system, service, and data;
- rare vendor and version identifiers;
- passive and nominalized claims;
- negated and conditional claims;
- one decision with different environment scopes;
- old superseded ADRs;
- contradictory current documents;
- duplicated source text copied under a different path and higher authority;
- diagram-only relationships;
- missing rationale;
- LLM proposals that conflict with deterministic claims.

### Snapshot tests

Tests cover:

- additions, modifications, renames, and deletions;
- dirty working-tree content;
- extractor and scoring configuration changes;
- implementation, schema, report-template, and dependency changes covered by pipeline digests;
- unchanged-input snapshot reuse with a new observation;
- source-revision grouping across pipeline/configuration rebuilds and duplicate paths;
- a changed-then-reverted corpus with explicit analysis-parent lineage;
- interrupted finalization;
- immutable published snapshots;
- concurrent publication, compare-and-swap failure, and atomic current-pointer updates;
- orphan observation detection after an interrupted pointer update;
- crash safety during review and observation ledger replacement;
- stale review exclusion and frozen reviewed snapshots;
- locked rejection of dangling evidence/supersession review appends and no-op reviewed-finalize reuse;
- accepted V1 replace-field proposal successor records;
- reuse of unchanged extraction records;
- corpus-wide TF-IDF, resolution, conflict, graph, rank, and report recomputation after a local edit.

### Evaluation

This labeled evaluation is a post-MVP validation milestone, not a prerequisite for shipping the first useful deterministic release. Phase 3 starts only after the deterministic baseline has been measured and its largest errors are understood.

A historical fixture set receives labels from architects and engineers for:

- claim spans and qualifiers;
- canonical entities;
- active and superseded state;
- contradictions;
- graded criticality;
- must-not-miss decisions;
- possible over-specification.

Evaluation reports:

- tuple and qualifier precision, recall, and F1;
- entity-resolution quality;
- contradiction precision and recall;
- nDCG at 10 for graded ranking;
- Recall at 10 for must-not-miss decisions;
- provenance coverage, with required targets of 100 percent claim-and-evidence coverage for source-facing report assertions and 100 percent input-and-derivation coverage for derived diagnostics;
- rank stability under source duplication and bounded source removal;
- architect acceptance and engineer time-to-answer.

Baselines include TF-IDF alone, raw degree, untyped PageRank, source chronology, and accepted-ADR order. Feature ablations show whether each score component improves the result.

## Implementation Phases

The first implementation plan covers Phases 1 and 2 only. Each phase has a runnable checkpoint; LLM enrichment and additional binary or image adapters remain separate projects.

### Phase 1: deterministic storage and ingestion

- repository and skill scaffold;
- configuration schema;
- source manifest;
- JSONL reader, writer, staging, and finalization;
- bounded status, get, and find commands;
- first vertical slice for Markdown ADRs and embedded Mermaid;
- follow-on text-native adapters for PlantUML, YAML, JSON, and configured plain text;
- a checkpoint that reproduces the same source, segment, evidence, and manifest records from fixed inputs.

### Phase 2: deterministic architecture analysis

- term dictionary and TF-IDF;
- qualified SVO and relation extraction;
- entity and predicate normalization;
- claim ledger;
- immutable proposal and review ledgers, successor materialization, field origins, and projection filters exercised with fixtures rather than a live model;
- decision graph;
- criticality, review-priority, and confidence scores;
- engineer report;
- bounded decisions, neighbors, evidence, explain, and context commands;
- content-addressed snapshots and semantic diffs;
- an early checkpoint that produces an evidence-backed decision report from authority, modality, scope, driver, and consequence features before centrality and semantic diffs;
- a completion checkpoint that adds graph metrics and semantic diffs without an LLM or network call.

Phase 2 completes the useful deterministic product.

### Phase 3: LLM enrichment

- bounded enrichment adapter;
- derivation and payload audit;
- alias, qualifier, clustering, and wording proposals;
- enrichment-specific review projection;
- failure isolation from the deterministic snapshot.

Phase 3 is complete when a live model can create only schema-valid, evidence-linked proposals, every proposal records its derivation, and model failure leaves the deterministic product and current pointer unchanged.

### Phase 4: additional source adapters

- PDF and DOCX structure extraction;
- draw.io support;
- image-diagram OCR or vision extraction;
- cross-repository architecture corpora.

## Acceptance Criteria

The first deterministic release is complete when:

- index performs no LLM or network call by default;
- identical material inputs, analysis parent, and installed tool or model artifacts produce the same snapshot digest;
- repeated observation of unchanged material inputs reuses the snapshot and appends only an observation;
- every output-affecting deterministic stage and installed dependency is covered by deterministic_pipeline_digest;
- every claim carries assertion kind, extraction confidence, and evidence, and resolves to derivations with producer kind, method, configuration, and actual tool or model artifact versions;
- every generated record type either references derivation IDs directly or has a schema-defined provenance path to producer kind, method, inputs, configuration, and evidence;
- every source-facing report assertion cites claims and evidence, while every derived score or diagnostic cites its input records and derivation;
- deterministic and LLM-derived records can be filtered independently;
- every accepted proposal preserves field-level deterministic, LLM, and human origin;
- stale or conflicting reviews have deterministic, testable projection results;
- no command requires a database; durable state is standard JSON and JSONL;
- query commands stay within declared output limits;
- the report ranks decisions rather than isolated nouns;
- the report separates criticality, review priority, and confidence;
- possible over-specification uses flagged, not_flagged, or unknown and checks rationale, consequence, scope, and current status;
- changed sources produce claim-, decision-, conflict-, and rank-level diffs;
- every corpus-global analysis stage reruns after a material local change;
- unaccepted LLM proposals cannot enter the current graph or criticality ranking;
- a failed index or enrichment run cannot replace the current snapshot.

## References

- [Shared design discussion](https://chatgpt.com/share/6a5d3a5f-d6dc-83ea-80e3-427cfc3705f4).
- Michael Nygard, [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).
- ISO, [ISO/IEC/IEEE 42010:2022, Architecture Description](https://www.iso.org/standard/74393.html).
- RFC Editor, [RFC 2119: Key words for use in RFCs to Indicate Requirement Levels](https://www.rfc-editor.org/info/rfc2119).
- scikit-learn, [TfidfVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html).
- Stanford NLP Group, [Open Information Extraction](https://nlp.stanford.edu/software/openie.html).
- Universal Dependencies, [Nominal Subject](https://universaldependencies.org/u/dep/nsubj.html).
- Rada Mihalcea and Paul Tarau, [TextRank: Bringing Order into Text](https://aclanthology.org/W04-3252/).
- NetworkX, [PageRank](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html) and [Centrality](https://networkx.org/documentation/stable/reference/algorithms/centrality.html).
- W3C, [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/).
- [JSON Lines format](https://jsonlines.org/).
- jsonlines, [Python documentation](https://jsonlines.readthedocs.io/en/latest/).
- PyYAML, [project page](https://pypi.org/project/PyYAML/).
- ijson, [Iterative JSON parser](https://pypi.org/project/ijson/).
- JMESPath, [Specification](https://jmespath.org/specification.html).
- jq, [Streaming manual](https://jqlang.org/manual/dev/).
