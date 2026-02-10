# Error Visualization Implementation

## Overview
Complete implementation of visual error indicators throughout the trace hierarchy UI. This feature provides immediate visual feedback for error spans in OpenTelemetry traces.

## Components Modified

### 1. Error Detection (metrics_populator.py)
**Location**: `trace_analyzer/processors/metrics_populator.py` lines 73-78

**Critical Fixes**:
- **Status Code Type**: Changed from string comparison `'STATUS_CODE_ERROR'` to numeric check `status_code in [1, 2]`
  - OpenTelemetry uses numeric codes: 0 (UNSET/OK), 1 (ERROR), 2 (ERROR)
- **Empty Message Handling**: Fixed using `or` operator for empty strings
  ```python
  error_message = (span_status.get('message') or 'Unknown Error') if is_error else None
  ```
  - OpenTelemetry traces can have `"message": ""` even when `code: 2`
  - `dict.get('message', 'default')` only applies default when key is missing, not when value is empty/falsy

### 2. Hierarchy Error Extraction (hierarchy_builder.py)
**Location**: `trace_analyzer/processors/hierarchy_builder.py` lines 46-64

**Functionality**:
- Extracts `status.code` and `status.message` from each span
- Extracts `http.status_code` from attributes array (handles both intValue and stringValue)
- Stores in span_nodes dictionary:
  - `is_error`: Boolean indicating error state
  - `error_message`: Error description or 'Unknown Error'
  - `http_status_code`: HTTP status (400, 502, etc.) if available

### 3. Aggregation Error Preservation (normalizer.py)
**Location**: `trace_analyzer/processors/normalizer.py` lines 148-207

**Critical Implementation**:
The aggregation system was losing error information. Fixed by:

**Single Node Handling** (lines 148-156):
```python
node['aggregated'] = False
node['count'] = 1
# Ensure error information preserved
if 'is_error' not in node:
    node['is_error'] = False
    node['error_message'] = None
    node['http_status_code'] = None
```

**Aggregated Node Creation** (lines 169-207):
```python
# Aggregate error information from all children
any_errors = any(c.get('is_error', False) for c in group_children)
error_count = sum(1 for c in group_children if c.get('is_error', False))

# Collect unique error messages and HTTP status codes
error_messages = set()
http_status_codes = set()
for c in group_children:
    if c.get('is_error', False):
        if c.get('error_message'):
            error_messages.add(c.get('error_message'))
        if c.get('http_status_code'):
            http_status_codes.add(c.get('http_status_code'))

# Format aggregated error message
if any_errors:
    if len(error_messages) == 1:
        agg_error_message = list(error_messages)[0]
    else:
        agg_error_message = f"Multiple errors ({error_count}/{count})"
    agg_http_status = list(http_status_codes)[0] if http_status_codes else None

agg_node = {
    # ... existing fields ...
    'is_error': any_errors,
    'error_message': agg_error_message,
    'http_status_code': agg_http_status,
    'error_count': error_count
}
```

### 4. Template Rendering (results.html)
**Location**: `templates/results.html` lines 11-47 (render_trace_node macro)

**Visual Elements**:
```html
<li class="{{ 'collapsible' if node.children }} trace-node {{ 'error-span' if node.is_error }}"
    data-error="{{ 'true' if node.is_error else 'false' }}"
    data-error-message="{{ node.error_message }}"
    data-http-status="{{ node.http_status_code }}">
    
    {% if node.is_error %}
    <span class="error-indicator" title="Error: {{ node.error_message }}">🔴</span>
    {% endif %}
    
    <span class="metric error-badge" title="{{ node.error_message }}">
        <strong>❌ Error{% if node.aggregated and node.error_count %} ({{ node.error_count }}/{{ node.count }}){% elif node.http_status_code %} ({{ node.http_status_code }}){% endif %}</strong>
    </span>
```

**Badge Display Logic**:
- Single error span: `❌ Error (502)` - shows HTTP status code
- Aggregated error span: `❌ Error (4/4)` - shows error_count/total_count ratio

### 5. CSS Styling (style.css)
**Location**: `static/style.css` lines 749-820

