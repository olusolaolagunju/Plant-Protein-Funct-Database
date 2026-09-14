"""
Keyword search across the full triples file: finds every row where the
given word/phrase appears in ANY column (source, material, target,
interaction, flagged_phrase, corresponding_sentence, category, etc.),
not just one field. Case-insensitive, matches partial words by default
(e.g. "ultrasonication" also matches "ultrasonication-assisted").

Usage:
    python search_triples.py phase2_terra_full_triples_categorized.xlsx "ultrasonication"

    # whole-word match only (won't match "ultrasonicated" if searching "ultrasonic"):
    python search_triples.py phase2_terra_full_triples_categorized.xlsx "ultrasonication" --whole-word

    # python search_triples.py phase2_terra_full_triples_categorized.xlsx "guar gum"
    # search only specific columns:
    python search_triples.py phase2_terra_full_triples_categorized.xlsx "ultrasonication" --columns source,target
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Search all columns of a triples file for a keyword.")
    parser.add_argument("file", help="Path to the .xlsx file to search")
    parser.add_argument("keyword", help="Word or phrase to search for")
    parser.add_argument("--whole-word", action="store_true",
                         help="Match only whole words (default: partial match anywhere in the cell)")
    parser.add_argument("--columns", default=None,
                         help="Comma-separated list of columns to search (default: all columns)")
    parser.add_argument("--case-sensitive", action="store_true",
                         help="Match case exactly (default: case-insensitive)")
    args = parser.parse_args()

    in_path = Path(args.file)
    if not in_path.exists():
        print(f"File not found: {in_path}")
        sys.exit(1)

    df = pd.read_excel(in_path)
    print(f"Loaded {len(df)} rows from {in_path}")

    search_columns = args.columns.split(",") if args.columns else df.columns.tolist()
    missing = [c for c in search_columns if c not in df.columns]
    if missing:
        print(f"Warning: these columns don't exist and will be skipped: {missing}")
        search_columns = [c for c in search_columns if c in df.columns]

    flags = 0 if args.case_sensitive else re.IGNORECASE
    if args.whole_word:
        pattern = re.compile(rf"\b{re.escape(args.keyword)}\b", flags)
    else:
        pattern = re.compile(re.escape(args.keyword), flags)

    def row_matches(row) -> bool:
        for col in search_columns:
            val = row.get(col, "")
            if pd.isna(val):
                continue
            if pattern.search(str(val)):
                return True
        return False

    mask = df.apply(row_matches, axis=1)
    results = df[mask]

    print(f"\nFound {len(results)} row(s) containing '{args.keyword}' "
          f"in {'these columns: ' + str(search_columns) if args.columns else 'any column'}")

    if len(results) == 0:
        print("No matches.")
        return

    out_path = in_path.parent / f"{in_path.stem}_search_{args.keyword.replace(' ', '_')}.xlsx"
    results.to_excel(out_path, index=False)
    print(f"Results saved -> {out_path}")

    # Quick console preview of the most relevant columns, if present
    preview_cols = [c for c in ["chunk_id", "source", "material", "target",
                                 "interaction", "category", "corresponding_sentence"]
                     if c in results.columns]
    if preview_cols:
        pd.set_option("display.max_colwidth", 60)
        print("\nPreview:")
        print(results[preview_cols].head(20).to_string())
        if len(results) > 20:
            print(f"... and {len(results) - 20} more row(s), see the saved file for the full list.")


if __name__ == "__main__":
    main()