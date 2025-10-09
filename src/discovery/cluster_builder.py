"""
关键词簇构建器
构建30个内置关键词簇（10语言 × 3层级）
"""

import json
import os
from typing import List
from datetime import datetime
from dataclasses import dataclass

from src.discovery.cluster_models import KeywordCluster, SearchIntent
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SubredditCluster:
    """Subreddit簇（用于发现引擎）"""
    subreddit_name: str
    category: str
    description: str = ""


class ClusterBuilder:
    """关键词簇构建器"""

    def get_all_clusters(self) -> List[SubredditCluster]:
        """获取所有Subreddit簇（30个）"""
        return [
            SubredditCluster("CryptoCurrency", "crypto_general", "General crypto discussion"),
            SubredditCluster("Bitcoin", "crypto_general", "Bitcoin community"),
            SubredditCluster("ethereum", "crypto_general", "Ethereum discussion"),
            SubredditCluster("CryptoTechnology", "crypto_general", "Crypto tech"),
            SubredditCluster("CryptoMarkets", "trading", "Market analysis"),
            SubredditCluster("altcoin", "crypto_general", "Altcoin discussion"),
            SubredditCluster("BlockChain", "crypto_general", "Blockchain tech"),
            SubredditCluster("defi", "crypto_general", "DeFi ecosystem"),

            SubredditCluster("Tronix", "tron_ecosystem", "Official TRON"),
            SubredditCluster("TronTRX", "tron_ecosystem", "TRON TRX"),
            SubredditCluster("Tronscan", "tron_ecosystem", "TRON explorer"),
            SubredditCluster("JustStable", "tron_ecosystem", "USDD stablecoin"),
            SubredditCluster("SunSwap", "tron_ecosystem", "SunSwap DEX"),
            SubredditCluster("TronLink", "tron_ecosystem", "TronLink wallet"),

            SubredditCluster("SatoshiStreetBets", "trading", "Crypto trading bets"),
            SubredditCluster("CryptoMoonShots", "meme_culture", "Moonshot coins"),
            SubredditCluster("CryptoCurrencyTrading", "trading", "Trading discussion"),
            SubredditCluster("CoinMarketCap", "trading", "CMC community"),
            SubredditCluster("binance", "trading", "Binance exchange"),
            SubredditCluster("CoinBase", "trading", "Coinbase users"),

            SubredditCluster("ethdev", "development", "Ethereum dev"),
            SubredditCluster("CryptoDev", "development", "Crypto development"),
            SubredditCluster("bitcoindev", "development", "Bitcoin dev"),
            SubredditCluster("solidity", "development", "Solidity language"),
            SubredditCluster("web3", "development", "Web3 development"),

            SubredditCluster("SatoshiStreetDegens", "meme_culture", "Degen culture"),
            SubredditCluster("CryptoMeme", "meme_culture", "Crypto memes"),
            SubredditCluster("CryptoHumor", "meme_culture", "Crypto humor"),
            SubredditCluster("dogecoin", "meme_culture", "Dogecoin community"),
            SubredditCluster("Shibainucoin", "meme_culture", "Shiba Inu"),
        ]

    def build_clusters(self) -> List[KeywordCluster]:
        """构建完整的关键词簇池"""
        clusters = []

        # Tier 1: 英语簇
        clusters.extend(self._build_english_tier1())

        # Tier 1: 中文簇（带双语混写）
        clusters.extend(self._build_chinese_tier1())

        # Tier 1: 西班牙语簇
        clusters.extend(self._build_spanish_tier1())

        # Tier 2: 葡萄牙语、越南语、印地语
        clusters.extend(self._build_tier2_clusters())

        # Tier 3: 其他语言
        clusters.extend(self._build_tier3_clusters())

        logger.info(f"构建关键词簇完成，共{len(clusters)}个簇")
        return clusters

    def _build_english_tier1(self) -> List[KeywordCluster]:
        """构建英语Tier1簇"""
        return [
            KeywordCluster(
                cluster_id="usdt_fee_reduce_en_t1",
                intent=SearchIntent.REDUCE_FEES,
                language="en",
                tier=1,
                core_keywords=[
                    "USDT withdrawal fee",
                    "TRC20 fee",
                    "TRON network fee",
                    "cheap USDT transfer"
                ],
                phrase_expansions=[
                    "how to reduce USDT fees",
                    "USDT send fee too high",
                    "cheapest way to transfer USDT",
                    "avoid high USDT withdrawal fees",
                    "USDT fee comparison TRC20 ERC20",
                    "why TRC20 USDT cheaper"
                ],
                colloquial_variants=[
                    "trc-20",
                    "trc20 usdt",
                    "trx usdt fee",
                    "tron usdt cost",
                    "usdt trc20 cheap"
                ]
            ),
            KeywordCluster(
                cluster_id="usdt_fee_complain_en_t1",
                intent=SearchIntent.COMPLAIN_FEES,
                language="en",
                tier=1,
                core_keywords=[
                    "USDT fee too high",
                    "Binance withdrawal fee expensive",
                    "Coinbase USDT withdrawal"
                ],
                phrase_expansions=[
                    "Binance USDT withdrawal fee ridiculous",
                    "why does Binance charge so much for USDT",
                    "USDT withdrawal fees are insane",
                    "got charged high fee withdrawing USDT"
                ],
                colloquial_variants=[
                    "binance usdt fee wtf",
                    "usdt withdrawal scam",
                    "usdt fee ripoff"
                ]
            )
        ]

    def _build_chinese_tier1(self) -> List[KeywordCluster]:
        """构建中文Tier1簇（带双语混写）"""
        return [
            KeywordCluster(
                cluster_id="usdt_fee_reduce_zh_t1",
                intent=SearchIntent.REDUCE_FEES,
                language="zh",
                tier=1,
                core_keywords=[
                    "USDT 提现 手续费",
                    "USDT 手续费 太高",
                    "TRC20 手续费",
                    "波场 手续费 便宜"
                ],
                phrase_expansions=[
                    "USDT 怎么 提现 便宜",
                    "TRC20 和 ERC20 手续费 对比",
                    "波场 转账 USDT 手续费",
                    "币安 提现 USDT 手续费"
                ],
                colloquial_variants=[
                    "trc20 usdt",
                    "波场 usdt",
                    "trx 手续费"
                ],
                bilingual_mix=[
                    "USDT 手续费 cheap",
                    "TRC20 提现 fee",
                    "TRON 转账 手续费 low",
                    "波场 USDT fee",
                    "USDT withdrawal 手续费",
                    "cheapest USDT 提现"
                ]
            )
        ]

    def _build_spanish_tier1(self) -> List[KeywordCluster]:
        """构建西班牙语Tier1簇"""
        return [
            KeywordCluster(
                cluster_id="usdt_fee_reduce_es_t1",
                intent=SearchIntent.REDUCE_FEES,
                language="es",
                tier=1,
                core_keywords=[
                    "tarifas TRON",
                    "comisiones TRX",
                    "TRC20 USDT"
                ],
                phrase_expansions=[
                    "cómo reducir tarifas USDT",
                    "USDT TRC20 más barato",
                    "comisiones retiro USDT"
                ],
                colloquial_variants=[
                    "trc20 usdt",
                    "comisión usdt"
                ],
                bilingual_mix=[
                    "USDT fee tarifas",
                    "TRC20 comisión cheap",
                    "TRON tarifas low"
                ]
            )
        ]

    def _build_tier2_clusters(self) -> List[KeywordCluster]:
        """构建Tier2簇（葡萄牙语、越南语、印地语）"""
        return [
            # 葡萄牙语
            KeywordCluster(
                cluster_id="usdt_fee_reduce_pt_t2",
                intent=SearchIntent.REDUCE_FEES,
                language="pt",
                tier=2,
                core_keywords=[
                    "taxas TRON",
                    "taxas TRX"
                ],
                phrase_expansions=[
                    "taxas de retirada USDT",
                    "transferência barata USDT"
                ],
                bilingual_mix=[
                    "USDT fee taxas",
                    "TRC20 taxas cheap"
                ]
            ),
            # 越南语
            KeywordCluster(
                cluster_id="usdt_fee_reduce_vi_t2",
                intent=SearchIntent.REDUCE_FEES,
                language="vi",
                tier=2,
                core_keywords=[
                    "phí TRON",
                    "phí TRX"
                ],
                phrase_expansions=[
                    "phí rút USDT",
                    "chuyển USDT rẻ"
                ],
                bilingual_mix=[
                    "USDT fee phí",
                    "TRC20 phí cheap"
                ]
            )
        ]

    def _build_tier3_clusters(self) -> List[KeywordCluster]:
        """构建Tier3簇（泰语、阿拉伯语、土耳其语、印尼语）"""
        return [
            # 泰语
            KeywordCluster(
                cluster_id="usdt_fee_reduce_th_t3",
                intent=SearchIntent.REDUCE_FEES,
                language="th",
                tier=3,
                core_keywords=[
                    "ค่าธรรมเนียม TRON",
                    "USDT ค่าธรรมเนียม"
                ],
                bilingual_mix=[
                    "USDT fee ค่าธรรมเนียม",
                    "TRC20 ค่าธรรมเนียม cheap"
                ]
            )
        ]

    def load_from_file(self, filepath: str) -> List[KeywordCluster]:
        """从外部JSON加载簇（支持动态修改）"""
        if not os.path.exists(filepath):
            logger.warning(f"簇配置文件不存在: {filepath}，使用内置簇")
            return self.build_clusters()

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        clusters = [KeywordCluster(**cluster) for cluster in data["clusters"]]
        logger.info(f"从文件加载簇: {len(clusters)}个")
        return clusters

    def save_clusters(self, clusters: List[KeywordCluster], filepath: str):
        """保存簇配置到JSON"""
        data = {
            "clusters": [c.dict() for c in clusters],
            "updated_at": datetime.utcnow().isoformat()
        }
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"簇配置已保存: {filepath}")
