"""
M6 Monitoring - 监控指挥中心
实时指标 + 告警 + 降频控制
"""

from src.monitoring.metrics import MetricsCollector
from src.monitoring.dashboard import app

__all__ = [
    'MetricsCollector',
    'app',
]

__version__ = '0.6.0'
