// Step D (nodes) — run AFTER 01_constraints.cypher.
// Copy all CSVs from neo4j_import/ into your Neo4j Desktop database's
// "import" folder first (Desktop: DB card > ⋮ > Open folder > Import).
// Run each block with `:auto` in Neo4j Browser, or omit `:auto` and run the
// whole file via cypher-shell.
//
// nodes_<Label>.csv now has just two columns (name, occurrence_count) --
// type-conflict/LLM-resolution provenance moved upstream into
// entity_type_lookup.csv and the *_type_resolution columns of
// triples_types_resolved.xlsx, since build_kg_csvs.py no longer knows
// anything about how types were resolved.

:auto LOAD CSV WITH HEADERS FROM 'file:///nodes_FunctionalProperty.csv' AS row
CALL {
  WITH row
  MERGE (n:FunctionalProperty {name: row.name})
  SET n.occurrence_count = toInteger(row.occurrence_count)
} IN TRANSACTIONS OF 500 ROWS;

:auto LOAD CSV WITH HEADERS FROM 'file:///nodes_PhysicochemicalProperty.csv' AS row
CALL {
  WITH row
  MERGE (n:PhysicochemicalProperty {name: row.name})
  SET n.occurrence_count = toInteger(row.occurrence_count)
} IN TRANSACTIONS OF 500 ROWS;

:auto LOAD CSV WITH HEADERS FROM 'file:///nodes_StructuralProperty.csv' AS row
CALL {
  WITH row
  MERGE (n:StructuralProperty {name: row.name})
  SET n.occurrence_count = toInteger(row.occurrence_count)
} IN TRANSACTIONS OF 500 ROWS;

:auto LOAD CSV WITH HEADERS FROM 'file:///nodes_ModificationMethod.csv' AS row
CALL {
  WITH row
  MERGE (n:ModificationMethod {name: row.name})
  SET n.occurrence_count = toInteger(row.occurrence_count)
} IN TRANSACTIONS OF 500 ROWS;

:auto LOAD CSV WITH HEADERS FROM 'file:///nodes_ExtractionMethod.csv' AS row
CALL {
  WITH row
  MERGE (n:ExtractionMethod {name: row.name})
  SET n.occurrence_count = toInteger(row.occurrence_count)
} IN TRANSACTIONS OF 500 ROWS;

:auto LOAD CSV WITH HEADERS FROM 'file:///nodes_MaterialUsedDirectly.csv' AS row
CALL {
  WITH row
  MERGE (n:MaterialUsedDirectly {name: row.name})
  SET n.occurrence_count = toInteger(row.occurrence_count)
} IN TRANSACTIONS OF 500 ROWS;

:auto LOAD CSV WITH HEADERS FROM 'file:///nodes_RheologicalProperty.csv' AS row
CALL {
  WITH row
  MERGE (n:RheologicalProperty {name: row.name})
  SET n.occurrence_count = toInteger(row.occurrence_count)
} IN TRANSACTIONS OF 500 ROWS;

:auto LOAD CSV WITH HEADERS FROM 'file:///nodes_SensoryProperty.csv' AS row
CALL {
  WITH row
  MERGE (n:SensoryProperty {name: row.name})
  SET n.occurrence_count = toInteger(row.occurrence_count)
} IN TRANSACTIONS OF 500 ROWS;
