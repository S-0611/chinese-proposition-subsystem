# -*- coding: utf-8 -*-
"""人工复核结果读取与发布门禁。

人工语义问题无法由正则校验完全覆盖，因此发布前必须读取
reports/levelN/manual_review.json，并确认所有 P0 问题均已解决。
"""
import json
from pathlib import Path


def review_path(root: Path, level: int) -> Path:
    return root / "reports" / f"level{level}" / "manual_review.json"


def load_review(root: Path, level: int) -> dict:
    path = review_path(root, level)
    if not path.exists():
        return {
            "level": level,
            "status": "missing",
            "issues": [],
            "path": str(path),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "level": level,
            "status": "invalid",
            "issues": [],
            "path": str(path),
            "error": str(exc),
        }
    data.setdefault("level", level)
    data.setdefault("issues", [])
    data["path"] = str(path)
    return data


def blocking_p0(review: dict) -> list[dict]:
    """返回仍未 resolved 的 P0 问题。缺失/无效复核文件由调用方单独处理。"""
    return [
        issue for issue in review.get("issues", [])
        if issue.get("severity") == "P0" and issue.get("status") != "resolved"
    ]


def manual_review_gate(root: Path, level: int) -> dict:
    review = load_review(root, level)
    if review.get("status") in {"missing", "invalid"}:
        return {
            "ok": False,
            "reason": "manual_review_missing_or_invalid",
            "review": review,
            "blocking_p0": [],
        }
    blocking = blocking_p0(review)
    return {
        "ok": not blocking,
        "reason": "pass" if not blocking else "unresolved_p0",
        "review": review,
        "blocking_p0": blocking,
    }
