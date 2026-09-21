from fastapi import APIRouter, Response, status

from app.api.deps import AuthServiceDep, CurrentUser
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: User) -> None:
    """セッションを Cookie に載せる。

    httponly: JavaScript から読めないようにして XSS でのトークン持ち出しを防ぐ。
    samesite=lax: 他サイトからのリクエストには付かないため CSRF 対策になる。
    （フロントとAPIは同一サイト扱いなので通常の操作では送られる）
    """
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_access_token(user.id),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, service: AuthServiceDep) -> User:
    """ユーザーを登録し、そのままログイン状態にする。"""
    user = service.register(payload)
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, service: AuthServiceDep) -> User:
    """メールアドレスとパスワードでログインする。"""
    user = service.authenticate(str(payload.email), payload.password)
    if user is None:
        raise UnauthorizedError("メールアドレスまたはパスワードが違います")
    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """セッションを破棄する。"""
    response.delete_cookie(get_settings().session_cookie_name, path="/")


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    """ログイン中のユーザーを返す。"""
    return user
