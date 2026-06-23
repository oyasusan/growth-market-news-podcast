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
- 全フィールドは必須です。空文字・nullは絶対に使用しないこと

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
以下のJSON形式で厳密に出力してください。各フィールドは必ず100文字以上の内容を入れること：

{{
  "market_summary": "市場全体の動向をニュースキャスター口調で200〜300文字で要約（必須・空不可）",
  "spotlight_companies": [
    {{
      "code": "銘柄コード",
      "name": "企業名",
      "reason": "注目理由（50〜100文字・必須）",
      "detail": "詳細説明（100〜200文字、客観的事実のみ・必須）"
    }}
  ],
  "theme_analysis": "本日資金が流入したと思われるテーマを分析（AI、SaaS、FinTech等）。データがない場合も市場全体のテーマや傾向を150〜250文字で必ず記述すること（必須・空不可）",
  "tomorrow_points": "本日以降の注目ポイント（決算、IPO、イベント、マクロ経済指標等）を100〜200文字で必ず記述すること。IPO情報があれば必ず含める（必須・空不可）",
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

                # 重要フィールドが空の場合はフォールバックで補完
                fallback = self._fallback_analysis(target_date, market_data, stock_data, news, ipo_text)
                for key in ("theme_analysis", "tomorrow_points", "market_summary"):
                    if not parsed.get(key):
                        logger.warning(f"AIが {key} を返さなかったためフォールバックで補完")
                        parsed[key] = fallback[key]
                if not parsed.get("trending_themes"):
                    parsed["trending_themes"] = fallback.get("trending_themes", [])

                return parsed

            except Exception as e:
                logger.warning(f"AI分析失敗 (試行{attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        logger.error("AI分析全試行失敗 - フォールバック分析を使用")
        return self._fallback_analysis(target_date, market_data, stock_data, news, ipo_text)

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
            name = s.get("company_name") or code
            close = s.get("close_price", "N/A")
            pct = s.get("change_pct", "N/A")
            vol = s.get("volume", "N/A")
            stock_lines.append(f"  {name}（{code}）: 終値{close} 前日比{pct}% 出来高{vol}")
        stock_text = "\n".join(stock_lines) if stock_lines else "データなし"

        news_lines = []
        for i, n in enumerate(news[:30]):
            company = n.get("company_name") or n.get("company_code") or "市場全般"
            news_lines.append(f"  [{i+1}] ({company}) {n['title']}")
        news_text = "\n".join(news_lines) if news_lines else "ニュースなし"

        return ANALYSIS_PROMPT_TEMPLATE.format(
            date=target_date,
            market_data=market_text,
            stock_data=stock_text,
            news_data=news_text,
            ipo_data=ipo_text,
        )

    # 無料で利用可能なモデルの優先順リスト（利用不可の場合は次を試行）
    OPENROUTER_FREE_MODELS = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
        "microsoft/phi-3-mini-128k-instruct:free",
        "deepseek/deepseek-r1:free",
    ]

    def _call_openrouter(self, prompt: str) -> str:
        from openai import OpenAI

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY が設定されていません")

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/grawth-podcast",
                "X-Title": "Grawth Podcast",
            },
        )

        # 環境変数で指定されたモデルを先頭に、フォールバックリストと結合
        primary = os.getenv("OPENROUTER_MODEL", "")
        candidates = (
            [primary] + [m for m in self.OPENROUTER_FREE_MODELS if m != primary]
            if primary
            else self.OPENROUTER_FREE_MODELS
        )

        last_error = None
        for model in candidates:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.settings.get("ai", {}).get("max_tokens", 4000),
                    temperature=self.settings.get("ai", {}).get("temperature", 0.7),
                )
                content = response.choices[0].message.content
                self._used_model = model
                logger.info(f"OpenRouter応答取得 (model={model}, tokens={response.usage.total_tokens})")
                return content
            except Exception as e:
                err_str = str(e)
                if "404" in err_str or "unavailable" in err_str.lower() or "free" in err_str.lower():
                    logger.warning(f"モデル {model} は無料利用不可 - 次を試行")
                    last_error = e
                    continue
                raise

        raise RuntimeError(f"全フォールバックモデル試行失敗: {last_error}")

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
        return getattr(self, "_used_model", os.getenv("OPENROUTER_MODEL", "openrouter-free"))

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
                           stock_data: list[dict], news: list[dict],
                           ipo_text: str = "") -> dict:
        """AI呼び出し失敗時のフォールバック - データから自動生成"""
        # market_summary
        market_text = "本日の市場データは取得中です。各銘柄の動向を中心にお伝えします。"
        if market_data and market_data.get("close_price"):
            close = market_data["close_price"]
            pct = market_data.get("change_pct", 0) or 0
            direction = "上昇" if pct > 0 else "下落" if pct < 0 else "横ばい"
            adv = market_data.get("advance_count") or 0
            dec = market_data.get("decline_count") or 0
            market_text = (
                f"前日の東証グロース市場250指数は{close}ポイントと、前日比{abs(pct):.2f}%の{direction}で引けました。"
            )
            if adv or dec:
                market_text += f"監視銘柄では上昇が{adv}社、下落が{dec}社となりました。"

        # spotlight
        spotlight = []
        sorted_stocks = sorted(
            stock_data, key=lambda x: abs(x.get("change_pct") or 0), reverse=True
        )[:3]
        for s in sorted_stocks:
            code = s.get("company_code", "")
            name = s.get("company_name") or code
            pct = s.get("change_pct", 0) or 0
            direction = "上昇" if pct > 0 else "下落"
            close_price = s.get("close_price", "N/A")
            volume = s.get("volume", "N/A")
            spotlight.append({
                "code": code,
                "name": name,
                "reason": f"前日比{pct:+.1f}%と大きく{direction}しました。",
                "detail": (
                    f"終値{close_price}円、出来高{volume}株での取引となりました。"
                    f"引き続き動向に注目が集まっています。"
                ),
            })

        # theme_analysis - ニュースのキーワードとセクターから生成
        theme_map = {
            "AI・機械学習": ["AI", "人工知能", "機械学習", "ChatGPT", "生成AI", "LLM"],
            "SaaS・クラウド": ["SaaS", "クラウド", "DX", "デジタル変革", "サブスクリプション"],
            "FinTech・決済": ["フィンテック", "決済", "FinTech", "キャッシュレス", "金融"],
            "エンタメ・コンテンツ": ["VTuber", "ゲーム", "エンタメ", "コンテンツ", "ライブ"],
            "HR・採用": ["採用", "人材", "HR", "バイト", "スキマ", "就職"],
            "宇宙・ディープテック": ["宇宙", "衛星", "ロケット", "月面"],
            "IoT・スマートデバイス": ["IoT", "スマート", "センサー", "デバイス"],
            "EC・物流": ["EC", "物流", "通販", "ネットショップ"],
        }

        found_themes = []
        all_text = " ".join(n.get("title", "") for n in news[:20])
        for theme, keywords in theme_map.items():
            if any(kw in all_text for kw in keywords):
                found_themes.append(theme)

        gainers = sorted(
            [s for s in stock_data if (s.get("change_pct") or 0) > 0],
            key=lambda x: x.get("change_pct", 0), reverse=True
        )[:3]
        losers = sorted(
            [s for s in stock_data if (s.get("change_pct") or 0) < 0],
            key=lambda x: x.get("change_pct", 0)
        )[:3]

        if found_themes:
            theme_text = (
                f"前日の市場では{'、'.join(found_themes[:3])}関連に注目が集まりました。"
            )
        else:
            theme_text = "前日のグロース市場では、個別銘柄の材料に反応する展開となりました。"

        if gainers:
            gainer_names = "、".join(
                f"{s.get('company_name') or s.get('company_code', '')}（{s.get('change_pct', 0):+.1f}%）"
                for s in gainers
            )
            theme_text += f"上昇した銘柄としては{gainer_names}が挙げられます。"
        if losers:
            loser_names = "、".join(
                f"{s.get('company_name') or s.get('company_code', '')}（{s.get('change_pct', 0):+.1f}%）"
                for s in losers
            )
            theme_text += f"一方、{loser_names}は下落しました。"

        # tomorrow_points - IPO情報とニュースから生成
        tomorrow_parts = []
        if ipo_text and "ありません" not in ipo_text and "なし" not in ipo_text:
            tomorrow_parts.append(f"IPO情報として{ipo_text}")

        recent_news_titles = [n.get("title", "") for n in news[:3] if n.get("title")]
        if recent_news_titles:
            tomorrow_parts.append(
                f"また、{recent_news_titles[0]}など、適時開示や決算発表の内容にも注目が集まります。"
            )

        if not tomorrow_parts:
            tomorrow_parts.append(
                "引き続き、グロース市場各社の決算発表や適時開示情報に注目してまいります。"
                "マクロ経済指標の動向やドル円相場も、グロース株への資金フローに影響を与える可能性があります。"
            )

        tomorrow_text = "".join(tomorrow_parts)

        return {
            "market_summary": market_text,
            "spotlight_companies": spotlight,
            "theme_analysis": theme_text,
            "tomorrow_points": tomorrow_text,
            "trending_themes": [t.split("・")[0] for t in found_themes[:5]],
            "keywords": [],
            "model_used": "fallback",
            "raw_prompt": "",
        }
