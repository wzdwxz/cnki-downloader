"""下载任务状态模型"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DownloadTask:
    """下载任务"""

    task_id: str
    paper_title: str
    url: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0       # 0.0 ~ 1.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    output_path: str = ""
    error_message: str = ""
