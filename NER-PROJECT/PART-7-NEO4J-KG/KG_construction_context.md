# KG Construction Context — Plant Protein Knowledge Graph (Neo4j)

Paste this whole document as the first message in a new chat to continue this work with full context, without needing the original (very long) conversation history.

---

## 1. Project background (brief)

PhD dissertation project (Kansas State University) building a knowledge graph from ~192 plant protein research papers (target: scale to ~12,000 papers), covering plant protein isolates/concentrates, extraction/modification methods, and functional properties (solubility, water/oil holding capacity, foaming, emulsifying properties, gelation, rheology, etc.). Feeds into FoodProt, a multi-institution collaborative platform. Advisors: Dr. Li (domain/food science), Dr. Zhao (broader grant PI, predictive modeling co-supervisor).

**Everything before knowledge graph construction is DONE**: triple extraction, abbreviation resolution, entity name resolution (soy/soybean synonyms, formatting variants, etc.), and entity TYPE resolution (closed 8-category taxonomy). This new chat is scoped **only** to building the actual Neo4j knowledge graph from that finished, resolved data. Do not re-litigate entity/type resolution methodology unless a genuine new problem surfaces in the final data.

---

## 2. Current data state

**Final resolved triples file** (columns below reflect the fully-processed pipeline; confirm exact current filename/path, since several cleanup passes were applied in sequence — likely something like `type_resolved_triples_migrated_v2.xlsx` plus a formatting-variant cleanup pass and manual fixes on top):

Key columns available per triple row:
- `doi` — paper identifier
- `chunk_id`, `section`, `pmid` — provenance
- `resolved_source`, `resolved_target` — final, fully entity-resolved node names (use these, NOT the raw `source`/`target` columns, which are the untouched original extraction)
- `source_type`, `target_type` — closed-taxonomy type label for each entity (see taxonomy below)
- `interaction` — relationship type (e.g. `increased`, `decreased`, `no_significant_change`, `induced`, `exhibited`, `outperformed`, etc. — NOT a closed list, this is open vocabulary from extraction)
- `compared_property` — what property is being compared (if applicable)
- `reported_value` — the measured numeric outcome, if the sentence gives one
- `claim_status` — `observed` or `hypothesis`
- `corresponding_sentence` — verbatim source sentence, for traceability

**Closed entity-type taxonomy (8 categories, finalized and confirmed correct)**:
```
functional_property, physicochemical_property, structural_property,
modification_method, extraction_method, material_used_directly,
rheological_property, sensory_property
```
No `other` category should remain in the final file. (Two legacy categories, `gelling_property` and `water_oil_interaction`, existed briefly from an earlier open taxonomy and were manually migrated into `rheological_property` and `physicochemical_property` respectively — confirm this is fully resolved in whatever file you start from.)

**Known residual data-quality issue, still being manually cleaned as of last session**: a family of "foam" entities (`foam activity/capacity/ability`, `foaming activity/capacity/ability`, `foam capacity index`, and a likely typo `form activity`) were being manually consolidated into `foaming capacity`. Confirm this cleanup is complete before loading, or note it as a known limitation.

---

## 3. Database decision: Neo4j

**Decided**: Neo4j, not a pure-Python approach (e.g. the precedent set by PlantConnectome, a comparable literature-mined plant biology KG, which used networkx + pickle + Flask + Cytoscape.js instead).

