"""
Normalizes parsed variants from any source format into a unified schema.
Deduplicates, filters low-quality entries, and adds metadata fields.
"""

from typing import List, Dict
import re


# Chromosomes we care about
VALID_CHROMS = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}

# Valid nucleotide characters (IUPAC + indel markers)
VALID_BASES = set("ACGTNID.-")


def normalize_variants(raw_variants: List[Dict]) -> List[Dict]:
    """
    Takes raw parsed variants and returns a clean, deduplicated list.
    Each variant is guaranteed to have all required fields.
    """
    normalized = []
    seen_rsids = set()

    for v in raw_variants:
        # Required field check
        rsid = v.get("rsid", "").strip()
        if not rsid or not rsid.startswith("rs"):
            continue

        # Deduplicate by rsid
        if rsid in seen_rsids:
            continue
        seen_rsids.add(rsid)

        # Chromosome validation
        chrom = str(v.get("chromosome", "")).upper()
        if chrom not in VALID_CHROMS:
            continue

        # Position
        position = v.get("position")
        if position is None or position <= 0:
            continue

        # Genotype cleanup
        genotype = str(v.get("genotype", "")).upper().strip()
        genotype = re.sub(r"[^ACGTNID.\-]", "", genotype)
        if not genotype or "--" in genotype or genotype in ("00", "NN"):
            continue

        a1 = v.get("allele1") or (genotype[0] if len(genotype) >= 1 else None)
        a2 = v.get("allele2") or (genotype[1] if len(genotype) >= 2 else None)

        normalized.append({
            "rsid": rsid,
            "chromosome": chrom,
            "position": int(position),
            "genotype": genotype,
            "allele1": str(a1).upper() if a1 else None,
            "allele2": str(a2).upper() if a2 else None,
            "ref": v.get("ref"),
            "alt": v.get("alt"),
            "source_format": v.get("source_format", "unknown"),
            # Placeholders for annotation data (filled by API layer)
            "clinical_significance": None,
            "gene": None,
            "consequence": None,
            "cadd_score": None,
            "revel_score": None,
            "gnomad_af": None,
            "gnomad_af_popmax": None,
            "category": None,
        })

    return normalized
