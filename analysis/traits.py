"""
Physical and sensory traits analysis.
"""

from typing import List, Dict

TRAITS_CATALOG = {
    "rs12913832": {
        "trait": "Eye Color",
        "gene": "HERC2/OCA2",
        "description": "Strong predictor of blue vs. brown eye color",
        "interpretations": {
            "AA": "Likely blue or green eyes",
            "AG": "Blue, green, or hazel eyes",
            "GG": "Likely brown eyes",
        },
        "icon": "👁️",
    },
    "rs1805007": {
        "trait": "Hair Color",
        "gene": "MC1R",
        "description": "MC1R variant associated with red hair and fair skin",
        "interpretations": {
            "TT": "Two copies — likely red hair, very fair skin",
            "CT": "One copy — possible red tint, freckles, sun sensitivity",
            "CC": "No copies — unlikely to have red hair",
        },
        "icon": "💇",
    },
    "rs4988235": {
        "trait": "Lactose Tolerance",
        "gene": "LCT",
        "description": "Determines ability to digest lactose into adulthood",
        "interpretations": {
            "TT": "Likely lactose tolerant",
            "CT": "Likely lactose tolerant (one copy)",
            "CC": "Likely lactose intolerant",
        },
        "icon": "🥛",
    },
    "rs762551": {
        "trait": "Caffeine Metabolism",
        "gene": "CYP1A2",
        "description": "How quickly you metabolize caffeine",
        "interpretations": {
            "AA": "Fast caffeine metabolizer",
            "AC": "Intermediate caffeine metabolism",
            "CC": "Slow caffeine metabolizer — higher cardiovascular sensitivity",
        },
        "icon": "☕",
    },
    "rs53576": {
        "trait": "Empathy & Social Behavior",
        "gene": "OXTR",
        "description": "Oxytocin receptor variant linked to empathy and social responsiveness",
        "interpretations": {
            "GG": "Higher empathy, prosocial behavior tendency",
            "AG": "Intermediate",
            "AA": "Lower trait empathy, associated with higher stress reactivity",
        },
        "icon": "🤝",
    },
    "rs1799971": {
        "trait": "Pain Sensitivity",
        "gene": "OPRM1",
        "description": "Mu-opioid receptor variant affecting pain perception",
        "interpretations": {
            "AA": "Standard pain sensitivity",
            "AG": "Possibly higher pain threshold",
            "GG": "Higher pain threshold reported in some studies",
        },
        "icon": "⚡",
    },
    "rs1042602": {
        "trait": "Skin Pigmentation",
        "gene": "TYR",
        "description": "Tyrosinase variant associated with skin tone",
        "interpretations": {
            "AA": "Lighter skin pigmentation",
            "AC": "Intermediate",
            "CC": "Standard pigmentation",
        },
        "icon": "🌞",
    },
    "rs2814778": {
        "trait": "Malaria Resistance",
        "gene": "DARC/ACKR1",
        "description": "Duffy-null variant — near-complete protection from Plasmodium vivax malaria",
        "interpretations": {
            "TT": "Homozygous Duffy-null — strong protection from P. vivax",
            "CT": "Heterozygous — partial protection",
            "CC": "Standard Duffy-positive — no special protection",
        },
        "icon": "🛡️",
    },
}


def analyze_traits(variants: List[Dict]) -> List[Dict]:
    """
    Returns trait findings for the user's variants.
    """
    variant_map = {v["rsid"]: v for v in variants}
    results = []

    for rsid, trait_def in TRAITS_CATALOG.items():
        if rsid not in variant_map:
            continue

        v = variant_map[rsid]
        genotype = v.get("genotype", "")
        interpretation = trait_def["interpretations"].get(
            genotype,
            trait_def["interpretations"].get(genotype[::-1], "Interpretation not available for this genotype")
        )

        results.append({
            "rsid": rsid,
            "trait": trait_def["trait"],
            "gene": trait_def["gene"],
            "description": trait_def["description"],
            "your_genotype": genotype,
            "interpretation": interpretation,
            "icon": trait_def["icon"],
        })

    return results
