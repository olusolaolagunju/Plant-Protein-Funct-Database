// Step E — Verification queries. Run after loading nodes and relationships.

// 1. Node count by label — should sum to 2744 and match the per-file counts
//    printed by build_kg_csvs.py.
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS node_count
ORDER BY node_count DESC;

// 2. Relationship count by type — should sum to 10324 (one edge per source row;
//    increased=3960, decreased=2224, exhibited=1327, outperformed=895,
//    no_significant_change=728, induced=706, equivalent_to=196,
//    underperformed=188, other=100).
MATCH ()-[r]->()
RETURN type(r) AS interaction_type, count(*) AS edge_count
ORDER BY edge_count DESC;

// 3. Total relationship count sanity check against source row count (10324).
MATCH ()-[r]->()
RETURN count(r) AS total_relationships;

// 4. No entity name should appear under more than one label — should return
//    zero rows. (Guaranteed by running the type-resolution scripts before
//    build_kg_csvs.py; this just confirms it landed correctly.)
MATCH (n)
WITH n.name AS name, collect(DISTINCT labels(n)[0]) AS lbls
WHERE size(lbls) > 1
RETURN name, lbls;

// 5. Spot-check a well-known entity — confirm "solubility" has the expected
//    number of connections against the frequency analysis from the prior
//    pipeline work.
MATCH (n {name: "solubility"})
OPTIONAL MATCH (n)-[r]-()
RETURN n.name, labels(n)[0] AS label, count(r) AS degree;

// 6. Relationship count by category — should match the source file's
//    category column distribution (12 values: treatment_property_change
//    7953, protein_protein_comparison 778, treatment_treatment_comparison
//    360, combined_treatment_property_change 352, protein_fraction 256,
//    protein_conjugation 212, cultivar_genotype_comparison 167,
//    other_interaction_needs_manual_review 100, protein_protein_complex 56,
//    protein_protein_blend 47, commercial_protein_comparison 33,
//    protein_polyphenol_complex 10).
MATCH ()-[r]->()
RETURN r.category AS category, count(*) AS edge_count
ORDER BY edge_count DESC;

// 6b. The 100 edges the source data itself flagged as needing manual
//     review (category = other_interaction_needs_manual_review) — worth a
//     look before citing anything built from them.
MATCH (s)-[r {category: "other_interaction_needs_manual_review"}]->(t)
RETURN s.name AS source, type(r) AS interaction, t.name AS target, r.doi
LIMIT 25;

// 7. Any relationship endpoints that failed to MATCH during load would have
//    silently produced no row rather than an error — cross-check the loaded
//    relationship count (query 3) against the relationships.csv row count as
//    the authoritative check for that failure mode.
