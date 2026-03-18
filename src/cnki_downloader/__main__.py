"""python -m cnki_downloader 入口"""

from cnki_downloader.core.exceptions import install_global_handler
from cnki_downloader.utils.logging import setup_logging

setup_logging()
install_global_handler()

from cnki_downloader.cli.app import main  # noqa: E402

main()
