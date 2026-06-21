import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
PR_TIMES_RSS = "https://prtimes.jp/rss/company/{code}.rss"
TDNET_URL = "https://www.release.tdnet.info/inbs/I_list_001_{date}.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GrawthPodcastBot/1.0; "
        "+https://github.com/grawth-podcast)"
    )
}


class NewsCollector:
    def __init__(self, settings: dict):
        self.settings = settings
        self.max_age_hours = settings.get("news", {}).get("article_age_limit_hours", 48)
        self.max_per_company = settings.get("news", {}).get("max_articles_per_company", 5)

    def _is_recent(self, published_at: str) -> bool:
        if not published_at:
            return True
        try:
            pub = datetime.strptime(published_at[:19], "%Y-%m-%dT%H:%M:%S")
            return datetime.now() - pub < timedelta(hours=self.max_age_hours)
        except ValueError:
            return True

    def _parse_feed_entry(self, entry, company_code: Optional[str],
                          source: str, target_date: str) -> Optional[dict]:
        title = getattr(entry, "title", "") or ""
        url = getattr(entry, "link", "") or ""
        summary = getattr(entry, "summary", "") or ""

        published_at = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6])
            published_at = dt.isoformat()

        if not self._is_recent(published_at):
            return None

        summary_clean = BeautifulSoup(summary, "html.parser").get_text()[:500]

        return {
            "date": target_date,
            "company_code": company_code,
            "source": source,
            "title": title[:300],
            "url": url[:500],
            "summary": summary_clean,
            "published_at": published_at,
        }

    def fetch_google_news(self, query: str, company_code: Optional[str],
                          target_date: str) -> list[dict]:
        url = GOOGLE_NEWS_RSS.format(query=quote(query))
        try:
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[: self.max_per_company]:
                article = self._parse_feed_entry(entry, company_code, "Google News", target_date)
                if article:
                    articles.append(article)
            return articles
        except Exception as e:
            logger.warning(f"Google News取得失敗 ({query}): {e}")
            return []

    def fetch_prtimes_rss(self, company_code: str, target_date: str) -> list[dict]:
        url = PR_TIMES_RSS.format(code=company_code)
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                return []
            articles = []
            for entry in feed.entries[: self.max_per_company]:
                article = self._parse_feed_entry(entry, company_code, "PR TIMES", target_date)
                if article:
                    articles.append(article)
            return articles
        except Exception as e:
            logger.debug(f"PR TIMES取得失敗 ({company_code}): {e}")
            return []

    def fetch_tdnet(self, target_date: str) -> list[dict]:
        """TDnet（適時開示情報）を取得"""
        date_fmt = datetime.strptime(target_date, "%Y-%m-%d").strftime("%Y%m%d")
        url = TDNET_URL.format(date=date_fmt)
        articles = []
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "lxml")

            table = soup.find("table", class_="J-tbList")
            if not table:
                return []

            for row in table.find_all("tr")[1:50]:
                cols = row.find_all("td")
                if len(cols) < 5:
                    continue
                time_text = cols[0].get_text(strip=True)
                code_text = cols[1].get_text(strip=True)
                company_text = cols[2].get_text(strip=True)
                title_text = cols[3].get_text(strip=True)
                link_tag = cols[3].find("a")
                href = ""
                if link_tag and link_tag.get("href"):
                    href = "https://www.release.tdnet.info" + link_tag["href"]

                articles.append({
                    "date": target_date,
                    "company_code": code_text if len(code_text) <= 6 else None,
                    "source": "TDnet",
                    "title": title_text[:300],
                    "url": href,
                    "summary": f"{company_text} {title_text}",
                    "published_at": f"{target_date}T{time_text}:00" if time_text else "",
                })
        except Exception as e:
            logger.warning(f"TDnet取得失敗: {e}")
        return articles

    def fetch_market_news(self, target_date: str) -> list[dict]:
        """グロース市場全般のニュースを収集"""
        queries = [
            "東証グロース市場",
            "グロース250",
            "東京証券取引所グロース",
        ]
        articles = []
        for query in queries:
            articles.extend(self.fetch_google_news(query, None, target_date))
            time.sleep(1)
        return articles

    def fetch_company_news(self, company: dict, target_date: str) -> list[dict]:
        """特定企業のニュースを収集"""
        articles = []
        code = company["code"]
        keywords = []
        try:
            import json
            kw_raw = company.get("keywords", "[]")
            if isinstance(kw_raw, str):
                keywords = json.loads(kw_raw)
            else:
                keywords = kw_raw
        except Exception:
            keywords = [company["name"]]

        query = f"{company['name']} 株式"
        articles.extend(self.fetch_google_news(query, code, target_date))
        time.sleep(0.5)

        articles.extend(self.fetch_prtimes_rss(code, target_date))
        time.sleep(0.5)

        seen_urls = {a["url"] for a in articles}
        for kw in keywords[1:2]:
            more = self.fetch_google_news(kw, code, target_date)
            for a in more:
                if a["url"] not in seen_urls:
                    articles.append(a)
                    seen_urls.add(a["url"])
            time.sleep(0.5)

        return articles[: self.max_per_company * 2]

    def fetch_all(self, companies: list[dict], target_date: str) -> list[dict]:
        """全ニュースを収集"""
        all_articles = []

        logger.info("市場全般ニュースを収集中...")
        all_articles.extend(self.fetch_market_news(target_date))

        logger.info("TDnet開示情報を収集中...")
        all_articles.extend(self.fetch_tdnet(target_date))

        logger.info(f"{len(companies)}社のニュースを収集中...")
        for company in companies:
            articles = self.fetch_company_news(company, target_date)
            all_articles.extend(articles)
            logger.debug(f"  {company['name']}: {len(articles)}件")
            time.sleep(1)

        seen_urls: set = set()
        unique_articles = []
        for a in all_articles:
            if a["url"] not in seen_urls:
                unique_articles.append(a)
                seen_urls.add(a["url"])

        logger.info(f"ニュース収集完了: 合計{len(unique_articles)}件")
        return unique_articles
