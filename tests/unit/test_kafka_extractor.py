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
        span_name = "user-events send"
        
        operation, name, details = KafkaExtractor.extract_kafka_info(attributes, span_name)
        
        assert operation == "send"
        assert name == "user-events"
        assert "destination: user-events" in details
    
    def test_extract_kafka_receive_operation(self):
        """Test extracting Kafka receive/consume operation."""
        attributes = make_attributes(**{
            "messaging.system": "kafka",
            "messaging.operation": "receive",
            "messaging.destination": "order-events"
        })
        span_name = "order-events receive"
        
        operation, name, details = KafkaExtractor.extract_kafka_info(attributes, span_name)
        
        assert operation == "receive"
        assert name == "order-events"
    
    def test_extract_kafka_poll_operation(self):
        """Test extracting Kafka poll operation."""
        attributes = make_attributes(**{
            "messaging.system": "kafka",
            "messaging.operation": "poll"
        })
        span_name = "kafka poll"
        
        operation, name, details = KafkaExtractor.extract_kafka_info(attributes, span_name)
        
        assert operation == "poll"
    
    def test_extract_kafka_from_span_name_only(self):
        """Test extracting Kafka info when only span name indicates Kafka."""
        attributes = []
        span_name = "my-topic send"
        
        operation, name, details = KafkaExtractor.extract_kafka_info(attributes, span_name)
        
        # Should detect from span name
        assert operation == "send"
        assert name == "my-topic"
    
    def test_non_kafka_span(self):
        """Test with non-Kafka span."""
        attributes = make_attributes(**{
            "http.method": "GET",
            "http.target": "/api/users"
        })
        span_name = "GET /api/users"
        
        operation, name, details = KafkaExtractor.extract_kafka_info(attributes, span_name)
        
        # Should return empty/None values for non-Kafka spans
        assert operation in ["", None]
        assert name in ["", None]
    
    def test_kafka_with_consumer_group(self):
        """Test Kafka span with consumer group information."""
        attributes = make_attributes(**{
            "messaging.system": "kafka",
            "messaging.operation": "receive",
            "messaging.destination": "events",
            "messaging.kafka.consumer_group": "my-consumer-group"
        })
        span_name = "events receive"
        
        operation, name, details = KafkaExtractor.extract_kafka_info(attributes, span_name)
        
        assert operation == "receive"
        assert name == "events"
        # Details might include consumer group
        assert details is not None
    
    def test_empty_attributes(self):
        """Test with empty attributes."""
        attributes = []
        span_name = "some operation"
        
        operation, name, details = KafkaExtractor.extract_kafka_info(attributes, span_name)
        
        # Should handle gracefully
        assert operation is not None or name is not None
