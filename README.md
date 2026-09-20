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

## ドキュメント

- [要件定義書](docs/要件定義書.md)
- [開発手順（フェーズ計画）](docs/開発手順.md)
- [Claude Code での実装手順](docs/claude-code-開発フロー.md)
