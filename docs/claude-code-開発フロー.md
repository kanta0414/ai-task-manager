# Claude Code での実装手順

`docs/開発手順.md` のフェーズ計画を、**Claude Code に投げる単位**へ落とし込んだもの。

---

## 0. 基本サイクル（毎フェーズ共通）

1 フェーズ = 1 セッション。以下の 5 ステップを必ず回す。

```
① プランモードで設計させる    → 方針だけ先に確認（コードは書かせない）
② 承認して実装させる          → 1フェーズ分だけ
③ 自分で動かして確認          → ブラウザ / http://localhost:8000/docs / pytest
④ /code-review でレビュー     → 指摘を直す
⑤ コミット → CLAUDE.md の進捗更新 → 新しいセッションへ
```

**守るべきこと**

- **1メッセージ = 1フェーズ。** 「Phase 1〜4 まとめてやって」は破綻する。
- **プランモードを先に使う。** 特に Phase 2・6・12（設計の分岐が大きい箇所）。
- **フェーズごとにコミットする。** 壊れたときに戻れる単位を作る。
- **自分で動かして確認する。** 「できました」を鵜呑みにせず、画面とAPIを自分で触る。
- **フェーズが終わったらセッションを切り替える**（`/clear` 相当）。文脈が混ざると精度が落ちる。
- **仕様変更は CLAUDE.md か docs/ に書く。** チャットだけで伝えた決定は次のセッションに残らない。

---

## 1. フェーズ別プロンプト集

そのままコピーして使える。各プロンプトは「参照ドキュメント + 範囲の限定 + 完了条件」の3点を含める。

### Phase 0: 環境構築 ✅ 完了済み

Next.js / FastAPI / PostgreSQL の疎通確認まで完了。

---

### Phase 1: データモデル

```
docs/要件定義書.md の「27. データモデル」に従って、users / tasks / calendar_events の
SQLAlchemy モデルを backend/app/models/ に作成してください。
- status と priority は Enum で定義
- 日時は timezone-aware
- Alembic のマイグレーションを作成して upgrade head まで実行
- psql で 3 テーブルができていることを確認して報告
tags / conversations / messages は今はまだ作らないでください。
```

---

### Phase 2: CRUD API（最重要）

ここで **Repository → Service → Router** の型が決まる。以降すべてがこの形を踏襲するので、
プランモードで構成を確認してから実装させる。

```
プランモードで: Task の CRUD API を Repository / Service / Router の3層で実装する設計を
提案してください。LLM の Tool も後で同じ Service を呼ぶ前提にしてください。
```

承認後:

```
提案の構成で Task CRUD API を実装してください。
- POST/GET/GET{id}/PATCH/DELETE /tasks、完了用の POST /tasks/{id}/complete
- GET /tasks は status / due_date範囲 / キーワード / 並び順でフィルタできること
- Pydantic スキーマは schemas/task.py に分離
- pytest で CRUD 一通りのAPIテストを書き、全部通るところまで確認
```

続けて Calendar:

```
Task と同じ構成で CalendarEvent の CRUD API を実装してください。
- POST/GET/GET{id}/PATCH/DELETE /events
- GET /events は期間（from / to）で絞り込めること
- end_at > start_at のバリデーションを Service 層に入れる
- 同様に pytest まで
```

---

### Phase 3: タスクUI

```
frontend でタスク管理画面を実装してください。
- 一覧 / 作成フォーム / 編集 / 削除（確認ダイアログ付き）/ 完了チェック
- API 呼び出しは src/lib/api.ts 経由、型は src/types/ に定義
- 検索ボックスと、status・優先度でのフィルタ
- 実装後 npm run build が通ることを確認
デザインは Tailwind でシンプルに。カレンダーはまだ作らないでください。
```

---

### Phase 4: カレンダーUI（← ここで一旦「完成」）

```
週表示のカレンダーを実装してください。
- 縦軸が時間、横軸が7日間のグリッド
- 空き枠クリックで予定作成、予定クリックで編集/削除
- ドラッグ&ドロップでの時間移動（まずはクリック編集だけでも可）
- /events API と接続
```

完了したら一度立ち止まり、**LLMなしのタスク管理アプリとして使えるか**を自分で触って確認する。
ここが Milestone 1。

---

### Phase 5: LLM基盤

```
LLM Provider を抽象化した基盤を backend/app/llm/ に実装してください。
- 抽象基底クラス LLMProvider（chat メソッド、tool定義を受け取れる形）
- ClaudeProvider を実装（APIキーは .env から。フロントへは絶対に渡さない）
- POST /chat で単純な会話ができるところまで
- フロントに AI Assistant のチャットUIを追加
Ollama 用の実装は後で追加できるよう、インターフェースだけ揃えてください。
```

---

### Phase 6-8: Tool Calling と自然言語CRUD

```
プランモードで: Tool Calling の設計を提案してください。
Tool 定義・引数のバリデーション・Service 呼び出し・実行結果のLLMへの返し方、
そして削除など危険操作の確認フローの持たせ方を含めてください。
```

承認後、**Tool は一気に全部ではなく 2〜3個ずつ**:

```
まず create_task / search_tasks / update_task を実装してください。
- Tool 引数は Pydantic で検証し、不正なら LLM にエラーを返して再試行させる
- Tool は必ず既存の Service を呼ぶ（新しいDBアクセスを書かない）
- 「9月30日までにESを完成させるタスクを追加して」で動くことを確認
```

その後 `complete_task` / `delete_task`（確認フロー付き）→ Calendar 系 Tool の順。

---

### Phase 9: 会話コンテキスト

```
conversations / messages テーブルを追加し、会話履歴を保存・復元してください。
「明日の企業研究を18時からにして」→「やっぱり19時から」で対象を引き継げることを確認。
```

---

### Phase 10-12: 複数Tool連携・空き時間・自動スケジューリング

```
find_free_time Tool を実装してください。
制約（1日の上限時間、就寝時間帯、除外曜日）は Backend 側のルールとして持たせ、
LLM に自由に決めさせないでください。
```

```
generate_schedule を実装してください。
未完了タスク・期限・優先度・所要時間・既存予定から配置案を作り、
即時登録せず「提案 → ユーザー承認 → 登録」の2段階にしてください。
```

---

## 2. レビューと品質

| タイミング | コマンド |
| --- | --- |
| 各フェーズ実装後 | `/code-review` |
| LLM連携が入ったあと | `/security-review`（APIキー・入力検証・権限） |
| 大きな変更の後 | `/simplify`（重複や冗長な実装の整理） |

Phase 6 以降は **「どの入力でどの Tool が選ばれるか」のテスト**が重要（`docs/開発手順.md` の Phase 18）。

```
「タスクを追加して」→ create_task のように、入力と期待Toolの対応表でテストを書いてください。
```

---

## 3. つまずきやすい点

- **日時の扱い**: 「明日の14時」を LLM が解釈する際、ユーザーのタイムゾーンと「今日」を
  システムプロンプトで必ず渡す。ここを曖昧にすると全部ズレる。
- **Tool の粒度**: 多すぎると LLM が選択を誤る。MVP では Task 6個 + Calendar 5個程度に抑える。
- **確認フロー**: 削除・一括変更は「LLMが実行する前に人間に見せる」。要件定義書「24. 操作確認ポリシー」の分類に従う。
- **Service の重複**: Tool 用に別ロジックを書き始めたら設計が崩れているサイン。

---

## 4. 最後（Phase 20: ポートフォリオ化）

```
README にシステム構成図・ER図・API仕様・技術選定理由・Tool Calling の説明を追記してください。
Mermaid で図を書いてください。
```
