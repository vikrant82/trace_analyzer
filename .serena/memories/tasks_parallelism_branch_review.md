# Parallelism branches review (parallel_calls vs parallel_calls_gemini)

Date: 2025-12-05

## Context
Compared feature implementation for Parallelism Detection spec across branches `parallel_calls` and `parallel_calls_gemini` without modifying workspace.

## Findings
- **Parallelism detection logic**
  - `parallel_calls`: Uses `TimingCalculator.merge_time_intervals` and `calculate_wall_clock_ms`; Normalizer distinguishes real vs inherited parallelism (parent_count/is_root_level), marks parent `has_parallel_children` only when fan-out exists and factor >1.05.
  - `parallel_calls_gemini`: Duplicated effective-time logic in `Aggregator` and `Normalizer`; parent marking now heuristic (any child parallelism_factor>1.05 via TimingCalculator), UI suppresses only if child parallelism is within +0.2 of parent; risk of false positives and loss of “real vs inherited” guarantee.
- **HTTP path extraction**
  - `parallel_calls`: Prefers `http.route` then url/target/path (matches spec).
  - `parallel_calls_gemini`: Removes `http.route` preference -> violates spec acceptance #7.
- **Self-time calculation**
  - `parallel_calls`: Uses cumulative child total times; can mis-handle parallel children for self-time.
  - `parallel_calls_gemini`: Uses effective child time for self_time and recalculation (better handling of parallelism), but calls private aggregator method and duplicates logic.
- **Aggregated node fields**
  - `parallel_calls`: Uses `wall_clock_ms` and `parallelism_factor` only when real parallelism; retains start/end min/max.
  - `parallel_calls_gemini`: Adds `effective_time_ms`, `parallelism_factor` always computed for aggregated groups; start/end kept; removes `children_wall_clock_ms`/`children_cumulative_ms`.
- **UI indicators**
  - `parallel_calls`: Shows ⚡ only when aggregated & wall_clock present; ⊗ on parent flagged in Normalizer (real fan-out only).
  - `parallel_calls_gemini`: Shows ⚡ when factor>1.05 and more than parent+0.2; ⊗ when any child factor>1.05; may surface inherited parallelism.
- **Tests**
  - `parallel_calls`: Has `tests/unit/test_timing_calculator.py` covering interval merge/wall clock/parallelism.
  - `parallel_calls_gemini`: Deletes that file; adds `tests/unit/test_parallelism.py` for aggregator._calculate_effective_time only (narrower coverage).
- **Sample trace**
  - `parallel_calls_gemini` replaces batch trace with small explicit parallel example (parent + 3 parallel child calls); `parallel_calls` kept older batch trace (no explicit parallel demo).
- **Documentation**
  - `parallel_calls_gemini` deletes `PARALLELISM_FEATURE_SPEC.md` (regression).

## Recommendation
Favor `parallel_calls` as baseline for adherence to spec (http.route preference, real vs inherited detection). Borrow targeted improvements from `parallel_calls_gemini` cautiously: effective-time-based self_time calculation and sample parallel trace. Restore spec doc and robust interval-merging tests when merging changes.