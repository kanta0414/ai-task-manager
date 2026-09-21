"""既存ユーザーにパスワードを設定する（運用・移行用）。

認証を入れる前に作られたユーザーはパスワードを持たないため、
そのままではログインできない。このスクリプトで設定する。

    ./.venv/bin/python -m scripts.set_password owner@example.com
"""

import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import session_scope
from app.models.user import User


def main() -> int:
    if len(sys.argv) != 2:
        print("使い方: python -m scripts.set_password <メールアドレス>")
        return 1

    email = sys.argv[1].lower()
    password = getpass.getpass("新しいパスワード: ")
    if len(password) < 8:
        print("パスワードは8文字以上にしてください")
        return 1
    if password != getpass.getpass("もう一度入力: "):
        print("入力が一致しません")
        return 1

    with session_scope() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            print(f"ユーザー {email} が見つかりません")
            return 1
        user.password_hash = hash_password(password)
        db.commit()
        print(f"{email} のパスワードを設定しました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
