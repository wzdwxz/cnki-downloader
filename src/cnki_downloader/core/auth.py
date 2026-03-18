"""认证：校园网检测、账号登录、Cookie管理"""

from __future__ import annotations

import logging

from cnki_downloader.core.exceptions import AuthError, CampusNetworkError
from cnki_downloader.core.session import CNKI_BASE_URL, SessionManager
from cnki_downloader.models.user import Credential

logger = logging.getLogger(__name__)

CNKI_LOGIN_URL = "https://login.cnki.net/login/"
CNKI_LOGIN_API = "https://login.cnki.net/login/login"
CNKI_LOGOUT_URL = "https://login.cnki.net/login/logout"


async def check_campus_network(session: SessionManager) -> bool:
    """检测当前网络是否具有知网机构访问权限。"""
    try:
        resp = await session.get(CNKI_BASE_URL)
        resp.raise_for_status()
        text = resp.text
        has_institution = (
            "showInstitution" in text
            or "university" in text.lower()
            or "欢迎" in text
        )
        if has_institution:
            logger.info("检测到校园网/机构网络环境")
        else:
            logger.info("未检测到机构网络环境")
        return has_institution
    except Exception as e:
        logger.warning("校园网检测失败: %s", e)
        return False


async def ensure_campus_access(session: SessionManager) -> None:
    """确保当前具有校园网访问权限，否则抛出异常。"""
    if not await check_campus_network(session):
        raise CampusNetworkError(
            "当前网络无法访问知网机构资源。请确认已连接校园网或VPN。"
        )


async def login(session: SessionManager, credential: Credential) -> bool:
    """使用账号密码登录知网。

    Args:
        session: HTTP会话管理器
        credential: 用户凭证

    Returns:
        是否登录成功
    """
    if not credential.username or not credential.password:
        raise AuthError("用户名和密码不能为空")

    try:
        # Step 1: 访问登录页获取必要的cookie和token
        login_page = await session.get(CNKI_LOGIN_URL)
        login_page.raise_for_status()

        # Step 2: 提交登录表单
        login_data = {
            "userName": credential.username,
            "pwd": credential.password,
            "isAutoLogin": "false",
        }
        resp = await session.post(CNKI_LOGIN_API, data=login_data)
        resp.raise_for_status()

        # Step 3: 检查登录结果
        content_type = resp.headers.get("content-type", "")
        result = resp.json() if content_type.startswith("application/json") else {}
        if result.get("code") == 200 or result.get("isSuccess"):
            logger.info("登录成功: %s", credential.username)
            return True

        # 检查是否有错误信息
        error_msg = result.get("msg", result.get("message", "未知错误"))
        logger.warning("登录失败: %s", error_msg)
        raise AuthError(f"登录失败: {error_msg}")

    except AuthError:
        raise
    except Exception as e:
        raise AuthError(f"登录过程出错: {e}") from e


async def logout(session: SessionManager) -> None:
    """登出知网。"""
    try:
        await session.get(CNKI_LOGOUT_URL)
        logger.info("已登出")
    except Exception as e:
        logger.warning("登出失败: %s", e)


async def check_login_status(session: SessionManager) -> bool:
    """检查当前是否已登录。"""
    try:
        resp = await session.get(CNKI_BASE_URL)
        resp.raise_for_status()
        # 已登录时页面会显示用户名或"退出"链接
        text = resp.text
        return "logout" in text.lower() or "退出" in text
    except Exception:
        return False


def save_credential(credential: Credential) -> None:
    """将凭证安全存储到系统密钥环。"""
    try:
        import keyring

        keyring.set_password("cnki_downloader", credential.username, credential.password)
        logger.info("凭证已保存到系统密钥环")
    except Exception as e:
        logger.warning("保存凭证失败: %s", e)


def load_credential(username: str) -> Credential | None:
    """从系统密钥环加载凭证。"""
    try:
        import keyring

        password = keyring.get_password("cnki_downloader", username)
        if password:
            return Credential(username=username, password=password, auth_type="account")
        return None
    except Exception as e:
        logger.warning("加载凭证失败: %s", e)
        return None


def delete_credential(username: str) -> None:
    """从系统密钥环删除凭证。"""
    try:
        import keyring

        keyring.delete_password("cnki_downloader", username)
        logger.info("凭证已从系统密钥环删除")
    except Exception as e:
        logger.warning("删除凭证失败: %s", e)
