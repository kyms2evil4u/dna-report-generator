"""
Tests for all analysis modules.
All inputs are in-memory fixtures — zero API calls.
"""

import pytest

from analysis.categorizer       import categorize_variants
from analysis.ancestry          import compute_ancestry
from analysis.risk_scorer       import compute_risk_scores
from analysis.pharmacogenomics  import analyze_pharmacogenomics
from analysis.traits            import analyze_traits


# ─────────────────────────────────────────────────────────────────────────────
# categorize_variants
# ─────────────────────────────────────────────────────────────────────────────
class TestCategorizer:
    def test_returns_dict(self, annotated_variants):
        result = categorize_variants(annotated_variants)
        assert isinstance(result, dict)

    def test_expected_category_keys(self, annotated_variants):
        result = categorize_variants(annotated_variants)
        expected = {"pathogenic", "disease_risk", "pharmacogenomics", "traits", "ancestry"}
        assert expected.issubset(set(result.keys()))

    def test_pathogenic_contains_correct_variants(self, annotated_variants):
        result = categorize_variants(annotated_variants)
        pathogenic_rsids = {v["rsid"] for v in result.get("pathogenic", [])}
        # rs4244285 (CYP2C19) and rs429358 (APOE) are pathogenic in our fixtures
        assert "rs429358" in pathogenic_rsids

    def test_all_variants_categorized(self, annotated_variants):
        result = categorize_variants(annotated_variants)
        categorized = set()
        for vlist in result.values():
            categorized.update(v["rsid"] for v in vlist)
        input_rsids = {v["rsid"] for v in annotated_variants}
        # Every input variant must appear in at least one category
        assert input_rsids.issubset(categorized)

    def test_empty_input(self):
        result = categorize_variants([])
        assert isinstance(result, dict)
        for vlist in result.values():
            assert vlist == []


# ─────────────────────────────────────────────────────────────────────────────
# compute_ancestry
# ─────────────────────────────────────────────────────────────────────────────
class TestAncestry:
    def test_returns_dict(self, annotated_variants):
        result = compute_ancestry(annotated_variants)
        assert isinstance(result, dict)

    def test_has_top_population(self, annotated_variants):
        result = compute_ancestry(annotated_variants)
        assert "top_population" in result
        assert isinstance(result["top_population"], str)

    def test_has_composition_list(self, annotated_variants):
        result = compute_ancestry(annotated_variants)
        assert "composition" in result
        assert isinstance(result["composition"], list)

    def test_percentages_sum_to_100(self, annotated_variants):
        result = compute_ancestry(annotated_variants)
        total = sum(pop["percentage"] for pop in result["composition"])
        assert abs(total - 100.0) < 1.0  # allow small floating-point rounding

    def test_composition_has_required_fields(self, annotated_variants):
        result = compute_ancestry(annotated_variants)
        for entry in result["composition"]:
            assert "population" in entry
            assert "percentage" in entry
            assert 0.0 <= entry["percentage"] <= 100.0

    def test_empty_input_returns_defaults(self):
        result = compute_ancestry([])
        assert "top_population" in result
        assert "composition" in result


# ─────────────────────────────────────────────────────────────────────────────
# compute_risk_scores
# ─────────────────────────────────────────────────────────────────────────────
class TestRiskScorer:
    def test_returns_list(self, annotated_variants):
        result = compute_risk_scores(annotated_variants)
        assert isinstance(result, list)

    def test_each_entry_has_required_fields(self, annotated_variants):
        result = compute_risk_scores(annotated_variants)
        required = {"condition", "risk_tier", "risk_label",
                    "relative_risk", "adjusted_risk_pct", "baseline_risk_pct"}
        for entry in result:
            assert required.issubset(set(entry.keys())), f"Missing fields in {entry}"

    def test_risk_tier_valid_values(self, annotated_variants):
        valid = {"high", "elevated", "average", "below_average"}
        for entry in compute_risk_scores(annotated_variants):
            assert entry["risk_tier"] in valid

    def test_percentages_are_positive(self, annotated_variants):
        for entry in compute_risk_scores(annotated_variants):
            assert entry["adjusted_risk_pct"] >= 0
            assert entry["baseline_risk_pct"] >= 0

    def test_relative_risk_is_positive(self, annotated_variants):
        for entry in compute_risk_scores(annotated_variants):
            assert entry["relative_risk"] > 0

    def test_empty_input_returns_list(self):
        result = compute_risk_scores([])
        assert isinstance(result, list)


# ─────────────────────────────────────────────────────────────────────────────
# analyze_pharmacogenomics
# ─────────────────────────────────────────────────────────────────────────────
class TestPGx:
    def test_returns_list(self, annotated_variants):
        result = analyze_pharmacogenomics(annotated_variants)
        assert isinstance(result, list)

    def test_each_entry_has_required_fields(self, annotated_variants):
        result = analyze_pharmacogenomics(annotated_variants)
        required = {"rsid", "gene", "star_allele", "your_genotype",
                    "drugs_affected", "effect", "severity"}
        for entry in result:
            assert required.issubset(set(entry.keys()))

    def test_drugs_affected_is_list(self, annotated_variants):
        for entry in analyze_pharmacogenomics(annotated_variants):
            assert isinstance(entry["drugs_affected"], list)
            assert len(entry["drugs_affected"]) >= 1

    def test_severity_valid_values(self, annotated_variants):
        valid = {"high", "moderate", "low"}
        for entry in analyze_pharmacogenomics(annotated_variants):
            assert entry["severity"] in valid

    def test_cyp2c19_detected(self, annotated_variants):
        """rs4244285 is the CYP2C19*2 variant — must be detected."""
        result = analyze_pharmacogenomics(annotated_variants)
        genes = [e["gene"] for e in result]
        assert "CYP2C19" in genes

    def test_empty_input(self):
        assert analyze_pharmacogenomics([]) == []


# ─────────────────────────────────────────────────────────────────────────────
# analyze_traits
# ─────────────────────────────────────────────────────────────────────────────
class TestTraits:
    def test_returns_list(self, annotated_variants):
        result = analyze_traits(annotated_variants)
        assert isinstance(result, list)

    def test_each_entry_has_required_fields(self, annotated_variants):
        required = {"trait", "rsid", "your_result", "confidence", "description"}
        for entry in analyze_traits(annotated_variants):
            assert required.issubset(set(entry.keys()))

    def test_confidence_valid_values(self, annotated_variants):
        valid = {"high", "moderate", "low"}
        for entry in analyze_traits(annotated_variants):
            assert entry["confidence"] in valid

    def test_eye_color_trait_detected(self, annotated_variants):
        """rs12913832 (HERC2) is a well-known eye color marker."""
        result = analyze_traits(annotated_variants)
        traits = [e["trait"] for e in result]
        assert any("eye" in t.lower() or "color" in t.lower() for t in traits)

    def test_empty_input(self):
        assert analyze_traits([]) == []
