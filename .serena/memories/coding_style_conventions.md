# Coding Style & Conventions

## Python Style Guide

### General Principles
- Follow PEP 8 conventions
- Use descriptive variable and function names
- Keep functions focused on single responsibilities

### Naming Conventions
- **Classes**: PascalCase (e.g., `TraceAnalyzer`, `EndpointStats`)
- **Functions/Methods**: snake_case (e.g., `process_trace_file`, `extract_http_path`)
- **Variables**: snake_case (e.g., `trace_id`, `normalized_path`, `total_time_ms`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `ALLOWED_EXTENSIONS`, `MAX_CONTENT_LENGTH`)
- **Private/Protected**: prefix with underscore (e.g., `_build_raw_hierarchy`, `_calculate_hierarchy_timings`)

### Type Hints
- Use type hints for function parameters and return values
- Import from `typing` module: `Dict`, `Tuple`, `List`, `DefaultDict`
- Use `TypedDict` for structured dictionaries (e.g., `EndpointStats`, `KafkaStats`)

Example:
```python
def normalize_path(self, path: str) -> Tuple[str, List[str]]:
    """Normalize a path by replacing parameter values."""
    ...
```

### Docstrings
- Use triple-quoted strings for docstrings
- Include description of purpose, parameters (Args), and return values
- Place at the beginning of functions/classes

Example:
```python
def process_trace_file(self, file_path: str):
    """
    Process the trace JSON file by first grouping all spans by traceId,
    then building a hierarchy for each trace.
    """
```

### Code Organization
- Group related imports together (standard library, third-party, local)
- Use blank lines to separate logical sections
- Private helper methods start with underscore
- Main logic methods come before helper methods

### Data Structures
- Use `defaultdict` for auto-initializing dictionaries
- Use tuples for composite keys in dictionaries
- Structure data before processing (e.g., group by trace_id first)

### Comments
- Use inline comments sparingly, prefer self-documenting code
- Add comments for complex algorithms or non-obvious logic
- Document why, not what (code should show what)

### Error Handling
- Use try-except blocks for file operations
- Provide meaningful error messages
- Clean up resources (e.g., delete temp files)

### Flask-Specific Conventions
- Routes use snake_case function names
- Use `@app.route()` decorator
- Return JSON for API endpoints, render templates for web pages
- Validate file uploads before processing

### Frontend (HTML/JavaScript)
- Use Jinja2 template syntax for dynamic content
- Keep JavaScript in `<script>` tags at bottom of HTML
- Use data attributes for storing metadata (e.g., `data-state`, `data-total-time`)
- Use CSS classes for styling, not inline styles
