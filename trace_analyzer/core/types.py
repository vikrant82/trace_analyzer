"""
Type definitions for trace analysis.
"""

from typing import TypedDict, DefaultDict


class EndpointStats(TypedDict):
    """Statistics for an HTTP endpoint or service call."""
    count: int
    total_time_ms: float
    total_self_time_ms: float
    error_count: int
    error_messages: DefaultDict[str, int]


class KafkaStats(TypedDict):
    """Statistics for Kafka/messaging operations."""
    count: int
    total_time_ms: float
    error_count: int
    error_messages: DefaultDict[str, int]


class TraceConfig:
    """Configuration for trace analysis."""
    
    def __init__(
        self,
        strip_query_params: bool = True,
        include_gateway_services: bool = False,
        include_service_mesh: bool = False
    ):
        """
        Initialize trace analysis configuration.
        
        Args:
            strip_query_params: If True, removes query parameters from URLs before analysis.
                               Default: True (recommended for cleaner grouping)
            
            include_gateway_services: If True, includes services that only have CLIENT spans
                                     or act as pure proxies/gateways in service counts.
                                     Default: False (excludes pure gateway/proxy services)
            
            include_service_mesh: If True, includes service mesh sidecar spans (Istio/Envoy)
                                 in the analysis, showing duplicate entries for each logical
                                 operation (both application and sidecar spans).
                                 Default: False (filters out sidecar duplicates)
        """
        self.strip_query_params = strip_query_params
        self.include_gateway_services = include_gateway_services
        self.include_service_mesh = include_service_mesh
