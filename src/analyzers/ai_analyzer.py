import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


ANALYSIS_PROMPT_TEMPLATE = """あなたは東証グロース市場専門の金融アナリストです。
以下のデータを分析して、Podcastの素材となる情報を日本語で生成してください。

【注意事項】
- 投資助言にならないよう客観的な事実の分析・説明に留めること
- 「〜すべき」「〜を買え」等の投資判断の言葉は使用しない
- 教育目的の情報提供であることを意識する

【入力データ】
対象日付: {date}

■ 市場データ（グロース市場250指数）
{market_data}

■ 監視銘柄の株価データ
{stock_data}

■ 本日のニュース（最大30件）
{news_data}

■ IPO情報
{ipo_data}

【出力形式】
以下のJSON形式で厳密に出力してください：

{{
  "market_summary": "市場全体の動向をニュースキャスター口調で200〜300文字で要約",
  "spotlight_companies": [
    {{
      "code": "銘柄コード",
      "name": "企業名",
      "reason": "注目理由（50〜100文字）",
      "detail": "詳細説明（100〜200文字、客観的事実のみ）"
    }}
  ],
  "theme_analysis": "本日資金が流入したと思われるテーマを分析（AI、SaaS、FinTech等）。150〜250文字",
  "tomorrow_points": "明日の注目ポイント（決算、IPO、イベント等）。100〜200文字",
  "trending_themes": ["テーマ1", "テーマ2", "テーマ3"],
  "keywords": ["キーワード1", "キーワード2", "キーワード3", "キーワード4", "キーワード5"]
}}

spotlight_companiesは必ず3社選定してください（データがある場合）。
JSONのみを出力し、マークダウンやコードブロックは使用しないこと。"""


class AIAnalyzer:
    def __init__(self, settings: dict):
        self.settings = settings
        self.provider = os.getenv("AI_PROVIDER", "openrouter")
        self.max_retries = settings.get("ai", {}).get("max_retries", 3)
        self.retry_delay = settings.get("ai", {}).get("retry_delay", 5)

    def analyze(self, target_date: str, market_data: Optional[dict],
                stock_data: list[dict], news: list[dict], ipo_text: str) -> dict:
        prompt = self._build_prompt(target_date, market_data, stock_data, news, ipo_text)

        for attempt in range(self.max_retries):
            try:
                if self.provider == "gemini":
                    result = self._call_gemini(prompt)
                else:
                    result = self._call_openrouter(prompt)

                parsed = self._parse_response(result)
                parsed["raw_prompt"] = prompt[:2000]
                parsed["model_used"] = self._get_model_name()
                return parsed

            except Exception as e:
                logger.warning(f"AI分析失敗 (試行{attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        logger.error("AI分析全試行失敗 - フォールバック分析を使用")
        return self._fallback_analysis(target_date, market_data, stock_data, news)

    def _build_prompt(self, target_date: str, market_data: Optional[dict],
                      stock_data: list[dict], news: list[dict], ipo_text: str) -> str:
        if market_data:
            market_text = (
                f"終値: {market_data.get('close_price', 'N/A')}\n"
                f"前日比: {market_data.get('change_amount', 'N/A')} "
                f"({market_data.get('change_pct', 'N/A')}%)\n"
                f"出来高: {market_data.get('volume', 'N/A')}\n"
                f"上昇銘柄数: {market_data.get('advance_count', 'N/A')}\n"
                f"下落銘柄数: {market_data.get('decline_count', 'N/A')}"
            )
        else:
            market_text = "取得できませんでした"

        stock_lines = []
        for s in sorted(stock_data, key=lambda x: abs(x.get("change_pct") or 0), reverse=True)[:15]:
            code = s.get("company_code", "")
            close = s.get("close_price", "N/A")
            pct = s.get("change_pct", "N/A")
            vol = s.get("volume", "N/A")
            stock_lines.append(f"  {code}: 終値{close} 前日比{pct}% 出来高{vol}")
        stock_text = "\n".join(stock_lines) if stock_lines else "データなし"

        news_lines = []
        for i, n in enumerate(news[:30]):
            company = n.get("company_code", "市場全般")
            news_lines.append(f"  [{i+1}] ({company}) {n['title']}")
        news_text = "\n".join(news_lines) if news_lines else "ニュースなし"

        return ANALYSIS_PROMPT_TEMPLATE.format(
            date=target_date,
            market_data=market_text,
            stock_data=stock_text,
            news_data=news_text,
            ipo_data=ipo_text,
        )

    def _call_openrouter(self, prompt: str) -> str:
        from openai import OpenAI

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY が設定されていません")

        model = os.getenv("OPENROUTER_MODEL", "google/gemma-3-27b-it:free")
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/grawth-podcast",
                "X-Title": "Grawth Podcast",
            },
        )

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.settings.get("ai", {}).get("max_tokens", 4000),
            temperature=self.settings.get("ai", {}).get("temperature", 0.7),
        )
        content = response.choices[0].message.content
        logger.info(f"OpenRouter応答取得 (model={model}, tokens={response.usage.total_tokens})")
        return content

    def _call_gemini(self, prompt: str) -> str:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        logger.info("Gemini応答取得")
        return response.text

    def _get_model_name(self) -> str:
        if self.provider == "gemini":
            return "gemini-1.5-flash"
        return os.getenv("OPENROUTER_MODEL", "google/gemma-3-27b-it:free")

    def _parse_response(self, response_text: str) -> dict:
        text = response_text.strip()

        # コードブロックを除去
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        # JSON先頭を探す
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

        data = json.loads(text)

        required_keys = [
            "market_summary", "spotlight_companies", "theme_analysis",
            "tomorrow_points", "trending_themes", "keywords",
        ]
        for key in required_keys:
            if key not in data:
                data[key] = [] if key in ("spotlight_companies", "trending_themes", "keywords") else ""

        return data

    def _fallback_analysis(self, target_date: str, market_data: Optional[dict],
                           stock_data: list[dict], news: list[dict]) -> dict:
        """AI呼び出し失敗時のフォールバック"""
        market_text = "データ取得できませんでした"
        if market_data and market_data.get("close_price"):
            close = market_data["close_price"]
            pct = market_data.get("change_pct", 0) or 0
            direction = "上昇" if pct > 0 else "下落" if pct < 0 else "横ばい"
            market_text = (
                f"東証グロース市場250指数は{close}ポイントと前日比{abs(pct):.1f}%の{direction}となりました。"
            )

        top_news = [n["title"] for n in news[:5]]
        news_text = "本日の主なニュース: " + "、".join(top_news) if top_news else "ニュース取得中"

        spotlight = []
        sorted_stocks = sorted(
            stock_data, key=lambda x: abs(x.get("change_pct") or 0), reverse=True
        )[:3]
        for s in sorted_stocks:
            code = s.get("company_code", "")
            pct = s.get("change_pct", 0) or 0
            spotlight.append({
                "code": code,
                "name": code,
                "reason": f"前日比{pct:+.1f}%と大きく動きました",
                "detail": f"終値{s.get('close_price', 'N/A')}円、出来高{s.get('volume', 'N/A')}株",
            })

        return {
            "market_summary": market_text,
            "spotlight_companies": spotlight,
            "theme_analysis": "本日のテーマ分析は取得できませんでした。",
            "tomorrow_points": "明日の注目ポイントは取得できませんでした。",
            "trending_themes": [],
            "keywords": [],
            "model_used": "fallback",
            "raw_prompt": "",
        }
