"""认证模块单元测试"""

import pytest

from cnki_downloader.core.auth import login
from cnki_downloader.core.exceptions import AuthError
from cnki_downloader.models.user import Credential


class TestLogin:
    @pytest.mark.asyncio
    async def test_empty_credentials_raises(self) -> None:
        from unittest.mock import AsyncMock

        session = AsyncMock()
        with pytest.raises(AuthError, match="不能为空"):
            await login(session, Credential(username="", password=""))

    @pytest.mark.asyncio
    async def test_empty_password_raises(self) -> None:
        from unittest.mock import AsyncMock

        session = AsyncMock()
        with pytest.raises(AuthError, match="不能为空"):
            await login(session, Credential(username="user", password=""))


class TestCredential:
    def test_default_auth_type(self) -> None:
        c = Credential()
        assert c.auth_type == "campus"

    def test_account_auth_type(self) -> None:
        c = Credential(username="u", password="p", auth_type="account")
        assert c.auth_type == "account"
