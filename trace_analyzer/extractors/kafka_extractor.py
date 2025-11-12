"""
Kafka and messaging information extraction from OpenTelemetry spans.
"""

from typing import List, Dict, Tuple


class KafkaExtractor:
    """Extracts Kafka/messaging-related information from spans."""
    
    @staticmethod
    def extract_kafka_info(span: Dict, attributes: List[Dict]) -> Tuple[str, str, str]:
        """
        Extract Kafka messaging information from span.
        
        Args:
            span: Span dictionary containing span metadata
            attributes: List of span attribute dictionaries
            
        Returns:
            Tuple of (operation_type, span_name, details)
            - operation_type: 'consumer', 'producer', or 'internal'
            - span_name: Name of the span
            - details: Comma-separated key=value pairs or '[no-details]'
        """
        span_kind = span.get('kind', '')
        span_name = span.get('name', '')
        
        # Determine operation type from span kind
        operation_type = 'internal'
        if span_kind == 'SPAN_KIND_CONSUMER':
            operation_type = 'consumer'
        elif span_kind == 'SPAN_KIND_PRODUCER':
            operation_type = 'producer'
        
        # Extract relevant attributes for details
        details_parts = []
        for attr in attributes:
            key = attr.get('key', '')
            value = attr.get('value', {})
            string_value = value.get('stringValue', '')
            
            if key in ['amf-service-id', 'amf-message-id', 'Kafka client', 'Message Uuid']:
                if string_value:
                    details_parts.append(f"{key}={string_value}")
        
        details = ', '.join(details_parts) if details_parts else '[no-details]'
        
        return operation_type, span_name, details
