"""
JSON trace file processing using streaming parser.
"""

import ijson
from collections import defaultdict
from typing import Dict, List


class TraceFileProcessor:
    """Processes OpenTelemetry trace JSON files using streaming parser."""
    
    @staticmethod
    def process_file(file_path: str) -> Dict[str, List[Dict]]:
        """
        Process a trace JSON file and group spans by traceId.
        
        Args:
            file_path: Path to the trace JSON file
            
        Returns:
            Dictionary mapping trace_id -> list of spans
        """
        traces = defaultdict(list)
        
        print(f"Processing {file_path}...")
        
        with open(file_path, 'rb') as f:
            parser = ijson.items(f, 'batches.item')
            batch_count, span_count = 0, 0
            
            for batch in parser:
                batch_count += 1
                for inst_lib_span in batch.get('instrumentationLibrarySpans', []):
                    for span in inst_lib_span.get('spans', []):
                        span_count += 1
                        trace_id = span.get('traceId')
                        if trace_id:
                            # Attach resource info to span for later service name extraction
                            span['resource'] = batch.get('resource', {})
                            traces[trace_id].append(span)
                
                if batch_count % 100 == 0:
                    print(f"  Read {batch_count} batches, {span_count} spans...")
        
        print(f"Completed reading file: {batch_count} batches, {span_count} spans found.")
        print(f"Found {len(traces)} unique traces.")
        
        return dict(traces)
