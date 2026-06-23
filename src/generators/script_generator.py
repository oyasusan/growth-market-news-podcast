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


def _company_label(name: str, code: str) -> str:
    """「企業名、証券コードXXXX」形式の読み上げ用テキストを返す。"""
    if name and code and name != code:
        return f"{name}、証券コード{code}"
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
            self._theme_analysis(analysis, stock_data, news),
            self._tomorrow_points(analysis, ipo_text, news),
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
                label = _company_label(
                    top.get("company_name") or "", top.get("company_code") or ""
                )
                pct = top.get("change_pct", 0)
                lines.append(line(N, f"特に目立った銘柄はありましたか？"))
                lines.append(line(K, f"監視銘柄の中では{label}が前日比{pct:.1f}パーセント上昇し、最も大きく動きました。"))

        return lines

    # ── Spotlight Companies ───────────────────────────────────────────────

    def _spotlight_companies(self, analysis: dict, stock_data: list[dict]) -> list[str]:
        companies = analysis.get("spotlight_companies", [])
        if not companies:
            return []

        lines = [line(N, "続きまして、前日の注目企業を3社ご紹介します。ケンタさん、まず1社目は？")]
        ordinals = ["1社目", "2社目", "3社目"]
        transitions = [
            line(N, "詳しく教えてください。"),
            line(N, "なるほど。2社目はいかがでしょう？"),
            line(N, "3社目はどちらですか？"),
        ]

        for i, company in enumerate(companies[:3]):
            name = _company_name(company, stock_data)
            code = company.get("code", "")
            label = _company_label(name, code)
            reason = company.get("reason", "")
            detail = company.get("detail", "")

            if i == 0:
                lines.append(line(K, f"{ordinals[i]}は{label}です。{reason}"))
                if detail:
                    lines.append(transitions[0])
                    lines.append(line(K, detail))
            elif i == 1:
                lines.append(transitions[1])
                lines.append(line(K, f"{ordinals[i]}は{label}です。{reason}"))
                if detail:
                    lines.append(line(N, "詳しく教えてください。"))
                    lines.append(line(K, detail))
            elif i == 2:
                lines.append(transitions[2])
                lines.append(line(K, f"{ordinals[i]}は{label}です。{reason}"))
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

            company_name = article.get("company_name") or ""
            company_code = article.get("company_code") or ""
            source = _source_label(article.get("source", ""))

            if company_name or company_code:
                label = _company_label(company_name, company_code)
                intro = f"{label}に関するニュースです。"
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

    def _theme_analysis(self, analysis: dict, stock_data: list[dict] = None,
                        news: list[dict] = None) -> list[str]:
        theme_text = analysis.get("theme_analysis", "")

        if not theme_text:
            theme_text = self._build_theme_fallback(stock_data or [], news or [])

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

    def _build_theme_fallback(self, stock_data: list[dict], news: list[dict]) -> str:
        gainers = sorted(
            [s for s in stock_data if (s.get("change_pct") or 0) > 0],
            key=lambda x: x.get("change_pct", 0), reverse=True
        )[:3]
        if gainers:
            names = "、".join(
                _company_label(s.get("company_name") or "", s.get("company_code") or "")
                for s in gainers
            )
            return (
                f"前日のグロース市場では個別銘柄への選別物色が続きました。"
                f"中でも{names}が上昇するなど、成長性の高い銘柄に資金が向かう展開でした。"
            )
        if news:
            return (
                "前日のグロース市場では、個別銘柄の開示情報や決算への反応が中心の展開でした。"
                "全体的には様子見ムードが漂い、方向感の定まりにくい一日となりました。"
            )
        return ""

    # ── Tomorrow's Points ─────────────────────────────────────────────────

    def _tomorrow_points(self, analysis: dict, ipo_text: str,
                         news: list[dict] = None) -> list[str]:
        tomorrow = analysis.get("tomorrow_points", "")

        if not tomorrow:
            tomorrow = self._build_tomorrow_fallback(ipo_text, news or [])

        lines = [line(N, "最後に、本日以降の注目ポイントを教えてください。")]
        lines.append(line(K, tomorrow))

        if ipo_text and "ありません" not in ipo_text and tomorrow and ipo_text not in tomorrow:
            lines.append(line(N, f"IPO情報もありますね。{ipo_text}"))
            lines.append(line(K, "新規上場銘柄は初値動向にも注目が集まりますね。"))

        lines.append(line(N, "ケンタさん、本日もありがとうございました。"))
        lines.append(line(K, "ありがとうございました。"))
        return lines

    def _build_tomorrow_fallback(self, ipo_text: str, news: list[dict]) -> str:
        parts = []
        if ipo_text and "ありません" not in ipo_text and "なし" not in ipo_text:
            parts.append(f"今週のIPO案件として{ipo_text}")
        top_titles = [n.get("title", "") for n in news[:2] if n.get("title")]
        if top_titles:
            parts.append(
                f"また、{top_titles[0]}など、"
                "グロース企業の適時開示や決算発表の動向を引き続きウォッチしてまいります。"
            )
        if not parts:
            parts.append(
                "本日以降も、グロース市場各社の決算発表・適時開示情報に注目です。"
                "為替動向やマクロ経済指標も引き続き確認してまいりましょう。"
            )
        return "".join(parts)

    # ── Ending ────────────────────────────────────────────────────────────

    def _ending(self, date_jp: str) -> list[str]:
        return [
            line(N, f"以上、{date_jp}のグロース市場ニュースをお届けしました。"),
            line(K, f"改めて、{DISCLAIMER}"),
            line(N, "グロース市場ニュースは毎朝配信しています。ポッドキャストアプリでの購読登録もぜひ。"),
            line(N, "本日もよい一日をお過ごしください。"),
            line(K, "それでは。"),
        ]
