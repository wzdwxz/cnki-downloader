"""文献管理：收藏、分类、标签"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Category:
    """分类目录节点"""

    id: int = 0
    name: str = ""
    parent_id: int | None = None
    sort_order: int = 0
    children: list[Category] = field(default_factory=list)


@dataclass
class Tag:
    """标签"""

    id: int = 0
    name: str = ""
    color: str = "#808080"


def build_category_tree(flat_categories: list[Category]) -> list[Category]:
    """将扁平分类列表构建为树形结构。"""
    by_id: dict[int, Category] = {c.id: c for c in flat_categories}
    roots: list[Category] = []

    for cat in flat_categories:
        if cat.parent_id is None or cat.parent_id not in by_id:
            roots.append(cat)
        else:
            parent = by_id[cat.parent_id]
            parent.children.append(cat)

    return roots
