<div align="center">

# 🌱 Plant Protein Literature Data Mining

**Turning a fragmented body of plant-protein research into a structured, queryable knowledge graph.**

![Status](https://img.shields.io/badge/status-work--in--progress-yellow)
![Domain](https://img.shields.io/badge/domain-food%20science-6aa84f)
![Pipeline](https://img.shields.io/badge/pipeline-literature%20mining%20%E2%86%92%20NER%20%E2%86%92%20knowledge%20graph-blue)
![Graph DB](https://img.shields.io/badge/graph--db-Neo4j-008cc1)

</div>

---

## Overview

This project applies data mining and NLP techniques to the published literature on plant protein functional properties, with two connected goals:

1. **Systematic literature review** — searching, aggregating, and deduplicating records across major bibliographic databases to build a reliable corpus of relevant publications.
2. **Knowledge extraction** — mining the full text of that corpus to identify entities and relationships (materials, methods, treatments, and their effects on protein functionality), and organizing the extracted knowledge into a structured knowledge graph.

The broader aim is to make it easier to see patterns and connections across a large, fragmented body of plant protein research that would be difficult to review manually at scale.

> *Search strategies, prompts, and some intermediate methodology details are intentionally kept out of this public repository while the work is ongoing.*

## Pipeline

```mermaid
graph LR
    A[Literature Search<br/>WOS · Scopus · EBSCOHost] --> B[Deduplication &<br/>Relevance Filtering]
    B --> C[Article Retrieval<br/>PDF / Full Text]
    C --> D[Text Preprocessing<br/>& Chunking]
    D --> E[Relation / Triple<br/>Extraction]
    E --> F[Entity & Type<br/>Resolution]
    F --> G[(Knowledge Graph<br/>Neo4j)]
```

## The knowledge graph: In progress..... 