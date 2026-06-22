"""
VCF (Variant Call Format) parser using PyVCF3.
Falls back to manual parsing if PyVCF3 is unavailable.
"""

from typing import List, Dict


def parse_vcf(filepath: str) -> List[Dict]:
    """
    Parse a VCF file and return normalized variant dicts.
    """
    try:
        import vcf as pyvcf
        return _parse_with_pyvcf(filepath)
    except ImportError:
        return _parse_vcf_manual(filepath)


def _parse_with_pyvcf(filepath: str) -> List[Dict]:
    import vcf as pyvcf

    rows = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = pyvcf.Reader(f)
        for record in reader:
            rsid = record.ID if record.ID else f"{record.CHROM}:{record.POS}"
            ref = str(record.REF)

            for sample in record.samples:
                gt = sample["GT"] if "GT" in sample.data._fields else None
                if gt:
                    alleles = _decode_gt(gt, ref, record.ALT)
                    rows.append({
                        "rsid": rsid,
                        "chromosome": _normalize_chrom(str(record.CHROM)),
                        "position": record.POS,
                        "genotype": "".join(alleles),
                        "allele1": alleles[0] if len(alleles) > 0 else None,
                        "allele2": alleles[1] if len(alleles) > 1 else None,
                        "ref": ref,
                        "alt": ",".join(str(a) for a in record.ALT),
                        "source_format": "vcf",
                    })
                    break  # Take first sample only

    return rows


def _decode_gt(gt_str: str, ref: str, alts: list) -> List[str]:
    """Convert GT field (e.g. '0/1') to actual nucleotide alleles."""
    allele_map = {0: ref}
    for i, alt in enumerate(alts or []):
        allele_map[i + 1] = str(alt) if alt is not None else "."

    alleles = []
    for idx_str in gt_str.replace("|", "/").split("/"):
        try:
            idx = int(idx_str)
            alleles.append(allele_map.get(idx, "."))
        except ValueError:
            alleles.append(".")
    return alleles


def _parse_vcf_manual(filepath: str) -> List[Dict]:
    """
    Fallback manual VCF parser (no external dependencies).
    """
    rows = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue
            chrom, pos, vid, ref, alt = parts[0], parts[1], parts[2], parts[3], parts[4]

            rows.append({
                "rsid": vid if vid != "." else f"{chrom}:{pos}",
                "chromosome": _normalize_chrom(chrom),
                "position": _safe_int(pos),
                "genotype": ref + alt.split(",")[0],
                "allele1": ref,
                "allele2": alt.split(",")[0],
                "ref": ref,
                "alt": alt,
                "source_format": "vcf",
            })

    return rows


def _normalize_chrom(chrom: str) -> str:
    chrom = chrom.upper().replace("CHR", "")
    if chrom == "M":
        return "MT"
    return chrom


def _safe_int(val: str):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
