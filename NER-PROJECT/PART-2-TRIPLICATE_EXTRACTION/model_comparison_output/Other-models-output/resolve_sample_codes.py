"""
Phase 2 post-processing: automated sample-code resolution.

Problem: despite the prompt's code-resolution rule (rule 3), Luna still
leaves bare local codes in `source`/`material`/`target` for a meaningful
share of triples (e.g. "TT", "SS", "PA", "PG", "PPI 1", "HP-20"). These
codes are meaningless outside the paper they came from and will not merge
correctly in the knowledge graph.

This script requires NO further API calls. It works entirely from data
already in phase2_luna_full_triples.xlsx:

  1. Flags rows whose source/material/target looks like a bare code
     (all-caps abbreviation, code+digit, or code with a hyphenated suffix).
  2. For each flagged row, looks at every OTHER row from the SAME chunk_id
     (same paper, same chunk) to find a fully-resolved phrase that most
     plausibly corresponds to the code -- using two signals:
       a) the code appears as a parenthetical abbreviation inside another
          row's source/material/target in the same chunk
          (e.g. "hemp seed protein isolate ultrafiltration (UF)" defines UF)
       b) the code appears verbatim inside another row's flagged_phrase
          or corresponding_sentence in the same chunk, immediately preceded
          by a resolved noun phrase
  3. Writes a review file with every flagged row, its best-guess resolution,
     and a confidence label, so you can spot-check before trusting it.
  4. Writes a corrected copy of the triples table with resolved values
     substituted in wherever a confident match was found, and leaves
     everything else untouched.

Nothing here calls the OpenAI or Gemini API. This is pure post-processing
against your existing extraction output.

Usage:
    python resolve_sample_codes.py phase2_luna_full_triples.xlsx
"""

import re
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FIELDS_TO_CHECK = ["source", "material", "target"]

# A field counts as a "bare code" if it matches any of these patterns and
# is short enough that it's very unlikely to be a real descriptive phrase.
CODE_PATTERNS = [
    r"^[A-Z]{2,6}$",                     # TT, SS, CC, PA, GL, PG, HPP, DIC, SPU
    r"^[A-Z]{1,4}\s?\d{1,3}$",           # PPI 1, PPI2, SP-4 (without hyphen), G5
    r"^[A-Z]{1,5}-\d{1,3}$",             # HP-20, SP-207
    r"^[A-Z]\d{1,3}-[A-Z]{1,4}$",        # G5-UF, G5-IP
    r"^[A-Z]{2,6}\d{0,3}-[A-Z]{2,6}$",   # NaCas-like compound codes, PPI-NaCas
]
CODE_RE = re.compile("|".join(f"(?:{p})" for p in CODE_PATTERNS))

# Common legitimate short chemical formulas / units to NEVER flag as codes,
# since they're real, portable entities, not paper-local shorthand.
KNOWN_SAFE = {
    "NaCl", "KCl", "CaCl2", "MgCl2", "NaOH", "HCl", "H2O2", "Na2SO4",
    "NaSCN", "NaClO4", "NaI", "CO2", "GDL", "UV", "pH", "PBS", "SDS",
    "DTT", "GABA", "ACE",
}


