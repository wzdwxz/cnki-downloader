"""python -m cnki_downloader 入口"""

import sys

try:
    from cnki_downloader.core.exceptions import install_global_handler
    from cnki_downloader.utils.logging import setup_logging

    setup_logging()
    install_global_handler()

    from cnki_downloader.utils.frozen import setup_playwright_env  # noqa: E402

    setup_playwright_env()

    if getattr(sys, "frozen", False) and len(sys.argv) <= 1:
        from cnki_downloader.gui.app import run_gui  # noqa: E402

        run_gui(theme="light")
    else:
        from cnki_downloader.cli.app import main  # noqa: E402

        main()
except Exception as e:
    # 双击启动时如果崩溃，弹窗显示错误信息（防止控制台一闪而过）
    if getattr(sys, "frozen", False) and len(sys.argv) <= 1:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, f"启动失败:\n\n{e}", "CNKI Downloader", 0x10
            )
        except Exception:
            input(f"启动失败: {e}\n按回车退出...")
    else:
        raise
