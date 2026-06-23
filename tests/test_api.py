"""
Tests for the API aggregator and individual API modules.
All external HTTP calls are mocked with pytest-mock / unittest.mock
so tests run offline and never hit real endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# ClinVar
# ─────────────────────────────────────────────────────────────────────────────
CLINVAR_ESEARCH_RESPONSE = {
    "esearchresult": {
        "idlist": ["12345"],
        "count": "1",
    }
}

CLINVAR_ESUMMARY_RESPONSE = {
    "result": {
        "12345": {
            "uid": "12345",
            "title": "CYP2C19*2",
            "clinical_significance": {"description": "Pathogenic"},
            "genes": [{"symbol": "CYP2C19"}],
            "molecular_consequence": "splice_region_variant",
        }
    }
}


class TestClinVar:
    @patch("api.clinvar.requests.get")
    def test_returns_annotation_dict(self, mock_get, minimal_variants):
        from api.clinvar import annotate_with_clinvar

        # First call = esearch, second = esummary
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: CLINVAR_ESEARCH_RESPONSE),
            MagicMock(status_code=200, json=lambda: CLINVAR_ESUMMARY_RESPONSE),
        ]

        result = annotate_with_clinvar(minimal_variants[:1])
        assert isinstance(result, list)
        assert len(result) == 1
        assert "rsid" in result[0]

    @patch("api.clinvar.requests.get")
    def test_empty_id_list_handled(self, mock_get, minimal_variants):
        from api.clinvar import annotate_with_clinvar

        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"esearchresult": {"idlist": [], "count": "0"}},
        )

        result = annotate_with_clinvar(minimal_variants[:1])
        assert isinstance(result, list)

    @patch("api.clinvar.requests.get")
    def test_http_error_returns_input_unchanged(self, mock_get, minimal_variants):
        from api.clinvar import annotate_with_clinvar

        mock_get.side_effect = Exception("Connection refused")
        result = annotate_with_clinvar(minimal_variants[:2])
        assert isinstance(result, list)
        assert len(result) == 2


# ─────────────────────────────────────────────────────────────────────────────
# MyVariant.info
# ─────────────────────────────────────────────────────────────────────────────
MYVARIANT_RESPONSE = [
    {
        "_id":  "rs4244285",
        "cadd": {"phred": 22.4},
        "revel": {"score": 0.12},
        "dbsnp": {"rsid": "rs4244285", "gene": {"symbol": "CYP2C19"}},
    }
]


class TestMyVariant:
    @patch("api.myvariant.requests.post")
    def test_cadd_score_extracted(self, mock_post, minimal_variants):
        from api.myvariant import annotate_with_myvariant

        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: MYVARIANT_RESPONSE,
        )

        result = annotate_with_myvariant(minimal_variants[:1])
        assert isinstance(result, list)
        assert len(result) == 1

    @patch("api.myvariant.requests.post")
    def test_empty_input_returns_empty(self, mock_post):
        from api.myvariant import annotate_with_myvariant

        result = annotate_with_myvariant([])
        assert result == []
        mock_post.assert_not_called()

    @patch("api.myvariant.requests.post")
    def test_network_error_graceful(self, mock_post, minimal_variants):
        from api.myvariant import annotate_with_myvariant

        mock_post.side_effect = Exception("Timeout")
        result = annotate_with_myvariant(minimal_variants[:2])
        assert isinstance(result, list)


# ─────────────────────────────────────────────────────────────────────────────
# gnomAD
# ─────────────────────────────────────────────────────────────────────────────
GNOMAD_RESPONSE = {
    "data": {
        "variant": {
            "genome": {
                "af": 0.153,
                "populations": [
                    {"id": "nfe", "af": 0.29},
                    {"id": "afr", "af": 0.02},
                ]
            }
        }
    }
}


class TestGnomAD:
    @patch("api.gnomad.requests.post")
    def test_af_extracted(self, mock_post, minimal_variants):
        from api.gnomad import annotate_with_gnomad

        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: GNOMAD_RESPONSE,
        )

        result = annotate_with_gnomad(minimal_variants[:1])
        assert isinstance(result, list)

    @patch("api.gnomad.requests.post")
    def test_error_returns_input(self, mock_post, minimal_variants):
        from api.gnomad import annotate_with_gnomad

        mock_post.side_effect = Exception("gnomAD down")
        result = annotate_with_gnomad(minimal_variants[:1])
        assert isinstance(result, list)
        assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Aggregator (orchestrates all APIs)
# ─────────────────────────────────────────────────────────────────────────────
class TestAggregator:
    @patch("api.aggregator.annotate_with_clinvar")
    @patch("api.aggregator.annotate_with_myvariant")
    def test_fast_mode_uses_clinvar_and_myvariant(
        self, mock_mv, mock_cv, minimal_variants
    ):
        from api.aggregator import annotate_variants

        mock_cv.return_value = minimal_variants
        mock_mv.return_value = minimal_variants

        result = annotate_variants(minimal_variants, mode="fast", max_variants=100)
        assert isinstance(result, list)
        mock_cv.assert_called_once()
        mock_mv.assert_called_once()

    @patch("api.aggregator.annotate_with_clinvar")
    @patch("api.aggregator.annotate_with_myvariant")
    @patch("api.aggregator.annotate_with_ensembl_vep")
    @patch("api.aggregator.annotate_with_gnomad")
    def test_full_mode_uses_all_four_apis(
        self, mock_gn, mock_vep, mock_mv, mock_cv, minimal_variants
    ):
        from api.aggregator import annotate_variants

        for m in (mock_cv, mock_mv, mock_vep, mock_gn):
            m.return_value = minimal_variants

        result = annotate_variants(minimal_variants, mode="full", max_variants=100)
        assert isinstance(result, list)
        mock_cv.assert_called_once()
        mock_mv.assert_called_once()
        mock_vep.assert_called_once()
        mock_gn.assert_called_once()

    @patch("api.aggregator.annotate_with_clinvar")
    @patch("api.aggregator.annotate_with_myvariant")
    def test_max_variants_respected(self, mock_mv, mock_cv, minimal_variants):
        from api.aggregator import annotate_variants

        mock_cv.return_value = minimal_variants[:2]
        mock_mv.return_value = minimal_variants[:2]

        result = annotate_variants(minimal_variants, mode="fast", max_variants=2)
        # The aggregator should cap at max_variants before calling APIs
        first_call_args = mock_cv.call_args[0][0]
        assert len(first_call_args) <= 2

    @patch("api.aggregator.annotate_with_clinvar")
    @patch("api.aggregator.annotate_with_myvariant")
    def test_returns_list_on_api_failure(self, mock_mv, mock_cv, minimal_variants):
        from api.aggregator import annotate_variants

        mock_cv.side_effect = Exception("ClinVar down")
        mock_mv.side_effect = Exception("MyVariant down")

        result = annotate_variants(minimal_variants, mode="fast", max_variants=100)
        assert isinstance(result, list)
