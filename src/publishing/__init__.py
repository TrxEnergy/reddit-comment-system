"""
M5 Publishing Pipeline - 发布协调模块
独立的Reddit账号池和完全随机调度系统
"""

from src.publishing.models import (
    PublishState,
    PublishRequest,
    PublishResult,
    RedditAccount,
    PublishingStats
)

from src.publishing.local_account_manager import LocalAccountManager
from src.publishing.reddit_client import RedditClient
from src.publishing.random_scheduler import UniformRandomScheduler
from src.publishing.pipeline_orchestrator import PipelineOrchestrator
from src.publishing.scheduler_runner import SchedulerRunner

__all__ = [
    'PublishState',
    'PublishRequest',
    'PublishResult',
    'RedditAccount',
    'PublishingStats',
    'LocalAccountManager',
    'RedditClient',
    'UniformRandomScheduler',
    'PipelineOrchestrator',
    'SchedulerRunner',
]

__version__ = '0.5.0'
