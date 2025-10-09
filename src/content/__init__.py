"""
M4: Persona内容工厂模块
负责基于M3筛选结果生成符合Persona特征的高质量评论
"""

from src.content.models import (
    Persona,
    IntentGroup,
    StyleGuide,
    CommentRequest,
    GeneratedComment,
    QualityScores,
    ComplianceCheck,
)

__all__ = [
    "Persona",
    "IntentGroup",
    "StyleGuide",
    "CommentRequest",
    "GeneratedComment",
    "QualityScores",
    "ComplianceCheck",
]
