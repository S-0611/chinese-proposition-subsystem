# -*- coding: utf-8 -*-
"""命题子系统后端服务（成员B 交付物，支持一级至九级按等级查询）。

统一字段：id / level / text / tokens / grammar / status / rec_count / last_selected_at
抽题权重（按历史覆盖程度）：w = max(0, C - rec_count)，C 默认 10，可通过 ?C= 调整。

启动（项目根目录）：
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
    Swagger 文档：http://127.0.0.1:8001/docs

等级约定：
    level 取值范围 1—9；数据文件 data/levels/levelN.json，题库 banks/levelN/，报告 reports/levelN/。
    七至九级按标准合并：data/levels/level8.json、level9.json 的 merged_into=7，
    所有 level=8/9 的请求统一归一到 level=7 读写；响应保留 requested_level 便于调用方追踪。
    尚未建立题库的等级返回标准空题库响应（见 docs/九级空题库返回示例.json）。
"""
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

CN_TZ = timezone(timedelta(hours=8))  # 北京时间（UTC+8）

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402
from lib import SUPPORTED_LEVELS, load_level, validate_bank, validate_item  # noqa: E402
import stats as stats_mod  # noqa: E402
from manual_review import manual_review_gate  # noqa: E402

app = FastAPI(title="命题子系统后端 API", version="0.3.1",
              description="题库查询 / 校验 / 统计 / 发布 / 按等级抽题 / 按覆盖程度推荐抽题（一级至九级；7-9 合并为 level 7）")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_api(request, call_next):
    """题库会导入/发布更新，API 响应禁止浏览器缓存，避免读到旧题库。"""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


DEFAULT_C = 10            # w = max(0, C - rec_count) 的常数
DEFAULT_CANDIDATE = 20    # 最低覆盖候选集大小
DEFAULT_RECENT_MIN = 10   # 短时间内不重复返回同一题（分钟）
MAX_N = 20

STATUS_FLOW = {
    "draft": {"validated", "rejected"},
    "validated": {"ready", "rejected", "draft"},
    "rejected": {"draft"},
    "ready": {"rejected"},
    "published": {"rejected"},
}


def _load_level_aliases() -> dict[int, int]:
    """读取配置中的 merged_into，建立 8/9 → 7 的别名表。"""
    aliases: dict[int, int] = {}
    for n in SUPPORTED_LEVELS:
        path = ROOT / "data" / "levels" / f"level{n}.json"
        if not path.exists():
            continue
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        target = cfg.get("merged_into")
        if target:
            aliases[int(n)] = int(target)
    return aliases


LEVEL_ALIASES = _load_level_aliases()


def canonical_level(level: int | None) -> int | None:
    """把 8/9 等合并级别归一到实际存储级别（7）；支持多跳别名。"""
    if level is None:
        return None
    seen = set()
    while level in LEVEL_ALIASES and level not in seen:
        seen.add(level)
        level = LEVEL_ALIASES[level]
    return level


def level_meta(requested: int | None, canonical: int | None) -> dict:
    """响应中的等级元数据：level 为实际读写级别，requested_level 保留入参。"""
    merged = requested if requested != canonical else None
    return {
        "level": canonical,
        "requested_level": requested,
        "merged_into": canonical if merged is not None else None,
    }


def now_iso() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def fetch_items(conn, level=None, status=None):
    sql = "SELECT * FROM questions WHERE 1=1"
    args = []
    if level is not None:
        level = canonical_level(level)
        sql += " AND level=?"
        args.append(level)
    if status is not None:
        sql += " AND status=?"
        args.append(status)
    return [db.row_to_item(r) for r in conn.execute(sql, args)]


def level_has_data(conn, level) -> bool:
    level = canonical_level(level)
    return conn.execute("SELECT COUNT(*) FROM questions WHERE level=?", (level,)).fetchone()[0] > 0


# ── 查询接口 ────────────────────────────────────────────────

@app.get("/")
def service_info():
    conn = db.connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    finally:
        conn.close()
    return {"service": "命题子系统后端", "version": "0.3.1",
            "questions_total": n, "docs": "/docs",
            "merged_levels": LEVEL_ALIASES}


MAX_LEVEL = max(SUPPORTED_LEVELS)  # 9


