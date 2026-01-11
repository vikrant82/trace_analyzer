"""
Result builder for web interface output.
"""

from collections import defaultdict


def prepare_results(analyzer):
    """
    Convert analyzer results to a structured format for JSON/HTML output.
    This function passes the hierarchical data to the template
    and uses corrected summary metrics.
    
    Args:
        analyzer: TraceAnalyzer instance with completed analysis
        
    Returns:
        Dictionary with structured results for rendering
    """
    # Section 1 & 2: Services Overview and Incoming Requests
    # Get effective times for endpoints
    endpoint_effective = analyzer.effective_times.get('endpoints', {})
    service_effective = analyzer.effective_times.get('services', {})
    
    services_data = defaultdict(list)
    for (service, http_method, endpoint, param), stats in analyzer.endpoint_params.items():
        key = (service, http_method, endpoint, param)
        eff_time = endpoint_effective.get(key, stats['total_time_ms'])
        cumulative = stats['total_time_ms']
        parallelism = cumulative / eff_time if eff_time > 0 else 1.0
        
        services_data[service].append({
            'http_method': http_method,
            'endpoint': endpoint,
            'parameter': param,
            'count': stats['count'],
            'total_time_ms': cumulative,
            'total_time_formatted': analyzer.format_time(cumulative),
            'effective_time_ms': eff_time,
            'effective_time_formatted': analyzer.format_time(eff_time),
            'parallelism_factor': parallelism,
            'has_parallelism': parallelism > 1.15 and stats['count'] > 1,
            'total_self_time_ms': stats.get('total_self_time_ms', 0.0),
            'total_self_time_formatted': analyzer.format_time(stats.get('total_self_time_ms', 0.0)),
            'error_count': stats['error_count'],
            'error_messages': sorted(stats['error_messages'].items(), key=lambda item: -item[1])
        })
    
    for service in services_data:
        services_data[service].sort(key=lambda x: -x['total_time_ms'])
    
    services_summary = []
    for service, endpoints in services_data.items():
        total_count = sum(e['count'] for e in endpoints)
        total_time = sum(e['total_time_ms'] for e in endpoints)
        total_self_time = sum(e['total_self_time_ms'] for e in endpoints)
        
        # Get effective time for the service overall
        eff_time = service_effective.get(service, total_time)
        parallelism = total_time / eff_time if eff_time > 0 else 1.0
        
        services_summary.append({
            'name': service,
            'request_count': total_count,
            'total_time_ms': total_time,
            'total_time_formatted': analyzer.format_time(total_time),
            'effective_time_ms': eff_time,
            'effective_time_formatted': analyzer.format_time(eff_time),
            'parallelism_factor': parallelism,
            'has_parallelism': parallelism > 1.15 and total_count > 1,
            'total_self_time_ms': total_self_time,
            'total_self_time_formatted': analyzer.format_time(total_self_time),
            'unique_combinations': len(endpoints)
        })
    
    services_summary.sort(key=lambda x: -x['total_time_ms'])
    
    # Section 3: Service-to-Service Calls
    service_call_effective = analyzer.effective_times.get('service_calls', {})
    
    service_calls = defaultdict(list)
    for (caller, callee, http_method, endpoint, param), stats in analyzer.service_calls.items():
        key = (caller, callee, http_method, endpoint, param)
        eff_time = service_call_effective.get(key, stats['total_time_ms'])
        cumulative = stats['total_time_ms']
        parallelism = cumulative / eff_time if eff_time > 0 else 1.0
        
        service_calls[(caller, callee)].append({
            'http_method': http_method,
            'endpoint': endpoint,
            'parameter': param,
            'count': stats['count'],
            'total_time_ms': cumulative,
            'total_time_formatted': analyzer.format_time(cumulative),
            'effective_time_ms': eff_time,
            'effective_time_formatted': analyzer.format_time(eff_time),
            'parallelism_factor': parallelism,
            'has_parallelism': parallelism > 1.15 and stats['count'] > 1,
            'total_self_time_ms': stats.get('total_self_time_ms', 0.0),
            'total_self_time_formatted': analyzer.format_time(stats.get('total_self_time_ms', 0.0)),
            'error_count': stats['error_count'],
            'error_messages': sorted(stats['error_messages'].items(), key=lambda item: -item[1])
        })
    
    service_calls_list = []
    for (caller, callee), calls in service_calls.items():
        calls.sort(key=lambda x: -x['total_time_ms'])
        total_count = sum(c['count'] for c in calls)
        total_time = sum(c['total_time_ms'] for c in calls)
        total_self_time = sum(c['total_self_time_ms'] for c in calls)
        
        # Calculate effective time for the caller-callee pair
        # Sum effective times of individual endpoints for this pair
        eff_time = sum(c['effective_time_ms'] for c in calls)
        parallelism = total_time / eff_time if eff_time > 0 else 1.0
        
        service_calls_list.append({
            'caller': caller,
            'callee': callee,
            'total_calls': total_count,
            'total_time_ms': total_time,
            'total_time_formatted': analyzer.format_time(total_time),
            'effective_time_ms': eff_time,
            'effective_time_formatted': analyzer.format_time(eff_time),
            'parallelism_factor': parallelism,
            'has_parallelism': parallelism > 1.15 and total_count > 1,
            'total_self_time_ms': total_self_time,
            'total_self_time_formatted': analyzer.format_time(total_self_time),
            'calls': calls
        })
    
    service_calls_list.sort(key=lambda x: -x['total_time_ms'])
    
    # Kafka Operations
    kafka_effective = analyzer.effective_times.get('kafka', {})
    
    kafka_by_service = defaultdict(list)
    for (service, operation, message_type, details), stats in analyzer.kafka_messages.items():
        key = (service, operation, message_type, details)
        eff_time = kafka_effective.get(key, stats['total_time_ms'])
        cumulative = stats['total_time_ms']
        parallelism = cumulative / eff_time if eff_time > 0 else 1.0
        
        kafka_by_service[service].append({
            'operation': operation,
            'message_type': message_type,
            'details': details,
            'count': stats['count'],
            'total_time_ms': cumulative,
            'total_time_formatted': analyzer.format_time(cumulative),
            'effective_time_ms': eff_time,
            'effective_time_formatted': analyzer.format_time(eff_time),
            'parallelism_factor': parallelism,
            'has_parallelism': parallelism > 1.15 and stats['count'] > 1,
            'error_count': stats['error_count'],
            'error_messages': sorted(stats['error_messages'].items(), key=lambda item: -item[1])
        })
    
    kafka_services_list = []
    for service, operations in kafka_by_service.items():
        operations.sort(key=lambda x: -x['total_time_ms'])
        total_count = sum(op['count'] for op in operations)
        total_time = sum(op['total_time_ms'] for op in operations)
        
        # Calculate effective time for all kafka ops for this service
        eff_time = sum(op['effective_time_ms'] for op in operations)
        parallelism = total_time / eff_time if eff_time > 0 else 1.0
        
        kafka_services_list.append({
            'service': service,
            'total_operations': total_count,
            'total_time_ms': total_time,
            'total_time_formatted': analyzer.format_time(total_time),
            'effective_time_ms': eff_time,
            'effective_time_formatted': analyzer.format_time(eff_time),
            'parallelism_factor': parallelism,
            'has_parallelism': parallelism > 1.15 and total_count > 1,
            'operations': operations
        })
    
    kafka_services_list.sort(key=lambda x: -x['total_time_ms'])
    
    # Summary statistics
    total_requests = sum(stats['count'] for stats in analyzer.endpoint_params.values())
    total_wall_clock_time_ms = sum(summary['wall_clock_duration_ms'] 
                                   for summary in analyzer.trace_summary.values())
    total_kafka_ops = sum(stats['count'] for stats in analyzer.kafka_messages.values())
    total_kafka_time = sum(stats['total_time_ms'] for stats in analyzer.kafka_messages.values())
    
    # Error Analysis
    errors_by_service = defaultdict(list)
    
    # Process errors from incoming requests
    for service, endpoints in services_data.items():
        for endpoint in endpoints:
            if endpoint['error_count'] > 0:
                errors_by_service[service].append({
                    'type': 'Incoming Request',
                    'http_method': endpoint['http_method'],
                    'endpoint': endpoint['endpoint'],
                    'parameter': endpoint['parameter'],
                    'error_count': endpoint['error_count'],
                    'top_messages': endpoint['error_messages']
                })
    
    # Process errors from service-to-service calls
    for call in service_calls_list:
        for endpoint in call['calls']:
            if endpoint['error_count'] > 0:
                errors_by_service[call['caller']].append({
                    'type': f"Outgoing Call to {call['callee']}",
                    'http_method': endpoint['http_method'],
                    'endpoint': endpoint['endpoint'],
                    'parameter': endpoint['parameter'],
                    'error_count': endpoint['error_count'],
                    'top_messages': endpoint['error_messages']
                })
    
    # Process errors from Kafka operations
    for service_ops in kafka_services_list:
        for op in service_ops['operations']:
            if op['error_count'] > 0:
                errors_by_service[service_ops['service']].append({
                    'type': f"Kafka {op['operation']}",
                    'http_method': op['message_type'],  # Re-using this field for consistency
                    'endpoint': op['details'],
                    'parameter': '',
                    'error_count': op['error_count'],
                    'top_messages': op['error_messages']
                })
    
    # Sort errors within each service by count
    for service in errors_by_service:
        errors_by_service[service].sort(key=lambda x: -x['error_count'])
    
    total_errors = sum(e['error_count'] for service_errors in errors_by_service.values() 
                      for e in service_errors)
    
    final_results = {
        'summary': {
            'total_requests': total_requests,
            'total_time_ms': total_wall_clock_time_ms,
            'total_time_formatted': analyzer.format_time(total_wall_clock_time_ms),
            'unique_services': len(services_data),
            'unique_endpoints': len(set((k[0], k[1]) for k in analyzer.endpoint_params.keys())),
            'unique_combinations': len(analyzer.endpoint_params),
            'total_kafka_operations': total_kafka_ops,
            'total_kafka_time_ms': total_kafka_time,
            'total_kafka_time_formatted': analyzer.format_time(total_kafka_time),
            'total_traces': len(analyzer.trace_summary),
            'total_errors': total_errors
        },
        'services': {
            'summary': services_summary,
            'details': dict(services_data)
        },
        'service_calls': service_calls_list,
        'kafka_operations': kafka_services_list,
        'error_analysis': dict(errors_by_service),
        'trace_hierarchies': analyzer.trace_hierarchies,
        'trace_summary': analyzer.trace_summary
    }
    return final_results
