"""
23andMe raw data parser.
Format: TSV with comment lines starting with '#'
Columns: rsid, chromosome, position, genotype
"""

import re
from typing import List, Dict


def parse_23andme(filepath: str) -> List[Dict]:
    """
    Parse a 23andMe raw data file and return a list of normalized variant dicts.
    """
    rows = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"\t", line)
            if len(parts) < 4:
                continue
            rsid, chrom, pos, genotype = parts[0], parts[1], parts[2], parts[3]

            # Skip header row if present
            if rsid.lower() == "rsid":
                continue

            # Skip internal IDs (i-prefixed, non-dbSNP)
            if rsid.startswith("i") and not rsid.startswith("rs"):
                continue

            rows.append({
                "rsid": rsid.strip(),
                "chromosome": _normalize_chrom(chrom.strip()),
                "position": _safe_int(pos.strip()),
                "genotype": genotype.strip().upper(),
                "allele1": genotype[0] if len(genotype) >= 1 else None,
                "allele2": genotype[1] if len(genotype) >= 2 else None,
                "source_format": "23andme",
            })

    return rows


def _normalize_chrom(chrom: str) -> str:
    """Normalize chromosome names to standard format (1-22, X, Y, MT)."""
    chrom = chrom.upper().replace("CHR", "")
    if chrom == "M":
        return "MT"
    return chrom


def _safe_int(val: str):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
