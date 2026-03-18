"""CAJ → PDF 格式转换"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from cnki_downloader.core.exceptions import ConvertError

logger = logging.getLogger(__name__)


def check_caj2pdf() -> bool:
    """检查 caj2pdf 是否可用。"""
    return shutil.which("caj2pdf") is not None


def convert_caj_to_pdf(
    caj_path: Path,
    output_path: Path | None = None,
    delete_caj: bool = False,
) -> Path:
    """将CAJ文件转换为PDF。

    优先使用 caj2pdf 命令行工具，若不可用则尝试 PyMuPDF。

    Args:
        caj_path: CAJ文件路径
        output_path: 输出PDF路径，默认为同名.pdf
        delete_caj: 转换成功后是否删除原CAJ文件

    Returns:
        生成的PDF文件路径
    """
    if not caj_path.exists():
        raise ConvertError(f"CAJ文件不存在: {caj_path}")

    if not caj_path.suffix.lower() == ".caj":
        raise ConvertError(f"不是CAJ文件: {caj_path}")

    if output_path is None:
        output_path = caj_path.with_suffix(".pdf")

    # 方法1: 使用 caj2pdf 命令行
    if check_caj2pdf():
        return _convert_with_caj2pdf(caj_path, output_path, delete_caj)

    # 方法2: 尝试 PyMuPDF (fitz) 直接打开
    # 某些CAJ文件本质上是PDF格式，可以直接用 PyMuPDF 打开
    return _convert_with_pymupdf(caj_path, output_path, delete_caj)


def _convert_with_caj2pdf(
    caj_path: Path, output_path: Path, delete_caj: bool
) -> Path:
    """使用 caj2pdf 工具转换。"""
    try:
        result = subprocess.run(
            ["caj2pdf", "convert", str(caj_path), "-o", str(output_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise ConvertError(f"caj2pdf转换失败: {result.stderr}")

        if not output_path.exists():
            raise ConvertError("caj2pdf运行完成但未生成PDF文件")

        logger.info("CAJ转PDF完成 (caj2pdf): %s -> %s", caj_path, output_path)

        if delete_caj:
            caj_path.unlink()
            logger.info("已删除原CAJ文件: %s", caj_path)

        return output_path

    except subprocess.TimeoutExpired:
        raise ConvertError("caj2pdf转换超时（120秒）")
    except FileNotFoundError:
        raise ConvertError("caj2pdf工具未找到")


def _convert_with_pymupdf(
    caj_path: Path, output_path: Path, delete_caj: bool
) -> Path:
    """尝试用 PyMuPDF 转换（适用于伪装成CAJ的PDF文件）。"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ConvertError(
            "未安装转换工具。请安装 caj2pdf 或 pip install 'cnki-downloader[convert]'"
        )

    try:
        doc = fitz.open(str(caj_path))
        doc.save(str(output_path))
        doc.close()

        logger.info("CAJ转PDF完成 (PyMuPDF): %s -> %s", caj_path, output_path)

        if delete_caj:
            caj_path.unlink()
            logger.info("已删除原CAJ文件: %s", caj_path)

        return output_path

    except Exception as e:
        raise ConvertError(
            f"PyMuPDF转换失败（文件可能是真正的CAJ格式，需要caj2pdf工具）: {e}"
        ) from e
