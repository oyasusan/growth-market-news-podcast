import json
import logging
from datetime import datetime, date
from typing import Optional
from .models import get_connection

logger = logging.getLogger(__name__)


class Repository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self):
        return get_connection(self.db_path)

    # ── Companies ──────────────────────────────────────────────────────────

    def upsert_companies(self, companies: list[dict]) -> None:
        sql = """
            INSERT INTO companies (code, name, name_en, sector, keywords)
            VALUES (:code, :name, :name_en, :sector, :keywords)
            ON CONFLICT(code) DO UPDATE SET
                name=excluded.name,
                name_en=excluded.name_en,
                sector=excluded.sector,
                keywords=excluded.keywords,
                updated_at=datetime('now','localtime')
        """
        with self._conn() as conn:
            for c in companies:
                conn.execute(sql, {
                    "code": c["code"],
                    "name": c["name"],
                    "name_en": c.get("name_en", ""),
                    "sector": c.get("sector", ""),
                    "keywords": json.dumps(c.get("keywords", []), ensure_ascii=False),
                })
        logger.info(f"{len(companies)}社をDBに登録/更新")

    def get_all_companies(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM companies WHERE enabled=1 ORDER BY code"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Market Data ────────────────────────────────────────────────────────

    def upsert_market_data(self, data: dict) -> None:
        sql = """
            INSERT INTO market_data
                (date, company_code, data_type, open_price, high_price,
                 low_price, close_price, volume, turnover,
                 change_amount, change_pct, advance_count, decline_count, unchanged_count)
            VALUES
                (:date, :company_code, :data_type, :open_price, :high_price,
                 :low_price, :close_price, :volume, :turnover,
                 :change_amount, :change_pct, :advance_count, :decline_count, :unchanged_count)
            ON CONFLICT(date, company_code, data_type) DO UPDATE SET
                open_price=excluded.open_price,
                high_price=excluded.high_price,
                low_price=excluded.low_price,
                close_price=excluded.close_price,
                volume=excluded.volume,
                turnover=excluded.turnover,
                change_amount=excluded.change_amount,
                change_pct=excluded.change_pct,
                advance_count=excluded.advance_count,
                decline_count=excluded.decline_count,
                unchanged_count=excluded.unchanged_count
        """
        with self._conn() as conn:
            conn.execute(sql, {
                "date": data.get("date"),
                "company_code": data.get("company_code"),
                "data_type": data.get("data_type", "stock"),
                "open_price": data.get("open_price"),
                "high_price": data.get("high_price"),
                "low_price": data.get("low_price"),
                "close_price": data.get("close_price"),
                "volume": data.get("volume"),
                "turnover": data.get("turnover"),
                "change_amount": data.get("change_amount"),
                "change_pct": data.get("change_pct"),
                "advance_count": data.get("advance_count"),
                "decline_count": data.get("decline_count"),
                "unchanged_count": data.get("unchanged_count"),
            })

    def get_market_data(self, target_date: str, data_type: str = "index") -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM market_data WHERE date=? AND data_type=?",
                (target_date, data_type)
            ).fetchone()
        return dict(row) if row else None

    def get_stock_data_for_date(self, target_date: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT m.*, c.name as company_name, c.sector
                   FROM market_data m
                   LEFT JOIN companies c ON m.company_code = c.code
                   WHERE m.date=? AND m.data_type='stock'
                   ORDER BY ABS(COALESCE(m.change_pct, 0)) DESC""",
                (target_date,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_top_movers(self, target_date: str, n: int = 5) -> dict:
        with self._conn() as conn:
            top_gain = conn.execute(
                """SELECT m.*, c.name, c.sector FROM market_data m
                   LEFT JOIN companies c ON m.company_code = c.code
                   WHERE m.date=? AND m.data_type='stock' AND m.change_pct IS NOT NULL
                   ORDER BY m.change_pct DESC LIMIT ?""",
                (target_date, n)
            ).fetchall()
            top_loss = conn.execute(
                """SELECT m.*, c.name, c.sector FROM market_data m
                   LEFT JOIN companies c ON m.company_code = c.code
                   WHERE m.date=? AND m.data_type='stock' AND m.change_pct IS NOT NULL
                   ORDER BY m.change_pct ASC LIMIT ?""",
                (target_date, n)
            ).fetchall()
            top_volume = conn.execute(
                """SELECT m.*, c.name, c.sector FROM market_data m
                   LEFT JOIN companies c ON m.company_code = c.code
                   WHERE m.date=? AND m.data_type='stock' AND m.volume IS NOT NULL
                   ORDER BY m.volume DESC LIMIT ?""",
                (target_date, n)
            ).fetchall()
        return {
            "top_gainers": [dict(r) for r in top_gain],
            "top_losers": [dict(r) for r in top_loss],
            "top_volume": [dict(r) for r in top_volume],
        }

    # ── News ───────────────────────────────────────────────────────────────

    def upsert_news(self, articles: list[dict]) -> int:
        sql = """
            INSERT OR IGNORE INTO news
                (date, company_code, source, title, url, summary, published_at)
            VALUES
                (:date, :company_code, :source, :title, :url, :summary, :published_at)
        """
        inserted = 0
        with self._conn() as conn:
            for a in articles:
                cur = conn.execute(sql, {
                    "date": a.get("date"),
                    "company_code": a.get("company_code"),
                    "source": a.get("source", ""),
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "summary": a.get("summary", ""),
                    "published_at": a.get("published_at", ""),
                })
                inserted += cur.rowcount
        logger.info(f"ニュース {inserted}/{len(articles)} 件を新規挿入")
        return inserted

    def get_news_for_date(self, target_date: str, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT n.*, c.name as company_name, c.sector
                   FROM news n
                   LEFT JOIN companies c ON n.company_code = c.code
                   WHERE n.date=?
                   ORDER BY n.relevance_score DESC, n.published_at DESC
                   LIMIT ?""",
                (target_date, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Analysis ───────────────────────────────────────────────────────────

    def save_analysis(self, target_date: str, analysis: dict) -> None:
        sql = """
            INSERT INTO analysis
                (date, market_summary, spotlight_companies, theme_analysis,
                 tomorrow_points, trending_stocks, volume_stocks,
                 trending_themes, keywords, raw_prompt, model_used)
            VALUES
                (:date, :market_summary, :spotlight_companies, :theme_analysis,
                 :tomorrow_points, :trending_stocks, :volume_stocks,
                 :trending_themes, :keywords, :raw_prompt, :model_used)
            ON CONFLICT(date) DO UPDATE SET
                market_summary=excluded.market_summary,
                spotlight_companies=excluded.spotlight_companies,
                theme_analysis=excluded.theme_analysis,
                tomorrow_points=excluded.tomorrow_points,
                trending_stocks=excluded.trending_stocks,
                volume_stocks=excluded.volume_stocks,
                trending_themes=excluded.trending_themes,
                keywords=excluded.keywords,
                raw_prompt=excluded.raw_prompt,
                model_used=excluded.model_used
        """
        with self._conn() as conn:
            conn.execute(sql, {
                "date": target_date,
                "market_summary": analysis.get("market_summary", ""),
                "spotlight_companies": json.dumps(
                    analysis.get("spotlight_companies", []), ensure_ascii=False),
                "theme_analysis": analysis.get("theme_analysis", ""),
                "tomorrow_points": analysis.get("tomorrow_points", ""),
                "trending_stocks": json.dumps(
                    analysis.get("trending_stocks", []), ensure_ascii=False),
                "volume_stocks": json.dumps(
                    analysis.get("volume_stocks", []), ensure_ascii=False),
                "trending_themes": json.dumps(
                    analysis.get("trending_themes", []), ensure_ascii=False),
                "keywords": json.dumps(
                    analysis.get("keywords", []), ensure_ascii=False),
                "raw_prompt": analysis.get("raw_prompt", ""),
                "model_used": analysis.get("model_used", ""),
            })
        logger.info(f"分析結果を保存: {target_date}")

    def get_analysis(self, target_date: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM analysis WHERE date=?", (target_date,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        for field in ("spotlight_companies", "trending_stocks",
                      "volume_stocks", "trending_themes", "keywords"):
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
                    result[field] = []
        return result

    # ── Episodes ───────────────────────────────────────────────────────────

    def save_episode(self, episode: dict) -> None:
        sql = """
            INSERT INTO episodes
                (date, title, script_path, audio_path, duration_seconds, file_size_bytes)
            VALUES
                (:date, :title, :script_path, :audio_path, :duration_seconds, :file_size_bytes)
            ON CONFLICT(date) DO UPDATE SET
                title=excluded.title,
                script_path=excluded.script_path,
                audio_path=excluded.audio_path,
                duration_seconds=excluded.duration_seconds,
                file_size_bytes=excluded.file_size_bytes
        """
        with self._conn() as conn:
            conn.execute(sql, {
                "date": episode["date"],
                "title": episode["title"],
                "script_path": episode.get("script_path", ""),
                "audio_path": episode.get("audio_path", ""),
                "duration_seconds": episode.get("duration_seconds"),
                "file_size_bytes": episode.get("file_size_bytes"),
            })
        logger.info(f"エピソード保存: {episode['date']}")

    def get_recent_episodes(self, limit: int = 7) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM episodes ORDER BY date DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_episode_published(self, target_date: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE episodes SET rss_published=1 WHERE date=?", (target_date,)
            )

    # ── Trend Analysis ─────────────────────────────────────────────────────

    def get_trending_stocks_history(self, days: int = 30) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT m.company_code, c.name, c.sector,
                          AVG(m.change_pct) as avg_change,
                          MAX(m.change_pct) as max_change,
                          COUNT(*) as appearance_count
                   FROM market_data m
                   LEFT JOIN companies c ON m.company_code = c.code
                   WHERE m.data_type='stock'
                     AND m.date >= date('now', ?, 'localtime')
                   GROUP BY m.company_code
                   ORDER BY avg_change DESC""",
                (f"-{days} days",)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_keyword_frequency(self, days: int = 30) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT keywords FROM analysis
                   WHERE date >= date('now', ?, 'localtime')
                     AND keywords IS NOT NULL""",
                (f"-{days} days",)
            ).fetchall()

        freq: dict[str, int] = {}
        for row in rows:
            try:
                kws = json.loads(row["keywords"])
                for kw in kws:
                    freq[kw] = freq.get(kw, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass
        return sorted(
            [{"keyword": k, "count": v} for k, v in freq.items()],
            key=lambda x: x["count"],
            reverse=True,
        )
