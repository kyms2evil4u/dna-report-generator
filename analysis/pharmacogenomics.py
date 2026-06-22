"""
Pharmacogenomics analysis.
Identifies drug-gene interactions based on known PGx variants.
"""

from typing import List, Dict

PGX_VARIANTS = {
    "rs4244285":  {"gene": "CYP2C19", "star_allele": "*2", "drugs": ["Clopidogrel", "Omeprazole", "Escitalopram"], "effect": "Poor metabolizer — reduced drug activation", "severity": "high"},
    "rs4986893":  {"gene": "CYP2C19", "star_allele": "*3", "drugs": ["Clopidogrel"], "effect": "No function — severely reduced metabolism", "severity": "high"},
    "rs3892097":  {"gene": "CYP2D6",  "star_allele": "*4", "drugs": ["Codeine", "Tramadol", "Metoprolol", "Tamoxifen"], "effect": "Poor metabolizer", "severity": "high"},
    "rs1065852":  {"gene": "CYP2D6",  "star_allele": "*10","drugs": ["Antidepressants", "Antipsychotics", "Codeine"], "effect": "Reduced metabolism", "severity": "moderate"},
    "rs1799853":  {"gene": "CYP2C9",  "star_allele": "*2", "drugs": ["Warfarin", "Ibuprofen", "Phenytoin"], "effect": "Reduced metabolism — bleeding risk with warfarin", "severity": "high"},
    "rs1057910":  {"gene": "CYP2C9",  "star_allele": "*3", "drugs": ["Warfarin", "Celecoxib", "Losartan"], "effect": "Significantly reduced metabolism", "severity": "high"},
    "rs9923231":  {"gene": "VKORC1", "star_allele": "-1639G>A", "drugs": ["Warfarin"], "effect": "Lower warfarin dose required", "severity": "moderate"},
    "rs4149056":  {"gene": "SLCO1B1","star_allele": "c.521T>C", "drugs": ["Simvastatin", "Atorvastatin", "Rosuvastatin"], "effect": "Increased myopathy risk with statins", "severity": "moderate"},
    "rs762551":   {"gene": "CYP1A2", "star_allele": "*1F",      "drugs": ["Caffeine", "Clozapine", "Theophylline"], "effect": "Rapid caffeine metabolizer (AA) or slow (CC)", "severity": "low"},
    "rs2108622":  {"gene": "CYP4F2", "star_allele": "V433M",    "drugs": ["Warfarin", "Acenocoumarol"], "effect": "Higher warfarin dose requirement", "severity": "moderate"},
}


def analyze_pharmacogenomics(variants: List[Dict]) -> List[Dict]:
    """
    Returns PGx findings for the user's variants.
    """
    variant_map = {v["rsid"]: v for v in variants}
    results = []

    for rsid, pgx_def in PGX_VARIANTS.items():
        if rsid not in variant_map:
            continue

        v = variant_map[rsid]
        genotype = v.get("genotype", "")

        results.append({
            "rsid": rsid,
            "gene": pgx_def["gene"],
            "star_allele": pgx_def["star_allele"],
            "your_genotype": genotype,
            "drugs_affected": pgx_def["drugs"],
            "effect": pgx_def["effect"],
            "severity": pgx_def["severity"],
            "chromosome": v.get("chromosome"),
            "position": v.get("position"),
        })

    # Sort by severity
    severity_order = {"high": 0, "moderate": 1, "low": 2}
    results.sort(key=lambda x: severity_order.get(x["severity"], 3))
    return results
