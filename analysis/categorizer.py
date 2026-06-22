"""
Variant categorizer — assigns each annotated variant to one or more categories:
  1. pathogenic          — Pathogenic/Likely pathogenic clinical significance
  2. ancestry            — Population frequency-based ancestry markers
  3. traits              — Physical/sensory traits
  4. complex_disease     — Polygenic risk factors for complex diseases
  5. inherited           — Autosomal dominant/recessive carrier status
  6. pharmacogenomics    — Drug metabolism and response
  7. age_related         — Age-related disease risk (AMD, Alzheimer's, etc.)
"""

from typing import List, Dict

# ──────────────────────────────────────────────
# Known SNP catalog (curated subset, free sources)
# Maps rsid -> category metadata
# Sources: GWAS Catalog, PharmGKB (public), ClinVar
# ──────────────────────────────────────────────
KNOWN_SNP_CATALOG = {
    # ── PHARMACOGENOMICS ──────────────────────
    "rs4244285":  {"category": "pharmacogenomics", "gene": "CYP2C19", "drug": "Clopidogrel / PPIs", "effect": "Reduced metabolism (poor metabolizer)"},
    "rs4986893":  {"category": "pharmacogenomics", "gene": "CYP2C19", "drug": "Clopidogrel", "effect": "No function (*3 allele)"},
    "rs3892097":  {"category": "pharmacogenomics", "gene": "CYP2D6",  "drug": "Codeine / Antidepressants", "effect": "Reduced metabolism"},
    "rs1065852":  {"category": "pharmacogenomics", "gene": "CYP2D6",  "drug": "Tamoxifen / Codeine", "effect": "Reduced metabolism"},
    "rs1799853":  {"category": "pharmacogenomics", "gene": "CYP2C9",  "drug": "Warfarin / NSAIDs", "effect": "Reduced metabolism (*2 allele)"},
    "rs1057910":  {"category": "pharmacogenomics", "gene": "CYP2C9",  "drug": "Warfarin", "effect": "Significantly reduced metabolism (*3 allele)"},
    "rs9923231":  {"category": "pharmacogenomics", "gene": "VKORC1", "drug": "Warfarin", "effect": "Warfarin dose requirement reduced"},
    "rs2108622":  {"category": "pharmacogenomics", "gene": "CYP4F2", "drug": "Warfarin", "effect": "Higher warfarin dose requirement"},
    "rs4149056":  {"category": "pharmacogenomics", "gene": "SLCO1B1","drug": "Statins", "effect": "Increased statin myopathy risk"},
    "rs429358":   {"category": "pharmacogenomics", "gene": "APOE",   "drug": "Statins / Alzheimer's drugs", "effect": "APOE ε4 — altered drug efficacy"},

    # ── COMPLEX DISEASE RISK ──────────────────
    "rs7903146":  {"category": "complex_disease", "gene": "TCF7L2", "condition": "Type 2 Diabetes", "risk_allele": "T", "or": 1.37},
    "rs12255372": {"category": "complex_disease", "gene": "TCF7L2", "condition": "Type 2 Diabetes", "risk_allele": "T", "or": 1.30},
    "rs1801282":  {"category": "complex_disease", "gene": "PPARG",  "condition": "Type 2 Diabetes", "risk_allele": "C", "or": 1.25},
    "rs10830963": {"category": "complex_disease", "gene": "MTNR1B", "condition": "Type 2 Diabetes", "risk_allele": "G", "or": 1.15},
    "rs1333049":  {"category": "complex_disease", "gene": "CDKN2B-AS1", "condition": "Coronary Artery Disease", "risk_allele": "C", "or": 1.29},
    "rs10757278": {"category": "complex_disease", "gene": "CDKN2A/B",  "condition": "Coronary Artery Disease", "risk_allele": "G", "or": 1.26},
    "rs1801133":  {"category": "complex_disease", "gene": "MTHFR",  "condition": "Cardiovascular / Folate metabolism", "risk_allele": "T", "or": 1.20},
    "rs1800497":  {"category": "complex_disease", "gene": "ANKK1",  "condition": "Addiction / Reward pathway", "risk_allele": "T", "or": 1.15},
    "rs6265":     {"category": "complex_disease", "gene": "BDNF",   "condition": "Depression / Anxiety", "risk_allele": "T", "or": 1.10},

    # ── AGE-RELATED RISK ─────────────────────
    "rs10490924": {"category": "age_related", "gene": "ARMS2", "condition": "Age-related Macular Degeneration", "risk_allele": "T", "or": 2.73},
    "rs1061170":  {"category": "age_related", "gene": "CFH",   "condition": "Age-related Macular Degeneration", "risk_allele": "T", "or": 2.45},
    "rs3764261":  {"category": "age_related", "gene": "CETP",  "condition": "HDL Cholesterol (cardiovascular aging)", "risk_allele": "A", "or": 0.85},
    "rs2070895":  {"category": "age_related", "gene": "LIPC",  "condition": "HDL Cholesterol", "risk_allele": "A", "or": 1.12},
    "rs5174":     {"category": "age_related", "gene": "LRP8",  "condition": "Coronary Artery Disease (late onset)", "risk_allele": "C", "or": 1.18},

    # ── INHERITED / CARRIER STATUS ───────────
    "rs334":      {"category": "inherited", "gene": "HBB",   "condition": "Sickle Cell Anemia", "inheritance": "Autosomal Recessive"},
    "rs76723693": {"category": "inherited", "gene": "BRCA1", "condition": "Hereditary Breast/Ovarian Cancer", "inheritance": "Autosomal Dominant"},
    "rs80357382": {"category": "inherited", "gene": "BRCA2", "condition": "Hereditary Breast/Ovarian Cancer", "inheritance": "Autosomal Dominant"},
    "rs28897696": {"category": "inherited", "gene": "MLH1",  "condition": "Lynch Syndrome / Colorectal Cancer", "inheritance": "Autosomal Dominant"},
    "rs63750447": {"category": "inherited", "gene": "APP",   "condition": "Early-onset Alzheimer's Disease", "inheritance": "Autosomal Dominant"},

    # ── PHYSICAL TRAITS ──────────────────────
    "rs12913832": {"category": "traits", "gene": "HERC2",  "trait": "Eye Color", "effect": "Blue/light eyes (A allele)"},
    "rs1800401":  {"category": "traits", "gene": "OCA2",   "trait": "Eye Color", "effect": "Brown/dark eyes"},
    "rs1805007":  {"category": "traits", "gene": "MC1R",   "trait": "Hair Color / Skin", "effect": "Red hair / fair skin risk"},
    "rs1805008":  {"category": "traits", "gene": "MC1R",   "trait": "Hair Color / Freckles", "effect": "Red hair / freckling"},
    "rs4988235":  {"category": "traits", "gene": "LCT",    "trait": "Lactase Persistence", "effect": "Lactose tolerance in adulthood"},
    "rs1042602":  {"category": "traits", "gene": "TYR",    "trait": "Skin Pigmentation", "effect": "Lighter skin (A allele)"},
    "rs2814778":  {"category": "traits", "gene": "DARC",   "trait": "Malaria Resistance", "effect": "Duffy-null — protection from P. vivax"},
    "rs53576":    {"category": "traits", "gene": "OXTR",   "trait": "Empathy / Social behavior", "effect": "Oxytocin receptor variant"},
    "rs1799971":  {"category": "traits", "gene": "OPRM1",  "trait": "Pain sensitivity", "effect": "Altered opioid receptor affinity"},
    "rs762551":   {"category": "traits", "gene": "CYP1A2", "trait": "Caffeine metabolism", "effect": "Fast/slow caffeine metabolizer"},
    "rs2234922":  {"category": "traits", "gene": "EPHX1",  "trait": "Alcohol metabolism", "effect": "Altered epoxide hydrolase activity"},
}

