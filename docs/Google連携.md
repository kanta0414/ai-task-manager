# Google カレンダー連携の設定

連携すると、**Google 側の予定も「埋まっている時間」として扱い**、空き時間の検索と
自動スケジューリングがそれを避けるようになる。

連携しなくてもアプリは通常どおり動作する（認証情報が未設定なら機能自体が表示されない）。

## この連携で取得するもの

**予定のタイトルや参加者は取得しない。** Google の freeBusy API を使い、
「いつ埋まっているか」の時間帯だけを受け取る。要求する権限も読み取り専用。

| 権限 | 用途 |
| --- | --- |
| `calendar.readonly` | 埋まっている時間帯の取得 |
| `userinfo.email` | どのアカウントと連携中かを画面に表示するため |

## 手順

### 1. Google Cloud でプロジェクトを作る

1. https://console.cloud.google.com/ を開く
2. 上部のプロジェクト選択 →「新しいプロジェクト」→ 任意の名前で作成

### 2. Calendar API を有効にする

1. 「APIとサービス」→「ライブラリ」
2. 「Google Calendar API」を検索して「有効にする」

### 3. OAuth 同意画面を設定する

1. 「APIとサービス」→「OAuth 同意画面」
2. ユーザーの種類は「外部」を選択
3. アプリ名・サポートメール・デベロッパー連絡先を入力
4. スコープに次の2つを追加
   - `.../auth/calendar.readonly`
   - `.../auth/userinfo.email`
5. 「テストユーザー」に自分の Google アカウントを追加
   （公開申請をしない限り、ここに登録したアカウントだけが使える）

### 4. 認証情報を作る

1. 「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuth クライアント ID」
2. 種類は「ウェブアプリケーション」
3. **承認済みのリダイレクト URI** に次を追加

   ```
   http://localhost:8000/integrations/google/callback
   ```

4. 発行されたクライアントIDとシークレットを控える

### 5. アプリに設定する

`backend/.env`:

```
GOOGLE_CLIENT_ID=発行されたクライアントID
GOOGLE_CLIENT_SECRET=発行されたシークレット
GOOGLE_REDIRECT_URI=http://localhost:8000/integrations/google/callback
FRONTEND_BASE_URL=http://localhost:3000
```

バックエンドを再起動すると、画面上部に「Google カレンダー」の連携ボタンが現れる。

## 仕組み

```
画面「連携する」
  → GET /integrations/google/authorize   同意画面のURLを受け取る
  → Google の同意画面
  → GET /integrations/google/callback    認可コードを受け取る
  → トークンを暗号化して保存
  → 画面へ戻る
```

- `state` には**署名付きの短命トークン**を入れる。これが無いと、細工した
  コールバックを踏ませて別アカウントを紐づけられてしまう（CSRF）。
- 保存する refresh token は **SECRET_KEY から導いた鍵で暗号化**する。平文では置かない。
- アクセストークンの期限が近ければ、取得時に自動で更新する。
- **Google 側が落ちていても内部の空き時間計算は動く**（取得失敗時は外部の予定を
  考慮しないだけで、機能全体は止めない）。

## 解除

画面の「解除」を押すと、保存したトークンを削除する。
Google 側のアクセス権も取り消す場合は、
https://myaccount.google.com/permissions から削除する。

## 制限

- 現在は**読み取りのみ**。アプリで作った予定を Google 側へ書き出す機能は無い。
- 対象は主カレンダー（primary）のみ。
