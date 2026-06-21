# グロース市場ニュース Podcast

東証グロース市場に特化したデイリーPodcast自動生成システムです。

毎朝5〜10分で東証グロース市場の状況を把握できる音声ニュースを自動配信します。

**免責事項:** 本Podcastは教育目的の情報提供であり、投資助言ではありません。

---

## 機能

- 東証グロース市場250指数・個別銘柄データの自動収集
- AI（OpenRouter/Gemini）による市場分析・台本生成
- Edge TTSによる日本語音声合成
- FFmpegによるPodcast品質の音声処理
- GitHub Pages + RSSによる自動配信
- Apple Podcasts等で購読可能なRSS

## 技術スタック

| 用途 | 技術 |
|------|------|
| 言語 | Python 3.12 |
| データ | yfinance, feedparser, BeautifulSoup |
| AI分析 | OpenRouter（無料枠）/ Gemini（無料枠） |
| 音声合成 | edge-tts（Microsoft Azure TTS） |
| 音声処理 | FFmpeg |
| ストレージ | SQLite |
| CI/CD | GitHub Actions |
| 配信 | GitHub Pages + RSS |

## セットアップ

### 1. リポジトリの準備

```bash
git clone https://github.com/YOUR_USERNAME/grawth-podcast.git
cd grawth-podcast
```

### 2. GitHub Pagesの設定

リポジトリ設定 → Pages → Source: `Deploy from a branch` → Branch: `main` / `docs`

### 3. GitHub Secretsの設定

`Settings` → `Secrets and variables` → `Actions` で以下を設定:

| Secret名 | 説明 | 取得先 |
|---------|------|-------|
| `OPENROUTER_API_KEY` | OpenRouter APIキー | https://openrouter.ai/ |

### 4. GitHub Variablesの設定（任意）

`Settings` → `Secrets and variables` → `Actions` → `Variables`:

| Variable名 | デフォルト | 説明 |
|-----------|---------|------|
| `PODCAST_BASE_URL` | 自動推定 | GitHub PagesのURL |
| `PODCAST_TITLE` | グロース市場ニュース | Podcast名 |
| `PODCAST_AUTHOR` | リポジトリオーナー | 著者名 |
| `AI_PROVIDER` | openrouter | AI提供元 |
| `TTS_VOICE` | ja-JP-NanamiNeural | 音声 |

### 5. ローカル実行（開発用）

```bash
cp .env.example .env
# .envを編集してAPIキーを設定

pip install -r requirements.txt

# ドライラン（音声生成スキップ）
python -m src.main --dry-run

# 本番実行（今日の日付）
python -m src.main

# 指定日付で実行
python -m src.main --date 2025-01-10
```

### 6. Docker実行

```bash
cp .env.example .env
# .envを編集

# ビルド & 実行
docker compose run podcast-generator

# テスト実行（ドライラン）
docker compose run podcast-dry-run
```

## 音声アセットの追加（任意）

BGM・ジングルを追加するとPodcast品質が向上します。

```
assets/
  opening.mp3   # オープニングジングル（推奨: 5〜10秒）
  ending.mp3    # エンディングジングル（推奨: 5〜10秒）
  bgm.mp3       # バックグラウンドミュージック（ループ再生）
```

著作権フリーの音源を使用してください。推奨サイト:
- [Pixabay](https://pixabay.com/music/) - 完全無料
- [freesound.org](https://freesound.org/) - CC0ライセンス

## 監視企業の追加

`config/companies.yml` を編集してください:

```yaml
companies:
  - code: "XXXX"
    name: "企業名"
    name_en: "Company Name"
    sector: "セクター"
    keywords:
      - "検索キーワード1"
      - "検索キーワード2"
```

東証証券コードを `code` に設定してください。

## ディレクトリ構成

```
grawth-podcast/
├── .github/workflows/daily_podcast.yml  # GitHub Actions
├── src/
│   ├── collectors/      # データ収集
│   ├── database/        # SQLite操作
│   ├── analyzers/       # AI分析
│   ├── generators/      # 台本・RSS生成
│   ├── tts/             # 音声合成
│   ├── audio/           # FFmpeg処理
│   └── main.py          # メインスクリプト
├── config/
│   ├── companies.yml    # 監視企業リスト
│   └── settings.yml     # システム設定
├── data/                # SQLiteデータベース
├── output/              # 台本・中間ファイル
├── docs/                # GitHub Pages
│   ├── index.html
│   ├── feed.xml         # Podcast RSS
│   └── episodes/        # MP3ファイル（7日分）
├── assets/              # BGM・ジングル
└── tests/               # テスト
```

## テスト実行

```bash
python -m pytest tests/ -v
```

## コスト

| 項目 | 費用 |
|------|------|
| GitHub Actions | 無料（Public repo: 無制限） |
| GitHub Pages | 無料（1GB制限） |
| OpenRouter | 無料枠あり（rate limit: 20req/min） |
| edge-tts | 完全無料 |
| yfinance | 完全無料 |

**月額費用: ¥0**（Public repoの場合）

## ライセンス

MIT License

本システムは教育目的で作成されています。投資判断は自己責任でお願いします。
