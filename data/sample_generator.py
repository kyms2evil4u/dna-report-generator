"""
Sample variant generator for demo/testing purposes.
Produces a realistic set of known SNPs covering all analysis categories.
"""

from typing import List, Dict


SAMPLE_VARIANTS = [
    # ── Pharmacogenomics ────────────────────────────────────────────────────
    {"rsid": "rs4244285",  "chromosome": "10", "position": 96541616,  "genotype": "AG", "allele1": "A", "allele2": "G"},
    {"rsid": "rs4986893",  "chromosome": "10", "position": 96540410,  "genotype": "GA", "allele1": "G", "allele2": "A"},
    {"rsid": "rs3892097",  "chromosome": "22", "position": 42524175,  "genotype": "GA", "allele1": "G", "allele2": "A"},
    {"rsid": "rs1065852",  "chromosome": "22", "position": 42522613,  "genotype": "CT", "allele1": "C", "allele2": "T"},
    {"rsid": "rs1799853",  "chromosome": "10", "position": 96702047,  "genotype": "CT", "allele1": "C", "allele2": "T"},
    {"rsid": "rs1057910",  "chromosome": "10", "position": 96741053,  "genotype": "AC", "allele1": "A", "allele2": "C"},
    {"rsid": "rs9923231",  "chromosome": "16", "position": 31096368,  "genotype": "CT", "allele1": "C", "allele2": "T"},
    {"rsid": "rs4149056",  "chromosome": "12", "position": 21178615,  "genotype": "TC", "allele1": "T", "allele2": "C"},
    {"rsid": "rs762551",   "chromosome": "15", "position": 75041917,  "genotype": "AC", "allele1": "A", "allele2": "C"},
    {"rsid": "rs2108622",  "chromosome": "19", "position": 15990431,  "genotype": "CT", "allele1": "C", "allele2": "T"},

    # ── Complex Disease Risk ─────────────────────────────────────────────────
    {"rsid": "rs7903146",  "chromosome": "10", "position": 114758349, "genotype": "CT", "allele1": "C", "allele2": "T"},
    {"rsid": "rs12255372", "chromosome": "10", "position": 114773809, "genotype": "GT", "allele1": "G", "allele2": "T"},
    {"rsid": "rs1801282",  "chromosome": "3",  "position": 12393125,  "genotype": "CG", "allele1": "C", "allele2": "G"},
    {"rsid": "rs10830963", "chromosome": "11", "position": 92975544,  "genotype": "CG", "allele1": "C", "allele2": "G"},
    {"rsid": "rs1333049",  "chromosome": "9",  "position": 22125504,  "genotype": "CC", "allele1": "C", "allele2": "C"},
    {"rsid": "rs10757278", "chromosome": "9",  "position": 22098574,  "genotype": "AG", "allele1": "A", "allele2": "G"},
    {"rsid": "rs1801133",  "chromosome": "1",  "position": 11856378,  "genotype": "CT", "allele1": "C", "allele2": "T"},
    {"rsid": "rs1800497",  "chromosome": "11", "position": 113270828, "genotype": "CT", "allele1": "C", "allele2": "T"},
    {"rsid": "rs6265",     "chromosome": "11", "position": 27658369,  "genotype": "CT", "allele1": "C", "allele2": "T"},

    # ── Age-related Risk ─────────────────────────────────────────────────────
    {"rsid": "rs10490924", "chromosome": "10", "position": 124214448, "genotype": "GT", "allele1": "G", "allele2": "T"},
    {"rsid": "rs1061170",  "chromosome": "1",  "position": 196659237, "genotype": "TC", "allele1": "T", "allele2": "C"},
    {"rsid": "rs3764261",  "chromosome": "16", "position": 56987676,  "genotype": "CA", "allele1": "C", "allele2": "A"},

    # ── Physical Traits ──────────────────────────────────────────────────────
    {"rsid": "rs12913832", "chromosome": "15", "position": 28365618,  "genotype": "AG", "allele1": "A", "allele2": "G"},
    {"rsid": "rs1805007",  "chromosome": "16", "position": 89919709,  "genotype": "CT", "allele1": "C", "allele2": "T"},
    {"rsid": "rs4988235",  "chromosome": "2",  "position": 136608646, "genotype": "CT", "allele1": "C", "allele2": "T"},
    {"rsid": "rs53576",    "chromosome": "3",  "position": 8762685,   "genotype": "AG", "allele1": "A", "allele2": "G"},
    {"rsid": "rs1799971",  "chromosome": "6",  "position": 154360797, "genotype": "AG", "allele1": "A", "allele2": "G"},
    {"rsid": "rs1042602",  "chromosome": "11", "position": 88911696,  "genotype": "AC", "allele1": "A", "allele2": "C"},
    {"rsid": "rs2814778",  "chromosome": "1",  "position": 159175354, "genotype": "CT", "allele1": "C", "allele2": "T"},

    # ── Inherited Conditions ─────────────────────────────────────────────────
    {"rsid": "rs334",      "chromosome": "11", "position": 5246696,   "genotype": "AT", "allele1": "A", "allele2": "T"},

    # ── Ancestry AIMs ────────────────────────────────────────────────────────
    {"rsid": "rs1426654",  "chromosome": "15", "position": 48426484,  "genotype": "AG", "allele1": "A", "allele2": "G"},
    {"rsid": "rs16891982", "chromosome": "5",  "position": 33951693,  "genotype": "CG", "allele1": "C", "allele2": "G"},
    {"rsid": "rs1834640",  "chromosome": "15", "position": 28230318,  "genotype": "AG", "allele1": "A", "allele2": "G"},
    {"rsid": "rs3827760",  "chromosome": "2",  "position": 108962862, "genotype": "AA", "allele1": "A", "allele2": "A"},
    {"rsid": "rs4988235",  "chromosome": "2",  "position": 136608646, "genotype": "CT", "allele1": "C", "allele2": "T"},

    # ── APOE (Alzheimer's / Cardiovascular) ──────────────────────────────────
    {"rsid": "rs429358",   "chromosome": "19", "position": 44908684,  "genotype": "CT", "allele1": "C", "allele2": "T"},
    {"rsid": "rs7412",     "chromosome": "19", "position": 44908822,  "genotype": "CC", "allele1": "C", "allele2": "C"},
]


def generate_sample_variants() -> List[Dict]:
    """Return a copy of the sample variants with source_format tagged."""
    return [
        {**v, "source_format": "sample"}
        for v in SAMPLE_VARIANTS
    ]
