# Fuzzy Path Matching Feature (Jan 2026)

## Problem
CLIENT spans (Istio proxy) use `http.url` with raw paths (e.g., `.../bundles/data-model/versions/4.3.8`).
SERVER spans use `http.route` with framework-parameterized paths (e.g., `.../bundles/{bundleID}/versions/{versionID}`).
After `PathNormalizer` processes them, CLIENT spans still have concrete segments where SERVER spans have named placeholders.
These should merge but produced separate entries.

## Solution: Multi-Layer Approach

### Layer 1: Semver Normalization (`path_normalizer.py`)
- Added `semver_pattern = re.compile(r'/\d+\.\d+\.\d+(?:\.\d+)?(?=/|\?|$)')`
- Replaces `4.3.8` → `{version}`, `1.0.0.1` → `{version}`
- **Captures** the version value in `non_uuid_params` (added in Jan 2026 fix)
- Placed BEFORE numeric ID pattern to avoid `4` being caught as `{id}`

### Layer 2: Fuzzy Matching Helpers (`normalizer.py` module-level)
- `_PLACEHOLDER_RE = re.compile(r'\{[^}]+\}')` — matches any `{placeholder}`
- `_normalize_path_for_matching(path)` — replaces ALL named placeholders (`{uuid}`, `{bundleID}`, etc.) with generic `{param}` for comparison
- `_paths_match_fuzzy(a, b)` — segment-by-segment comparison; `{param}` matches ANY single segment
- `_pick_canonical_path(a, b)` — returns the path with more `{param}` placeholders
- `_extract_absorbed_values(source, display)` — extracts concrete segments from source that correspond to `{placeholder}` in display

### Layer 3: Hierarchy Aggregation (`normalizer.py` → `aggregate_siblings`)
- Records `original_index` before sorting to restore chronological order after grouping
- Sorts children by param count (most parameterized first) so they establish the canonical template
- Tracks `display_paths` (original names like `{bundleID}`) separate from `canonical_paths` (generic `{param}` form for matching)
- After grouping, collects ALL param values from ALL children in the group (not just `first`)
- Adds absorbed concrete values (e.g., `data-model` absorbed into `{bundleID}`)
- Restores original ordering via `ordered_groups` sorted by earliest original_index

### Layer 4: Flat Table Merging (`metrics_populator.py`)
- `_merge_fuzzy_metrics()` post-processes flat table dicts (endpoint_params, service_calls)
- Groups keys that share context (service, method, kind) with fuzzy-matching paths
- Picks most-parameterized path for display, collects absorbed values
- Merges counts, times, error info
- Called from `populate_flat_metrics()` after initial calculation

## Important Gotchas

### Param Value Collection
- Must collect from ALL children, not just `first` — different children may have different captured params (e.g., one has `4.3.8`, another has `data-model`)
- Use `set()` to deduplicate, then `sorted()` for deterministic display

### Semver Must Capture Values
- Initially semver was NOT captured in `non_uuid_params` (unlike UUID, rule_id, numeric_id)
- This meant CLIENT spans with `4.3.8` had empty `parameter_value`, losing the version info
- Fix: Added `non_uuid_params.append(param_value)` in the semver block

### Ordering Preservation
- Sorting by param count for grouping destroys the original chronological order
- Must record `original_index` BEFORE sorting and restore AFTER grouping
- Groups are ordered by the smallest `original_index` of any member

### Context Grouping in Flat Tables
- Flat table keys are tuples like `(service, method, path, params, kind)`
- When grouping for fuzzy merge, exclude BOTH `path` AND `params` from the context key
- `params` can differ between entries that should merge (one has `4.3.8`, other has nothing)

## Files Modified
- `trace_analyzer/extractors/path_normalizer.py` — semver pattern + capture
- `trace_analyzer/processors/normalizer.py` — fuzzy matching helpers + aggregate_siblings rewrite
- `trace_analyzer/processors/metrics_populator.py` — `_merge_fuzzy_metrics()` + imports

## Tests
- `tests/unit/test_path_normalizer.py` — 4 semver tests (capture values, four-part, combined with UUID, negative)
- `tests/unit/test_fuzzy_path_matching.py` — 11 tests across 3 classes:
  - `TestNormalizePathForMatching` (4 tests)
  - `TestPathsMatchFuzzy` (7 tests including real-world patterns)
  - `TestPickCanonicalPath` (2 tests)
- Total: 162 tests passing, 81% coverage

## Edge Case Awareness
- Fuzzy matching could theoretically over-merge two genuinely different endpoints with same structure but different static segments (e.g., `/api/users/{id}` vs `/api/items/{id}`). This is prevented by also matching on `service_name` and `http_method` in the grouping key.
- CLIENT-only spans (outgoing calls) don't merge because they all have raw URLs without `http.route` counterparts — no SERVER spans to establish `{param}` templates.
