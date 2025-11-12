"""
Trace Analyzer - OpenTelemetry Trace Analysis Tool
"""

__version__ = "2.0.0"

from .core.analyzer import TraceAnalyzer
from .core.types import EndpointStats, KafkaStats, TraceConfig

__all__ = ["TraceAnalyzer", "EndpointStats", "KafkaStats", "TraceConfig"]
