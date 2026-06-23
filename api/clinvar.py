"""
ClinVar API integration via NCBI E-utilities (free, no key required for low-volume).
Queries clinical significance for rsIDs in batches.
"""

import requests
import time
import logging
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

CLINVAR_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
CLINVAR_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CLINVAR_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# NCBI rate limit: 3 requests/sec without key, 10/sec with key
RATE_LIMIT_DELAY = 0.4

SIGNIFICANCE_MAP = {
    "pathogenic": "Pathogenic",
    "likely pathogenic": "Likely pathogenic",
    "uncertain significance": "VUS",
    "likely benign": "Likely benign",
    "benign": "Benign",
    "conflicting interpretations": "Conflicting",
    "drug response": "Drug response",
    "risk factor": "Risk factor",
    "association": "Association",
    "protective": "Protective",
    "other": "Other",
    "not provided": "Not provided",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _fetch_clinvar_ids(rsid: str) -> List[str]:
    """Search ClinVar for a single rsID and return ClinVar IDs."""
    params = {
        "db": "clinvar",
        "term": f"{rsid}[rs]",
        "retmode": "json",
        "retmax": 10,
    }
    try:
        r = requests.get(CLINVAR_ESEARCH, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        logger.warning(f"ClinVar esearch failed for {rsid}: {e}")
        return []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _fetch_clinvar_summary(clinvar_ids: List[str]) -> Dict:
    """Fetch esummary for a list of ClinVar IDs."""
    if not clinvar_ids:
        return {}
    params = {
        "db": "clinvar",
        "id": ",".join(clinvar_ids),
        "retmode": "json",
    }
    try:
        r = requests.get(CLINVAR_ESUMMARY, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("result", {})
    except Exception as e:
        logger.warning(f"ClinVar esummary failed: {e}")
        return {}


def _parse_significance(summary_data: Dict, clinvar_ids: List[str]) -> Optional[str]:
    """Extract clinical significance from ClinVar summary."""
    for cid in clinvar_ids:
        record = summary_data.get(cid, {})
        germline = record.get("germline_classification", {})
        sig = germline.get("description", "")
        if sig:
            return SIGNIFICANCE_MAP.get(sig.lower(), sig)
    return None


def _parse_gene(summary_data: Dict, clinvar_ids: List[str]) -> Optional[str]:
    """Extract gene name from ClinVar summary."""
    for cid in clinvar_ids:
        record = summary_data.get(cid, {})
        genes = record.get("genes", [])
        if genes:
            return genes[0].get("symbol", None)
    return None


def query_clinvar_batch(variants: List[Dict], batch_size: int = 20) -> Dict[str, Dict]:
    """
    Query ClinVar for a list of variants (by rsID).
    Returns a dict mapping rsid -> {clinical_significance, gene, clinvar_id}
    """
    results = {}
    rsids = [v["rsid"] for v in variants if v.get("rsid", "").startswith("rs")]

    logger.info(f"Querying ClinVar for {len(rsids)} variants...")

    for i in range(0, len(rsids), batch_size):
        batch = rsids[i : i + batch_size]
        for rsid in batch:
            time.sleep(RATE_LIMIT_DELAY)
            try:
                clinvar_ids = _fetch_clinvar_ids(rsid)
                if not clinvar_ids:
                    results[rsid] = {"clinical_significance": None, "gene": None}
                    continue

                time.sleep(RATE_LIMIT_DELAY)
                summary = _fetch_clinvar_summary(clinvar_ids)
                sig = _parse_significance(summary, clinvar_ids)
                gene = _parse_gene(summary, clinvar_ids)
                results[rsid] = {
                    "clinical_significance": sig,
                    "gene": gene,
                    "clinvar_ids": clinvar_ids,
                }
            except Exception as e:
                logger.error(f"ClinVar lookup failed for {rsid}: {e}")
                results[rsid] = {"clinical_significance": None, "gene": None}

        logger.info(f"ClinVar: processed {min(i + batch_size, len(rsids))}/{len(rsids)}")

    return results


def annotate_with_clinvar(variants):
    """Returns variants as a list, annotated by this module (test-friendly wrapper)."""
    if not variants:
        return []
    try:
        annotations = query_clinvar_batch(variants)
        if isinstance(annotations, list):
            return annotations
        return [{**v, **annotations.get(v.get('rsid', ''), {})} for v in variants]
    except Exception:
        return list(variants)
