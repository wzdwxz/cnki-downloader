"""自定义异常体系"""

from __future__ import annotations

import logging
import sys
import traceback

logger = logging.getLogger(__name__)


class CnkiError(Exception):
    """CNKI下载器基础异常"""

    def __init__(self, message: str = "", user_hint: str = "") -> None:
        super().__init__(message)
        self.user_hint = user_hint or message


class AuthError(CnkiError):
    """认证相关错误"""


class SessionExpiredError(AuthError):
    """会话过期"""

    def __init__(self, message: str = "会话已过期，请重新登录") -> None:
        super().__init__(message, user_hint="请重新登录知网账号或检查校园网连接")


class CampusNetworkError(AuthError):
    """非校园网环境"""

    def __init__(self, message: str = "") -> None:
        super().__init__(
            message or "当前网络无法访问知网机构资源",
            user_hint="请确认已连接校园网或VPN，或使用账号登录",
        )


class SearchError(CnkiError):
    """搜索相关错误"""


class NoResultsError(SearchError):
    """无搜索结果"""

    def __init__(self, message: str = "") -> None:
        super().__init__(
            message or "未找到相关结果",
            user_hint="请尝试更换关键词或调整搜索条件",
        )


class DownloadError(CnkiError):
    """下载相关错误"""


class FileExistsError(DownloadError):
    """文件已存在"""


class DownloadInterruptedError(DownloadError):
    """下载中断"""

    def __init__(self, message: str = "") -> None:
        super().__init__(
            message or "下载中断",
            user_hint="下载已中断，可使用断点续传重新下载",
        )


class ConvertError(CnkiError):
    """格式转换错误"""

    def __init__(self, message: str = "") -> None:
        super().__init__(
            message,
            user_hint="CAJ转换失败。请确认已安装 caj2pdf 或 pip install 'cnki-downloader[convert]'",
        )


class CaptchaRequiredError(CnkiError):
    """需要验证码"""

    def __init__(self, message: str = "") -> None:
        super().__init__(
            message or "知网要求输入验证码",
            user_hint="请求过于频繁，知网要求验证码。请稍等几分钟后重试，或使用GUI模式手动验证",
        )


def install_global_handler() -> None:
    """安装全局异常处理器，捕获未处理的异常并记录日志。"""
    original_hook = sys.excepthook

    def _handler(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            original_hook(exc_type, exc_value, exc_tb)
            return

        if issubclass(exc_type, CnkiError):
            logger.error("%s: %s", exc_type.__name__, exc_value)
            if hasattr(exc_value, "user_hint") and exc_value.user_hint:
                logger.info("提示: %s", exc_value.user_hint)
        else:
            logger.critical(
                "未处理的异常:\n%s",
                "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
            )

        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _handler
