"""管理者認証モジュール"""
import os
from fastapi import Header, HTTPException


def require_admin(x_admin_password: str = Header(None)):
    """管理者パスワードを検証するFastAPI依存関数"""
    admin_password = os.environ.get("ADMIN_PASSWORD", "changeme")
    if not x_admin_password or x_admin_password != admin_password:
        raise HTTPException(
            status_code=401,
            detail="管理者パスワードが必要です",
            headers={"WWW-Authenticate": "AdminPassword"},
        )
