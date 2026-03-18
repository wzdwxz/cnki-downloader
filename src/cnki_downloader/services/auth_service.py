"""认证服务 — 编排登录流程"""

from __future__ import annotations

import logging

from cnki_downloader.core.auth import (
    check_campus_network,
    check_login_status,
    delete_credential,
    load_credential,
    login,
    logout,
    save_credential,
)
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.user import Credential

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务：管理登录状态和凭证。"""

    def __init__(self, session: SessionManager) -> None:
        self._session = session

    async def login_with_account(
        self, username: str, password: str, remember: bool = False
    ) -> bool:
        """使用账号密码登录。"""
        credential = Credential(
            username=username, password=password, auth_type="account"
        )
        success = await login(self._session, credential)

        if success and remember:
            save_credential(credential)

        return success

    async def login_with_saved_credential(self, username: str) -> bool:
        """使用已保存的凭证登录。"""
        credential = load_credential(username)
        if not credential:
            logger.warning("未找到保存的凭证: %s", username)
            return False
        return await login(self._session, credential)

    async def logout(self) -> None:
        await logout(self._session)

    async def check_access(self) -> dict[str, bool]:
        """检查当前访问状态。"""
        campus = await check_campus_network(self._session)
        logged_in = await check_login_status(self._session)
        return {
            "campus_network": campus,
            "logged_in": logged_in,
            "has_access": campus or logged_in,
        }

    def remove_saved_credential(self, username: str) -> None:
        delete_credential(username)
