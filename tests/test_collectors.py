import unittest
from unittest.mock import MagicMock, patch
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def load_settings():
    with open(BASE_DIR / "config" / "settings.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestNewsCollector(unittest.TestCase):
    def setUp(self):
        from src.collectors.news_collector import NewsCollector
        self.settings = load_settings()
        self.collector = NewsCollector(self.settings)

    def test_is_recent_empty_string(self):
        self.assertTrue(self.collector._is_recent(""))

    def test_is_recent_old_date(self):
        self.assertFalse(self.collector._is_recent("2020-01-01T00:00:00"))

    def test_is_recent_today(self):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self.assertTrue(self.collector._is_recent(today))

    def test_parse_feed_entry_none_on_old(self):
        entry = MagicMock()
        entry.title = "古いニュース"
        entry.link = "https://example.com"
        entry.summary = "テスト"
        entry.published_parsed = (2020, 1, 1, 0, 0, 0, 0, 0, 0)
        result = self.collector._parse_feed_entry(entry, "4478", "Test", "2025-01-10")
        self.assertIsNone(result)

    @patch("feedparser.parse")
    def test_fetch_google_news_empty_feed(self, mock_parse):
        mock_parse.return_value = MagicMock(entries=[])
        result = self.collector.fetch_google_news("freee", "4478", "2025-01-10")
        self.assertEqual(result, [])

    @patch("feedparser.parse")
    def test_fetch_prtimes_rss_parse_error(self, mock_parse):
        mock_parse.return_value = MagicMock(bozo=True, entries=[])
        result = self.collector.fetch_prtimes_rss("4478", "2025-01-10")
        self.assertEqual(result, [])


class TestMarketDataCollector(unittest.TestCase):
    def setUp(self):
        from src.collectors.market_data import MarketDataCollector
        self.settings = load_settings()
        self.collector = MarketDataCollector(self.settings)

    def test_calculate_market_breadth(self):
        stock_data = [
            {"change_pct": 2.5},
            {"change_pct": -1.2},
            {"change_pct": 0.0},
            {"change_pct": 3.1},
            {"change_pct": -0.5},
        ]
        breadth = self.collector.calculate_market_breadth(stock_data)
        self.assertEqual(breadth["advance_count"], 2)
        self.assertEqual(breadth["decline_count"], 2)
        self.assertEqual(breadth["unchanged_count"], 1)

    def test_calculate_market_breadth_empty(self):
        breadth = self.collector.calculate_market_breadth([])
        self.assertEqual(breadth["advance_count"], 0)
        self.assertEqual(breadth["decline_count"], 0)


if __name__ == "__main__":
    unittest.main()
