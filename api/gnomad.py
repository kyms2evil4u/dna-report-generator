"""
gnomAD v4 GraphQL API integration.
Population allele frequencies, no authentication required.
"""

import requests
import logging
import time
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

GNOMAD_GRAPHQL_URL = "https://gnomad.broadinstitute.org/api"

# gnomAD population labels
POPULATION_LABELS = {
    "afr": "African/African American",
    "amr": "Latino/Admixed American",
    "asj": "Ashkenazi Jewish",
    "eas": "East Asian",
    "fin": "Finnish",
    "mid": "Middle Eastern",
    "nfe": "Non-Finnish European",
    "sas": "South Asian",
    "remaining": "Other",
}


GNOMAD_QUERY = """
query VariantFrequencies($variantId: String!, $dataset: DatasetId!) {
  variant(variantId: $variantId, dataset: $dataset) {
    variantId
    rsids
    genome {
      af
      ac
      an
      homozygote_count
      populations {
        id
        af
        ac
        an
      }
    }
    exome {
      af
      ac
      an
      homozygote_count
      populations {
        id
        af
        ac
        an
      }
    }
    clinvar {
      clinical_significance
    }
  }
}
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def _query_gnomad_variant(variant_id: str, dataset: str = "gnomad_r4") -> Optional[Dict]:
    """Query gnomAD for a single variant by its ID (chrom-pos-ref-alt format)."""
    payload = {
        "query": GNOMAD_QUERY,
        "variables": {"variantId": variant_id, "dataset": dataset},
    }
    try:
        r = requests.post(GNOMAD_GRAPHQL_URL, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        return data.get("data", {}).get("variant")
    except Exception as e:
        logger.debug(f"gnomAD query failed for {variant_id}: {e}")
        return None


def _format_variant_id(variant: Dict) -> Optional[str]:
    """Convert variant dict to gnomAD variant ID format: chrom-pos-ref-alt"""
    chrom = variant.get("chromosome", "")
    pos = variant.get("position")
    ref = variant.get("ref") or variant.get("allele1", "")
    alt = variant.get("alt") or variant.get("allele2", "")

    if not all([chrom, pos, ref, alt]):
        return None

    # gnomAD uses numeric chromosomes, no 'chr' prefix
    chrom = chrom.replace("CHR", "").upper()
    return f"{chrom}-{pos}-{ref}-{alt}"


def _extract_frequencies(gnomad_data: Optional[Dict]) -> Dict:
    """Extract population frequencies from gnomAD response."""
    result = {
        "gnomad_af": None,
        "gnomad_af_popmax": None,
        "gnomad_homozygotes": None,
        "gnomad_populations": {},
    }

    if not gnomad_data:
        return result

    # Prefer genome data, fall back to exome
    freq_data = gnomad_data.get("genome") or gnomad_data.get("exome")
    if not freq_data:
        return result

    result["gnomad_af"] = freq_data.get("af")
    result["gnomad_homozygotes"] = freq_data.get("homozygote_count")

    # Extract per-population frequencies
    pops = freq_data.get("populations", [])
    if pops:
        pop_afs = {}
        for pop in pops:
            pop_id = pop.get("id", "").lower().rstrip("_xx")  # strip sex suffix
            if pop_id in POPULATION_LABELS:
                af = pop.get("af", 0) or 0
                pop_afs[pop_id] = {
                    "label": POPULATION_LABELS[pop_id],
                    "af": af,
                    "ac": pop.get("ac"),
                    "an": pop.get("an"),
                }

        result["gnomad_populations"] = pop_afs

        # Calculate popmax (highest AF across populations)
        if pop_afs:
            popmax_entry = max(pop_afs.values(), key=lambda x: x.get("af", 0) or 0)
            result["gnomad_af_popmax"] = popmax_entry.get("af")

    return result


def query_gnomad_batch(variants: List[Dict], batch_size: int = 50) -> Dict[str, Dict]:
    """
    Query gnomAD for population allele frequencies.
    Returns dict mapping rsid -> frequency data.
    Note: gnomAD requires chrom-pos-ref-alt format, so we need ref/alt.
    """
    results = {}
    # Only query variants that have ref/alt data
    queryable = [v for v in variants if v.get("ref") and v.get("alt")]
    non_queryable = [v for v in variants if not (v.get("ref") and v.get("alt"))]

    # For non-queryable (e.g. from 23andMe without ref/alt), return empty
    for v in non_queryable:
        results[v["rsid"]] = {
            "gnomad_af": None,
            "gnomad_af_popmax": None,
            "gnomad_populations": {},
        }

    logger.info(f"Querying gnomAD for {len(queryable)} variants with ref/alt data...")

    for i in range(0, len(queryable), batch_size):
        batch = queryable[i : i + batch_size]
        for variant in batch:
            time.sleep(0.3)
            rsid = variant["rsid"]
            variant_id = _format_variant_id(variant)
            if not variant_id:
                results[rsid] = {"gnomad_af": None, "gnomad_af_popmax": None, "gnomad_populations": {}}
                continue

            try:
                gnomad_data = _query_gnomad_variant(variant_id)
                results[rsid] = _extract_frequencies(gnomad_data)
            except Exception as e:
                logger.error(f"gnomAD lookup failed for {rsid}: {e}")
                results[rsid] = {"gnomad_af": None, "gnomad_af_popmax": None, "gnomad_populations": {}}

        logger.info(f"gnomAD: processed {min(i + batch_size, len(queryable))}/{len(queryable)}")

    return results


def annotate_with_gnomad(variants):
    """Returns variants as a list, annotated by this module (test-friendly wrapper)."""
    if not variants:
        return []
    try:
        annotations = query_gnomad_batch(variants)
        if isinstance(annotations, list):
            return annotations
        return [{**v, **annotations.get(v.get('rsid', ''), {})} for v in variants]
    except Exception:
        return list(variants)
