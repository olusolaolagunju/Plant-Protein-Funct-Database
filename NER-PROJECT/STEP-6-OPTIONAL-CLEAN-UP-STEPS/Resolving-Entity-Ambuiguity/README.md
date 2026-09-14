# Plant Protein KG — Neo4j build package

Built from `final_formatting_cleaned_triples (Copy).xlsx` (10,324 resolved triples,
2,744 unique entities). See `KG_construction_context.md` for full project background.

## What's in here

| File | Purpose |
|---|---|
| `find_entity_type_ambiguities.py` | Standalone script: scans the triples file for entity names with conflicting `source_type`/`target_type` labels. Produces `entity_type_ambiguities.csv` and `entity_type_ambiguities_context.json` (grounding sentences per name/type, for LLM classification). Re-run any time the source file changes. |
| `entity_type_ambiguities.csv` | 145 entity names whose `source_type`/`target_type` disagreed across rows, with the full breakdown, majority type/share, and which 35 are near-ties (<65% majority). |
| `entity_type_ambiguities_context.json` | Same 145 names, with up to 4 example source sentences per candidate type — the evidence an LLM (or a human reviewer) needs to judge each one. |
| `llm_resolve_entity_types.py` | Calls an LLM (OpenAI `gpt-4o`, matching this project's existing extraction pipeline) to pick the best type per ambiguous name, using the taxonomy definitions and context sentences. Requires `OPENAI_API_KEY`. Produces `resolved_entity_types.csv`. |
| `apply_manual_llm_resolution.py` | What actually ran this session, since no API key was available here: the same classification performed directly by Claude against the same context data, with a written rationale per override. Produces the same `resolved_entity_types.csv` schema — swap in the real API-based script any time without changing anything downstream. |
| `resolved_entity_types.csv` | Final type decision per ambiguous name: `llm_chosen_type`, `llm_confidence`, `llm_rationale`, and whether it agreed with the majority vote. 21 of 145 names were overridden — see below. |
| `build_kg_csvs.py` | Builds the Neo4j CSVs. Uses `resolved_entity_types.csv` if present (falls back to pure majority vote otherwise). Re-run if the underlying triples file changes. |
| `neo4j_import/nodes_<Label>.csv` | One file per taxonomy label (8 files, 2,744 nodes total), deduplicated by entity name. |
| `neo4j_import/relationships.csv` | All 10,324 edges with evidence properties (doi, chunk_id, section, pmid, compared_property, reported_value, claim_status, corresponding_sentence). |
| `neo4j_import/01_constraints.cypher` | Run first — uniqueness constraints per label, plus per-type evidence_id indexes. |
| `neo4j_import/02_load_nodes.cypher` | Run second — loads all 8 node files. |
| `neo4j_import/03_load_relationships.cypher` | Run third — loads relationships.csv. **Requires the APOC Core plugin.** |
| `neo4j_import/04_verification.cypher` | Run fourth — sanity checks (counts, no cross-label name collisions, solubility spot-check, conflict list). |
| `neo4j_import/05_demo_queries.cypher` | Three ready-to-run advisor-demo queries (Step F). |

## How to run it (Neo4j Desktop)

1. Create or open a local database in Neo4j Desktop.
2. Install the **APOC Core** plugin for that database (DB card → Plugins tab → APOC → Install). Needed only for the relationship load, since Cypher can't create a relationship whose type comes from a CSV column value without it.
3. Open that database's import folder (DB card → ⋮ → Open folder → Import) and copy in every file from `neo4j_import/` (the 8 `nodes_*.csv`, `relationships.csv`, and the 5 `.cypher` files if you want them alongside for reference).
4. Start the database, open Neo4j Browser, and run the four scripts in order: `01_constraints.cypher`, `02_load_nodes.cypher`, `03_load_relationships.cypher`, `04_verification.cypher`. Each is written as standalone statements — paste the whole file in, or run block by block.
5. Run `05_demo_queries.cypher` for the Dr. Li walkthrough.

## Schema

**Node labels** (PascalCase from the 8 closed taxonomy categories): `FunctionalProperty`,
`PhysicochemicalProperty`, `StructuralProperty`, `ModificationMethod`, `ExtractionMethod`,
`MaterialUsedDirectly`, `RheologicalProperty`, `SensoryProperty`.

**Node properties**: `name` (unique key), `occurrence_count` (how many triple rows
reference this entity), `type_conflict` / `near_tie` / `type_conflict_detail`
(provenance for the 145 names whose original label was ambiguous — see below),
`llm_resolved` / `llm_confidence` / `llm_rationale` (how the final label was
decided for those same 145 names).

**Relationship types** (from the `interaction` column, upper-snake-cased):
`INCREASED`, `DECREASED`, `EXHIBITED`, `OUTPERFORMED`, `NO_SIGNIFICANT_CHANGE`,
`INDUCED`, `EQUIVALENT_TO`, `UNDERPERFORMED`, `OTHER`. Only 9 distinct values
existed in the data already — no consolidation of synonymous interaction types
was needed.

**Relationship properties**: `evidence_id` (synthetic, one per source row — the
MERGE key, so reloading is idempotent), `doi`, `chunk_id`, `section`, `pmid`,
`compared_property`, `reported_value`, `claim_status`, `corresponding_sentence`.
Every triple row becomes its own relationship (not collapsed across papers), so
`count(DISTINCT r.doi)` on a given edge pattern is how you measure "how many
papers support this claim."

## The entity-type-conflict issue (read before the advisor demo)

While building the schema, 145 entity names (≈4,166 row-occurrences, ~6% of the
data) turned out to carry inconsistent `source_type`/`target_type` labels across
different rows — e.g. "vacuum drying" is `modification_method` in 18 rows and
`material_used_directly` in 23; "viscoelasticity" splits exactly 50/50 between
`functional_property` and `rheological_property`. This wasn't caught in the
original type-resolution pass because that pass validated types per-row, not
per-entity-name across the whole corpus.

Since Neo4j node labels come from type and uniqueness constraints are
per-label, leaving this unresolved would have silently produced two nodes
with the same display name under different labels for each of these 145
entities — the exact duplicate-node bug class the constraints exist to
prevent.

**Resolution applied**: initially majority vote (each name's canonical label
decided by whichever type was more common across its occurrences), then
refined with an LLM classification pass grounded in the taxonomy definitions
and real source sentences (`entity_type_ambiguities_context.json`), because
frequency alone isn't evidence for the 35 names where the vote was close to
a coin flip — and because majority vote can't catch cases where several
spelling variants of the same underlying concept were extracted
inconsistently *as a group* (frequency looks fine per-name, but the pattern
across variants reveals the true category). That pass overrode the majority
vote for **21 of the 145 names** — for example:

- `gel strength` / `gel hardness` / `gel firmness` moved from
  `functional_property` to `rheological_property`, consistent with
  `gelling_property` having already been migrated wholesale into
  `rheological_property` earlier in this project, and with `hardness` /
  `breaking strength` (texture-analyzer measurements of the same kind)
  already landing there.
- `vacuum drying`, `conventional heating`, `thermal processing`, `sericin
  addition`, `high methoxyl pectin addition` moved from
  `material_used_directly` to `modification_method` — every other "X
  drying" / "X heating" / "X addition" entity in the data (freeze drying,
  spray drying, heat treatment, CaCl2 addition, sucrose addition, ...) was
  already confidently `modification_method`; these were the extraction
  artifact, not a genuine alternate reading.
