import unittest
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def load_settings():
    with open(BASE_DIR / "config" / "settings.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestScriptGenerator(unittest.TestCase):
    def setUp(self):
        from src.generators.script_generator import ScriptGenerator
        self.settings = load_settings()
        self.gen = ScriptGenerator(self.settings)

    def test_generate_basic(self):
        script = self.gen.generate(
            target_date="2025-01-10",
            market_data={
                "close_price": 850.5,
                "change_pct": 1.23,
                "change_amount": 10.3,
                "advance_count": 8,
                "decline_count": 5,
            },
            stock_data=[
                {"company_code": "4478", "close_price": 2000, "change_pct": 3.5, "volume": 500000},
            ],
            news=[
                {"title": "freeeが新機能発表", "company_code": "4478",
                 "company_name": "freee", "source": "Google News"},
            ],
            analysis={
                "market_summary": "本日のグロース市場は上昇しました。",
                "spotlight_companies": [
                    {"code": "4478", "name": "freee", "reason": "出来高急増", "detail": "詳細情報"},
                ],
                "theme_analysis": "AI関連銘柄に資金流入しました。",
                "tomorrow_points": "明日は複数社の決算発表があります。",
                "trending_themes": ["AI", "SaaS"],
                "keywords": ["freee", "AI"],
            },
            ipo_text="直近のIPO情報はありません。",
        )

        self.assertIsInstance(script, str)
        self.assertGreater(len(script), 100)
        self.assertIn("2025年1月10日", script)
        self.assertIn("グロース市場", script)
        self.assertIn("投資助言ではありません", script)
        self.assertIn("freee", script)

    def test_generate_without_market_data(self):
        script = self.gen.generate(
            target_date="2025-01-10",
            market_data=None,
            stock_data=[],
            news=[],
            analysis={
                "market_summary": "",
                "spotlight_companies": [],
                "theme_analysis": "",
                "tomorrow_points": "",
                "trending_themes": [],
                "keywords": [],
            },
            ipo_text="",
        )
        self.assertIsInstance(script, str)
        self.assertGreater(len(script), 50)

    def test_disclaimer_present(self):
        script = self.gen.generate(
            target_date="2025-06-01",
            market_data=None,
            stock_data=[],
            news=[],
            analysis={
                "market_summary": "市場テスト",
                "spotlight_companies": [],
                "theme_analysis": "",
                "tomorrow_points": "",
                "trending_themes": [],
                "keywords": [],
            },
            ipo_text="",
        )
        self.assertIn("教育目的", script)


class TestRSSGenerator(unittest.TestCase):
    def setUp(self):
        import os, tempfile
        from src.generators.rss_generator import RSSGenerator
        self.settings = load_settings()
        os.environ["PODCAST_BASE_URL"] = "https://test.github.io/grawth-podcast"
        os.environ["PODCAST_TITLE"] = "テストPodcast"
        self.gen = RSSGenerator(self.settings)
        self.tmpdir = tempfile.mkdtemp()

    def _make_dummy_mp3(self, date_str: str) -> str:
        path = Path(self.tmpdir) / f"podcast_{date_str}.mp3"
        path.write_bytes(b"\xff\xfb" * 100)
        return str(path)

    def test_generate_empty(self):
        rss = self.gen.generate([])
        self.assertIn("<?xml", rss)
        self.assertIn("<rss", rss)
        self.assertIn("<channel>", rss)

    def test_generate_with_episodes(self):
        mp3_path = self._make_dummy_mp3("2025-01-10")
        episodes = [
            {
                "date": "2025-01-10",
                "title": "2025-01-10のグロース市場ニュース",
                "audio_path": mp3_path,
                "duration_seconds": 420,
                "file_size_bytes": 7000000,
            }
        ]
        rss = self.gen.generate(episodes)
        self.assertIn("<item>", rss)
        self.assertIn("2025-01-10", rss)
        self.assertIn("audio/mpeg", rss)
        self.assertIn("itunes", rss)

    def test_max_episodes_limit(self):
        episodes = []
        for i in range(10):
            date_str = f"2025-01-{i+1:02d}"
            mp3_path = self._make_dummy_mp3(date_str)
            episodes.append({
                "date": date_str,
                "title": f"{date_str}のニュース",
                "audio_path": mp3_path,
                "duration_seconds": 300,
                "file_size_bytes": 5000000,
            })
        rss = self.gen.generate(episodes)
        item_count = rss.count("<item>")
        self.assertLessEqual(item_count, self.settings["podcast"]["max_episodes_in_rss"])


if __name__ == "__main__":
    unittest.main()
