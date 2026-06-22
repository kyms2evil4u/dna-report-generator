"""
Ensembl VEP (Variant Effect Predictor) REST API integration.
Free, no authentication required. GRCh37/hg19 and GRCh38 supported.
"""

import requests
import logging
import time
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

VEP_GRCH38_URL = "https://rest.ensembl.org/vep/human/id"
VEP_GRCH37_URL = "https://grch37.rest.ensembl.org/vep/human/id"

HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# VEP consequence severity (higher = more severe)
CONSEQUENCE_SEVERITY = {
    "transcript_ablation": 10,
    "splice_acceptor_variant": 9,
    "splice_donor_variant": 9,
    "stop_gained": 8,
    "frameshift_variant": 8,
    "stop_lost": 7,
    "start_lost": 7,
    "transcript_amplification": 6,
    "inframe_insertion": 5,
    "inframe_deletion": 5,
    "missense_variant": 4,
    "protein_altering_variant": 4,
    "splice_region_variant": 3,
    "synonymous_variant": 2,
    "stop_retained_variant": 2,
    "5_prime_UTR_variant": 1,
    "3_prime_UTR_variant": 1,
    "intron_variant": 0,
    "intergenic_variant": 0,
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def _post_vep_batch(rsids: List[str], grch38: bool = True) -> Dict:
    """POST a batch of rsIDs to Ensembl VEP."""
    url = VEP_GRCH38_URL if grch38 else VEP_GRCH37_URL
    payload = {"ids": rsids}
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", 5))
            logger.warning(f"VEP rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            raise Exception("Rate limited")
        r.raise_for_status()
        return {item["id"]: item for item in r.json()}
    except Exception as e:
        logger.warning(f"VEP batch request failed: {e}")
        raise


def _extract_most_severe(vep_record: Dict) -> Dict:
    """Extract the most severe consequence from a VEP result."""
    result = {
        "gene": None,
        "consequence": vep_record.get("most_severe_consequence"),
        "transcript_consequences": [],
        "impact": None,
    }

    transcripts = vep_record.get("transcript_consequences", [])
    if not transcripts:
        return result

    # Sort by severity
    def severity(tc):
        terms = tc.get("consequence_terms", [])
        return max((CONSEQUENCE_SEVERITY.get(t, 0) for t in terms), default=0)

    sorted_tc = sorted(transcripts, key=severity, reverse=True)
    top = sorted_tc[0]

    result["gene"] = top.get("gene_symbol")
    result["impact"] = top.get("impact")
    result["consequence"] = (top.get("consequence_terms") or [None])[0]
    result["transcript_consequences"] = [
        {
            "gene": tc.get("gene_symbol"),
            "transcript": tc.get("transcript_id"),
            "consequence": (tc.get("consequence_terms") or [None])[0],
            "impact": tc.get("impact"),
            "amino_acids": tc.get("amino_acids"),
            "codons": tc.get("codons"),
        }
        for tc in sorted_tc[:3]  # Top 3
    ]

    return result


def query_vep_batch(variants: List[Dict], batch_size: int = 200) -> Dict[str, Dict]:
    """
    Query Ensembl VEP for variant effect predictions.
    Returns dict mapping rsid -> {gene, consequence, impact, transcript_consequences}
    """
    results = {}
    rsids = [v["rsid"] for v in variants if v.get("rsid", "").startswith("rs")]
    logger.info(f"Querying Ensembl VEP for {len(rsids)} variants...")

    for i in range(0, len(rsids), batch_size):
        batch = rsids[i : i + batch_size]
        time.sleep(0.5)
        try:
            vep_data = _post_vep_batch(batch, grch38=True)
            for rsid in batch:
                if rsid in vep_data:
                    results[rsid] = _extract_most_severe(vep_data[rsid])
                else:
                    results[rsid] = {
                        "gene": None,
                        "consequence": None,
                        "impact": None,
                        "transcript_consequences": [],
                    }
        except Exception as e:
            logger.error(f"VEP batch {i}-{i+batch_size} failed: {e}")
            for rsid in batch:
                results[rsid] = {"gene": None, "consequence": None, "impact": None}

        logger.info(f"VEP: processed {min(i + batch_size, len(rsids))}/{len(rsids)}")

    return results
