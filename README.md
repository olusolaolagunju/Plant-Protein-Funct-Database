# Plant Protein Literature Data Mining

> **Status: work in progress.** This repository documents an active research project. Structure, scripts, and outputs are being iterated on and will continue to change.

## Overview

This project applies data mining and NLP techniques to the published literature on plant protein functional properties, with two connected goals:

1. **Systematic literature review** — searching, aggregating, and deduplicating records across major bibliographic databases to build a reliable corpus of relevant publications.
2. **Knowledge extraction** — mining the full text of that corpus to identify entities and relationships (e.g., materials, methods, treatments, and their effects on protein functionality), and organizing the extracted knowledge into a structured, queryable knowledge graph.

The broader aim is to make it easier to see patterns and connections across a large, fragmented body of plant protein research that would be difficult to review manually at scale.

*Search strategies, prompts, and some intermediate methodology details are intentionally omitted from this public repository while the work is ongoing.*

## Repository structure

```
Web-of-science-abstracts/   Literature search & deduplication across bibliographic databases
NER-PROJECT/                 Full pipeline from article retrieval through knowledge graph construction
    PART-0  Article retrieval (PDF / full-text acquisition)
    PART-1  Text preprocessing and chunking
    PART-2  Relation/triple extraction
    PART-3  Triple preprocessing and analysis
    PART-4  Entity resolution
    PART-5  Entity type resolution
    STEP-6  Optional clean-up steps
    PART-7  Knowledge graph construction (Neo4j)
```

## Notes

- Raw downloaded article text/figures, large database export dumps, and any API keys or credentials are **not** included in this repository (excluded via `.gitignore`) due to size, publisher licensing terms, and confidentiality.
- To run any of the notebooks/scripts locally, you will need your own API credentials (e.g., for literature databases, LLM providers, and Elsevier's TDM API where applicable) configured via a local `.env` file — see the `os.getenv(...)` calls in each script for the expected variable names.