**Why, specific to this project** (not generic Neo4j marketing):
- Uniqueness **constraints** structurally prevent the exact duplicate-node bugs (e.g. "water holding capacity" vs "water-holding capacity") that were repeatedly found and manually fixed during entity resolution. This is the single strongest project-specific argument.
- Relationships in this data carry real evidence payload (`doi`, `reported_value`, `claim_status`, etc.) — Neo4j's property graph model attaches properties to relationships natively; RDF/triple-store alternatives would require awkward reification for this.
- `LOAD CSV ... MERGE` supports incremental loading as the corpus grows toward 12,000 papers, without reprocessing everything each time.
- Cypher allows ad-hoc querying without writing new backend code per question (unlike PlantConnectome's custom Flask endpoints).

**Explicitly NOT yet decided / not blocking**: where this gets hosted long-term (local Neo4j Desktop vs AuraDB vs self-hosted Community Edition on university infrastructure). This is a separate, later decision — do not let it block graph construction. Build and use the graph locally first (Neo4j Desktop is free, runs on a laptop, no hosting required for development, dissertation figures, or advisor demos).

**Context on hosting economics** (for later, not now): Neo4j AuraDB Free tier (200,000 node/relationship cap — comfortably covers this project even at full 12,000-paper scale) pauses after 30 days inactivity, not suitable for a real public site long-term. AuraDB paid tiers are $65+/GB/month recurring. Self-hosted Community Edition is free (GPL-3.0) but still requires someone to maintain a running server indefinitely — same long-term sustainability risk as PlantConnectome's Google Cloud setup, which is why prior comparable projects' public sites are now broken/dead links. Long-term hosting commitment is a question for advisors (Dr. Li / Dr. Zhao / FoodProt), not a technical decision to solve alone.

---

## 4. What to build next: the actual task for this new chat

### Step A — Schema finalization
- Node labels: derive from the 8 closed `source_type`/`target_type` categories (e.g. `:FunctionalProperty`, `:ModificationMethod`, `:MaterialUsedDirectly`, etc. — confirm naming convention, PascalCase is Neo4j idiom).
- Relationship types: derive from `interaction` column values, uppercased with underscores per Neo4j convention (e.g. `INCREASED`, `DECREASED`, `NO_SIGNIFICANT_CHANGE`). Decide whether to keep the full open vocabulary or consolidate rare/synonymous interaction types.
- Relationship properties: `doi`, `reported_value`, `compared_property`, `claim_status`, `corresponding_sentence` (or a subset — decide what's useful to query vs. what's just provenance bloat).
- Node properties beyond the name itself: consider whether nodes need any properties, or whether the entity name is sufficient as the primary key.

### Step B — CSV export script
Build a Python script that transforms the final resolved triples file into Neo4j-ready CSVs:
- One CSV per node type (or one combined nodes CSV with a `label` column), deduplicated by entity name.
- One relationships CSV: `source_name, target_name, interaction_type, doi, reported_value, compared_property, claim_status, corresponding_sentence`.
- This is the next concrete deliverable — ask for it explicitly if not already provided.

### Step C — Constraints and indexes (Cypher, run first, before loading)
```cypher
CREATE CONSTRAINT FOR (n:FunctionalProperty) REQUIRE n.name IS UNIQUE;
-- repeat per label
```

### Step D — Load via LOAD CSV + MERGE
```cypher
LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
MERGE (s {name: row.source_name})
MERGE (t {name: row.target_name})
MERGE (s)-[r:RELATIONSHIP_TYPE {doi: row.doi}]->(t)
SET r.reported_value = row.reported_value
```
(Actual query needs refinement based on final schema decisions in Step A — this is illustrative, not final.)

### Step E — Verification queries
Sanity-check node counts, relationship counts, and a few known entities (e.g. confirm "solubility" has the expected number of connections) against the frequency analysis numbers already established in the prior pipeline work.

### Step F — Demo preparation
Prepare 2-3 concrete Cypher queries answering genuinely useful food-science questions (e.g. "top treatments that increase solubility, ranked by paper support") for an advisor demo — this was the agreed strategy for building a funding case with Dr. Li, more persuasive than a general walkthrough.

---

## 5. What NOT to relitigate in the new chat

- Entity name resolution methodology (embedding thresholds, LLM validation prompts, partition logic) — finished, don't rebuild.
- Entity type resolution methodology (closed taxonomy, domain guidance rules) — finished, don't rebuild.
- Abbreviation/code resolution pipeline — finished, don't rebuild.
- RDF vs Neo4j — already decided in favor of Neo4j, don't reopen unless new information changes the calculus.
- Hosting platform choice — explicitly deferred, not needed for graph construction.

If a genuine NEW data-quality issue surfaces while building the KG (e.g. an unexpected duplicate node, a malformed CSV row), treat it as a fresh, narrow bug to fix — verify against real data before concluding anything, same practice as before, but don't assume it requires reopening the whole resolution pipeline.
