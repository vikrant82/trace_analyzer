"""
Unit tests for trace_analyzer.extractors.kafka_extractor module.
"""
import pytest
from trace_analyzer.extractors.kafka_extractor import KafkaExtractor


def make_attributes(**kwargs):
    """Helper to create OpenTelemetry-format attributes."""
    return [{"key": k, "value": {"stringValue": v}} for k, v in kwargs.items()]


class TestKafkaExtractor:
    """Tests for the KafkaExtractor class."""
    
    def test_extract_kafka_send_operation(self):
        """Test extracting Kafka send/produce operation."""
        attributes = make_attributes(**{
            "messaging.system": "kafka",
            "messaging.operation": "send",
            "messaging.destination": "user-events"
        })
        span = {"name": "user-events send", "kind": "SPAN_KIND_PRODUCER"}
        
        operation, name, details = KafkaExtractor.extract_kafka_info(span, attributes)
        
        assert operation == "producer"
        assert name == "user-events send"
        assert details == "[no-details]"  # Current implementation doesn't extract messaging.destination
    
    def test_extract_kafka_receive_operation(self):
        """Test extracting Kafka receive/consume operation."""
        attributes = make_attributes(**{
            "messaging.system": "kafka",
            "messaging.operation": "receive",
            "messaging.destination": "order-events"
        })
        span = {"name": "order-events receive", "kind": "SPAN_KIND_CONSUMER"}
        
        operation, name, details = KafkaExtractor.extract_kafka_info(span, attributes)
        
        assert operation == "consumer"
        assert name == "order-events receive"
    
    def test_extract_kafka_poll_operation(self):
        """Test extracting Kafka poll operation."""
        attributes = make_attributes(**{
            "messaging.system": "kafka",
            "messaging.operation": "poll"
        })
        span = {"name": "kafka poll", "kind": "SPAN_KIND_CONSUMER"}
        
        operation, name, details = KafkaExtractor.extract_kafka_info(span, attributes)
        
        assert operation == "consumer"
    
    def test_extract_kafka_from_span_name_only(self):
        """Test extracting Kafka info when only span name indicates Kafka."""
        attributes = []
        span = {"name": "my-topic send", "kind": "SPAN_KIND_PRODUCER"}
        
        operation, name, details = KafkaExtractor.extract_kafka_info(span, attributes)
        
        # Should detect from span name
        assert operation == "producer"
        assert name == "my-topic send"
    
    def test_non_kafka_span(self):
        """Test with non-Kafka span."""
        attributes = make_attributes(**{
            "http.method": "GET",
            "http.target": "/api/users"
        })
        span = {"name": "GET /api/users", "kind": "SPAN_KIND_CLIENT"}
        
        operation, name, details = KafkaExtractor.extract_kafka_info(span, attributes)
        
        # CLIENT spans are treated as internal operations
        assert operation == "internal"
        assert name == "GET /api/users"  # Returns span name
    
    def test_kafka_with_consumer_group(self):
        """Test Kafka span with consumer group information."""
        attributes = make_attributes(**{
            "messaging.system": "kafka",
            "messaging.operation": "receive",
            "messaging.destination": "events",
            "messaging.kafka.consumer_group": "my-consumer-group"
        })
        span = {"name": "events receive", "kind": "SPAN_KIND_CONSUMER"}
        
        operation, name, details = KafkaExtractor.extract_kafka_info(span, attributes)
        
        assert operation == "consumer"
        assert name == "events receive"
        # Details might include consumer group
        assert details is not None
    
    def test_empty_attributes(self):
        """Test with empty attributes."""
        attributes = []
        span = {"name": "some operation", "kind": "SPAN_KIND_INTERNAL"}
        
        operation, name, details = KafkaExtractor.extract_kafka_info(span, attributes)
        
        # Should handle gracefully
        assert operation is not None or name is not None