def looks_like_code(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    v = value.strip()
    if v in KNOWN_SAFE:
        return False
    # Must match a code pattern
    if not CODE_RE.match(v):
        return False
    return True


# ---------------------------------------------------------------------------
# Resolution logic
# ---------------------------------------------------------------------------

def find_definition_in_text(code: str, text: str) -> str | None:
    """Look for a pattern like 'resolved phrase (CODE)' in the given text,
    which is the standard way papers define an abbreviation on first use.
    Returns the resolved phrase if found, else None.
    """
    if not isinstance(text, str) or not text:
        return None
    # Escape code for regex safety (handles hyphens, digits)
    escaped = re.escape(code)
    # Pattern: some words immediately followed by "(CODE)"
    pattern = rf"([A-Za-z][A-Za-z0-9\-\s]{{3,80}}?)\s*\(\s*{escaped}\s*\)"
    match = re.search(pattern, text)
    if match:
        phrase = match.group(1).strip()
        # Trim leading connector words that sometimes get captured
        phrase = re.sub(r"^(the|a|an|and|or|with)\s+", "", phrase, flags=re.IGNORECASE)
        return phrase
    return None


def resolve_code_for_chunk(code: str, chunk_rows: pd.DataFrame) -> tuple[str | None, str]:
    """Try to resolve `code` using every field of every row belonging to
    the same chunk. Returns (resolved_phrase_or_None, confidence_label).
    """
    search_fields = ["source", "material", "target", "flagged_phrase", "corresponding_sentence"]

    # Pass 1: look for "phrase (CODE)" definition pattern - highest confidence
    for _, row in chunk_rows.iterrows():
        for field in search_fields:
            text = row.get(field, "")
            resolved = find_definition_in_text(code, text)
            if resolved:
                return resolved, "high (explicit definition found)"

    # Pass 2: look for the code appearing as a substring inside a longer,
    # non-code phrase in source/material/target from the same chunk
    # (e.g. code "SS" appearing inside "SS ingredient" elsewhere, weak signal)
    candidates = []
    for _, row in chunk_rows.iterrows():
        for field in ["source", "material", "target"]:
            text = row.get(field, "")
            if not isinstance(text, str):
                continue
            if code in text and text.strip() != code and not looks_like_code(text):
                candidates.append(text.strip())
    if candidates:
        # Most frequent candidate wins
        best = max(set(candidates), key=candidates.count)
        return best, "medium (co-occurrence match, verify manually)"

    return None, "unresolved (no match found in chunk)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python resolve_sample_codes.py <triples_file.xlsx>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    df = pd.read_excel(in_path)
    print(f"Loaded {len(df)} triples from {in_path}")

    # Identify every row with a bare-code field
    flagged_rows = []
    for idx, row in df.iterrows():
        for field in FIELDS_TO_CHECK:
            val = row.get(field, "")
            if looks_like_code(val):
                flagged_rows.append({"row_index": idx, "field": field, "code": val.strip()})

    print(f"Found {len(flagged_rows)} bare-code field instances across "
          f"{len(set(r['row_index'] for r in flagged_rows))} rows.")

    if not flagged_rows:
        print("Nothing to resolve.")
        return

    # Resolve each flagged instance using other rows from the same chunk
    review_records = []
    df_corrected = df.copy()

    for item in flagged_rows:
        idx = item["row_index"]
        field = item["field"]
        code = item["code"]
        chunk_id = df.at[idx, "chunk_id"]

        chunk_rows = df[df["chunk_id"] == chunk_id]
        resolved, confidence = resolve_code_for_chunk(code, chunk_rows)

        review_records.append({
            "row_index": idx,
            "chunk_id": chunk_id,
            "field": field,
            "original_code": code,
            "resolved_to": resolved if resolved else "",
            "confidence": confidence,
            "corresponding_sentence": df.at[idx, "corresponding_sentence"]
                if "corresponding_sentence" in df.columns else "",
        })

        # Only auto-apply high-confidence resolutions to the corrected copy.
        # Medium-confidence matches are left in the review file for you to
        # confirm before applying, since they're a weaker signal.
        if resolved and confidence.startswith("high"):
            df_corrected.at[idx, field] = resolved

    review_df = pd.DataFrame(review_records)
    review_path = in_path.parent / f"{in_path.stem}_code_resolution_review.xlsx"
    review_df.to_excel(review_path, index=False)
    print(f"Review file ({len(review_df)} flagged instances) -> {review_path}")

    n_high = (review_df["confidence"].str.startswith("high")).sum()
    n_medium = (review_df["confidence"].str.startswith("medium")).sum()
    n_unresolved = (review_df["confidence"].str.startswith("unresolved")).sum()
    print(f"  High confidence (auto-applied): {n_high}")
    print(f"  Medium confidence (needs your review before applying): {n_medium}")
    print(f"  Unresolved (needs manual lookup or a targeted re-extraction): {n_unresolved}")

    corrected_path = in_path.parent / f"{in_path.stem}_code_resolved.xlsx"
    df_corrected.to_excel(corrected_path, index=False)
    print(f"Corrected triples (high-confidence fixes applied) -> {corrected_path}")

    print(
        "\nNext step: open the review file, check the 'medium' confidence rows, "
        "and if they look right, apply them manually or extend this script to "
        "auto-apply medium-confidence matches above a chosen threshold."
    )


if __name__ == "__main__":
    main()