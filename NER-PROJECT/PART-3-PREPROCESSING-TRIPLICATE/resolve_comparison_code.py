"""
Phase 2 post-processing: bare-code resolution on comparison rows.

Scans only rows where interaction is outperformed / underperformed /
equivalent_to (these need two cleanly-resolved entity names to be
useful for KG merging). For each bare code found in source or target,
searches every other row from the SAME chunk_id for a fuller name that
contains that code, and substitutes it in if found. Never invents a
name — if no other row in that chunk spells it out, the row is left
untouched and flagged for review instead.

Every result includes a `confidence` column so every fix (or non-fix)
can be manually spot-checked:
    - "high (single consistent match)"       -> auto-applied
    - "medium (...picked most frequent)"     -> auto-applied, worth a glance
    - "unresolved (...)"                      -> left untouched, needs review
                                                 or a Sol fallback pass

Usage:
    python resolve_comparison_codes.py <triples_file.xlsx>
"""

import re
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

COMPARISON_INTERACTIONS = {"outperformed", "underperformed", "equivalent_to"}

CODE_PATTERNS = [
    r"^[A-Z]{2,6}$",                     # PA, GL, PG, CT, CC, SS, TT
    r"^[A-Z]{1,4}\s?\d{1,3}$",           # PPI 1, PPI2, G5, M9, B9
    r"^[A-Z]{1,5}-\d{1,3}$",             # HP-20, SP-207
    r"^[A-Z]\d{1,3}-[A-Z]{1,4}$",        # G5-UF, G5-IP
    r"^[A-Z]{1,6}-[A-Z]{1,6}$",          # CS-PG, CP-PG, PT-TP
    r"^[A-Za-z]+\s?\d{1,3}\s?%?$",       # PP 80%, E86, E86 F30 (loose, checked below)
]
CODE_RE = re.compile("|".join(f"(?:{p})" for p in CODE_PATTERNS))

KNOWN_SAFE = {
    "NaCl", "KCl", "CaCl2", "MgCl2", "NaOH", "HCl", "H2O2", "Na2SO4",
    "NaSCN", "NaClO4", "NaI", "CO2", "GDL", "UV", "pH", "PBS", "SDS",
    "DTT", "GABA", "ACE", "SPI", "PPI", "WPI", "WPC",  # common, already-standard abbreviations
}

# Words that appear in company/brand names too generically to be codes.
NOT_A_CODE_IF_CONTAINS = {"and", "the", "with", "acid", "protein", "isolate"}


def looks_like_code(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    v = value.strip()
    if v in KNOWN_SAFE:
        return False
    if len(v.split()) > 3:
        return False  # too long to be a bare code
    lower_words = set(w.lower() for w in v.split())
    if lower_words & NOT_A_CODE_IF_CONTAINS:
        return False
    if not CODE_RE.match(v):
        return False
    return True


def find_fuller_name_in_chunk(code: str, chunk_rows: pd.DataFrame, exclude_idx) -> tuple[str | None, str]:
    """Search every field of every OTHER row in this chunk for a fuller
    name that contains `code` as a distinct token. Returns
    (best_match_or_None, confidence_label).
    """
    candidates = []
    for idx, row in chunk_rows.iterrows():
        if idx == exclude_idx:
            continue
        for field in ["source", "material", "target"]:
            text = row.get(field, "")
            if not isinstance(text, str) or not text.strip():
                continue
            # code must appear as a whole word/token inside a longer, non-code phrase
            if re.search(rf"\b{re.escape(code)}\b", text) and not looks_like_code(text):
                candidates.append(text.strip())

    if not candidates:
        return None, "unresolved (no fuller name found elsewhere in this chunk)"

    best = max(set(candidates), key=candidates.count)
    n_matches = len(set(candidates))
    confidence = "high (single consistent match)" if n_matches == 1 else "medium (multiple candidate names, picked most frequent)"
    return best, confidence


def resolve_comparison_codes(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    review_rows = []

    comparison_mask = df["interaction"].isin(COMPARISON_INTERACTIONS)
    comparison_idx = df[comparison_mask].index

    for idx in comparison_idx:
        row = df.loc[idx]
        chunk_id = row["chunk_id"]
        chunk_rows = df[df["chunk_id"] == chunk_id]

        for field in ["source", "target"]:
            val = row[field]
            if looks_like_code(val):
                resolved, confidence = find_fuller_name_in_chunk(val, chunk_rows, idx)
                review_rows.append({
                    "row_index": idx,
                    "chunk_id": chunk_id,
                    "field": field,
                    "original_code": val,
                    "resolved_to": resolved if resolved else "",
                    "confidence": confidence,
                    "interaction": row["interaction"],
                    "corresponding_sentence": row.get("corresponding_sentence", ""),
                })
                if resolved and confidence.startswith("high"):
                    df.at[idx, field] = resolved

    review_df = pd.DataFrame(review_rows)
    return df, review_df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python resolve_comparison_codes.py <triples_file.xlsx>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    df = pd.read_excel(in_path)
    print(f"Loaded {len(df)} triples from {in_path}")

    n_comparison = df["interaction"].isin(COMPARISON_INTERACTIONS).sum()
    print(f"Comparison-type rows (outperformed/underperformed/equivalent_to): {n_comparison}")

    df_fixed, review = resolve_comparison_codes(df)
    print(f"\nBare code resolution on comparison rows:")
    print(f"  Flagged instances: {len(review)}")
    if len(review):
        print(review["confidence"].value_counts().to_string())

    out_dir = in_path.parent
    stem = in_path.stem

    fixed_path = out_dir / f"{stem}_fixed.xlsx"
    df_fixed.to_excel(fixed_path, index=False)
    print(f"\nFixed triples -> {fixed_path}")

    if len(review):
        review_path = out_dir / f"{stem}_code_review.xlsx"
        review.to_excel(review_path, index=False)
        print(f"Review file (for manual verification) -> {review_path}")

    n_unresolved = (review["confidence"].str.startswith("unresolved")).sum() if len(review) else 0
    if n_unresolved:
        print(f"\n{n_unresolved} codes could not be resolved from context in this file — "
              f"these are candidates for a Sol fallback pass.")


if __name__ == "__main__":
    main()