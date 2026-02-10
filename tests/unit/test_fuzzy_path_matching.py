"""
Unit tests for fuzzy path matching helpers used in hierarchy normalization.
"""
import pytest
from trace_analyzer.processors.normalizer import (
    _normalize_path_for_matching,
    _paths_match_fuzzy,
    _pick_canonical_path,
)


class TestNormalizePathForMatching:
    """Tests for _normalize_path_for_matching."""
    
    def test_replaces_uuid_placeholder(self):
        path = "/v1/{uuid}/applications/{uuid}/data"
        assert _normalize_path_for_matching(path) == "/v1/{param}/applications/{param}/data"
    
    def test_replaces_custom_placeholders(self):
        path = "/v1/{isolationID}/applications/{applicationID}/bundles/{bundleID}"
        assert _normalize_path_for_matching(path) == "/v1/{param}/applications/{param}/bundles/{param}"
    
    def test_no_placeholders(self):
        path = "/api/users/profile"
        assert _normalize_path_for_matching(path) == "/api/users/profile"
    
    def test_mixed_placeholders(self):
        path = "/v1/{uuid}/rules/{rule_id}/versions/{version}"
        assert _normalize_path_for_matching(path) == "/v1/{param}/rules/{param}/versions/{param}"


class TestPathsMatchFuzzy:
    """Tests for _paths_match_fuzzy."""
    
    def test_identical_paths_match(self):
        assert _paths_match_fuzzy("/api/{param}/data", "/api/{param}/data")
    
    def test_param_matches_concrete_segment(self):
        """A {param} placeholder should match any concrete path segment."""
        path_a = "/v1/{param}/bundles/{param}/versions/{param}"
        path_b = "/v1/{param}/bundles/data-model/versions/{param}"
        assert _paths_match_fuzzy(path_a, path_b)
    
    def test_different_static_segments_no_match(self):
        path_a = "/v1/{param}/bundles/{param}"
        path_b = "/v1/{param}/rules/{param}"
        assert not _paths_match_fuzzy(path_a, path_b)
    
    def test_different_segment_count_no_match(self):
        path_a = "/v1/{param}/data"
        path_b = "/v1/{param}/data/extra"
        assert not _paths_match_fuzzy(path_a, path_b)
    
    def test_both_concrete_different_no_match(self):
        """Two different concrete segments (neither is {param}) should not match."""
        path_a = "/api/users/active"
        path_b = "/api/users/inactive"
        assert not _paths_match_fuzzy(path_a, path_b)
    
    def test_real_world_model_artifacts_case(self):
        """The exact scenario from the bug report — http.route vs raw URL."""
        server_path = "/v1/{param}/applications/{param}/model-artifacts/bundles/{param}/versions/{param}"
        client_path = "/v1/{param}/applications/{param}/model-artifacts/bundles/data-model/versions/{param}"
        assert _paths_match_fuzzy(server_path, client_path)
    
    def test_real_world_rules_case(self):
        """The rules/Field case from the second bug screenshot."""
        server_path = "/v1/{param}/applications/{param}/rules/{param}/rule-resolve"
        client_path = "/v1/{param}/applications/{param}/rules/Field/rule-resolve"
        assert _paths_match_fuzzy(server_path, client_path)


class TestPickCanonicalPath:
    """Tests for _pick_canonical_path."""
    
    def test_picks_more_parameterized(self):
        more = "/v1/{param}/bundles/{param}/versions/{param}"
        less = "/v1/{param}/bundles/data-model/versions/{param}"
        assert _pick_canonical_path(more, less) == more
        assert _pick_canonical_path(less, more) == more
    
    def test_equal_params_picks_first(self):
        path = "/v1/{param}/data"
        assert _pick_canonical_path(path, path) == path
