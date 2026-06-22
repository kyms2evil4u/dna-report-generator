"""
Polygenic Risk Scorer for complex diseases.
Computes relative risk scores for a set of common conditions
using published GWAS odds ratios.
"""

from typing import List, Dict

# Polygenic risk score definitions
# Format: condition -> [{"rsid", "risk_allele", "log_or", "weight"}]
PRS_DEFINITIONS = {
    "Type 2 Diabetes": {
        "description": "Insulin resistance and blood sugar regulation",
        "snps": [
            {"rsid": "rs7903146",  "risk_allele": "T", "log_or": 0.314, "weight": 1.0},
            {"rsid": "rs12255372", "risk_allele": "T", "log_or": 0.262, "weight": 1.0},
            {"rsid": "rs1801282",  "risk_allele": "C", "log_or": 0.223, "weight": 1.0},
            {"rsid": "rs10830963", "risk_allele": "G", "log_or": 0.140, "weight": 1.0},
        ],
        "baseline_risk": 0.11,  # 11% lifetime risk
    },
    "Coronary Artery Disease": {
        "description": "Atherosclerosis and heart disease risk",
        "snps": [
            {"rsid": "rs1333049",  "risk_allele": "C", "log_or": 0.255, "weight": 1.0},
            {"rsid": "rs10757278", "risk_allele": "G", "log_or": 0.231, "weight": 1.0},
            {"rsid": "rs1801133",  "risk_allele": "T", "log_or": 0.182, "weight": 0.8},
        ],
        "baseline_risk": 0.07,
    },
    "Atrial Fibrillation": {
        "description": "Irregular heart rhythm",
        "snps": [
            {"rsid": "rs2200733",  "risk_allele": "T", "log_or": 0.470, "weight": 1.0},
            {"rsid": "rs10033464", "risk_allele": "T", "log_or": 0.240, "weight": 1.0},
        ],
        "baseline_risk": 0.025,
    },
    "Breast Cancer": {
        "description": "Risk of hormone-receptor positive breast cancer",
        "snps": [
            {"rsid": "rs13387042", "risk_allele": "A", "log_or": 0.182, "weight": 1.0},
            {"rsid": "rs4973768",  "risk_allele": "T", "log_or": 0.154, "weight": 1.0},
        ],
        "baseline_risk": 0.125,
    },
    "Prostate Cancer": {
        "description": "Risk of prostate adenocarcinoma",
        "snps": [
            {"rsid": "rs1859962",  "risk_allele": "G", "log_or": 0.225, "weight": 1.0},
            {"rsid": "rs16901979", "risk_allele": "A", "log_or": 0.470, "weight": 1.0},
        ],
        "baseline_risk": 0.11,
    },
}

import math


def _count_risk_alleles(variant: Dict, risk_allele: str) -> int:
    """Count how many copies of the risk allele the user carries."""
    a1 = (variant.get("allele1") or "").upper()
    a2 = (variant.get("allele2") or "").upper()
    risk_allele = risk_allele.upper()
    return sum(1 for a in [a1, a2] if a == risk_allele)


def compute_risk_scores(variants: List[Dict]) -> List[Dict]:
    """
    Compute PRS for each defined condition.
    Returns a list of risk score objects.
    """
    variant_map = {v["rsid"]: v for v in variants}
    results = []

    for condition, definition in PRS_DEFINITIONS.items():
        prs = 0.0
        snps_found = 0
        snp_details = []

        for snp_def in definition["snps"]:
            rsid = snp_def["rsid"]
            if rsid not in variant_map:
                continue

            v = variant_map[rsid]
            risk_count = _count_risk_alleles(v, snp_def["risk_allele"])

            # Weighted allele dosage model
            contribution = risk_count * snp_def["log_or"] * snp_def["weight"]
            prs += contribution
            snps_found += 1

            snp_details.append({
                "rsid": rsid,
                "gene": v.get("gene") or snp_def.get("gene", ""),
                "risk_allele": snp_def["risk_allele"],
                "your_genotype": v.get("genotype", ""),
                "risk_copies": risk_count,
                "log_or": snp_def["log_or"],
                "contribution": round(contribution, 4),
            })

        if snps_found == 0:
            # No relevant SNPs found — skip this condition
            continue

        # Convert PRS to relative risk (approximate)
        # Relative risk = exp(PRS) relative to 0-risk baseline
        relative_risk = math.exp(prs)
        adjusted_risk = definition["baseline_risk"] * relative_risk

        # Cap at 1.0
        adjusted_risk = min(adjusted_risk, 0.99)

        # Risk tier
        if relative_risk < 0.8:
            risk_tier = "below_average"
            risk_label = "Below Average"
        elif relative_risk < 1.2:
            risk_tier = "average"
            risk_label = "Average"
        elif relative_risk < 1.5:
            risk_tier = "elevated"
            risk_label = "Slightly Elevated"
        elif relative_risk < 2.0:
            risk_tier = "high"
            risk_label = "Elevated"
        else:
            risk_tier = "high"
            risk_label = "High"

        results.append({
            "condition": condition,
            "description": definition["description"],
            "prs": round(prs, 4),
            "relative_risk": round(relative_risk, 3),
            "adjusted_risk_pct": round(adjusted_risk * 100, 1),
            "baseline_risk_pct": round(definition["baseline_risk"] * 100, 1),
            "risk_tier": risk_tier,
            "risk_label": risk_label,
            "snps_analyzed": snps_found,
            "snps_total": len(definition["snps"]),
            "snp_details": snp_details,
        })

    # Sort by relative risk descending
    results.sort(key=lambda x: x["relative_risk"], reverse=True)
    return results
