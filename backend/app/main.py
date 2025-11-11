from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sqlite3
import os
import time
import base64
import uuid
import re
from typing import List, Optional, Dict, Any
import logging


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(PROJECT_ROOT, 'data.db')
MGC_PATH = os.path.join(PROJECT_ROOT, 'mgc.txt')
UPLOADS_DIR = os.path.join(PROJECT_ROOT, 'uploads')
REPORT_UPLOAD_PWD = "123"
REPORT_ADMIN_PWD = "123"


def _init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    # SQLite 轻量优化
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA temp_store=MEMORY;")
    cur.execute("PRAGMA busy_timeout=3000;")
    # 表结构
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            character TEXT NOT NULL,
            score INTEGER NOT NULL,
            found_count INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scores_score ON scores(score);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scores_created ON scores(created_at);")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            npc TEXT,
            x INTEGER,
            y INTEGER,
            created_at INTEGER NOT NULL
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at);")
    # 兼容新增的审核/删除字段（若已存在则忽略错误）
    try:
        cur.execute("ALTER TABLE reports ADD COLUMN audited INTEGER NOT NULL DEFAULT 0;")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE reports ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0;")
    except Exception:
        pass
    # 兼容新增的图片字段（base64或dataURL），若已存在则忽略错误
    try:
        cur.execute("ALTER TABLE reports ADD COLUMN img_data TEXT;")
    except Exception:
        pass
    conn.commit()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _init_db(conn)
    return conn


