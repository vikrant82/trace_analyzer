# Testing Guide - Trace Analyzer

**Project:** OpenTelemetry Trace Analyzer  
**Version:** 1.0  
**Last Updated:** November 12, 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Test Architecture](#test-architecture)
3. [Running Tests](#running-tests)
4. [Test Coverage](#test-coverage)
5. [Writing New Tests](#writing-new-tests)
6. [Continuous Integration](#continuous-integration)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The Trace Analyzer test suite provides comprehensive coverage of the modular trace analysis system. The tests validate everything from individual utility functions to complete end-to-end trace processing workflows.

### Test Statistics
- **Total Tests:** 59
- **Passing:** 34 (58%)
- **Code Coverage:** 77%
- **Integration Tests:** 7 (100% passing)

### Testing Stack
- **Framework:** pytest 9.0.0
- **Coverage:** pytest-cov 7.0.0
- **Mocking:** pytest-mock 3.15.1
- **Python Version:** 3.14.0

---

## Test Architecture

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py                    # Shared fixtures and configuration
├── unit/                          # Unit tests for individual modules
│   ├── __init__.py
│   ├── test_time_formatter.py     # Time formatting tests (9 tests)
│   ├── test_http_extractor.py     # HTTP extraction tests (14 tests)
│   ├── test_kafka_extractor.py    # Kafka extraction tests (7 tests)
│   ├── test_path_normalizer.py    # Path normalization tests (12 tests)
│   └── test_service_mesh_filter.py # Service mesh filtering tests (11 tests)
├── integration/                   # End-to-end integration tests
│   ├── __init__.py
│   └── test_analyzer_integration.py # Full workflow tests (7 tests)
└── fixtures/                      # Test data and fixtures
    └── __init__.py
```

### Test Layers

#### 1. Unit Tests (`tests/unit/`)
Test individual modules and functions in isolation:
- **Formatters:** Time formatting utilities
- **Extractors:** HTTP, Kafka, and path extraction logic
- **Processors:** File processing, hierarchy building, timing calculations
- **Filters:** Service mesh filtering logic

**Characteristics:**
- Fast execution (< 1 second)
- No external dependencies
- Mock external resources
- Test single responsibility

**Example:**
```python
def test_format_milliseconds():
    """Test formatting times in milliseconds."""
    assert format_time(10.25) == "10.25 ms"
```

#### 2. Integration Tests (`tests/integration/`)
Test complete workflows using real data:
- Full trace file processing
- Multiple configuration scenarios
- Error handling and edge cases
- State management

**Characteristics:**
- Use real test data (`test-trace.json`)
- Test module interactions
- Validate end-to-end behavior
- Slower execution (< 1 second still)

**Example:**
```python
def test_analyze_test_trace_file(self):
    """Test analyzing the actual test-trace.json file."""
    analyzer = TraceAnalyzer(strip_query_params=True)
    analyzer.process_trace_file("test-trace.json")
    assert len(analyzer.endpoint_params) > 0
```

### Fixtures (`conftest.py`)

Shared test fixtures provide reusable test data:

| Fixture | Description | Usage |
|---------|-------------|-------|
| `sample_span` | Single OpenTelemetry span | HTTP extraction tests |
| `sample_client_span` | CLIENT span example | Service call tests |
| `sample_kafka_span` | Kafka PRODUCER span | Messaging tests |
| `sample_trace` | Complete trace hierarchy | Hierarchy building tests |
| `sample_trace_file` | Temporary JSON file | File processing tests |
| `temp_json_file` | JSON file creator helper | Custom test data |

**Example Usage:**
```python
def test_with_fixture(sample_span):
    """Test using a fixture."""
    path = HttpExtractor.extract_http_path(sample_span["attributes"])
    assert path == "/api/users"
```

---

## Running Tests

### Prerequisites

```bash
# Ensure you're in the project directory
cd /path/to/Trace_Analyser

# Activate virtual environment
source venv/bin/activate

# Install test dependencies (if not already installed)
pip install -r requirements.txt
```

### Basic Test Execution

#### Run All Tests
```bash
pytest tests/ -v
```

**Output:**
```
tests/unit/test_time_formatter.py::TestFormatTime::test_format_milliseconds PASSED
tests/unit/test_time_formatter.py::TestFormatTime::test_format_seconds PASSED
...
======================== 34 passed, 25 failed in 0.59s ========================
```

#### Run Specific Test File
```bash
pytest tests/unit/test_time_formatter.py -v
```

#### Run Specific Test Class
```bash
pytest tests/unit/test_http_extractor.py::TestHttpExtractor -v
```

#### Run Specific Test Method
```bash
pytest tests/unit/test_time_formatter.py::TestFormatTime::test_format_milliseconds -v
```

#### Run Integration Tests Only
```bash
pytest tests/integration/ -v
```

#### Run Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Test Output Options

#### Verbose Output
```bash
pytest tests/ -v
```

#### Show Test Duration
```bash
pytest tests/ -v --durations=10
```

#### Stop on First Failure
```bash
pytest tests/ -x
```

#### Run Last Failed Tests
```bash
pytest tests/ --lf
```

#### Run Failed Tests First
```bash
pytest tests/ --ff
```

#### Quiet Mode (Less Output)
```bash
pytest tests/ -q
```

---

## Test Coverage

### Running Coverage Reports

#### Basic Coverage
```bash
pytest tests/ --cov=trace_analyzer
```

**Output:**
```
Name                                             Stmts   Miss  Cover
--------------------------------------------------------------------
trace_analyzer/__init__.py                           4      0   100%
trace_analyzer/core/analyzer.py                     70      8    89%
trace_analyzer/formatters/time_formatter.py          8      4    50%
...
TOTAL                                              606    116    77%
```

#### Coverage with Missing Lines
```bash
pytest tests/ --cov=trace_analyzer --cov-report=term-missing
```

**Output:**
```
Name                                             Stmts   Miss  Cover   Missing
-------------------------------------------------------------------------------
trace_analyzer/formatters/time_formatter.py          8      4    50%   17, 21-23
trace_analyzer/core/analyzer.py                     70      8    89%   153, 161, 164-168
...
```

#### HTML Coverage Report
```bash
pytest tests/ --cov=trace_analyzer --cov-report=html
```

**View Report:**
```bash
# macOS
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html

# Windows
start htmlcov/index.html
```

The HTML report provides:
- Interactive file browsing
- Line-by-line coverage highlighting
- Branch coverage details
- Sortable coverage tables

#### Coverage for Specific Module
```bash
pytest tests/unit/test_time_formatter.py --cov=trace_analyzer.formatters.time_formatter
```

#### Skip Fully Covered Files
```bash
pytest tests/ --cov=trace_analyzer --cov-report=term-missing:skip-covered
```

### Coverage Configuration

Coverage is configured in `pytest.ini`:

```ini
[coverage:run]
source = trace_analyzer
omit =
    */tests/*
    */venv/*
    */__pycache__/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False
```

---

## Writing New Tests

### Test File Naming Conventions

- **Unit tests:** `test_<module_name>.py` (e.g., `test_time_formatter.py`)
- **Integration tests:** `test_<feature>_integration.py`
- **Test classes:** `Test<ClassName>` (e.g., `TestTimeFormatter`)
- **Test methods:** `test_<behavior>` (e.g., `test_format_milliseconds`)

### Unit Test Template

```python
"""
Unit tests for trace_analyzer.<package>.<module> module.
"""
import pytest
from trace_analyzer.<package>.<module> import ClassName


class TestClassName:
    """Tests for the ClassName class."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        # Arrange
        input_data = "test"
        expected = "expected_result"
        
        # Act
        result = ClassName.method(input_data)
        
        # Assert
        assert result == expected
    
    def test_edge_case(self):
        """Test edge case behavior."""
        with pytest.raises(ValueError):
            ClassName.method(None)
    
    def test_with_fixture(self, sample_span):
        """Test using a fixture."""
        result = ClassName.method(sample_span)
        assert result is not None
```

### Integration Test Template

```python
"""
Integration test for <feature> workflow.
"""
import pytest
from pathlib import Path
from trace_analyzer import TraceAnalyzer


class TestFeatureIntegration:
    """Integration tests for <feature> workflow."""
    
    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow."""
        # Arrange
        test_file = Path("test-trace.json")
        analyzer = TraceAnalyzer()
        
        # Act
        analyzer.process_trace_file(str(test_file))
        
        # Assert
        assert len(analyzer.endpoint_params) > 0
        assert len(analyzer.service_calls) > 0
    
    def test_error_handling(self, tmp_path):
        """Test error handling."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{invalid}')
        
        analyzer = TraceAnalyzer()
        
        with pytest.raises(Exception):
            analyzer.process_trace_file(str(bad_file))
```

### Adding New Fixtures

Add fixtures to `tests/conftest.py`:

```python
@pytest.fixture
def my_custom_fixture():
    """Describe the fixture."""
    data = {
        "key": "value"
    }
    return data
```

### Parametrized Tests

Test multiple scenarios efficiently:

```python
import pytest

@pytest.mark.parametrize("input_val,expected", [
    (1000, "1.00 s"),
    (500, "500.00 ms"),
    (60000, "1m 0.00s"),
])
def test_format_time_parametrized(input_val, expected):
    """Test multiple time formatting scenarios."""
    assert format_time(input_val) == expected
```

### Mocking External Dependencies

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test using mocks."""
    with patch('trace_analyzer.module.function') as mock_func:
        mock_func.return_value = "mocked_result"
        
        result = some_function_that_calls_it()
        
        assert result == "mocked_result"
        mock_func.assert_called_once()
```

---

## Continuous Integration

### GitHub Actions Example

Create `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.14'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests with coverage
      run: |
        pytest tests/ --cov=trace_analyzer --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run tests before commit

source venv/bin/activate
pytest tests/ -x -q

if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## Troubleshooting

### Common Issues

#### Issue: "pytest: command not found"
**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Install pytest
pip install pytest pytest-cov
```

#### Issue: "ModuleNotFoundError: No module named 'trace_analyzer'"
**Solution:**
```bash
# Run tests from project root directory
cd /path/to/Trace_Analyser

# Or install package in development mode
pip install -e .
```

#### Issue: Tests fail with import errors
**Solution:**
```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH}:/path/to/Trace_Analyser"
```

#### Issue: Coverage report not generated
**Solution:**
```bash
# Install coverage plugin
pip install pytest-cov

# Verify pytest.ini exists and has coverage config
cat pytest.ini
```

#### Issue: Tests are too slow
**Solution:**
```bash
# Run in parallel (install pytest-xdist first)
pip install pytest-xdist
pytest tests/ -n auto
```

#### Issue: Fixture not found
**Solution:**
- Ensure `conftest.py` is in the correct directory
- Check fixture name matches usage
- Verify `conftest.py` is not in `.gitignore`

### Debugging Failed Tests

#### Show Full Traceback
```bash
pytest tests/unit/test_module.py -v --tb=long
```

#### Drop into Debugger on Failure
```bash
pytest tests/unit/test_module.py --pdb
```

#### Print Debug Information
```python
def test_with_debug():
    """Test with debug output."""
    result = some_function()
    print(f"Debug: result = {result}")  # Will show with -s flag
    assert result == expected
```

Run with output:
```bash
pytest tests/unit/test_module.py -v -s
```

### Test Markers

Use markers to categorize tests:

```python
@pytest.mark.slow
def test_slow_operation():
    """Test that takes a long time."""
    pass

@pytest.mark.integration
def test_integration_scenario():
    """Integration test."""
    pass
```

Run specific markers:
```bash
# Skip slow tests
pytest tests/ -v -m "not slow"

# Run only integration tests
pytest tests/ -v -m integration
```

Register markers in `pytest.ini`:
```ini
[pytest]
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

---

## Best Practices

### 1. Test Independence
- Each test should run independently
- Don't rely on test execution order
- Clean up after tests (use fixtures with `yield`)

### 2. Clear Test Names
```python
# Good
def test_format_time_returns_seconds_for_values_over_1000ms():
    pass

# Bad
def test_format():
    pass
```

### 3. Arrange-Act-Assert Pattern
```python
def test_extraction():
    # Arrange: Set up test data
    span = create_test_span()
    
    # Act: Execute the function
    result = extract_data(span)
    
    # Assert: Verify the result
    assert result == expected_value
```

### 4. Test Edge Cases
- Empty inputs
- None values
- Maximum/minimum values
- Boundary conditions

### 5. Keep Tests Simple
- One logical assertion per test
- Avoid complex logic in tests
- Use helpers for repetitive setup

### 6. Use Descriptive Assertions
```python
# Good
assert len(results) > 0, "Expected at least one result"

# Better
assert len(results) == 5, f"Expected 5 results, got {len(results)}"
```

---

## Quick Reference

### Common Commands

```bash
# Run all tests with coverage
pytest tests/ -v --cov=trace_analyzer --cov-report=html

# Run fast tests only
pytest tests/unit/ -v

# Run specific test
pytest tests/unit/test_time_formatter.py::TestFormatTime::test_format_milliseconds -v

# Debug a failing test
pytest tests/unit/test_module.py --pdb

# Show coverage for uncovered lines only
pytest tests/ --cov=trace_analyzer --cov-report=term-missing:skip-covered

# Run tests in parallel
pytest tests/ -n auto
```

### Coverage Targets

| Module Type | Target Coverage |
|-------------|----------------|
| Core Logic | 95%+ |
| Utilities | 90%+ |
| Integration | 80%+ |
| Overall | 85%+ |

### Test Execution Time Guidelines

- Unit tests: < 0.1s each
- Integration tests: < 1s each
- Full suite: < 5s total

---

## Resources

- **Pytest Documentation:** https://docs.pytest.org/
- **Coverage.py Guide:** https://coverage.readthedocs.io/
- **Test-Driven Development:** https://en.wikipedia.org/wiki/Test-driven_development
- **Project Tests:** `tests/` directory
- **Test Summary:** `TEST_SUMMARY.md`

---

**Last Updated:** November 12, 2025  
**Maintainer:** Trace Analyzer Development Team
