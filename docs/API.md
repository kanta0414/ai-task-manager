# API 仕様

稼働中の OpenAPI 定義（`/openapi.json`）から生成している。
対話的な確認は http://localhost:8000/docs から行える。

通常UIもLLM Toolも、この API の裏にある同じ Service Layer を経由する。
認証は未実装（Phase 16）で、現在は既定ユーザーとして扱われる。

## タスク

| メソッド | パス | 説明 |
| --- | --- | --- |
| `GET` | `/tasks` | 条件でタスクを検索する。期限なしは常に末尾に並ぶ。 |
| `POST` | `/tasks` | タスクを作成する。 |
| `DELETE` | `/tasks/{task_id}` | タスクを削除する。 |
| `GET` | `/tasks/{task_id}` | タスクを1件取得する。 |
| `PATCH` | `/tasks/{task_id}` | タスクを部分更新する。未指定の項目は変更しない。 |
| `POST` | `/tasks/{task_id}/complete` | タスクを完了にする。 |
| `POST` | `/tasks/{task_id}/reopen` | 完了したタスクを未完了に戻す。 |

## カレンダー

| メソッド | パス | 説明 |
| --- | --- | --- |
| `GET` | `/events` | 期間やキーワードで予定を検索する。期間に重なる予定を返す。 |
| `POST` | `/events` | 予定を作成する。 |
| `DELETE` | `/events/{event_id}` | 予定を削除する。 |
| `GET` | `/events/{event_id}` | 予定を1件取得する。 |
| `PATCH` | `/events/{event_id}` | 予定を部分更新する。ドラッグ移動もこれを使う。 |

## スケジュール

| メソッド | パス | 説明 |
| --- | --- | --- |
| `GET` | `/schedule/free-time` | 空き時間を探す。通常UIとLLM Tool が同じ Service を使う。 |
| `GET` | `/schedule/plan` | 未完了タスクを空き時間に配置した案を返す（登録はしない）。 |
| `GET` | `/schedule/reschedule-plan` | 終わらなかった作業を組み直す案を返す（反映はしない）。 |

## AIアシスタント

| メソッド | パス | 説明 |
| --- | --- | --- |
| `POST` | `/chat` | Chat |
| `POST` | `/chat/confirm` | ユーザーが承認した操作を実行する（削除など）。 |
| `GET` | `/chat/status` | AI が使える状態かを返す。使えない理由を UI に表示するために使う。 |

## 会話

| メソッド | パス | 説明 |
| --- | --- | --- |
| `GET` | `/conversations` | 会話の一覧を新しい順に返す。 |
| `DELETE` | `/conversations/{conversation_id}` | 会話を発言ごと削除する。 |
| `GET` | `/conversations/{conversation_id}` | 会話を発言込みで取得する。 |

## 通知

| メソッド | パス | 説明 |
| --- | --- | --- |
| `GET` | `/notifications` | バックグラウンド処理が作った通知を返す。 |
| `POST` | `/notifications/{notification_id}/read` | 通知を既読にする。 |

## 死活確認

| メソッド | パス | 説明 |
| --- | --- | --- |
| `GET` | `/health` | アプリケーションの死活確認。 |
| `GET` | `/health/db` | DB 接続確認。Phase 0 の完了条件。 |

## その他

| メソッド | パス | 説明 |
| --- | --- | --- |
| `GET` | `/` | Root |
