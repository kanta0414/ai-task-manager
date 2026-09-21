# AI Task Manager

通常UIとAIアシスタント（自然言語）の両方から操作できる、タスク・スケジュール管理アプリ。

- **UIで作ったデータをLLMが操作でき、LLMで作ったデータをUIから操作できる**
- LLM が使えない環境でも、通常UIだけでタスク・カレンダー管理が完結する

## 構成

```
Next.js (通常UI) ─┐
                  ├→ FastAPI → Service → Repository → PostgreSQL
LLM (Tool Calling)┘
```

| 層 | 技術 |
| --- | --- |
| Frontend | Next.js (App Router) / React / TypeScript / Tailwind CSS |
| Backend | Python / FastAPI / Pydantic / SQLAlchemy / Alembic |
| DB | PostgreSQL 16 |
| AI | Claude API または Ollama（Provider 抽象化） |
| 非同期 | Celery / Redis（Phase 15 以降） |

## セットアップ

```bash
# 1. DB（ローカル PostgreSQL を使う場合）
createdb ai_task_manager
createdb ai_task_manager_test   # テスト用

# 2. Backend
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env          # DATABASE_URL などを環境に合わせて編集
./.venv/bin/alembic upgrade head
./.venv/bin/uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd ../frontend
npm install
cp .env.local.example .env.local
npm run dev
```

- API ドキュメント: http://localhost:8000/docs
- アプリ: http://localhost:3000

Docker で DB を動かす場合は `docker compose up -d db`（ホスト側ポート 5433）。

## AI アシスタント（任意）

LLM が無くても通常UIだけで全機能を利用できる。AI を使う場合は次のどちらかを設定する。

### ローカル LLM（Ollama / 料金なし）

```bash
ollama serve &                 # サーバー起動
ollama pull qwen3:1.7b         # Tool Calling に対応した小型モデル（約1.4GB）
```

`backend/.env`:

```
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3:1.7b
```

### Claude API（従量課金）

```
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-opus-5
```

APIキーは `.env` にのみ置き、Git にも Frontend にも渡さない。

## バックグラウンド処理（任意）

リマインダーと定期処理を動かす場合のみ必要。起動しなくてもアプリは使える。

```bash
cd backend
./.venv/bin/celery -A app.worker.celery_app worker --loglevel=info --pool=solo
./.venv/bin/celery -A app.worker.celery_app beat --loglevel=info
```

| 定期処理 | タイミング | 内容 |
| --- | --- | --- |
| リマインダー | 5分ごと | 30分以内に始まる予定を通知 |
| 今日のまとめ | 毎朝 7:00 | その日の予定と期限のタスクを通知 |
| やり残し確認 | 毎晩 23:00 | 終わらなかった作業を通知 |

ブローカーは既定で Redis（`CELERY_BROKER_URL`）。Redis を用意できない環境では
`CELERY_BROKER_URL=filesystem://` に切り替えるとインストール無しで動く（開発用）。

**macOS では `--pool=solo` を付ける。** 既定の prefork プールは macOS の
プロセス起動方式と相性が悪く、`not enough values to unpack` で失敗する。

## ドキュメント

- [要件定義書](docs/要件定義書.md)
- [開発手順（フェーズ計画）](docs/開発手順.md)
- [Claude Code での実装手順](docs/claude-code-開発フロー.md)
