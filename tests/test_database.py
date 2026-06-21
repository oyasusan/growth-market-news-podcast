import json
import os
import tempfile
import unittest

from src.database.models import initialize_database
from src.database.repository import Repository


class TestRepository(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.sqlite")
        initialize_database(self.db_path)
        self.repo = Repository(self.db_path)

    def test_upsert_companies(self):
        companies = [
            {"code": "4478", "name": "freee", "name_en": "freee K.K.",
             "sector": "SaaS", "keywords": ["freee", "クラウド会計"]},
            {"code": "5253", "name": "COVER", "name_en": "COVER Corporation",
             "sector": "エンタメ", "keywords": ["COVER", "ホロライブ"]},
        ]
        self.repo.upsert_companies(companies)
        result = self.repo.get_all_companies()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["code"], "4478")

    def test_upsert_companies_idempotent(self):
        companies = [{"code": "4478", "name": "freee", "sector": "SaaS", "keywords": []}]
        self.repo.upsert_companies(companies)
        self.repo.upsert_companies(companies)
        result = self.repo.get_all_companies()
        self.assertEqual(len(result), 1)

    def test_upsert_market_data(self):
        data = {
            "date": "2025-01-10",
            "company_code": None,
            "data_type": "index",
            "close_price": 850.5,
            "change_pct": 1.23,
            "volume": 1000000,
        }
        self.repo.upsert_market_data(data)
        result = self.repo.get_market_data("2025-01-10", "index")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["close_price"], 850.5)

    def test_upsert_market_data_update(self):
        data = {"date": "2025-01-10", "data_type": "index", "close_price": 850.0}
        self.repo.upsert_market_data(data)
        data["close_price"] = 900.0
        self.repo.upsert_market_data(data)
        result = self.repo.get_market_data("2025-01-10", "index")
        self.assertAlmostEqual(result["close_price"], 900.0)

    def test_upsert_news(self):
        articles = [
            {"date": "2025-01-10", "company_code": "4478", "source": "Google News",
             "title": "freeeが新機能を発表", "url": "https://example.com/1",
             "summary": "テスト", "published_at": "2025-01-10T09:00:00"},
            {"date": "2025-01-10", "company_code": "5253", "source": "PR TIMES",
             "title": "COVERが新VTuberデビュー", "url": "https://example.com/2",
             "summary": "テスト2", "published_at": "2025-01-10T10:00:00"},
        ]
        count = self.repo.upsert_news(articles)
        self.assertEqual(count, 2)

        count2 = self.repo.upsert_news(articles)
        self.assertEqual(count2, 0)

    def test_get_news_for_date(self):
        articles = [
            {"date": "2025-01-10", "company_code": "4478", "source": "Test",
             "title": f"ニュース{i}", "url": f"https://example.com/{i}",
             "summary": "", "published_at": ""}
            for i in range(5)
        ]
        self.repo.upsert_news(articles)
        result = self.repo.get_news_for_date("2025-01-10")
        self.assertEqual(len(result), 5)

    def test_save_and_get_analysis(self):
        analysis = {
            "market_summary": "テスト市場サマリー",
            "spotlight_companies": [{"code": "4478", "name": "freee", "reason": "テスト", "detail": "詳細"}],
            "theme_analysis": "テーマ分析",
            "tomorrow_points": "明日の注目",
            "trending_themes": ["AI", "SaaS"],
            "keywords": ["freee", "グロース"],
            "model_used": "test-model",
            "raw_prompt": "",
        }
        self.repo.save_analysis("2025-01-10", analysis)
        result = self.repo.get_analysis("2025-01-10")
        self.assertIsNotNone(result)
        self.assertEqual(result["market_summary"], "テスト市場サマリー")
        self.assertIsInstance(result["spotlight_companies"], list)
        self.assertEqual(len(result["spotlight_companies"]), 1)
        self.assertIsInstance(result["trending_themes"], list)

    def test_save_and_get_episode(self):
        episode = {
            "date": "2025-01-10",
            "title": "2025-01-10のグロース市場ニュース",
            "script_path": "/tmp/script.txt",
            "audio_path": "/tmp/podcast.mp3",
            "duration_seconds": 420,
            "file_size_bytes": 7000000,
        }
        self.repo.save_episode(episode)
        result = self.repo.get_recent_episodes(limit=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["duration_seconds"], 420)

    def test_get_top_movers(self):
        companies = [{"code": str(i), "name": f"Company{i}", "keywords": []} for i in range(5)]
        self.repo.upsert_companies(companies)

        for i, c in enumerate(companies):
            self.repo.upsert_market_data({
                "date": "2025-01-10",
                "company_code": c["code"],
                "data_type": "stock",
                "close_price": 1000 + i * 10,
                "change_pct": (i - 2) * 2.0,
                "volume": (i + 1) * 100000,
            })

        result = self.repo.get_top_movers("2025-01-10", n=3)
        self.assertIn("top_gainers", result)
        self.assertIn("top_losers", result)
        self.assertIn("top_volume", result)
        self.assertLessEqual(len(result["top_gainers"]), 3)


if __name__ == "__main__":
    unittest.main()