def _load_mgc_words() -> List[str]:
    if not os.path.exists(MGC_PATH):
        return []
    try:
        with open(MGC_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            words = [line.strip() for line in f if line.strip()]
            return words
    except Exception:
        return []


def contains_mgc(text: str, mgc_words: List[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    for w in mgc_words:
        if not w:
            continue
        if w.lower() in lower:
            return True
    return False


class APIResponse(BaseModel):
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ScoreSubmit(BaseModel):
    playerName: str = Field(..., min_length=1, max_length=40)
    character: str = Field(..., min_length=1, max_length=40)
    score: int = Field(..., ge=0, le=999999)
    foundCount: int = Field(0, ge=0, le=9999)
    ts: Optional[int] = None


class ReportSubmit(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    npc: Optional[str] = Field(None, max_length=40)
    x: Optional[int] = None
    y: Optional[int] = None
    ts: Optional[int] = None
    imgData: Optional[str] = None


class ScoreItem(BaseModel):
    id: int
    playerName: str
    character: str
    score: int
    foundCount: int
    createdAt: int


class ReportItem(BaseModel):
    id: int
    text: str
    npc: Optional[str]
    x: Optional[int]
    y: Optional[int]
    createdAt: int
    audited: int
    deleted: int
    imgData: Optional[str] = None


app = FastAPI()

# CORS（开发与生产可按需收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_conn = _get_conn()
_mgc = _load_mgc_words()

# 后端日志与启动信息
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [backend] %(message)s")
logger = logging.getLogger("backend")

@app.on_event("startup")
def _on_startup():
    try:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
    except Exception:
        pass
    mgc_count = len(_mgc) if _mgc else 0
    logger.info(
        f"Startup: DB_PATH={DB_PATH} exists={os.path.exists(DB_PATH)}; "
        f"UPLOADS_DIR={UPLOADS_DIR} exists={os.path.isdir(UPLOADS_DIR)}; "
        f"MGC_PATH={MGC_PATH} words={mgc_count}"
    )

@app.middleware("http")
async def _log_requests(request: Request, call_next):
    rid = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    client = request.client.host if request.client else "-"
    method = request.method
    path = request.url.path
    logger.info(f"[{rid}] {client} {method} {path} -> start")
    try:
        response = await call_next(request)
    except Exception as e:
        dur = (time.perf_counter() - start) * 1000
        logger.error(f"[{rid}] {client} {method} {path} -> ERROR {dur:.1f}ms: {e}")
        raise
    dur = (time.perf_counter() - start) * 1000
    logger.info(f"[{rid}] {client} {method} {path} -> {response.status_code} {dur:.1f}ms")
    return response


@app.get("/api/health", response_model=APIResponse)
def health() -> APIResponse:
    return APIResponse(ok=True, data={"ts": int(time.time())})

@app.get("/api/info", response_model=APIResponse)
def info() -> APIResponse:
    """运行时诊断信息，便于排查部署问题。"""
    data = {
        "dbPath": DB_PATH,
        "dbExists": os.path.exists(DB_PATH),
        "uploadsDir": UPLOADS_DIR,
        "uploadsExists": os.path.isdir(UPLOADS_DIR),
        "mgcPath": MGC_PATH,
        "mgcCount": len(_mgc) if _mgc else 0,
        "env": {
            "APP_ENV": os.environ.get("APP_ENV"),
            "HOSTNAME": os.environ.get("HOSTNAME"),
        },
    }
    return APIResponse(ok=True, data=data)


def _require_upload_pwd(request: Request) -> None:
    """Check password for uploading reports."""
    pwd = request.headers.get("X-Report-Pwd", "")
    if pwd != REPORT_UPLOAD_PWD:
        raise HTTPException(status_code=403, detail="上传密码错误或未提供")

def _require_admin_pwd(request: Request) -> None:
    """Check password for admin operations (audit/delete)."""
    pwd = request.headers.get("X-Report-Pwd", "")
    if pwd != REPORT_ADMIN_PWD:
        raise HTTPException(status_code=403, detail="管理密码错误或未提供")


@app.post("/api/scores/submit", response_model=APIResponse)
def submit_score(payload: ScoreSubmit) -> APIResponse:
    # 违禁词检查（姓名与角色）
    if contains_mgc(payload.playerName, _mgc) or contains_mgc(payload.character, _mgc):
        return APIResponse(ok=False, error="输入内容含违禁词，请修改")
    created_at = payload.ts or int(time.time())
    try:
        cur = _conn.cursor()
        cur.execute(
            "INSERT INTO scores(player_name, character, score, found_count, created_at) VALUES (?, ?, ?, ?, ?)",
            (payload.playerName, payload.character, int(payload.score), int(payload.foundCount or 0), int(created_at)),
        )
        _conn.commit()
        return APIResponse(ok=True, data={"id": cur.lastrowid})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scores/leaderboard", response_model=APIResponse)
def leaderboard(page: int = 1, limit: int = 20) -> APIResponse:
    page = max(1, page)
    limit = max(1, min(50, limit))
    offset = (page - 1) * limit
    try:
        cur = _conn.cursor()
        cur.execute("SELECT COUNT(*) FROM scores")
        total = int(cur.fetchone()[0])
        cur.execute(
            "SELECT id, player_name, character, score, found_count, created_at FROM scores ORDER BY score DESC, created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cur.fetchall()
        items: List[ScoreItem] = [
            ScoreItem(
                id=r[0], playerName=r[1], character=r[2], score=r[3], foundCount=r[4], createdAt=r[5]
            ) for r in rows
        ]
        return APIResponse(ok=True, data={"items": [i.dict() for i in items], "total": total, "page": page, "limit": limit})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reports/submit", response_model=APIResponse)
def submit_report(payload: ReportSubmit, request: Request) -> APIResponse:
    # 上传密码校验：禁止未授权提交，避免恶意上传
    _require_upload_pwd(request)
    if contains_mgc(payload.text, _mgc):
        return APIResponse(ok=False, error="爆料文本含违禁词，请修改")
    created_at = payload.ts or int(time.time())
    try:
        cur = _conn.cursor()
        # 将图片落盘并保存相对路径
        img_path = None
        if payload.imgData:
            img_path = _save_data_url_to_file(payload.imgData)
        cur.execute(
            "INSERT INTO reports(text, npc, x, y, created_at, img_data) VALUES (?, ?, ?, ?, ?, ?)",
            (payload.text, payload.npc or None, payload.x, payload.y, int(created_at), img_path or None),
        )
        _conn.commit()
        return APIResponse(ok=True, data={"id": cur.lastrowid})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/list", response_model=APIResponse)
def list_reports(page: int = 1, limit: int = 20) -> APIResponse:
    page = max(1, page)
    limit = max(1, min(50, limit))
    offset = (page - 1) * limit
    try:
        cur = _conn.cursor()
        cur.execute("SELECT COUNT(*) FROM reports")
        total = int(cur.fetchone()[0])
        cur.execute(
            "SELECT id, text, npc, x, y, created_at, audited, deleted, img_data FROM reports WHERE deleted = 0 ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cur.fetchall()
        items: List[ReportItem] = [
            ReportItem(
                id=r[0], text=r[1], npc=r[2], x=r[3], y=r[4], createdAt=r[5], audited=r[6] or 0, deleted=r[7] or 0, imgData=r[8]
            ) for r in rows
        ]
        return APIResponse(ok=True, data={"items": [i.dict() for i in items], "total": total, "page": page, "limit": limit})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ReportAudit(BaseModel):
    id: int
    audited: bool


@app.post("/api/reports/audit", response_model=APIResponse)
def audit_report(payload: ReportAudit, request: Request) -> APIResponse:
    # 管理密码校验：仅授权用户可审核
    _require_admin_pwd(request)
    try:
        cur = _conn.cursor()
        cur.execute("UPDATE reports SET audited = ? WHERE id = ?", (1 if payload.audited else 0, payload.id))
        _conn.commit()
        return APIResponse(ok=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ReportDelete(BaseModel):
    id: int


@app.post("/api/reports/delete", response_model=APIResponse)
def delete_report(payload: ReportDelete, request: Request) -> APIResponse:
    # 管理密码校验：仅授权用户可删除
    _require_admin_pwd(request)
    try:
        cur = _conn.cursor()
        cur.execute("UPDATE reports SET deleted = 1 WHERE id = ?", (payload.id,))
        _conn.commit()
        return APIResponse(ok=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 运行命令示例（文档）：
# uvicorn backend.app.main:app --host 127.0.0.1 --port 552 --workers 1 --loop uvloop --http httptools
def _save_data_url_to_file(data_url: str) -> Optional[str]:
    """Save a data URL (e.g., data:image/jpeg;base64,...) to uploads/ and return public path '/uploads/<file>'."""
    if not data_url:
        return None
    try:
        m = re.match(r'^data:(image/[^;]+);base64,(.+)$', data_url)
        if not m:
            return None
        mime = m.group(1).lower()
        b64 = m.group(2)
        # map mime to extension
        ext_map = {
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg',
            'image/png': 'png',
            'image/webp': 'webp',
            'image/gif': 'gif',
            'image/bmp': 'bmp'
        }
        ext = ext_map.get(mime, 'jpg')
        raw = base64.b64decode(b64)
        # ensure uploads dir
        try:
            os.makedirs(UPLOADS_DIR, exist_ok=True)
        except Exception:
            pass
        fname = f"{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}.{ext}"
        fpath = os.path.join(UPLOADS_DIR, fname)
        with open(fpath, 'wb') as f:
            f.write(raw)
        # return public path for frontend under static host
        return f"/uploads/{fname}"
    except Exception:
        return None