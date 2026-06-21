import logging
import time
from datetime import datetime, date, timedelta
from typing import Optional

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

GROWTH_INDEX_TICKERS = [
    "^TDXP",
    "2556.T",
]


def _safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        return None if pd.isna(f) else round(f, 2)
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    try:
        f = float(val)
        return None if pd.isna(f) else int(f)
    except (TypeError, ValueError):
        return None


class MarketDataCollector:
    def __init__(self, settings: dict):
        self.settings = settings

    def fetch_index_data(self, target_date: str) -> Optional[dict]:
        """グロース市場250指数を取得（複数ソースを試行）"""
        for ticker in GROWTH_INDEX_TICKERS:
            try:
                data = self._fetch_yfinance(ticker, target_date)
                if data:
                    data["data_type"] = "index"
                    data["company_code"] = None
                    logger.info(f"指数データ取得成功: {ticker} ({target_date})")
                    return data
            except Exception as e:
                logger.warning(f"指数データ取得失敗 {ticker}: {e}")
                time.sleep(1)

        logger.warning("指数データ取得失敗 - 全ソース試行済み")
        return None

    def fetch_stock_data(self, company_code: str, target_date: str) -> Optional[dict]:
        """個別銘柄データを取得"""
        ticker = f"{company_code}.T"
        try:
            data = self._fetch_yfinance(ticker, target_date)
            if data:
                data["data_type"] = "stock"
                data["company_code"] = company_code
                return data
        except Exception as e:
            logger.warning(f"株価データ取得失敗 {company_code}: {e}")
        return None

    def _fetch_yfinance(self, ticker: str, target_date: str) -> Optional[dict]:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        start = dt - timedelta(days=5)
        end = dt + timedelta(days=1)

        t = yf.Ticker(ticker)
        hist = t.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

        if hist.empty:
            return None

        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        target_dt = pd.Timestamp(target_date)

        row = None
        if target_dt in hist.index:
            row = hist.loc[target_dt]
        else:
            valid = hist[hist.index <= target_dt]
            if not valid.empty:
                row = valid.iloc[-1]

        if row is None:
            return None

        close = _safe_float(row.get("Close"))
        prev_close = None
        idx_pos = hist.index.get_loc(row.name) if hasattr(row, "name") else -1
        if idx_pos > 0:
            prev_row = hist.iloc[idx_pos - 1]
            prev_close = _safe_float(prev_row.get("Close"))

        change_amount = None
        change_pct = None
        if close is not None and prev_close is not None and prev_close != 0:
            change_amount = round(close - prev_close, 2)
            change_pct = round((close - prev_close) / prev_close * 100, 2)

        return {
            "date": target_date,
            "open_price": _safe_float(row.get("Open")),
            "high_price": _safe_float(row.get("High")),
            "low_price": _safe_float(row.get("Low")),
            "close_price": close,
            "volume": _safe_int(row.get("Volume")),
            "turnover": None,
            "change_amount": change_amount,
            "change_pct": change_pct,
            "advance_count": None,
            "decline_count": None,
            "unchanged_count": None,
        }

    def fetch_all_stocks(self, companies: list[dict], target_date: str) -> list[dict]:
        """全監視銘柄のデータを取得"""
        results = []
        for company in companies:
            code = company["code"]
            data = self.fetch_stock_data(code, target_date)
            if data:
                results.append(data)
                logger.debug(f"取得成功: {company['name']} ({code})")
            else:
                logger.warning(f"取得失敗: {company['name']} ({code})")
            time.sleep(0.5)  # API負荷軽減

        if results:
            advance = sum(1 for r in results if (r.get("change_pct") or 0) > 0)
            decline = sum(1 for r in results if (r.get("change_pct") or 0) < 0)
            unchanged = len(results) - advance - decline
            logger.info(f"監視銘柄: 上昇{advance} / 下落{decline} / 横ばい{unchanged}")

        return results

    def calculate_market_breadth(self, stock_data: list[dict]) -> dict:
        """監視銘柄から市場の幅を計算"""
        advance = sum(1 for r in stock_data if (r.get("change_pct") or 0) > 0)
        decline = sum(1 for r in stock_data if (r.get("change_pct") or 0) < 0)
        unchanged = len(stock_data) - advance - decline
        return {
            "advance_count": advance,
            "decline_count": decline,
            "unchanged_count": unchanged,
        }