@app.get("/api/questions")
def list_questions(level: int | None = Query(None, ge=1, le=MAX_LEVEL),
                   status: str | None = Query(None)):
    if status is not None and status not in db.ALLOWED_STATUS:
        raise HTTPException(400, f"非法状态 {status}，允许：{', '.join(db.ALLOWED_STATUS)}")
    requested_level = level
    level = canonical_level(level)
    conn = db.connect()
    try:
        if level is not None and not level_has_data(conn, level):
            # 标准空题库响应：明确区分“题库尚未完成”与“查询出错”，绝不返回其他等级的题目
            payload = {"total": 0, "items": [], "detail": "该等级题库尚未完成"}
            if requested_level is not None:
                payload.update(level_meta(requested_level, level))
            return payload
        items = fetch_items(conn, level, status)
    finally:
        conn.close()
    payload = {"total": len(items), "items": items}
    if requested_level is not None:
        payload.update(level_meta(requested_level, level))
    return payload


@app.get("/api/levels")
def list_levels():
    """九级题库状态总览：每级题目数量与是否可查询（供状态看板使用）。"""
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT level, COUNT(*) AS n FROM questions GROUP BY level").fetchall()
    finally:
        conn.close()
    counts = {r["level"]: r["n"] for r in rows}
    items = []
    for lv in SUPPORTED_LEVELS:
        canonical = canonical_level(lv)
        if canonical != lv:
            items.append({
                "level": lv,
                "question_count": 0,
                "status": "merged",
                "merged_into": canonical,
                "detail": f"该等级合并至 level {canonical}，请使用 level={canonical} 查询",
            })
            continue
        n = counts.get(lv, 0)
        items.append({
            "level": lv,
            "question_count": n,
            "status": "available" if n > 0 else "pending",
            "merged_into": None,
            "detail": None if n > 0 else "该等级题库尚未完成",
        })
    merged_groups = []
    for canonical in sorted({canonical_level(n) for n in SUPPORTED_LEVELS}):
        members = [n for n in SUPPORTED_LEVELS if canonical_level(n) == canonical]
        if len(members) > 1:
            merged_groups.append({
                "levels": members,
                "level": canonical,
                "question_count": counts.get(canonical, 0),
            })
    return {"total": len(items), "items": items, "merged_groups": merged_groups}


# ── 抽题接口（必须先于 /api/questions/{qid} 注册，避免路径抢占）──

@app.get("/api/questions/random")
def random_questions(level: int = Query(..., ge=1, le=MAX_LEVEL),
                     n: int = Query(1, ge=1, le=MAX_N)):
    """按等级抽题：仅在 published 题中等概率抽取；8/9 自动归一到 7。"""
    requested_level = level
    level = canonical_level(level)
    conn = db.connect()
    try:
        pool = fetch_items(conn, level=level, status="published")
        if not pool:
            raise HTTPException(404, f"等级 {level} 没有已发布（published）题目，请先发布题库")
        if n > len(pool):
            n = len(pool)
        picked = random.sample(pool, n)
        stamp = now_iso()
        for it in picked:
            conn.execute("UPDATE questions SET last_selected_at=? WHERE id=?", (stamp, it["id"]))
            it["last_selected_at"] = stamp
        db.add_run(conn, "draw", level, {"mode": "random", "n": n, "requested_level": requested_level,
                                         "ids": [i["id"] for i in picked]})
    finally:
        conn.close()
    return {"mode": "random", **level_meta(requested_level, level), "items": picked}


