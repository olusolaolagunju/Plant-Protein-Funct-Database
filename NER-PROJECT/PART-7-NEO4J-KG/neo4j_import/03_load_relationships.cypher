// Step D (relationships) — run AFTER 02_load_nodes.cypher.
//
// Requires the APOC Core plugin (Neo4j Desktop: DB card > Plugins > APOC >
// Install — one click). It's needed because Cypher's LOAD CSV can't create a
// relationship whose TYPE comes from a column value at read time; only APOC's
// apoc.merge.relationship can take the type as a runtime string.
//
// MERGE key is evidence_id (one per source triples-file row, already unique
// by construction), so re-running this file is safe and won't duplicate edges.
// Nodes are matched by name only, with no label specified: after type
// resolution every resolved entity name maps to exactly one label, so a
// plain {name: ...} match is unambiguous and label-independent.
//
// `category` is the row's original category column from the triples file
// (treatment_property_change, protein_protein_comparison, etc.) -- it
// describes what KIND of comparison the edge represents, independent of
// interaction_type (which only says increased/decreased/etc). Filter on it
// with e.g. MATCH ()-[r {category: "protein_protein_comparison"}]->().

:auto LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
CALL {
  WITH row
  MATCH (s {name: row.source_name})
  MATCH (t {name: row.target_name})
  CALL apoc.merge.relationship(
    s,
    row.interaction_type,
    {evidence_id: row.evidence_id},
    {
      doi: row.doi,
      chunk_id: row.chunk_id,
      section: row.section,
      pmid: row.pmid,
      compared_property: row.compared_property,
      reported_value: row.reported_value,
      claim_status: row.claim_status,
      category: row.category,
      corresponding_sentence: row.corresponding_sentence
    },
    t,
    {}
  ) YIELD rel
  RETURN rel
} IN TRANSACTIONS OF 500 ROWS
RETURN count(*) AS relationships_loaded;
