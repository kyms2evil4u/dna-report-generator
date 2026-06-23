"""
API Aggregator: orchestrates calls to ClinVar, VEP, MyVariant, and gnomAD,
then merges all annotations back into the variant list.
Supports a 'fast mode' (MyVariant + ClinVar only) and 'full mode' (all 4 APIs).
"""

import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from .clinvar import query_clinvar_batch
from .ensembl_vep import query_vep_batch
from .myvariant import query_myvariant_batch
from .gnomad import query_gnomad_batch
# Test-patchable aliases (tests patch these names on the module)
annotate_with_clinvar = query_clinvar_batch
annotate_with_ensembl_vep = query_vep_batch
annotate_with_myvariant = query_myvariant_batch
annotate_with_gnomad = query_gnomad_batch

logger = logging.getLogger(__name__)



def _to_rsid_dict(result, original_variants):
    """Accept either a {rsid: ann_dict} dict or a list of annotated variants; always return a dict."""
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        out = {}
        for item in result:
            rsid = item.get('rsid', '')
            if rsid:
                out[rsid] = item
        return out
    return {}

def annotate_variants(
    variants: List[Dict],
    mode: str = "fast",
    max_variants: int = 500,
) -> List[Dict]:
    """
    Annotate a list of normalized variants with data from external APIs.

    Args:
        variants: List of normalized variant dicts
        mode: 'fast' (ClinVar + MyVariant only) or 'full' (all 4 APIs)
        max_variants: Maximum number of variants to annotate (top by position)

    Returns:
        Annotated variant list
    """
    if len(variants) > max_variants:
        logger.info(f"Trimming to {max_variants} variants for annotation (from {len(variants)})")
        # Prioritize known rsIDs; sort by rsid number for determinism
        variants = sorted(variants, key=lambda v: int(v["rsid"][2:]) if v["rsid"][2:].isdigit() else 999999999)
        variants = variants[:max_variants]

    logger.info(f"Starting annotation pipeline in '{mode}' mode for {len(variants)} variants")

    # Always run ClinVar and MyVariant (most informative)
    clinvar_results = {}
    myvariant_results = {}
    vep_results = {}
    gnomad_results = {}

    if mode == "fast":
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(annotate_with_clinvar, variants): "clinvar",
                executor.submit(annotate_with_myvariant, variants): "myvariant",
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    if name == "clinvar":
                        clinvar_results = _to_rsid_dict(result, variants)
                    elif name == "myvariant":
                        myvariant_results = _to_rsid_dict(result, variants)
                except Exception as e:
                    logger.error(f"{name} annotation failed: {e}")

    elif mode == "full":
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(annotate_with_clinvar, variants): "clinvar",
                executor.submit(annotate_with_myvariant, variants): "myvariant",
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    if name == "clinvar":
                        clinvar_results = _to_rsid_dict(result, variants)
                    elif name == "myvariant":
                        myvariant_results = _to_rsid_dict(result, variants)
                except Exception as e:
                    logger.error(f"{name} annotation failed: {e}")

        # VEP and gnomAD sequentially (rate limits)
        try:
            vep_results = _to_rsid_dict(annotate_with_ensembl_vep(variants), variants)
        except Exception as e:
            logger.error(f"VEP annotation failed: {e}")

        try:
            gnomad_results = _to_rsid_dict(annotate_with_gnomad(variants), variants)
        except Exception as e:
            logger.error(f"gnomAD annotation failed: {e}")

    # Merge all annotations back into variants
    annotated = []
    for v in variants:
        rsid = v["rsid"]
        v = v.copy()

        # ClinVar
        cv = clinvar_results.get(rsid, {})
        v["clinical_significance"] = cv.get("clinical_significance") or v.get("clinical_significance")
        if not v.get("gene"):
            v["gene"] = cv.get("gene")

        # MyVariant (CADD/REVEL)
        mv = myvariant_results.get(rsid, {})
        v["cadd_score"] = mv.get("cadd_score") or v.get("cadd_score")
        v["revel_score"] = mv.get("revel_score") or v.get("revel_score")
        if not v.get("gene"):
            v["gene"] = mv.get("gene")
        if not v.get("consequence"):
            v["consequence"] = mv.get("consequence")

        # VEP
        vep = vep_results.get(rsid, {})
        if not v.get("gene"):
            v["gene"] = vep.get("gene")
        if not v.get("consequence"):
            v["consequence"] = vep.get("consequence")
        v["impact"] = vep.get("impact")
        v["transcript_consequences"] = vep.get("transcript_consequences", [])

        # gnomAD
        gn = gnomad_results.get(rsid, {})
        v["gnomad_af"] = gn.get("gnomad_af") or v.get("gnomad_af")
        v["gnomad_af_popmax"] = gn.get("gnomad_af_popmax") or v.get("gnomad_af_popmax")
        v["gnomad_populations"] = gn.get("gnomad_populations", {})

        annotated.append(v)

    logger.info(f"Annotation complete for {len(annotated)} variants")
    return annotated