PATHOGENIC_TERMS = {
    "pathogenic", "likely pathogenic", "Pathogenic", "Likely pathogenic"
}


def categorize_variants(annotated_variants: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Assign variants to categories and return a structured dict.
    Categories: pathogenic, ancestry, traits, complex_disease,
                inherited, pharmacogenomics, age_related, uncategorized
    """
    categories = {
        "pathogenic": [],
        "traits": [],
        "complex_disease": [],
        "inherited": [],
        "pharmacogenomics": [],
        "age_related": [],
        "uncategorized": [],
    }

    for v in annotated_variants:
        rsid = v.get("rsid", "")
        assigned = False

        # 1. Check known SNP catalog first
        if rsid in KNOWN_SNP_CATALOG:
            info = KNOWN_SNP_CATALOG[rsid]
            v = {**v, **info}  # merge catalog metadata
            cat = info.get("category", "uncategorized")
            categories.setdefault(cat, []).append(v)
            assigned = True

        # 2. Pathogenic from ClinVar annotation (even if not in catalog)
        if not assigned:
            sig = v.get("clinical_significance", "") or ""
            if any(term in sig for term in PATHOGENIC_TERMS):
                v["category"] = "pathogenic"
                categories["pathogenic"].append(v)
                assigned = True

        # 3. High CADD score -> flag as potential pathogenic
        if not assigned:
            cadd = v.get("cadd_score")
            if cadd and float(cadd) >= 20:
                v["category"] = "complex_disease"
                categories["complex_disease"].append(v)
                assigned = True

        # 4. Everything else -> uncategorized
        if not assigned:
            v["category"] = "uncategorized"
            categories["uncategorized"].append(v)

    # Sort pathogenic by CADD score desc
    categories["pathogenic"].sort(
        key=lambda v: float(v.get("cadd_score") or 0), reverse=True
    )

    return categories
