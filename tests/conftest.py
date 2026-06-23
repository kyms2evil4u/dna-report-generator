"""
Pytest configuration — shared fixtures used across all test modules.
"""

import uuid
import pytest

from app import app as flask_app


# ── Flask test client ─────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    with flask_app.test_client() as c:
        yield c


# ── Minimal normalized variant list ──────────────────────────────────────────
@pytest.fixture
def minimal_variants():
    return [
        {"rsid": "rs4244285",  "chromosome": "10", "position": 96541616,  "genotype": "AG", "allele1": "A", "allele2": "G"},
        {"rsid": "rs7903146",  "chromosome": "10", "position": 114758349, "genotype": "CT", "allele1": "C", "allele2": "T"},
        {"rsid": "rs12913832", "chromosome": "15", "position": 28365618,  "genotype": "AG", "allele1": "A", "allele2": "G"},
        {"rsid": "rs429358",   "chromosome": "19", "position": 44908684,  "genotype": "CT", "allele1": "C", "allele2": "T"},
        {"rsid": "rs1426654",  "chromosome": "15", "position": 48426484,  "genotype": "AG", "allele1": "A", "allele2": "G"},
        {"rsid": "rs334",      "chromosome": "11", "position": 5246696,   "genotype": "AT", "allele1": "A", "allele2": "T"},
        {"rsid": "rs9923231",  "chromosome": "16", "position": 31096368,  "genotype": "CT", "allele1": "C", "allele2": "T"},
    ]


# ── Mock annotated variant (what the API aggregator returns) ──────────────────
@pytest.fixture
def annotated_variants():
    return [
        {
            "rsid": "rs4244285",
            "chromosome": "10",
            "position": 96541616,
            "genotype": "AG",
            "allele1": "A",
            "allele2": "G",
            "gene": "CYP2C19",
            "consequence": "splice_region_variant",
            "clinical_significance": "pathogenic",
            "cadd_score": 22.4,
            "revel_score": 0.12,
            "gnomad_af": 0.153,
            "gnomad_af_popmax": 0.29,
            "category": "pharmacogenomics",
            "source_format": "23andme",
        },
        {
            "rsid": "rs7903146",
            "chromosome": "10",
            "position": 114758349,
            "genotype": "CT",
            "allele1": "C",
            "allele2": "T",
            "gene": "TCF7L2",
            "consequence": "intron_variant",
            "clinical_significance": "risk_factor",
            "cadd_score": 12.1,
            "revel_score": None,
            "gnomad_af": 0.298,
            "gnomad_af_popmax": 0.35,
            "category": "disease_risk",
            "source_format": "23andme",
        },
        {
            "rsid": "rs12913832",
            "chromosome": "15",
            "position": 28365618,
            "genotype": "AG",
            "allele1": "A",
            "allele2": "G",
            "gene": "HERC2",
            "consequence": "intron_variant",
            "clinical_significance": "benign",
            "cadd_score": 1.2,
            "revel_score": None,
            "gnomad_af": 0.44,
            "gnomad_af_popmax": 0.72,
            "category": "traits",
            "source_format": "23andme",
        },
        {
            "rsid": "rs429358",
            "chromosome": "19",
            "position": 44908684,
            "genotype": "CT",
            "allele1": "C",
            "allele2": "T",
            "gene": "APOE",
            "consequence": "missense_variant",
            "clinical_significance": "pathogenic",
            "cadd_score": 28.9,
            "revel_score": 0.61,
            "gnomad_af": 0.153,
            "gnomad_af_popmax": 0.22,
            "category": "disease_risk",
            "source_format": "23andme",
        },
        {
            "rsid": "rs1426654",
            "chromosome": "15",
            "position": 48426484,
            "genotype": "AG",
            "allele1": "A",
            "allele2": "G",
            "gene": "SLC24A5",
            "consequence": "missense_variant",
            "clinical_significance": "benign",
            "cadd_score": 4.5,
            "revel_score": 0.03,
            "gnomad_af": 0.71,
            "gnomad_af_popmax": 0.98,
            "category": "ancestry",
            "source_format": "23andme",
        },
    ]


# ── Full mock report (what the pipeline returns) ──────────────────────────────
@pytest.fixture
def mock_report(annotated_variants):
    return {
        "report_id":    str(uuid.uuid4()),
        "name":         "Test User",
        "generated_at": "June 22, 2026 at 10:00",
        "summary": {
            "format":             "23andme",
            "mode":               "fast",
            "total_variants":     len(annotated_variants),
            "annotated_variants": len(annotated_variants),
            "pathogenic_count":   2,
        },
        "ancestry": {
            "top_population":    "European",
            "composition": [
                {"population": "European",          "percentage": 68.0},
                {"population": "East Asian",        "percentage": 18.0},
                {"population": "African",           "percentage": 9.0},
                {"population": "South Asian",       "percentage": 5.0},
            ],
        },
        "risk_scores": [
            {
                "condition": "Type 2 Diabetes",
                "risk_tier": "elevated",
                "risk_label": "Elevated Risk",
                "relative_risk": 1.35,
                "adjusted_risk_pct": 14.9,
                "baseline_risk_pct": 11.0,
                "prs": 0.42,
                "snps_analyzed": 1,
                "snps_total": 5,
            }
        ],
        "pharmacogenomics": [
            {
                "rsid":          "rs4244285",
                "gene":          "CYP2C19",
                "star_allele":   "*2",
                "your_genotype": "AG",
                "drugs_affected": ["clopidogrel", "omeprazole"],
                "effect":        "Poor metabolizer — reduced drug activation",
                "severity":      "high",
            }
        ],
        "traits": [
            {
                "trait":        "Eye Color",
                "rsid":         "rs12913832",
                "your_result":  "Likely brown/hazel",
                "confidence":   "high",
                "description":  "The AG genotype at rs12913832 is associated with brown or hazel eyes.",
            }
        ],
        "categories": {
            "pathogenic":        [v for v in annotated_variants if v["clinical_significance"] == "pathogenic"],
            "pharmacogenomics":  [v for v in annotated_variants if v["category"] == "pharmacogenomics"],
            "disease_risk":      [v for v in annotated_variants if v["category"] == "disease_risk"],
            "traits":            [v for v in annotated_variants if v["category"] == "traits"],
            "ancestry":          [v for v in annotated_variants if v["category"] == "ancestry"],
        },
    }
