"""
L2深度筛选器
基于GPT-4o-mini的深度质量评估
"""

import time
import json
import asyncio
from typing import List, Dict, Optional
from openai import AsyncOpenAI

from src.core.logging import get_logger
from src.discovery.models import RawPost
from src.screening.models import L2FilterResult, FilterDecision, L1FilterResult

logger = get_logger(__name__)


class L2DeepFilter:
    """L2深度筛选器 - GPT-4o-mini深度评估"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        pass_threshold: float = 0.65,
        max_concurrency: int = 10,
        cost_per_call: float = 0.0015,
        temperature: float = 0.3,
        max_tokens: int = 150
    ):
        """
        初始化L2筛选器

        Args:
            api_key: OpenAI API密钥
            model: 模型名称
            pass_threshold: 通过阈值
            max_concurrency: 最大并发数
            cost_per_call: 单次调用成本
            temperature: 生成温度
            max_tokens: 最大token数
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.pass_threshold = pass_threshold
        self.max_concurrency = max_concurrency
        self.cost_per_call = cost_per_call
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.semaphore = asyncio.Semaphore(max_concurrency)

        logger.info(
            f"L2筛选器初始化 - 模型:{model}, 通过阈值:{pass_threshold}, "
            f"并发数:{max_concurrency}"
        )

    def _build_prompt(
        self,
        post: RawPost,
        l1_score: float,
        active_account_count: int
    ) -> str:
        """
        构建评估Prompt

        Args:
            post: 待评估帖子
            l1_score: L1预评分
            active_account_count: 当前活跃账号数

        Returns:
            Prompt字符串
        """
        selftext_preview = post.selftext[:300] if post.selftext else "(无正文)"

        # [2025-10-10] 通用加密货币相关性判断（不针对特定业务）
        prompt = f"""你是Reddit内容评估专家。任务：判断帖子是否与加密货币相关。

输入信息:
- 标题: {post.title}
- 正文摘要: {selftext_preview}
- 子版: {post.cluster_id}
- 热度: {post.score}赞 / {post.num_comments}评论

请以JSON格式输出:
{{
  "score": 0.0-1.0,
  "pass": true/false,
  "comment_angle": "可以从哪个角度评论（1句话）",
  "risk_level": "low/medium/high",
  "reason": "简要说明（不超过30字）"
}}

判断标准（极度宽松）:
1. 只要提到以下任意内容，直接通过:
   - 加密货币、虚拟货币、数字货币
   - 区块链、Web3、DeFi、NFT
   - 交易所、钱包、转账、手续费
   - 比特币、以太坊、TRON、USDT等任何币种
   - 挖矿、质押、流动性、Gas费

2. 只拒绝以下情况:
   - 完全无关（如体育、娱乐、政治等）
   - 高风险（色情、暴力、极端争议）

注意: 宽松判断，只要沾边就通过！"""

        return prompt

    async def _evaluate_single_post(
        self,
        post: RawPost,
        l1_result: L1FilterResult,
        active_account_count: int
    ) -> L2FilterResult:
        """
        评估单个帖子

        Args:
            post: 待评估帖子
            l1_result: L1筛选结果
            active_account_count: 活跃账号数

        Returns:
            L2筛选结果
        """
        async with self.semaphore:
            start_time = time.time()

            try:
                prompt = self._build_prompt(post, l1_result.score, active_account_count)

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是专业的Reddit内容评估专家。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content
                result_data = json.loads(content)

                score = float(result_data.get("score", 0.5))
                passed = result_data.get("pass", False)
                comment_angle = result_data.get("comment_angle", "")
                risk_level = result_data.get("risk_level", "medium")
                reason = result_data.get("reason", "")

                decision = FilterDecision.L2_PASS if (score >= self.pass_threshold and passed) else FilterDecision.L2_REJECT

                processing_time = (time.time() - start_time) * 1000

                return L2FilterResult(
                    post_id=post.post_id,
                    score=score,
                    decision=decision,
                    comment_angle=comment_angle,
                    risk_level=risk_level,
                    reason=reason,
                    l1_pre_score=l1_result.score,
                    processing_time_ms=processing_time,
                    api_cost=self.cost_per_call
                )

            except json.JSONDecodeError as e:
                logger.error(f"L2评估JSON解析失败 (帖子{post.post_id}): {e}")
                return self._create_fallback_result(post, l1_result, start_time)

            except Exception as e:
                logger.error(f"L2评估失败 (帖子{post.post_id}): {e}")
                return self._create_fallback_result(post, l1_result, start_time)

    def _create_fallback_result(
        self,
        post: RawPost,
        l1_result: L1FilterResult,
        start_time: float
    ) -> L2FilterResult:
        """创建降级结果（API失败时）"""
        processing_time = (time.time() - start_time) * 1000

        return L2FilterResult(
            post_id=post.post_id,
            score=l1_result.score * 0.8,
            decision=FilterDecision.L2_REJECT,
            comment_angle=None,
            risk_level="high",
            reason="API调用失败",
            l1_pre_score=l1_result.score,
            processing_time_ms=processing_time,
            api_cost=0.0
        )

    async def filter_posts(
        self,
        posts: List[RawPost],
        l1_results: Dict[str, L1FilterResult],
        active_account_count: int
    ) -> List[L2FilterResult]:
        """
        批量筛选帖子（异步并发）

        Args:
            posts: 待筛选帖子列表（已经过L1送审的）
            l1_results: L1筛选结果映射 {post_id: L1FilterResult}
            active_account_count: 活跃账号数

        Returns:
            L2筛选结果列表
        """
        if not posts:
            logger.warning("L2输入帖子列表为空")
            return []

        logger.info(f"开始L2深度筛选 - 待评估:{len(posts)}帖, 并发数:{self.max_concurrency}")

        tasks = []
        for post in posts:
            l1_result = l1_results.get(post.post_id)
            if not l1_result:
                logger.warning(f"帖子{post.post_id}缺少L1结果，跳过")
                continue

            task = self._evaluate_single_post(post, l1_result, active_account_count)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"L2任务异常: {result}")
            elif isinstance(result, L2FilterResult):
                valid_results.append(result)

        pass_count = sum(1 for r in valid_results if r.decision == FilterDecision.L2_PASS)
        total_cost = sum(r.api_cost for r in valid_results)

        logger.info(
            f"L2筛选完成 - 总计:{len(valid_results)}帖, "
            f"通过:{pass_count}, 拒绝:{len(valid_results) - pass_count}, "
            f"成本:${total_cost:.4f}"
        )

        return valid_results
