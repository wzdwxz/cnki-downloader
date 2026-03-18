"""文献卡片控件 — 展示单篇文献摘要信息"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from cnki_downloader.models.paper import Paper


class PaperCard(QFrame):
    """文献信息卡片。"""

    download_clicked = pyqtSignal(Paper)

    def __init__(self, paper: Paper, parent=None) -> None:
        super().__init__(parent)
        self._paper = paper
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            PaperCard {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
            }
            PaperCard:hover {
                border-color: #0d6efd;
            }
        """)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        title = QLabel(self._paper.title)
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #333;")
        title.setWordWrap(True)
        layout.addWidget(title)

        meta = QHBoxLayout()
        if self._paper.authors:
            authors_text = ", ".join(self._paper.authors[:3])
            if len(self._paper.authors) > 3:
                authors_text += " 等"
            authors = QLabel(authors_text)
            authors.setStyleSheet("color: #666; font-size: 12px;")
            meta.addWidget(authors)

        if self._paper.journal:
            journal = QLabel(self._paper.journal)
            journal.setStyleSheet("color: #0d6efd; font-size: 12px;")
            meta.addWidget(journal)

        if self._paper.publish_date:
            date = QLabel(self._paper.publish_date)
            date.setStyleSheet("color: #999; font-size: 12px;")
            meta.addWidget(date)

        meta.addStretch()
        layout.addLayout(meta)

        if self._paper.abstract:
            text = self._paper.abstract[:200]
            if len(self._paper.abstract) > 200:
                text += "..."
            abstract = QLabel(text)
            abstract.setStyleSheet("color: #555; font-size: 12px;")
            abstract.setWordWrap(True)
            layout.addWidget(abstract)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        dl_btn = QPushButton("下载")
        dl_btn.setObjectName("primaryBtn")
        dl_btn.setFixedWidth(80)
        dl_btn.clicked.connect(lambda: self.download_clicked.emit(self._paper))
        btn_layout.addWidget(dl_btn)
        layout.addLayout(btn_layout)

    @property
    def paper(self) -> Paper:
        return self._paper
