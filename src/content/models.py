"""
M4内容工厂 - 数据模型
定义Persona、意图组、风格卡、评论请求和生成结果的数据结构
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class IntentGroupType(str, Enum):
    """意图组类型枚举"""
    A = "A"  # Fees & Transfers
    B = "B"  # Exchange & Wallet Issues
    C = "C"  # Learning & Sharing


class Persona(BaseModel):
    """
    Persona模型
    定义评论生成的人格特征和约束
    """
    id: str = Field(description="Persona唯一标识")
    name: str = Field(description="Persona名称")
    background: str = Field(description="背景描述")
    tone: str = Field(description="语气风格")
    intent_groups: List[str] = Field(description="适用的意图组")
    interests: List[str] = Field(description="兴趣领域")
    catchphrases: Dict[str, List[str]] = Field(
        description="口头禅（opening/transition/ending）"
    )
    constraints: Dict[str, Any] = Field(description="使用约束")
    language_mix: bool = Field(default=False, description="是否支持多语言混写")

    @field_validator("catchphrases")
    @classmethod
    def validate_catchphrases(cls, v):
        """验证口头禅结构"""
        required_keys = ["opening", "transition", "ending"]
        for key in required_keys:
            if key not in v:
                raise ValueError(f"catchphrases must contain '{key}' key")
        return v


class IntentGroup(BaseModel):
    """
    意图组模型
    定义帖子的意图分类和响应策略
    """
    name: str = Field(description="意图组名称（A/B/C）")
    description: str = Field(description="意图描述")
    positive_clues: List[str] = Field(description="正向线索词")
    negative_lookalikes: List[str] = Field(description="负面混淆词")
    preferred_personas: List[str] = Field(description="推荐Persona列表")
    response_style: Dict[str, str] = Field(description="响应风格配置")


class StyleGuide(BaseModel):
    """
    子版风格卡模型
    定义特定Subreddit的评论风格要求
    """
    subreddit: str = Field(description="子版名称")
    tone: str = Field(description="语气风格")
    length: Dict[str, Any] = Field(description="长度约束")
    jargon_level: str = Field(description="术语使用级别")
    must_end_with_question: bool = Field(description="是否必须以问句结尾")
    dos: List[str] = Field(description="推荐做法")
    donts: List[str] = Field(description="禁止做法")
    compliance: Dict[str, Any] = Field(description="合规要求")


class CommentRequest(BaseModel):
    """
    评论生成请求
    封装M3筛选结果和账号信息
    """
    post_id: str = Field(description="帖子ID")
    title: str = Field(description="帖子标题")
    subreddit: str = Field(description="子版名称")
    score: int = Field(description="帖子得分")
    age_hours: float = Field(description="帖子年龄（小时）")
    lang: str = Field(description="语言")

    # M3元数据
    screening_metadata: Dict[str, Any] = Field(
        description="M3筛选元数据（intent_prob/topic_prob/suggestion）"
    )
    priority: float = Field(description="优先级分数")

    # 账号信息
    account_id: str = Field(description="预分配账号ID")
    account_username: str = Field(description="Reddit用户名")


class QualityScores(BaseModel):
    """
    质量评分（三分法）
    """
    relevance: float = Field(ge=0, le=1, description="相关性评分")
    natural: float = Field(ge=0, le=1, description="自然度评分")
    compliance: float = Field(ge=0, le=1, description="合规度评分")
    overall: float = Field(ge=0, le=1, description="综合评分")

    @field_validator("overall")
    @classmethod
    def calculate_overall(cls, v, info):
        """自动计算综合评分（加权平均）"""
        values = info.data
        if "relevance" in values and "natural" in values and "compliance" in values:
            # 权重：相关性40% + 自然度35% + 合规度25%
            return (
                values["relevance"] * 0.40 +
                values["natural"] * 0.35 +
                values["compliance"] * 0.25
            )
        return v


class ComplianceCheck(BaseModel):
    """
    合规检查结果
    """
    passed: bool = Field(description="是否通过检查")
    hard_violations: List[str] = Field(
        default_factory=list,
        description="硬禁止违规项"
    )
    soft_violations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="软约束违规项"
    )
    rewrite_needed: bool = Field(
        default=False,
        description="是否需要重写"
    )
    block_reason: Optional[str] = Field(
        default=None,
        description="阻止原因（如果未通过）"
    )
    compliance_score: float = Field(
        ge=0,
        le=1,
        description="合规度评分"
    )


class GeneratedComment(BaseModel):
    """
    生成的评论结果
    包含评论文本、元数据和质量评分
    """
    text: str = Field(description="最终评论文本")
    persona_used: str = Field(description="使用的Persona ID")
    intent_group: str = Field(description="意图组（A/B/C）")
    style_guide_id: str = Field(description="风格卡ID（subreddit）")

    # 质量评分
    quality_scores: QualityScores = Field(description="质量评分")

    # 审计元数据
    audit: Dict[str, Any] = Field(
        description="审计信息（policy_version/style_version/persona_version/rule_hits）"
    )

    # 时间戳
    timestamps: Dict[str, datetime] = Field(
        description="时间戳（generated_at/passed_checks_at）"
    )

    # 可选字段
    variants: Optional[List[str]] = Field(
        default=None,
        description="其他生成变体（如果有）"
    )

    # 原始请求引用
    request_id: str = Field(description="关联的CommentRequest ID")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "From my experience, TRC20 fees are significantly lower than ERC20 for USDT transfers. On most exchanges, TRC20 withdrawal is around $1 while ERC20 can be $10-20. Have you checked if your exchange supports TRC20?",
                "persona_used": "gas_optimizer",
                "intent_group": "A",
                "style_guide_id": "CryptoCurrency",
                "quality_scores": {
                    "relevance": 0.92,
                    "natural": 0.88,
                    "compliance": 0.98,
                    "overall": 0.92
                },
                "audit": {
                    "policy_version": "1.0.0",
                    "style_version": "1.0.0",
                    "persona_version": "1.0.0",
                    "rule_hits": []
                },
                "timestamps": {
                    "generated_at": "2025-10-09T10:30:00",
                    "passed_checks_at": "2025-10-09T10:30:02"
                },
                "request_id": "req_abc123"
            }
        }


class PersonaUsageRecord(BaseModel):
    """
    Persona使用记录（用于冷却管理）
    """
    persona_id: str
    subreddit: str
    post_id: str
    used_at: datetime
    comment_id: Optional[str] = None


class QuotaStatus(BaseModel):
    """
    配额状态
    """
    account_id: str
    daily_used: int = Field(default=0, description="当日已使用次数")
    daily_limit: int = Field(default=1, description="日配额限制")
    window_start: datetime = Field(description="窗口开始时间")
    remaining: int = Field(description="剩余配额")

    @field_validator("remaining")
    @classmethod
    def calculate_remaining(cls, v, info):
        """自动计算剩余配额"""
        values = info.data
        if "daily_limit" in values and "daily_used" in values:
            return max(0, values["daily_limit"] - values["daily_used"])
        return v


class CostTracker(BaseModel):
    """
    成本追踪器
    """
    date: str = Field(description="日期（YYYY-MM-DD）")
    total_generations: int = Field(default=0, description="总生成次数")
    total_cost: float = Field(default=0.0, description="总成本（美元）")
    daily_limit: float = Field(default=0.40, description="日成本限制")
    monthly_limit: float = Field(default=12.00, description="月成本限制")
    is_exceeded: bool = Field(default=False, description="是否超限")

    @field_validator("is_exceeded")
    @classmethod
    def check_exceeded(cls, v, info):
        """检查是否超限"""
        values = info.data
        if "total_cost" in values and "daily_limit" in values:
            return values["total_cost"] >= values["daily_limit"]
        return v
