# Plan: Implementing First-Class Error Analysis

This document outlines the step-by-step plan to integrate first-class error analysis into the Trace Analyzer tool.

---

## 1. Goal

The primary goal is to enhance the tool's output to include a detailed, aggregated summary of errors found in the trace file. This will allow users to quickly identify which services and endpoints are failing, how often they are failing, and why.

---

## 2. Implementation Steps

The implementation will be broken down into three main parts, touching each of the core components of the application.

### Step 1: Enhance the Backend Engine (`analyze_trace.py`)

This is where the core logic for detecting and aggregating errors will reside.

#### 1.1. New Data Structure
In the `TraceAnalyzer.__init__` method, we will add a new data structure to store error information:

```python
# In TraceAnalyzer.__init__
self.error_details = defaultdict(lambda: {'count': 0, 'messages': defaultdict(int)})
```
- **`self.error_details`:** A `defaultdict` where the key is a tuple `(service_name, normalized_endpoint)`.
  - The `count` will store the total number of errors for that endpoint.
  - The `messages` will be another `defaultdict` to store the frequency of each unique error message associated with that endpoint.

#### 1.2. Error Detection Logic
We need a way to identify a span as an "error." According to the OpenTelemetry specification, a span is considered an error if its `status.code` is set to `STATUS_CODE_ERROR`. We will check for this in the `_populate_flat_metrics` method.

#### 1.3. Update `_populate_flat_metrics`
Inside the main loop of this method, after processing a span, we will add the following logic:

```python
# In _populate_flat_metrics, inside the loop
span_status = span.get('status', {})
if span_status.get('code') == 'STATUS_CODE_ERROR':
    # This is an error span. Let's aggregate it.
    error_message = span_status.get('message', 'Unknown Error')
    
    # We use the same key as the performance metrics for consistency
    key = (node['service_name'], http_method, normalized_path, param_str)
    
    self.error_details[key]['count'] += 1
    self.error_details[key]['messages'][error_message] += 1
```

This ensures that for every span that is identified as an error, we increment the error count for its corresponding endpoint and also track the specific error message.

---

### Step 2: Update the Web Application (`app.py`)

The Flask application needs to be updated to process this new error data and pass it to the frontend.

#### 2.1. Enhance `prepare_results`
At the end of the `prepare_results` function, we will add a new section to process `self.error_details` into a format suitable for the template.

```python
# In prepare_results, before the return statement

# --- NEW: Error Analysis ---
errors_by_service = defaultdict(list)
for (service, method, endpoint, param), error_stats in analyzer.error_details.items():
    # Sort messages by frequency
    sorted_messages = sorted(error_stats['messages'].items(), key=lambda item: -item[1])
    errors_by_service[service].append({
        'http_method': method,
        'endpoint': endpoint,
        'parameter': param,
        'error_count': error_stats['count'],
        'top_messages': sorted_messages
    })

# Sort errors within each service by count
for service in errors_by_service:
    errors_by_service[service].sort(key=lambda x: -x['error_count'])

# Add to the final results dictionary
final_results['error_analysis'] = dict(errors_by_service)
```

This will create a new key, `error_analysis`, in our results payload, containing a structured summary of all the errors, grouped by service.

---

### Step 3: Enhance the Frontend (`templates/results.html`)

Finally, we need to display this new information in the UI.

#### 3.1. Add a New "Error Summary" Section
In `results.html`, we will add a new top-level section, similar to the existing "Incoming Requests" and "Service-to-Service Calls" sections.

```html
<!-- In results.html, after the other main sections -->
<div class="section">
    <h2>Error Summary by Service</h2>
    <p>This section shows a summary of failed operations (spans marked with an error status).</p>
    
    {% if results.error_analysis %}
        {% for service, errors in results.error_analysis.items() %}
            <div class="service-block">
                <h3>{{ service }}</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Normalized Endpoint</th>
                            <th>Error Count</th>
                            <th>Top Error Messages</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for error in errors %}
                            <tr>
                                <td>
                                    <span class="http-method">{{ error.http_method }}</span>
                                    {{ error.endpoint }}
                                    {% if error.parameter != '[no-params]' %}
                                        <span class="parameter-value">({{ error.parameter }})</span>
                                    {% endif %}
                                </td>
                                <td>{{ error.error_count }}</td>
                                <td>
                                    <ul>
                                    {% for message, count in error.top_messages %}
                                        <li><strong>({{ count }}x)</strong> {{ message }}</li>
                                    {% endfor %}
                                    </ul>
                                </td>
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% endfor %}
    {% else %}
        <p>No errors found in this trace file. Great job!</p>
    {% endif %}
</div>
```

This template will render a clean, table-based view of the errors, showing the problematic endpoints, the total number of errors, and a list of the most frequent error messages for each.

---

## 4. Plan Summary

This plan provides a clear path to implementing a valuable new feature. By following these steps, we will enhance the Trace Analyzer to provide not just performance insights, but also critical reliability information, making it a more comprehensive and indispensable tool for developers and SREs.