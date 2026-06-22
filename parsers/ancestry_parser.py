"""
AncestryDNA raw data parser.
Format: TSV with comment lines starting with '#'
Columns: rsid, chromosome, position, allele1, allele2
"""

import re
from typing import List, Dict


def parse_ancestry(filepath: str) -> List[Dict]:
    """
    Parse an AncestryDNA raw data file.
    """
    rows = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"\t|,", line)
            if len(parts) < 5:
                continue
            rsid, chrom, pos, a1, a2 = (
                parts[0], parts[1], parts[2], parts[3], parts[4]
            )
            if rsid.lower() == "rsid":
                continue

            a1 = a1.strip().upper()
            a2 = a2.strip().upper()
            genotype = a1 + a2

            rows.append({
                "rsid": rsid.strip(),
                "chromosome": _normalize_chrom(chrom.strip()),
                "position": _safe_int(pos.strip()),
                "genotype": genotype,
                "allele1": a1 if a1 not in ("0", "") else None,
                "allele2": a2 if a2 not in ("0", "") else None,
                "source_format": "ancestry",
            })

    return rows


def _normalize_chrom(chrom: str) -> str:
    chrom = chrom.upper().replace("CHR", "")
    if chrom == "M":
        return "MT"
    return chrom


def _safe_int(val: str):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
