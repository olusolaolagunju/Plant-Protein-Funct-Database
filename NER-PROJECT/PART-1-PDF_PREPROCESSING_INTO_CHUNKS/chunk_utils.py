"""
chunk_utils.py

Shared section-detection and token-aware chunking utilities for the
plant protein KG pipeline. Used by BOTH the PDF pipeline and the
Elsevier txt pipeline, so every paper regardless of source produces
identically-formatted chunks, one row per chunk, tagged with:

    {doi_safe}_{section}{index}

matching the PlantConnectome-style ID convention, but using DOI
instead of PubMed ID, and reusing the project's existing DOI-safe
naming rule (replace '.' with '-' and '/' with '_').

This module does the splitting BEFORE any GPT call is made. The
model never sees a whole paper and is never asked to do the
splitting itself, it only ever receives one already-cut chunk_text
at a time.

Save this file directly into your working directory (the same folder
your notebook runs from), do not pip install it, it is not a package.
"""

import re
import tiktoken


# ---------------------------------------------------------------------------
# DOI -> safe filename/ID conversion (matches existing project convention)
# ---------------------------------------------------------------------------
def doi_to_safe_id(doi: str) -> str:
    return doi.strip().replace(".", "-").replace("/", "_")


# ---------------------------------------------------------------------------
# Section detection
# Works for both PDF-extracted text (headers appear as short standalone
# lines) and Elsevier txt exports (ALL CAPS headers followed by a colon,
# colon already stripped before matching).
# ---------------------------------------------------------------------------
SECTION_PATTERNS = {
    "abstract":            r"abstract",
    "intro":               r"introduction",
    "methods":             r"material[s]?\s+and\s+method[s]?|method[s]?",
    "results_discussion":  r"result[s]?\s+and\s+discussion|result[s]?\s*&\s*discussion",
    "results":             r"result[s]?",
    "discussion":          r"discussion",
    "conclusion":          r"conclusion[s]?",
    "references":          r"reference[s]?|bibliography|works\s+cited",
}

# Many PDFs number their section headers ("2. Materials and Methods",
# "3. Results and Discussion"). A bare regex match against the whole line
# fails on these, since the leading number isn't part of the pattern, which
# left every downstream section silently un-detected and let a paper's full
# text (including its reference list) collapse into whatever section was
# last successfully matched. Strip a leading "2.", "3.1", "4)" style prefix
# before matching. Also added a "references" pattern above, this is
# deliberately NOT in SECTIONS_TO_KEEP below, so it exists purely to give
# the bibliography its own boundary and stop it from being swept into an
# earlier section, its own content is simply excluded, never mixed in.
HEADER_NUMBER_PREFIX = re.compile(r"^\d+(\.\d+)*[\.\)]?\s*")

# Full text: every detected section is kept, including intro and discussion.
#
# IMPORTANT: intro and discussion are the sections most likely to contain
# citations of other authors' prior findings and hedged/speculative
# language ("it would be interesting to test whether...", "as shown by
# X et al."), rather than this paper's own results. Since these are now
# included, the Phase 2 extraction prompt MUST have the citation-guard
# and hedging-guard rules (do not extract a claim attributed to another
# study or framed as a proposed future test) built in before this text
# is sent to GPT, otherwise you will get FUS3/IDD8-style false facts
# extracted from these two sections specifically.
SECTIONS_TO_KEEP = ["abstract", "intro", "methods", "results", "results_discussion", "discussion", "conclusion"]


def split_into_sections(text: str) -> dict:
    """
    Split raw article text into {section_name: section_text}.
    A line is only treated as a header if it is short (under 60 chars)
    and matches a section pattern on its own, this avoids accidentally
    matching the word "results" inside an ordinary sentence.
    """
    lines = text.splitlines()
    sections = {name: [] for name in SECTION_PATTERNS}
    current = None

    for line in lines:
        stripped = line.strip().rstrip(":").strip()
        candidate = HEADER_NUMBER_PREFIX.sub("", stripped).strip()
        matched = None
        if 0 < len(candidate) < 60:
            for name, pattern in SECTION_PATTERNS.items():
                if re.fullmatch(pattern, candidate, flags=re.IGNORECASE):
                    matched = name
                    break
        if matched:
            current = matched
            continue
        if current:
            sections[current].append(line)

    return {name: "\n".join(lns).strip() for name, lns in sections.items() if lns}


# ---------------------------------------------------------------------------
# Token-aware chunking
# Mirrors the batch_inputs_by_tokens pattern already used in
# generate_entity_embeddings.py: count real tokens with tiktoken, pack
# paragraphs into a chunk until the next one would exceed the budget,
# then start a new chunk. Never split mid-sentence.
# ---------------------------------------------------------------------------
def chunk_section_text(text: str, max_tokens: int = 3000, model: str = "gpt-4o") -> list:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, current, current_tokens = [], [], 0

    for para in paragraphs:
        n = len(encoding.encode(para))

        # a single paragraph itself exceeds the budget: split on sentences
        if n > max_tokens:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                sn = len(encoding.encode(sent))
                if current_tokens + sn > max_tokens and current:
                    chunks.append(" ".join(current))
                    current, current_tokens = [], 0
                current.append(sent)
                current_tokens += sn
            continue

        if current_tokens + n > max_tokens and current:
            chunks.append("\n\n".join(current))
            current, current_tokens = [], 0
        current.append(para)
        current_tokens += n

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def build_chunk_records(doi: str, full_text: str, max_tokens: int = 3000) -> list:
    """
    Full pipeline: raw article text -> list of chunk records ready for
    Phase 2 triple extraction.

    Each record: {id, doi, section, chunk_index, chunk_text}
    """
    safe_id = doi_to_safe_id(doi)
    sections = split_into_sections(full_text)

    records = []
    for section_name in SECTIONS_TO_KEEP:
        section_text = sections.get(section_name)
        if not section_text:
            continue
        chunks = chunk_section_text(section_text, max_tokens=max_tokens)
        for i, chunk in enumerate(chunks, start=1):
            records.append({
                "id": f"{safe_id}_{section_name}{i}",
                "doi": doi,
                "section": section_name,
                "chunk_index": i,
                "chunk_text": chunk,
            })
    return records


# ---------------------------------------------------------------------------
# Shared entry point for both pipelines: chunk every .txt file in a folder
# (one file per paper, named by its DOI-safe id) into one combined parquet.
# Used by both pdf_chunk_processing.py and elsevier_text_extraction.py, so
# a fix to the chunking logic only ever needs to happen in one place.
# ---------------------------------------------------------------------------
def process_txt_folder(folder: str, output_parquet: str, source_type: str, max_tokens: int = 3000):
    import os
    import pandas as pd

    files = [f for f in sorted(os.listdir(folder)) if f.endswith(".txt")]
    print(f"Found {len(files)} text files in {folder}/")

    all_records = []
    for i, fname in enumerate(files, 1):
        path = os.path.join(folder, fname)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        doi_safe = os.path.splitext(fname)[0]  # already DOI-safe, per project convention
        records = build_chunk_records(doi_safe, text, max_tokens=max_tokens)
        for r in records:
            r["source_type"] = source_type
        all_records.extend(records)
        print(f"[{i}/{len(files)}] {fname}  chunks={len(records)}")

    df = pd.DataFrame(all_records)
    df.to_parquet(output_parquet, index=False)
    print(f"\nSaved {len(df)} chunks from {len(files)} papers to {output_parquet}")
    return df