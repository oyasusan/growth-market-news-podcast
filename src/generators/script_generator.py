import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "本Podcastは教育目的の情報提供であり、投資助言ではありません。"
    "投資は自己責任でお願いいたします。"
)


def _format_date_jp(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    wd = weekdays[dt.weekday()]
    return f"{dt.year}年{dt.month}月{dt.day}日（{wd}）"


def _format_change(pct: Optional[float]) -> str:
    if pct is None:
        return "不明"
    direction = "上昇" if pct > 0 else "下落" if pct < 0 else "横ばい"
    return f"{direction}、前日比{abs(pct):.1f}パーセント"


class ScriptGenerator:
    def __init__(self, settings: dict):
        self.settings = settings

    def generate(
        self,
        target_date: str,
        market_data: Optional[dict],
        stock_data: list[dict],
        news: list[dict],
        analysis: dict,
        ipo_text: str,
    ) -> str:
        date_jp = _format_date_jp(target_date)
        sections = [
            self._opening(date_jp),
            self._market_overview(date_jp, market_data, stock_data, analysis),
            self._spotlight_companies(analysis),
            self._important_news(news),
            self._theme_analysis(analysis),
            self._tomorrow_points(analysis, ipo_text),
            self._ending(date_jp),
        ]
        script = "\n\n".join(s for s in sections if s)
        logger.info(f"台本生成完了: {len(script)}文字")
        return script

    def _opening(self, date_jp: str) -> str:
        return (
            f"おはようございます。{date_jp}のグロース市場ニュースをお届けします。\n\n"
            f"{DISCLAIMER}\n\n"
            "それでは、本日の東証グロース市場の状況をご覧いただきましょう。"
        )

    def _market_overview(self, date_jp: str, market_data: Optional[dict],
                         stock_data: list[dict], analysis: dict) -> str:
        lines = ["【第1章：市場全体の動向】\n"]

        market_summary = analysis.get("market_summary", "")
        if market_summary:
            lines.append(market_summary)
        elif market_data and market_data.get("close_price"):
            close = market_data["close_price"]
            pct = market_data.get("change_pct")
            change_text = _format_change(pct)
            lines.append(
                f"東証グロース市場250指数は{close}ポイントと{change_text}で取引を終えました。"
            )
        else:
            lines.append("本日の指数データは取得できませんでした。")

        if market_data:
            adv = market_data.get("advance_count")
            dec = market_data.get("decline_count")
            if adv is not None and dec is not None:
                lines.append(f"\n監視銘柄のうち上昇銘柄は{adv}社、下落銘柄は{dec}社でした。")

        if stock_data:
            sorted_stocks = sorted(
                stock_data, key=lambda x: x.get("change_pct") or 0, reverse=True
            )
            if sorted_stocks[0].get("change_pct") and sorted_stocks[0]["change_pct"] > 0:
                top = sorted_stocks[0]
                lines.append(
                    f"\n本日の監視銘柄で最も上昇率が高かったのは"
                    f"証券コード{top.get('company_code')}で、"
                    f"前日比{top['change_pct']:.1f}パーセントの上昇でした。"
                )

        return "\n".join(lines)

    def _spotlight_companies(self, analysis: dict) -> str:
        companies = analysis.get("spotlight_companies", [])
        if not companies:
            return ""

        lines = ["【第2章：注目企業3社】\n"]
        for i, company in enumerate(companies[:3], 1):
            name = company.get("name", company.get("code", ""))
            reason = company.get("reason", "")
            detail = company.get("detail", "")
            lines.append(f"注目企業その{i}、{name}です。")
            if reason:
                lines.append(reason)
            if detail:
                lines.append(detail)
            lines.append("")

        return "\n".join(lines)

    def _important_news(self, news: list[dict]) -> str:
        if not news:
            return ""

        lines = ["【第3章：重要ニュース】\n"]
        seen_titles: set = set()
        count = 0

        for article in news[:20]:
            title = article.get("title", "")
            if title in seen_titles or not title:
                continue
            seen_titles.add(title)

            company_name = article.get("company_name") or article.get("company_code") or "市場全般"
            source = article.get("source", "")
            lines.append(f"{company_name}に関するニュースです。{title}")

            count += 1
            if count >= 5:
                break

        if count == 0:
            return ""

        return "\n".join(lines)

    def _theme_analysis(self, analysis: dict) -> str:
        theme_text = analysis.get("theme_analysis", "")
        if not theme_text:
            return ""

        lines = ["【第4章：テーマ分析】\n", theme_text]

        themes = analysis.get("trending_themes", [])
        if themes:
            theme_list = "、".join(themes[:5])
            lines.append(f"\n本日の注目テーマは{theme_list}などでした。")

        return "\n".join(lines)

    def _tomorrow_points(self, analysis: dict, ipo_text: str) -> str:
        tomorrow_text = analysis.get("tomorrow_points", "")
        lines = ["【第5章：明日の注目ポイント】\n"]

        if tomorrow_text:
            lines.append(tomorrow_text)
        else:
            lines.append("明日の注目ポイントを確認しましょう。")

        if ipo_text and "ありません" not in ipo_text:
            lines.append(f"\nIPO情報です。{ipo_text}")

        return "\n".join(lines)

    def _ending(self, date_jp: str) -> str:
        return (
            "【エンディング】\n\n"
            f"以上が{date_jp}の東証グロース市場ニュースでした。\n\n"
            f"{DISCLAIMER}\n\n"
            "グロース市場ニュースは毎朝配信中です。"
            "ポッドキャストアプリでの購読登録もお忘れなく。"
            "本日もよい一日をお過ごしください。"
        )
