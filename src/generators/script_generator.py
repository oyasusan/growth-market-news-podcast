"""
台本生成モジュール。
ナナ（女性アナウンサー）とケンタ（男性アナリスト）の掛け合いで構成。
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "Google News": "グーグルニュース",
    "PR TIMES": "PRタイムス",
    "TDnet": "TDネット（適時開示情報）",
}

DISCLAIMER = (
    "本Podcastは教育目的の情報提供であり、投資助言ではありません。"
    "投資は自己責任でお願いいたします。"
)


def _date_jp(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    return f"{dt.year}年{dt.month}月{dt.day}日（{weekdays[dt.weekday()]}）"


def _change_text(pct: Optional[float], amount: Optional[float] = None) -> str:
    if pct is None:
        return "不明"
    direction = "上昇" if pct > 0 else "下落" if pct < 0 else "横ばい"
    a = f"{abs(amount):.1f}ポイント、" if amount else ""
    return f"{direction}（前日比 {a}{abs(pct):.2f}パーセント）"


def _source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def _company_name(company: dict, stock_data: list[dict]) -> str:
    name = company.get("name", "")
    code = company.get("code", "")
    if name and name != code:
        return name
    for s in stock_data:
        if s.get("company_code") == code and s.get("company_name"):
            return s["company_name"]
    return name or code


N = "ナナ"
K = "ケンタ"


def line(speaker: str, text: str) -> str:
    return f"{speaker}：{text}"


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
        date_jp = _date_jp(target_date)
        sections = [
            self._opening(date_jp),
            self._market_overview(market_data, stock_data, analysis),
            self._spotlight_companies(analysis, stock_data),
            self._important_news(news),
            self._theme_analysis(analysis),
            self._tomorrow_points(analysis, ipo_text),
            self._ending(date_jp),
        ]
        script = "\n".join(ln for sec in sections for ln in sec if ln)
        logger.info(f"台本生成完了: {len(script)}文字")
        return script

    # ── Opening ───────────────────────────────────────────────────────────

    def _opening(self, date_jp: str) -> list[str]:
        return [
            line(N, f"おはようございます。グロース市場ニュース、{date_jp}版をお届けします。"),
            line(K, "おはようございます。マーケットアナリストのケンタです。本日もよろしくお願いします。"),
            line(N, "本日は、前日の東証グロース市場の動向と、今朝時点での最新情報をまとめてお伝えします。"),
            line(K, f"なお、{DISCLAIMER}"),
            line(N, "それでは早速参りましょう。"),
        ]

    # ── Market Overview ───────────────────────────────────────────────────

    def _market_overview(self, market_data: Optional[dict],
                         stock_data: list[dict], analysis: dict) -> list[str]:
        lines = [line(N, "まずは、前日の市場全体の動向からです。ケンタさん、いかがでしたか？")]

        summary = analysis.get("market_summary", "")
        if summary:
            lines.append(line(K, summary))
        elif market_data and market_data.get("close_price"):
            close = market_data["close_price"]
            pct = market_data.get("change_pct")
            amt = market_data.get("change_amount")
            ct = _change_text(pct, amt)
            lines.append(line(K, f"前日の東証グロース市場250指数は{close}ポイントと、{ct}で引けました。"))
        else:
            lines.append(line(K, "前日の指数データは取得できませんでしたが、各銘柄の動向からご報告します。"))

        if market_data:
            adv = market_data.get("advance_count")
            dec = market_data.get("decline_count")
            if adv is not None and dec is not None:
                lines.append(line(N, f"なるほど。監視銘柄ではどうでしたか？"))
                lines.append(line(K, f"監視銘柄のうち、上昇が{adv}社、下落が{dec}社でした。"))

        if stock_data:
            top = next((s for s in stock_data if (s.get("change_pct") or 0) > 0), None)
            if top:
                name = top.get("company_name") or top.get("company_code", "")
                pct = top.get("change_pct", 0)
                lines.append(line(N, f"特に目立った銘柄はありましたか？"))
                lines.append(line(K, f"監視銘柄の中では{name}が前日比{pct:.1f}パーセント上昇し、最も大きく動きました。"))

        return lines

    # ── Spotlight Companies ───────────────────────────────────────────────

    def _spotlight_companies(self, analysis: dict, stock_data: list[dict]) -> list[str]:
        companies = analysis.get("spotlight_companies", [])
        if not companies:
            return []

        lines = [line(N, "続きまして、前日の注目企業を3社ご紹介します。ケンタさん、まず1社目は？")]
        ordinals = ["1社目", "2社目", "3社目"]
        transitions = [
            (N, "詳しく教えてください。"),
            (N, "なるほど。2社目はいかがでしょう？"),
            (N, "3社目はどちらですか？"),
        ]

        for i, company in enumerate(companies[:3]):
            name = _company_name(company, stock_data)
            reason = company.get("reason", "")
            detail = company.get("detail", "")

            if i == 0:
                lines.append(line(K, f"{ordinals[i]}は{name}です。{reason}"))
                if detail:
                    lines.append(transitions[0])
                    lines.append(line(K, detail))
            elif i == 1:
                lines.append(transitions[1])
                lines.append(line(K, f"{ordinals[i]}は{name}です。{reason}"))
                if detail:
                    lines.append(line(N, "詳しく教えてください。"))
                    lines.append(line(K, detail))
            elif i == 2:
                lines.append(transitions[2])
                lines.append(line(K, f"{ordinals[i]}は{name}です。{reason}"))
                if detail:
                    lines.append(line(N, "詳しく教えてください。"))
                    lines.append(line(K, detail))

        lines.append(line(N, "ありがとうございます。気になる企業が多いですね。"))
        return lines

    # ── Important News ────────────────────────────────────────────────────

    def _important_news(self, news: list[dict]) -> list[str]:
        if not news:
            return []

        lines = [line(N, "続きまして、今朝時点での重要ニュースをお伝えします。")]

        seen: set = set()
        count = 0
        for article in news[:20]:
            title = article.get("title", "").strip()
            if not title or title in seen:
                continue
            seen.add(title)

            company_name = (
                article.get("company_name")
                or (f"証券コード{article['company_code']}" if article.get("company_code") else None)
            )
            source = _source_label(article.get("source", ""))

            if company_name:
                intro = f"{company_name}に関するニュースです。"
            else:
                intro = "市場全般のニュースです。"

            citation = f"引用元は{source}です。" if source else ""
            lines.append(line(N, f"{intro}「{title}」、{citation}"))

            count += 1
            if count >= 5:
                break

        if count == 0:
            return []

        lines.append(line(K, "昨夜から今朝にかけて、さまざまなニュースが出ていましたね。"))
        return lines

    # ── Theme Analysis ────────────────────────────────────────────────────

    def _theme_analysis(self, analysis: dict) -> list[str]:
        theme_text = analysis.get("theme_analysis", "")
        if not theme_text:
            return []

        lines = [
            line(N, "次に、テーマ分析です。前日はどのようなテーマに資金が流入しましたか、ケンタさん。"),
            line(K, theme_text),
        ]

        themes = analysis.get("trending_themes", [])
        if themes:
            theme_list = "、".join(themes[:5])
            lines.append(line(N, f"{theme_list}といったテーマが注目されたんですね。"))
            lines.append(line(K, "そうですね。引き続きこれらのテーマの動向に注目です。"))

        return lines

    # ── Tomorrow's Points ─────────────────────────────────────────────────

    def _tomorrow_points(self, analysis: dict, ipo_text: str) -> list[str]:
        tomorrow = analysis.get("tomorrow_points", "")
        lines = [line(N, "最後に、本日以降の注目ポイントを教えてください。")]

        if tomorrow:
            lines.append(line(K, tomorrow))
        else:
            lines.append(line(K, "本日以降の具体的な注目イベントについては引き続き情報を収集中です。"))

        if ipo_text and "ありません" not in ipo_text:
            lines.append(line(N, f"IPO情報もありますね。{ipo_text}"))
            lines.append(line(K, "新規上場銘柄は初値動向にも注目が集まりますね。"))

        lines.append(line(N, "ケンタさん、本日もありがとうございました。"))
        lines.append(line(K, "ありがとうございました。"))
        return lines

    # ── Ending ────────────────────────────────────────────────────────────

    def _ending(self, date_jp: str) -> list[str]:
        return [
            line(N, f"以上、{date_jp}のグロース市場ニュースをお届けしました。"),
            line(K, f"改めて、{DISCLAIMER}"),
            line(N, "グロース市場ニュースは毎朝配信しています。ポッドキャストアプリでの購読登録もぜひ。"),
            line(N, "本日もよい一日をお過ごしください。"),
            line(K, "それでは。"),
        ]
