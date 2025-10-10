"""
M3智能筛选系统 - 数据模型
定义池子配置、筛选结果等核心数据结构
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class AccountScale(Enum):
    """账号规模枚举"""
    SMALL = "small"      # 1-50账号
    MEDIUM = "medium"    # 51-100账号
    LARGE = "large"      # 101-200账号


class FilterDecision(Enum):
    """筛选决策枚举"""
    DIRECT_PASS = "direct_pass"      # L1直接通过
    SEND_TO_L2 = "send_to_l2"        # 送L2精筛
    DIRECT_REJECT = "direct_reject"  # L1直接拒绝
    L2_PASS = "l2_pass"              # L2通过
    L2_REJECT = "l2_reject"          # L2拒绝


class PoolConfig(BaseModel):
    """动态池子配置"""
    active_accounts: int = Field(description="当前活跃账号数")
    pool_size: int = Field(description="池子规模（帖子数）")
    buffer_ratio: float = Field(description="安全系数（倍数）")
    account_scale: AccountScale = Field(description="账号规模档位")

    l1_direct_pass_threshold: float = Field(description="L1直通阈值")
    l1_review_threshold: float = Field(description="L1送审阈值（送L2）")
    l2_pass_threshold: float = Field(description="L2通过阈值")

    estimated_l2_calls: int = Field(description="预估L2调用次数")
    estimated_daily_cost: float = Field(description="预估日成本（美元）")

    calculated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True


class L1FilterResult(BaseModel):
    """L1筛选结果（单个帖子）"""
    post_id: str = Field(description="帖子ID")
    score: float = Field(description="L1综合评分 0-1")
    decision: FilterDecision = Field(description="筛选决策")

    topic_relevance_score: float = Field(description="话题相关性得分")
    interaction_potential_score: float = Field(description="互动潜力得分")
    sentiment_score: float = Field(description="情感倾向得分")
    title_quality_score: float = Field(description="标题质量得分")

    processing_time_ms: float = Field(default=0.0, description="处理耗时（毫秒）")

    # [FIX 2025-10-10] 移除use_enum_values，保持decision为枚举对象以便正确比较
    # class Config:
    #     use_enum_values = True


class L2FilterResult(BaseModel):
    """L2筛选结果（单个帖子）"""
    post_id: str = Field(description="帖子ID")
    score: float = Field(description="L2深度评分 0-1")
    decision: FilterDecision = Field(description="筛选决策（L2_PASS/L2_REJECT）")

    comment_angle: Optional[str] = Field(default=None, description="推荐评论切入点")
    risk_level: str = Field(default="low", description="风险等级（low/medium/high）")
    reason: str = Field(default="", description="评分理由")

    l1_pre_score: float = Field(description="L1预评分")
    processing_time_ms: float = Field(default=0.0, description="处理耗时（毫秒）")
    api_cost: float = Field(default=0.0015, description="API调用成本")

    # [FIX 2025-10-10] 移除use_enum_values，保持decision为枚举对象以便正确比较
    # class Config:
    #     use_enum_values = True


class ScreeningStats(BaseModel):
    """筛选统计信息"""
    total_input: int = Field(description="输入帖子总数")

    l1_direct_pass: int = Field(description="L1直通数量")
    l1_sent_to_l2: int = Field(description="L1送审L2数量")
    l1_direct_reject: int = Field(description="L1直接拒绝数量")
    l1_processing_time_s: float = Field(description="L1处理总耗时（秒）")

    l2_pass: int = Field(description="L2通过数量")
    l2_reject: int = Field(description="L2拒绝数量")
    l2_processing_time_s: float = Field(description="L2处理总耗时（秒）")
    l2_total_cost: float = Field(description="L2总成本（美元）")

    final_output: int = Field(description="最终输出帖子数")
    total_processing_time_s: float = Field(description="总处理耗时（秒）")

    pool_utilization_rate: float = Field(description="池子利用率")
    l1_accuracy_rate: Optional[float] = Field(default=None, description="L1准确率（L1直通在L2的确认率）")

    def get_summary(self) -> str:
        """获取统计摘要"""
        return (
            f"输入{self.total_input}帖 → "
            f"L1直通{self.l1_direct_pass} + L2通过{self.l2_pass} = "
            f"最终{self.final_output}帖 | "
            f"利用率{self.pool_utilization_rate:.1%} | "
            f"L2成本${self.l2_total_cost:.4f} | "
            f"总耗时{self.total_processing_time_s:.1f}秒"
        )


class ScreeningResult(BaseModel):
    """完整筛选结果"""
    pool_config: PoolConfig = Field(description="池子配置")
    stats: ScreeningStats = Field(description="统计信息")

    passed_post_ids: List[str] = Field(description="通过的帖子ID列表")
    l1_results: Dict[str, L1FilterResult] = Field(description="L1结果映射 {post_id: result}")
    l2_results: Dict[str, L2FilterResult] = Field(description="L2结果映射 {post_id: result}")

    timestamp: datetime = Field(default_factory=datetime.now)

    def get_final_posts_with_metadata(self) -> List[Dict]:
        """获取最终帖子列表（含元数据）"""
        results = []
        for post_id in self.passed_post_ids:
            l1_result = self.l1_results.get(post_id)
            l2_result = self.l2_results.get(post_id)

            results.append({
                "post_id": post_id,
                "l1_score": l1_result.score if l1_result else None,
                "l2_score": l2_result.score if l2_result else None,
                "decision_path": l1_result.decision.value if l1_result else "unknown",
                "comment_angle": l2_result.comment_angle if l2_result else None,
                "risk_level": l2_result.risk_level if l2_result else "unknown"
            })

        return results


class CostGuardStatus(BaseModel):
    """成本守护状态"""
    daily_cost: float = Field(description="当日已消耗成本")
    monthly_cost: float = Field(description="当月已消耗成本")
    daily_limit: float = Field(description="日成本上限")
    monthly_limit: float = Field(description="月成本上限")

    is_daily_exceeded: bool = Field(description="是否超日限")
    is_monthly_exceeded: bool = Field(description="是否超月限")
    remaining_daily_budget: float = Field(description="剩余日预算")

    last_reset_date: datetime = Field(description="上次重置日期")

    def can_proceed(self) -> bool:
        """是否可以继续调用L2"""
        return not (self.is_daily_exceeded or self.is_monthly_exceeded)
