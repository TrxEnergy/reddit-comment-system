"""
关键词簇数据模型
实现主题 → 意图 → 关键词簇的层次结构
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class SearchIntent(str, Enum):
    """搜索意图枚举"""
    REDUCE_FEES = "reduce_fees"           # 寻找降低手续费方法
    COMPARE_CHAINS = "compare_chains"     # 对比不同链的费用
    COMPLAIN_FEES = "complain_fees"       # 抱怨手续费太高
    ASK_CHEAPEST = "ask_cheapest"         # 询问最便宜方式
    EXPLAIN_FEES = "explain_fees"         # 解释费用机制


class KeywordCluster(BaseModel):
    """
    关键词簇（替代单个关键词）

    一个簇包含8-25个关键词变体，针对特定意图和语言优化
    """

    cluster_id: str = Field(description="簇ID，如 'usdt_fee_reduce_en_t1'")
    intent: SearchIntent = Field(description="搜索意图")
    language: str = Field(description="主语言：en/zh/es/pt等")
    tier: int = Field(description="优先级层级 1-3", ge=1, le=3)

    # 核心关键词（2-4个精准词）
    core_keywords: List[str] = Field(
        description="核心关键词",
        min_items=2,
        max_items=6
    )

    # 短语扩写（4-8个自然句式）
    phrase_expansions: List[str] = Field(
        default_factory=list,
        description="短语扩写"
    )

    # 俗称/错拼（2-5个常见变体）
    colloquial_variants: List[str] = Field(
        default_factory=list,
        description="俗称和错拼"
    )

    # 双语混写（仅非英语簇，3-6个）
    bilingual_mix: Optional[List[str]] = Field(
        default=None,
        description="双语混写（超高命中率）"
    )

    # 历史命中率（动态更新）
    hit_rate: float = Field(
        default=0.5,
        description="历史命中率 0-1",
        ge=0.0,
        le=1.0
    )
    total_queries: int = Field(default=0, description="总查询次数")
    total_hits: int = Field(default=0, description="总命中帖子数")
    last_updated: Optional[datetime] = None

    def get_all_keywords(self) -> List[str]:
        """获取该簇的所有关键词（8-25条）"""
        all_kw = []
        all_kw.extend(self.core_keywords)
        all_kw.extend(self.phrase_expansions)
        all_kw.extend(self.colloquial_variants)
        if self.bilingual_mix:
            all_kw.extend(self.bilingual_mix)
        return all_kw

    def update_hit_rate(self, hits: int):
        """更新命中率"""
        self.total_queries += 1
        self.total_hits += hits
        self.hit_rate = self.total_hits / self.total_queries if self.total_queries > 0 else 0.5
        self.last_updated = datetime.utcnow()

    class Config:
        use_enum_values = True
