import json
import logging
from collections import Counter

from ..database.repository import Repository

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    def __init__(self, repo: Repository):
        self.repo = repo

    def generate_analysis_json(self, target_date: str) -> dict:
        """蓄積データからトレンド分析JSONを生成"""
        trending_stocks_30d = self.repo.get_trending_stocks_history(days=30)
        keyword_freq = self.repo.get_keyword_frequency(days=30)

        top_gainers = sorted(
            trending_stocks_30d, key=lambda x: x.get("avg_change", 0), reverse=True
        )[:10]
        top_losers = sorted(
            trending_stocks_30d, key=lambda x: x.get("avg_change", 0)
        )[:5]
        top_volume = sorted(
            trending_stocks_30d, key=lambda x: x.get("appearance_count", 0), reverse=True
        )[:10]

        analysis = self.repo.get_analysis(target_date)
        theme_counter: Counter = Counter()
        if analysis and analysis.get("trending_themes"):
            themes = analysis["trending_themes"]
            if isinstance(themes, list):
                theme_counter.update(themes)

        for i in range(1, 30):
            from datetime import date, timedelta
            d = (date.fromisoformat(target_date) - timedelta(days=i)).isoformat()
            past_analysis = self.repo.get_analysis(d)
            if past_analysis and past_analysis.get("trending_themes"):
                themes = past_analysis["trending_themes"]
                if isinstance(themes, list):
                    weight = max(1, 30 - i)
                    for t in themes:
                        theme_counter[t] += weight

        top_themes = [
            {"theme": t, "score": s}
            for t, s in theme_counter.most_common(10)
        ]

        result = {
            "generated_at": target_date,
            "period_days": 30,
            "top_gainers_30d": [
                {
                    "code": s["company_code"],
                    "name": s.get("name", s["company_code"]),
                    "sector": s.get("sector", ""),
                    "avg_change_pct": round(s.get("avg_change", 0) or 0, 2),
                    "max_change_pct": round(s.get("max_change", 0) or 0, 2),
                }
                for s in top_gainers
            ],
            "top_losers_30d": [
                {
                    "code": s["company_code"],
                    "name": s.get("name", s["company_code"]),
                    "avg_change_pct": round(s.get("avg_change", 0) or 0, 2),
                }
                for s in top_losers
            ],
            "top_volume_stocks": [
                {
                    "code": s["company_code"],
                    "name": s.get("name", s["company_code"]),
                    "appearance_count": s.get("appearance_count", 0),
                }
                for s in top_volume
            ],
            "trending_themes": top_themes,
            "top_keywords": keyword_freq[:20],
        }

        logger.info(f"トレンド分析JSON生成完了: {target_date}")
        return result
