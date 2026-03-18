"""构建脚本 — 使用PyInstaller打包为独立可执行文件"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def build_exe() -> None:
    """使用PyInstaller打包。"""
    project_root = Path(__file__).parent.parent
    spec_file = project_root / "cnki_downloader.spec"

    if not spec_file.exists():
        print(f"Error: spec file not found: {spec_file}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(spec_file),
        "--distpath", str(project_root / "dist"),
        "--workpath", str(project_root / "build"),
        "--clean",
    ]

    print(f"Building with command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(project_root))
    sys.exit(result.returncode)


if __name__ == "__main__":
    build_exe()
