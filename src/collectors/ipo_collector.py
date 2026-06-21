import logging
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

JPX_IPO_URL = "https://www.jpx.co.jp/listing/stocks/new/index.html"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GrawthPodcastBot/1.0; "
        "+https://github.com/grawth-podcast)"
    )
}


class IPOCollector:
    def fetch_upcoming_ipos(self) -> list[dict]:
        """JPXからIPOスケジュールを取得"""
        ipos = []
        try:
            resp = requests.get(JPX_IPO_URL, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "lxml")

            table = soup.find("table")
            if not table:
                logger.warning("IPOテーブルが見つかりません")
                return []

            headers_row = table.find("tr")
            if not headers_row:
                return []

            for row in table.find_all("tr")[1:]:
                cols = row.find_all(["td", "th"])
                if len(cols) < 4:
                    continue

                texts = [c.get_text(strip=True) for c in cols]
                ipo = {
                    "listing_date": texts[0] if len(texts) > 0 else "",
                    "code": texts[1] if len(texts) > 1 else "",
                    "name": texts[2] if len(texts) > 2 else "",
                    "market": texts[3] if len(texts) > 3 else "",
                    "business": texts[4] if len(texts) > 4 else "",
                    "price": texts[5] if len(texts) > 5 else "",
                }
                if ipo["name"] and "グロース" in ipo.get("market", ""):
                    ipos.append(ipo)

        except Exception as e:
            logger.warning(f"IPO情報取得失敗: {e}")

        logger.info(f"IPO情報: {len(ipos)}件取得")
        return ipos

    def get_upcoming_ipos_text(self, days_ahead: int = 7) -> str:
        """今後のIPOをテキストで返す"""
        ipos = self.fetch_upcoming_ipos()
        if not ipos:
            return "直近のIPO情報はありません。"

        today = datetime.now()
        upcoming = []
        for ipo in ipos:
            date_str = ipo.get("listing_date", "")
            try:
                listing_dt = datetime.strptime(date_str, "%Y/%m/%d")
                days_until = (listing_dt - today).days
                if 0 <= days_until <= days_ahead:
                    upcoming.append(
                        f"・{date_str} {ipo['name']}（{ipo.get('code', '')}）{ipo.get('market', '')}"
                    )
            except ValueError:
                if date_str:
                    upcoming.append(
                        f"・{date_str} {ipo['name']}（{ipo.get('code', '')}）{ipo.get('market', '')}"
                    )

        if not upcoming:
            return f"今後{days_ahead}日間のグロース市場IPOはありません。"

        return "今後のIPO予定:\n" + "\n".join(upcoming[:5])
