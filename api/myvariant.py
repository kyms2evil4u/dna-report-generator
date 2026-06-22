"""
MyVariant.info API integration.
Aggregated variant scores: CADD, REVEL, ClinVar, dbSNP, gnomAD.
Free, no authentication required.
"""

import requests
import logging
import time
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

MYVARIANT_URL = "https://myvariant.info/v1/variant"
MYVARIANT_QUERY_URL = "https://myvariant.info/v1/query"
MYVARIANT_BATCH_URL = "https://myvariant.info/v1/variant"

HEADERS = {"Content-Type": "application/json"}

FIELDS = ",".join([
    "cadd.phred",
    "cadd.consequence",
    "cadd.gene.genename",
    "revel.revel_score",
    "clinvar.rcv.clinical_significance",
    "clinvar.gene.symbol",
    "dbsnp.rsid",
    "dbsnp.gene.symbol",
    "gnomad_exome.af.af",
    "gnomad_exome.af.af_popmax",
])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _post_myvariant_batch(rsids: List[str]) -> List[Dict]:
    """POST a batch of rsIDs to MyVariant.info."""
    payload = {"ids": rsids, "fields": FIELDS}
    try:
        r = requests.post(
            MYVARIANT_BATCH_URL,
            json=payload,
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning(f"MyVariant batch request failed: {e}")
        raise


def _extract_scores(record: Dict) -> Dict:
    """Extract relevant scores from a MyVariant.info record."""
    result = {
        "cadd_score": None,
        "revel_score": None,
        "gene": None,
        "consequence": None,
    }

    if not record or record.get("notfound"):
        return result

    # CADD score
    cadd = record.get("cadd", {})
    if isinstance(cadd, list):
        cadd = cadd[0]
    result["cadd_score"] = cadd.get("phred")
    result["consequence"] = cadd.get("consequence")

    # Gene from CADD
    cadd_gene = cadd.get("gene", {})
    if isinstance(cadd_gene, list):
        cadd_gene = cadd_gene[0]
    result["gene"] = cadd_gene.get("genename")

    # REVEL score (only for missense)
    revel = record.get("revel", {})
    if isinstance(revel, list):
        revel = revel[0]
    result["revel_score"] = revel.get("revel_score")

    # Fallback gene from dbSNP
    if not result["gene"]:
        dbsnp = record.get("dbsnp", {})
        gene_info = dbsnp.get("gene", {})
        if isinstance(gene_info, list):
            gene_info = gene_info[0]
        result["gene"] = gene_info.get("symbol")

    return result


def query_myvariant_batch(variants: List[Dict], batch_size: int = 1000) -> Dict[str, Dict]:
    """
    Query MyVariant.info for CADD/REVEL scores.
    Returns dict mapping rsid -> {cadd_score, revel_score, gene, consequence}
    """
    results = {}
    rsids = [v["rsid"] for v in variants if v.get("rsid", "").startswith("rs")]
    logger.info(f"Querying MyVariant.info for {len(rsids)} variants...")

    for i in range(0, len(rsids), batch_size):
        batch = rsids[i : i + batch_size]
        time.sleep(0.2)
        try:
            records = _post_myvariant_batch(batch)
            for record in records:
                # MyVariant uses the rsid or query field as key
                rsid = record.get("_id", record.get("query", ""))
                # Normalize: sometimes returned as rsXXXX, sometimes as chr:pos:ref:alt
                if not rsid.startswith("rs"):
                    # Try to match back by position in batch
                    rsid = record.get("query", "")
                results[rsid] = _extract_scores(record)
        except Exception as e:
            logger.error(f"MyVariant batch {i}-{i+batch_size} failed: {e}")
            for rsid in batch:
                results[rsid] = {"cadd_score": None, "revel_score": None, "gene": None}

        logger.info(f"MyVariant: processed {min(i + batch_size, len(rsids))}/{len(rsids)}")

    return results