@app.get("/api/questions/recommend")
def recommend_questions(level: int = Query(..., ge=1, le=MAX_LEVEL),
                        n: int = Query(1, ge=1, le=MAX_N),
                        C: float = Query(DEFAULT_C, gt=0),
                        candidate_size: int = Query(DEFAULT_CANDIDATE, ge=1),
                        recent_minutes: int = Query(DEFAULT_RECENT_MIN, ge=0)):
    """按历史覆盖程度抽题（成员B 第六天任务，权重已改为 w = max(0, C - rec_count)）。

    两阶段：
      1. 候选集 = 该等级 published 题中 rec_count 最低的前 candidate_size 题。
      2. 排除最近 recent_minutes 内抽过的题后，按 w = max(0, C - rec_count) 加权不放回抽取 n 题。
    若候选被时间窗排空，自动放宽时间窗；若候选权重全为 0（录音数已达 C），返回 404。
    """
    requested_level = level
    level = canonical_level(level)
    conn = db.connect()
    try:
        pool = fetch_items(conn, level=level, status="published")
        if not pool:
            raise HTTPException(404, f"等级 {level} 没有已发布（published）题目，请先发布题库")

        pool.sort(key=lambda x: x["rec_count"])
        cand = pool[:candidate_size]
        weights = {i["id"]: max(0.0, C - i["rec_count"]) for i in cand}
        if all(w <= 0 for w in weights.values()):
            raise HTTPException(404, f"等级 {level} 候选题目录音数均已达到上限 C={C}，无题可推荐")

        window = timedelta(minutes=recent_minutes)
        relaxed = None
        while True:
            cutoff = datetime.now(CN_TZ) - window
            avail = [i for i in cand if not i["last_selected_at"]
                     or datetime.fromisoformat(i["last_selected_at"]) < cutoff]
            if len(avail) >= min(n, len(cand)):
                break
            if window <= timedelta(0):
                avail = cand
                relaxed = 0
                break
            window //= 2
            relaxed = int(window.total_seconds() // 60)

        if not avail:
            raise HTTPException(404, f"等级 {level} 当前无可推荐题目")

        picked, picked_ids, stamp = [], set(), now_iso()
        for _ in range(min(n, len(avail))):
            wsum = sum(weights[i["id"]] for i in avail if i["id"] not in picked_ids)
            if wsum <= 0:
                break
            r = random.random() * wsum
            acc = 0.0
            for it in avail:
                if it["id"] in picked_ids:
                    continue
                acc += weights[it["id"]]
                if acc >= r:
                    picked.append(it)
                    picked_ids.add(it["id"])
                    break
        if not picked:
            raise HTTPException(404, f"等级 {level} 当前无可推荐题目（权重全为 0）")

        for it in picked:
            conn.execute("UPDATE questions SET last_selected_at=? WHERE id=?", (stamp, it["id"]))
            it["last_selected_at"] = stamp
        db.add_run(conn, "draw", level, {"mode": "recommend", "n": len(picked),
                                         "requested_level": requested_level,
                                         "C": C, "candidate_size": candidate_size,
                                         "recent_minutes": recent_minutes,
                                         "window_relaxed_min": relaxed,
                                         "ids": [i["id"] for i in picked]})
    finally:
        conn.close()
    return {
        **level_meta(requested_level, level), "mode": "recommend",
        "algorithm": {
            "formula": "w = max(0, C - rec_count)",
            "C": C, "candidate_size": candidate_size,
            "recent_window_min": recent_minutes,
            "window_relaxed_min": relaxed,
            "weights_used": {i["id"]: weights[i["id"]] for i in picked},
        },
        "items": picked,
    }


@app.get("/api/questions/{qid}")
def get_question(qid: str):
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(404, f"题目不存在：{qid}")
    return db.row_to_item(row)


# ── 录音计数（覆盖口径：学生端成功上传并保存的有效录音）──────

class RecordedBody(BaseModel):
    recording_id: str | None = None
    speaker_id: str | None = None


@app.post("/api/questions/{qid}/recorded")
def mark_recorded(qid: str, body: RecordedBody | None = None):
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        if row is None:
            raise HTTPException(404, f"题目不存在：{qid}")
        recording_id = body.recording_id if body else None
        if recording_id:
            existing = conn.execute(
                "SELECT recording_id FROM recording_events WHERE recording_id=?", (recording_id,)
            ).fetchone()
            if existing:
                row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
                return {"ok": True, "duplicate": True, "item": db.row_to_item(row)}
            conn.execute(
                "INSERT INTO recording_events(recording_id, question_id, speaker_id, created_at) VALUES (?,?,?,?)",
                (recording_id, qid, body.speaker_id if body else None, now_iso()),
            )
        conn.execute("UPDATE questions SET rec_count = rec_count + 1 WHERE id=?", (qid,))
        db.add_run(conn, "record", row["level"], {"id": qid})
        row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    finally:
        conn.close()
    return {"ok": True, "item": db.row_to_item(row)}


class CoverageItem(BaseModel):
    question_id: str
    recording_count: int
    unique_speaker_count: int


class CoverageSnapshot(BaseModel):
    snapshot_version: str
    generated_at: str
    items: list[CoverageItem]


@app.put("/api/v1/integration/coverage")
def update_coverage(snapshot: CoverageSnapshot):
    """接收管理端按题覆盖快照；同一 snapshot_version 重放不重复累加。"""
    for item in snapshot.items:
        if item.recording_count < 0 or item.unique_speaker_count < 0:
            raise HTTPException(422, "录音数和独立说话人数不能为负数")
    payload = snapshot.model_dump()
    conn = db.connect()
    try:
        existing = conn.execute(
            "SELECT payload FROM coverage_snapshots WHERE snapshot_version=?",
            (snapshot.snapshot_version,),
        ).fetchone()
        if existing:
            return {"ok": True, "applied": False, "snapshot": json.loads(existing["payload"])}
        conn.execute(
            "INSERT INTO coverage_snapshots(snapshot_version, generated_at, payload, created_at) VALUES (?,?,?,?)",
            (snapshot.snapshot_version, snapshot.generated_at,
             json.dumps(payload, ensure_ascii=False), now_iso()),
        )
        db.add_run(conn, "coverage", None, {"snapshot_version": snapshot.snapshot_version,
                                             "items": len(snapshot.items)})
    finally:
        conn.close()
    return {"ok": True, "applied": True, "snapshot": payload}


# ── 状态管理与发布（第四/七天任务）──────────────────────────

class StatusBody(BaseModel):
    status: str


@app.post("/api/questions/{qid}/status")
def set_status(qid: str, body: StatusBody):
    if body.status not in db.ALLOWED_STATUS:
        raise HTTPException(400, f"非法状态 {body.status}，允许：{', '.join(db.ALLOWED_STATUS)}")
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        if row is None:
            raise HTTPException(404, f"题目不存在：{qid}")
        allowed = STATUS_FLOW.get(row["status"], set())
        if body.status not in allowed:
            raise HTTPException(400, f"状态不能从 {row['status']} 变更为 {body.status}（允许：{', '.join(sorted(allowed))}）")
        conn.execute("UPDATE questions SET status=? WHERE id=?", (body.status, qid))
        db.add_run(conn, "status", row["level"], {"id": qid, "from": row["status"], "to": body.status})
        row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    finally:
        conn.close()
    return {"ok": True, "item": db.row_to_item(row)}


def _publish_gate(conn, level, qid):
    """发布前检查：自动校验、统计达标和人工 P0 复核全部通过。"""
    items = fetch_items(conn, level=level)
    target = next((i for i in items if i["id"] == qid), None)
    if target is None:
        raise HTTPException(404, f"题目不存在：{qid}")
    cfg = load_level(level)
    check = validate_item(target, cfg)
    if not check["ok"]:
        raise HTTPException(400, f"题目 {qid} 校验不通过，不能发布：{'；'.join(check['errors'])}")
    s, _ = stats_mod.compute(cfg, items)
    if s["verdict"] != "pass":
        raise HTTPException(400, f"题库整体未达标，不能发布：{'；'.join(s['failed_checks'])}")
    if cfg.get("manual_review_required", True):
        review_gate = manual_review_gate(ROOT, level)
        if not review_gate["ok"]:
            if review_gate["reason"] == "manual_review_missing_or_invalid":
                raise HTTPException(400, f"人工复核门禁未通过：复核文件缺失或无效（{review_gate['review'].get('path')}）")
            ids = '、'.join(i.get("id", "?") for i in review_gate["blocking_p0"])
            raise HTTPException(400, f"人工复核门禁未通过：仍有未解决的 P0 问题（{ids}）")
    return target


@app.post("/api/questions/{qid}/publish")
def publish_one(qid: str):
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        if row is None:
            raise HTTPException(404, f"题目不存在：{qid}")
        _publish_gate(conn, row["level"], qid)
        conn.execute("UPDATE questions SET status='published' WHERE id=?", (qid,))
        db.add_run(conn, "publish", row["level"], {"id": qid, "scope": "single"})
        row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    finally:
        conn.close()
    return {"ok": True, "message": f"{qid} 已发布", "item": db.row_to_item(row)}


class PublishBody(BaseModel):
    level: int = Field(ge=1, le=9, description="等级 1—9")


@app.post("/api/pipeline/publish")
def publish_level(body: PublishBody):
    """整级发布：先做题库整体达标检查，通过后把该等级全部 ready/validated/draft 题置为 published；8/9 归一到 7。"""
    requested_level = body.level
    level = canonical_level(requested_level)
    conn = db.connect()
    try:
        if not level_has_data(conn, level):
            raise HTTPException(404, f"等级 {level} 题库尚未完成（该等级题库尚未完成，请先导入）")
        items = fetch_items(conn, level=level)
        cfg = load_level(level)
        s, _ = stats_mod.compute(cfg, items)
        if s["verdict"] != "pass":
            raise HTTPException(400, f"题库整体未达标，不能发布：{'；'.join(s['failed_checks'])}")
        if cfg.get("manual_review_required", True):
            review_gate = manual_review_gate(ROOT, level)
            if not review_gate["ok"]:
                if review_gate["reason"] == "manual_review_missing_or_invalid":
                    raise HTTPException(400, f"人工复核门禁未通过：复核文件缺失或无效（{review_gate['review'].get('path')}）")
                ids = '、'.join(i.get("id", "?") for i in review_gate["blocking_p0"])
                raise HTTPException(400, f"人工复核门禁未通过：仍有未解决的 P0 问题（{ids}）")
        cur = conn.execute(
            "UPDATE questions SET status='published' WHERE level=? AND status IN ('ready','validated','draft')",
            (level,)).rowcount
        db.add_run(conn, "publish", level, {"scope": "level", "requested_level": requested_level, "count": cur})
    finally:
        conn.close()
    return {"ok": True, **level_meta(requested_level, level), "published_count": cur,
            "message": f"等级 {level} 已发布 {cur} 题（仅 published 题目可被抽取）"}


# ── 校验 / 统计接入（第三天任务）────────────────────────────

def _save_round(level, kind, payload):
    d = ROOT / "reports" / f"level{level}"
    d.mkdir(parents=True, exist_ok=True)
    fname = d / f"api_{kind}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    fname.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return fname


@app.post("/api/pipeline/validate")
def pipeline_validate(level: int = Query(1, ge=1, le=MAX_LEVEL)):
    requested_level = level
    level = canonical_level(level)
    conn = db.connect()
    try:
        items = fetch_items(conn, level=level)
        if not items:
            raise HTTPException(404, f"等级 {level} 题库尚未完成（该等级题库尚未完成，请先导入）")
        cfg = load_level(level)
        _, results, dup_ids, dup_texts = validate_bank(items, cfg)
        bad = [{"id": r["item"]["id"], "text": r["item"]["text"],
                "errors": r["errors"]} for r in results if not r["ok"]]
        payload = {
            "kind": "validate", **level_meta(requested_level, level),
            "run_at": now_iso(), "total": len(items),
            "valid": len(items) - len(bad), "invalid": len(bad),
            "dup_ids": dup_ids, "dup_texts": dup_texts,
            "verdict": "pass" if not bad and not dup_ids else "fail",
            "bad_items": bad,
        }
        fname = _save_round(level, "validate", payload)
        db.add_run(conn, "validate", level, {"verdict": payload["verdict"],
                                             "requested_level": requested_level,
                                             "valid": payload["valid"],
                                             "invalid": payload["invalid"], "file": str(fname)})
    finally:
        conn.close()
    return {**payload, "saved_to": str(fname.relative_to(ROOT))}


@app.post("/api/pipeline/stats")
def pipeline_stats(level: int = Query(1, ge=1, le=MAX_LEVEL)):
    requested_level = level
    level = canonical_level(level)
    conn = db.connect()
    try:
        items = fetch_items(conn, level=level)
        if not items:
            raise HTTPException(404, f"等级 {level} 题库尚未完成（该等级题库尚未完成，请先导入）")
        cfg = load_level(level)
        s, plan = stats_mod.compute(cfg, items)
        payload = {"kind": "stats", **level_meta(requested_level, level), "run_at": now_iso(), **s,
                   "plan": {"suggested_new_items": plan["suggested_new_items"],
                            "uncovered_chars": plan["new_chars"],
                            "uncovered_grammar": plan["new_grammar"]}}
        fname = _save_round(level, "stats", payload)
        db.add_run(conn, "stats", level, {"verdict": s["verdict"],
                                          "requested_level": requested_level, "file": str(fname)})
    finally:
        conn.close()
    return {**payload, "saved_to": str(fname.relative_to(ROOT))}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8001)