**Key Styles**:
- `.tree li.error-span`: Subtle red gradient background, left border
- `.error-indicator`: Pulsing animation on red dot (🔴)
- `.metric.error-badge`: Red background, border, hover effects
- `.tree li.error-span.time-highlighted`: Combined error + performance indicators
- Hover tooltips: Display full error messages on hover

## Design Principles

### Independence from Performance Indicators
- Error indicators (red) work independently from performance indicators (time-based)
- Spans can have both error AND slow performance indicators simultaneously
- Visual hierarchy: Errors more prominent than performance warnings

### Aggregation-Aware Display
- Single spans show HTTP status codes: `❌ Error (502)`
- Aggregated spans show error ratio: `❌ Error (4/4)`
- Error messages aggregate intelligently:
  - Single unique message: Display that message
  - Multiple messages: Display "Multiple errors (X/Y)"

## Common Pitfalls & Solutions

### Pitfall 1: Empty String Messages
**Problem**: OpenTelemetry JSON has `"status": {"code": 2, "message": ""}`
**Why dict.get() fails**: `dict.get('key', 'default')` only uses default when key is missing, not when value is empty
**Solution**: Use `or` operator: `(span_status.get('message') or 'Unknown Error')`

### Pitfall 2: Data Loss in Aggregation
**Problem**: Aggregated nodes lose error information during sibling aggregation
**Root cause**: `agg_node` dictionary only included basic fields (span, service_name, times)
**Solution**: Explicitly aggregate error fields from all children, calculate error_count, format messages

### Pitfall 3: HTTP Status Code Extraction
**Problem**: OpenTelemetry attributes array can have intValue or stringValue
**Solution**: Check both fields when extracting http.status_code:
```python
if attr.get('key') == 'http.status_code':
    http_status_code = attr.get('value', {}).get('intValue') or attr.get('value', {}).get('stringValue')
```

## Tooltip Implementation (Updated Jan 2026)

### Design Decision: Tooltip on Error Badge Only
The error detail tooltip was moved from `<li class="error-span">` to `.metric.error-badge`:
- **Why**: The `<li>` is a huge hover target (entire subtree container). CSS `:hover` bubbles to all ancestors, causing stacking tooltips from nested error spans. Also conflicts with native `title` tooltips on timeline bars inside the same `<li>`.
- **How**: `data-error-message` attribute on `.error-badge` span + CSS `::after` pseudo-element
- **CSS Selector**: `.metric.error-badge[data-error-message]:hover::after`
- **Key properties**: `pointer-events: none` on the tooltip itself to prevent hover interference

### Previous Approach (Failed)
- Tooltip on `<li>` with `:not(:has(li.error-span:hover))` — only fixed parent/child `<li>` stacking but NOT the conflict with native `title` tooltips on timeline bars

### `title` Attributes Removed
- Removed `title` from `.error-indicator` (🔴 dot)
- Removed `title` from `.error-badge` span
- These caused double-tooltips (native browser + CSS `::after`)

## Testing Checklist

- ✅ Single error spans display red dot and error badge with HTTP status
- ✅ Aggregated error spans display error count ratio (e.g., 4/4)
- ✅ Hover tooltips show full error messages (on error badge only, no stacking)
- ✅ Pulsing animation on red dot indicator
- ✅ Combined error + performance highlighting works (red + time borders)
- ✅ Error Summary section correlates with Trace Hierarchy indicators
- ✅ Empty error messages handled gracefully
- ✅ Mixed aggregated nodes (some errors, some not) display correctly

## Data Flow

1. **ijson** reads OpenTelemetry JSON file
2. **metrics_populator.py** detects errors (status.code check)
3. **hierarchy_builder.py** extracts error info into node dictionary
4. **normalizer.py** aggregates error info when grouping siblings
5. **result_builder.py** passes nodes to template
6. **results.html** renders error indicators conditionally
7. **style.css** applies visual styling and animations

## File References
- Error detection: `trace_analyzer/processors/metrics_populator.py`
- Hierarchy extraction: `trace_analyzer/processors/hierarchy_builder.py`
- Aggregation: `trace_analyzer/processors/normalizer.py`
- Template: `templates/results.html`
- Styling: `static/style.css`
- Test data: `error-trace.json` (72 spans, 8 errors across 2 endpoints)
