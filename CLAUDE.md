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
# Celery（バックグラウンド処理。macOS では --pool=solo が必要）
cd backend
./.venv/bin/celery -A app.worker.celery_app worker --loglevel=info --pool=solo
./.venv/bin/celery -A app.worker.celery_app beat --loglevel=info
```

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
npm test        # Vitest（日時・カレンダー配置などのロジック）
npx eslint src --max-warnings=0
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
POST   /chat（conversation_id 省略で新規会話）   POST /chat/confirm   GET /chat/status
GET    /conversations      GET /conversations/{id}    DELETE /conversations/{id}
GET    /schedule/free-time（空き時間を探す）
GET    /schedule/plan（未完了タスクを配置した案。登録はしない）
GET    /schedule/reschedule-plan（やり残しの組み直し案。反映はしない）
GET    /notifications        POST /notifications/{id}/read
```

## LLM

```
app/llm/base.py     LLMProvider（抽象）/ ChatMessage / ChatResult
app/llm/ollama.py   OllamaProvider … 既定。ローカル実行で課金なし
app/llm/claude.py   ClaudeProvider … 呼ぶと従量課金。LLM_PROVIDER=claude のときだけ使う
app/llm/factory.py  設定からプロバイダを選ぶ唯一の場所
app/llm/schema_utils.py  Pydantic の $ref を展開（プロバイダが解釈できないため）
app/services/tool_registry.py  LLM が実行できる操作の定義と実行
app/schemas/tools.py          Tool 引数の検証スキーマ
```

### Tool Calling

- Tool は `ToolRegistry` にまとめ、**必ず既存の Service を呼ぶ**（新たなDBアクセスを書かない）。
- 引数は Pydantic で検証し、不正なら例外にせず `{"error": ...}` を LLM に返して修正させる。
- 削除など取り消せない操作は `needs_confirmation=True`。実行せず `pending_action` を返し、
  ユーザーが承認したら `POST /chat/confirm` で実行する（引数はそこで再検証する）。
- エージェントループは最大 8 往復（`MAX_TOOL_ITERATIONS`）。検索→空き時間→作成の連鎖に必要。
- Tool は15個（Task 7 / Calendar 5 / Schedule 3）。増やすと LLM の選択精度が落ちるため安易に足さない。
- `apply_schedule` は `exposed=False`。承認後の実行専用で LLM には見せない。
- **スケジュールの制約（何時〜何時に入れてよいか、土日を除くか）は Backend が持つ**
  （`ScheduleConstraints` / `SCHEDULE_DAY_START_HOUR`）。LLM に決めさせない。
- **Service が返す日時は利用者のタイムゾーンに揃える**（`astimezone`）。UTC のまま返すと
  LLM が時差込みの数字をそのまま読み上げる。
- 自動配置の順番は「期限が近い → 優先度が高い → 所要時間が長い」、1日6時間まで。
  置けなかったタスクは理由つきで返す。提案の段階では**予定を作らない**。
- `inline_refs` は JSON Schema の注釈 `title` を落とすが、`properties` の中の
  プロパティ名 `title` は残す（落とすと LLM から引数が見えなくなる）。

- 会話履歴は **DB（conversations / messages）が持つ**。クライアントは会話IDだけを渡す。
  LLM へ渡す現在日時は保存しない（表示にも次回の履歴にも不要なため）。
- **既定は `LLM_PROVIDER=ollama` / `qwen3:1.7b`。** Claude へ切り替えると従量課金が発生する。
- Ollama は `ollama serve` で起動する（このマシンには公式CLIを /usr/local/lib/ollama に導入済み）。

### ローカルLLMでの実測（Intel i5-7360U / 8GB）

- プロンプト処理 約30 tok/s、生成 約18 tok/s。**入力トークン数が応答時間に直結する。**
- そのため次の3点を守る:
  1. **現在日時はシステムプロンプトに入れない。** 利用者メッセージの先頭に付ける
     （システムプロンプト＋Tool定義を固定して Ollama のプロンプトキャッシュを効かせる。
     これで2回目以降は 100秒 → 19秒）。
  2. Tool のスキーマは `simplify_nullable` で削る（任意項目の `anyOf: [型, null]` と
     `default: null`、文字数制限は LLM に渡さない）。
  3. Tool を増やさない（11個で入力約2000トークン）。
- `temperature=0`（Tool 選択を揺らがせない）、`num_ctx=6144`（既定4096だと溢れて切り捨てられる）、
  `think=false`（qwen3 の思考トークンは CPU では高コスト）。
- **1.5B 級では Tool Calling が成立しない**（qwen2.5:1.5b は Tool 1個でも呼べなかった）。
- システムプロンプト（`app/services/chat_service.py`）には**現在日時とタイムゾーンを必ず含める**。
  「明日の14時」の解釈がここに依存する。
- Anthropic SDK は公式の `anthropic` パッケージを使う。例外は
  AuthenticationError → NotFoundError → RateLimitError → APIStatusError → APIConnectionError
  の順に個別に捕捉し、`LLMUnavailableError`(503) / `LLMError`(502) に変換する。

## 非同期処理

```
app/worker/celery_app.py  Celery アプリと beat スケジュール
app/worker/tasks.py       定期タスク（セッションを用意して Service を呼ぶだけ）
```

- **処理の中身は `NotificationService` に置く。** タスク側を薄く保つことで、
  ブローカー無しでもテストできる。
- 通知の重複は DB の一意制約（user_id, dedup_key）で防ぐ。
  5分ごとに実行されても同じ予定の通知は増えない。
- ブローカーは `CELERY_BROKER_URL`。Redis が無い環境では `filesystem://` に切り替え可能。

## Frontend 構成

```
src/types/      API のレスポンス型（TaskRead などと1対1）
src/lib/        api.ts(共通fetch) / tasks.ts(API呼び出し) / datetime.ts(JST整形)
src/store/      TasksProvider … 取得・更新・フィルタの状態を集約
src/components/ tasks/(TaskBoard,TaskItem,TaskForm,TaskFilters)
                calendar/(WeekCalendar,EventForm) ui/(Modal,ConfirmDialog)
```

- データ取得・更新は `TasksProvider` / `EventsProvider` の中だけで行い、コンポーネントは
  `useTasks()` / `useEvents()` を使う。AI アシスタントが操作した結果も `refresh()` で反映する（Phase 5 以降）。
- カレンダーの座標計算は `src/lib/calendarLayout.ts`（重なりの列割り当て・日またぎの切り詰め）。
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
- [x] Phase 4 カレンダーUI ← **Milestone 1: LLMなしで完成したタスク管理アプリ**
- [x] Phase 5 LLM基盤（Provider抽象化 / POST /chat / AIチャットUI）※実LLM未接続
- [x] Phase 6 Tool Calling（Task 6種 + Calendar 5種 + 確認フロー）※実LLM未接続
- [x] Phase 9 会話コンテキスト（conversations / messages にDB保存）
- [x] Phase 10 複数Tool連携（エージェントループで連鎖実行）
- [x] Phase 11 空き時間検索（find_free_time）
- [x] Phase 12 自動スケジューリング（提案 → 承認 → 登録）
- [x] Phase 13 タスク分解（create_subtasks / tasks.parent_task_id）
- [x] Phase 14 未完了タスクの再配置（reschedule_unfinished）
- [x] Phase 15 Celery / Redis（リマインダー・朝のまとめ・やり残し確認）
