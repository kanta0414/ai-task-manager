class AppError(Exception):
    """アプリケーション共通の基底例外。

    Service Layer は HTTPException を投げない。通常UI(router)からも
    LLM Tool からも同じ Service を呼ぶため、HTTP に依存しない例外を投げ、
    router 側で HTTP ステータスへ変換する。
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    """対象が存在しない、または他ユーザーのデータである場合。"""

    def __init__(self, resource: str, resource_id: int | str) -> None:
        super().__init__(f"{resource} (id={resource_id}) が見つかりません")
        self.resource = resource
        self.resource_id = resource_id


class BusinessRuleError(AppError):
    """業務ルール違反（例: 終了時刻が開始時刻より前）。"""


class LLMError(AppError):
    """LLM 呼び出しに関する失敗。"""


class LLMUnavailableError(LLMError):
    """LLM に接続できない（未起動・APIキー未設定・ネットワーク断など）。"""


class UnauthorizedError(AppError):
    """ログインしていない、またはセッションが無効。"""


class ConflictError(AppError):
    """既に存在するものを作ろうとした（メールアドレスの重複など）。"""
