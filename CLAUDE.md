# AI Task Manager — プロジェクト規約

Claude Code はこのファイルを毎回読み込む。実装前に必ず `docs/要件定義書.md` と
`docs/開発手順.md` の該当フェーズを参照すること。

## プロジェクト概要

通常UI（Next.js）と LLM（Tool Calling）の2経路から、**同じ Service Layer / 同じDB** を
操作できるタスク・スケジュール管理アプリ。LLM は必須ではなく、通常UIだけで全機能が完結する。

## ディレクトリ

```
backend/   FastAPI + SQLAlchemy + Alembic（レイヤード構成）
frontend/  Next.js (App Router) + TypeScript + Tailwind
docs/      要件定義書・開発手順・Claude Code 開発フロー
```

## アーキテクチャの絶対ルール

```
Next.js ─┐
         ├→ FastAPI(router) → Service → Repository → PostgreSQL
LLM Tool ┘
```

1. **LLM に SQL を書かせない・DBを直接触らせない。** 必ず Tool → Service を経由する。
2. **ビジネスロジックは Service Layer に置く。** router は入出力の変換のみ、repository は永続化のみ。
3. **LLM Tool は router と同じ Service を呼ぶ。** Tool 用に別ロジックを作らない。
4. **LLM の出力を信用しない。** Tool 引数は Pydantic で型・日時・ID・所有者・存在を検証する。
5. 破壊的操作（削除・複数予定の変更）は即時実行せず、確認フローを挟む。

## コマンド

```bash
# Backend（必ず backend/ で実行）
cd backend
./.venv/bin/uvicorn app.main:app --reload --port 8000   # 起動 → http://localhost:8000/docs
./.venv/bin/alembic revision --autogenerate -m "message" # マイグレーション作成
./.venv/bin/alembic upgrade head                         # 適用
./.venv/bin/alembic check                                # モデルとマイグレーションの差分検出
./.venv/bin/python -m pytest -q                          # テスト（要 createdb ai_task_manager_test）

# Frontend
cd frontend
npm run dev     # http://localhost:3000
npm run build   # 型チェック込みのビルド確認
```

DB: ローカル Homebrew PostgreSQL（`ai_task_manager` / ユーザー `kanta` / 5432）。
Docker を使う場合は `docker compose up -d db`（5433、`.env` の DATABASE_URL を切替）。
テストは開発用DBを壊さないよう `ai_task_manager_test` に対して実行する。

## 既存API

```
GET    /health , /health/db
POST   /tasks              GET /tasks（status/keyword/due_from/due_to/sort_by/order/limit/offset）
GET    /tasks/{id}         PATCH /tasks/{id}      DELETE /tasks/{id}
POST   /tasks/{id}/complete , /tasks/{id}/reopen
POST   /events             GET /events（from/to/keyword/task_id/order/limit/offset）
GET    /events/{id}        PATCH /events/{id}     DELETE /events/{id}
```

## Frontend 構成

```
src/types/      API のレスポンス型（TaskRead などと1対1）
src/lib/        api.ts(共通fetch) / tasks.ts(API呼び出し) / datetime.ts(JST整形)
src/store/      TasksProvider … 取得・更新・フィルタの状態を集約
src/components/ tasks/(TaskBoard,TaskItem,TaskForm,TaskFilters) ui/(Modal,ConfirmDialog)
```

- データ取得・更新は `TasksProvider` の中だけで行い、コンポーネントは `useTasks()` を使う。
  AI アシスタントが操作した結果も `refresh()` でこの状態に反映する（Phase 5 以降）。
- 日時入力は `<input type="datetime-local">` の値（オフセット無し）をそのまま送り、
  Backend 側で Asia/Tokyo として解釈させる。フロントでタイムゾーン変換しない。

- 「現在のユーザー」は `app/api/deps.py` の `get_current_user` のみが決める（Phase 16 で認証へ差し替え）。
- Service はドメイン例外（`NotFoundError` / `BusinessRuleError`）を投げ、`main.py` の
  exception handler が HTTP へ変換する。**Service で HTTPException を使わない**。
- 日時は `app/schemas/common.py` の `AwareDatetime` を使う（naive は Asia/Tokyo として解釈）。

## コーディング規約

- Backend: 型ヒント必須。SQLAlchemy 2.0 の `Mapped[...]` スタイル。日時は timezone-aware (JST/UTC を混ぜない)。
- Frontend: API 呼び出しは `src/lib/api.ts` 経由に統一。`any` 禁止。
- 命名は英語、コメント・UI文言は日本語。
- 新しいテーブルを足したら必ず Alembic のマイグレーションも作り、`app/models/__init__.py` に追記する
  （autogenerate の対象になるため）。ENUM を含むテーブルは downgrade で型の drop も書く。

## セキュリティ

- `.env` は Git 管理しない。APIキーはフロントエンドへ渡さない（`NEXT_PUBLIC_` に入れない）。
- LLM プロバイダ呼び出しは backend のみ。

## 進捗

- [x] Phase 0 開発環境構築（Next.js / FastAPI / PostgreSQL 接続確認済み）
- [x] Phase 1 データモデル（users / tasks / calendar_events）
- [x] Phase 2 CRUD API（Task / Calendar）
- [x] Phase 3 タスクUI
- [ ] Phase 4 カレンダーUI ← ここで「LLMなしでも完成したアプリ」
- [ ] Phase 5 LLM基盤 / Phase 6 Tool Calling / Phase 7-8 自然言語CRUD
- [ ] Phase 9 会話コンテキスト / Phase 10-12 複数Tool連携・空き時間・自動スケジューリング
