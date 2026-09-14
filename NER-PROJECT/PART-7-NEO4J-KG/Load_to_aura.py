"""
Load a fully-built Neo4j KG (the neo4j_import/ folder produced by
build_kg_csvs.py: nodes_<Label>.csv + relationships.csv) into an AuraDB
instance directly over the network. No local "import" folder needed, no
APOC needed -- this replaces 02_load_nodes.cypher and
03_load_relationships.cypher for Aura, since Aura has no file:/// access
and doesn't have apoc.merge.relationship.

Works identically against Neo4j Desktop too, just point NEO4J_URI at your
local DBMS's bolt address instead (e.g. "neo4j://localhost:7687") -- so
you don't need two separate scripts depending on which instance you end
up using.

Designed for Jupyter/Colab execution. No __main__ guard -- just set the
CONFIG values below and run the whole cell/file.

pip install neo4j pandas --break-system-packages
"""

import os

import pandas as pd
from neo4j import GraphDatabase

# ---------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------
NEO4J_URI = "neo4j+s://f1cebb95.databases.neo4j.io"     # <- your Aura instance URI
NEO4J_USERNAME = "f1cebb95"
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")   # <- fill in here, or set the env var
NEO4J_DATABASE = "f1cebb95"

NODES_DIR = "neo4j_import"   # <- folder containing nodes_<Label>.csv + relationships.csv
BATCH_SIZE = 1000

# Cypher can't parameterize labels or relationship types -- they get spliced
# directly into the query string below. That's only safe because both lists
# are a fixed whitelist defined here, never taken from row data. If a row's
# type isn't in these lists, the script stops rather than silently skipping
# or injecting something unexpected.
LABELS = [
    "FunctionalProperty", "PhysicochemicalProperty", "StructuralProperty",
    "ModificationMethod", "ExtractionMethod", "MaterialUsedDirectly",
    "RheologicalProperty", "SensoryProperty",
]
REL_TYPES = [
    "INCREASED", "DECREASED", "EXHIBITED", "OUTPERFORMED",
    "NO_SIGNIFICANT_CHANGE", "INDUCED", "EQUIVALENT_TO",
    "UNDERPERFORMED", "OTHER",
]


def batched(rows, size):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


# ---------------------------------------------------------------
# CONNECT
# ---------------------------------------------------------------
if not NEO4J_PASSWORD:
    raise SystemExit(
        "Set NEO4J_PASSWORD above, or set it as an environment variable "
        "before running this script."
    )

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
driver.verify_connectivity()
print(f"Connected to {NEO4J_URI}")


def run(query, **params):
    with driver.session(database=NEO4J_DATABASE) as session:
        return session.run(query, **params).consume()


# ---------------------------------------------------------------
# CONSTRAINTS -- same uniqueness guarantee as 01_constraints.cypher, just
# issued over the driver instead of pasted into Neo4j Browser.
# ---------------------------------------------------------------
for label in LABELS:
    constraint_name = f"{label.lower()}_name"
    run(
        f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
        f"FOR (n:{label}) REQUIRE n.name IS UNIQUE"
    )
print("Constraints created (or already existed).")

# ---------------------------------------------------------------
# NODES
# ---------------------------------------------------------------
total_nodes = 0
for label in LABELS:
    path = os.path.join(NODES_DIR, f"nodes_{label}.csv")
    if not os.path.exists(path):
        print(f"  skip {label}: {path} not found")
        continue
    # keep_default_na=False: otherwise pandas reads blank CSV fields back as
    # NaN, and NaN can't be sent as a Cypher parameter cleanly.
    df = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)
    rows = df.to_dict("records")
    for chunk in batched(rows, BATCH_SIZE):
        run(
            f"UNWIND $rows AS row "
            f"MERGE (n:{label} {{name: row.name}}) "
            f"SET n.occurrence_count = toInteger(row.occurrence_count)",
            rows=chunk,
        )
    total_nodes += len(rows)
    print(f"  {label}: {len(rows)} nodes loaded")
print(f"Total nodes loaded: {total_nodes}")

# ---------------------------------------------------------------
# RELATIONSHIPS -- grouped by type, since relationship type also can't be
# parameterized. MERGE key is evidence_id, so re-running this script is
# safe and won't duplicate edges.
# ---------------------------------------------------------------
rel_path = os.path.join(NODES_DIR, "relationships.csv")
rel_df = pd.read_csv(rel_path, encoding="utf-8-sig", keep_default_na=False)

unexpected_types = set(rel_df["interaction_type"].unique()) - set(REL_TYPES)
if unexpected_types:
    raise SystemExit(f"STOP: relationship types not in the whitelist: {unexpected_types}")

total_rels = 0
for rel_type in REL_TYPES:
    sub = rel_df[rel_df["interaction_type"] == rel_type]
    if sub.empty:
        continue
    rows = sub.to_dict("records")
    for chunk in batched(rows, BATCH_SIZE):
        run(
            f"UNWIND $rows AS row "
            f"MATCH (s {{name: row.source_name}}) "
            f"MATCH (t {{name: row.target_name}}) "
            f"MERGE (s)-[r:{rel_type} {{evidence_id: row.evidence_id}}]->(t) "
            f"SET r.doi = row.doi, r.chunk_id = row.chunk_id, r.section = row.section, "
            f"    r.pmid = row.pmid, r.compared_property = row.compared_property, "
            f"    r.reported_value = row.reported_value, r.claim_status = row.claim_status, "
            f"    r.category = row.category, r.corresponding_sentence = row.corresponding_sentence",
            rows=chunk,
        )
    total_rels += len(rows)
    print(f"  {rel_type}: {len(rows)} relationships loaded")
print(f"Total relationships loaded: {total_rels}")

driver.close()
print("Done.")