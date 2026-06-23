"""
MyHeritage DNA raw data parser.
Format: CSV with comment lines starting with '#' or '##'
Columns: RSID, CHROMOSOME, POSITION, RESULT
"""

import csv
from typing import List, Dict


def parse_myheritage(filepath: str) -> List[Dict]:
    """
    Parse a MyHeritage raw data file.
    """
    rows = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        # Skip comment lines
        lines = []
        for line in f:
            if not line.startswith("#"):
                lines.append(line)

    reader = csv.DictReader(lines)
    for row in reader:
        # Normalize keys (strip whitespace, upper)
        row = {k.strip().upper(): v.strip() for k, v in row.items()}

        rsid = row.get("RSID", "").strip()
        if not rsid or rsid.upper() == "RSID":
            continue

        result = row.get("RESULT", "").upper().strip()
        a1 = result[0] if len(result) >= 1 else None
        a2 = result[1] if len(result) >= 2 else None

        rows.append({
            "rsid": rsid,
            "chromosome": _normalize_chrom(row.get("CHROMOSOME", "")),
            "position": _safe_int(row.get("POSITION", "")),
            "genotype": result,
            "allele1": a1,
            "allele2": a2,
            "source_format": "myheritage",
        })

    return rows


def _normalize_chrom(chrom: str) -> str:
    chrom = chrom.upper().replace("CHR", "").strip()
    if chrom == "M":
        return "MT"
    return chrom


def _safe_int(val: str):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