- `viscoelasticity`, `mechanical properties`, `complex viscosity`,
  `elastic modulus`, `breaking force`, `friction coefficient` moved to
  `rheological_property` — these name mechanical/rheometry measurements
  directly, not application-level functional outcomes.
- `glycation` moved to `modification_method` (a chemical modification
  reaction, matching phosphorylation/acetylation/acylation/succinylation);
  `degree of phosphorylation` moved the other direction, to
  `physicochemical_property` (a measured extent, distinct from the
  treatment itself).

The full list with rationale is in `resolved_entity_types.csv`. **Every
override was decided this session by Claude directly reading the entity
names, breakdowns, and grounding sentences — not by calling an external LLM
API**, since no `OPENAI_API_KEY` was available in this environment.
`llm_resolve_entity_types.py` is provided so this same step can be re-run
against a real GPT-4o call later (e.g. when new conflicts appear as the
corpus scales toward 12,000 papers) — worth doing for anything you'd cite
formally, as a second opinion against this session's manual pass.

Every affected node carries `type_conflict` / `near_tie` (how contested the
raw data was) and `llm_resolved` / `llm_confidence` / `llm_rationale` (how
the final label was decided) as properties in the graph itself, so query 6
in `04_verification.cypher` pulls the live list any time. The remaining 124
names kept their majority-vote label — either the majority was already
clearly correct, or no stronger evidence justified overriding it.

## What's still open

- **Hosting** (local vs. AuraDB vs. self-hosted) is explicitly deferred per the
  project context doc — everything here runs against a local Neo4j Desktop
  database.
- **This session's 21 manual overrides** are functional in the graph and each
  carries a written rationale (`resolved_entity_types.csv`), but were decided
  by Claude reading names/sentences directly rather than a scripted, temperature-0
  API call — worth a real `llm_resolve_entity_types.py` run (or a domain read
  from Dr. Li) before citing any of them formally.
- **The other 124 near-tie/conflicted names** kept their majority-vote label;
  the 35 originally flagged as near-ties (`near_tie = true`) are still the
  ones most worth a second look even though most weren't overridden.
- **Foam-entity consolidation** (`foam activity/capacity/ability` family →
  `foaming capacity`) was checked against this file and appears complete: none
  of the specific variants named in the project context doc remain as separate
  entities. The other foam-related terms in the data (`foamability`, `foam
  formation capacity`, `foam-forming ability`, etc.) are genuinely distinct
  properties, not unmerged duplicates.
