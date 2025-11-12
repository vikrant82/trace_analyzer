#!/usr/bin/env python3
"""
Trace Endpoint Analyzer - Backward Compatibility Facade
"""

import sys
from trace_analyzer import TraceAnalyzer
from trace_analyzer.core.types import EndpointStats, KafkaStats


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Analyze Grafana trace JSON files and extract HTTP endpoint statistics.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_trace.py trace.json
  python analyze_trace.py trace.json --keep-query-params
  python analyze_trace.py trace.json --include-gateways
  python analyze_trace.py trace.json --include-service-mesh
        """
    )
    parser.add_argument('input_file', help='Path to the trace JSON file')
    parser.add_argument('-o', '--output', dest='output_file', default='trace_analysis.md', help='Output markdown file')
    parser.add_argument('--keep-query-params', action='store_true', help='Keep query parameters in URLs')
    parser.add_argument('--include-gateways', action='store_true', 
                       help='Include gateway/proxy services with only CLIENT spans')
    parser.add_argument('--include-service-mesh', action='store_true',
                       help='Include service mesh sidecar spans (Istio/Envoy)')
    args = parser.parse_args()
    
    analyzer = TraceAnalyzer(
        strip_query_params=not args.keep_query_params,
        include_gateway_services=args.include_gateways,
        include_service_mesh=args.include_service_mesh
    )
    
    try:
        print(f"\nConfiguration:")
        print(f"  Input file: {args.input_file}")
        print(f"  Strip query params: {not args.keep_query_params}")
        print(f"  Include gateway services: {args.include_gateways}")
        print(f"  Include service mesh: {args.include_service_mesh}\n")
        analyzer.process_trace_file(args.input_file)
        print(f"\n✓ Analysis complete!")
    except FileNotFoundError:
        print(f"Error: File '{args.input_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
