"""パーツDB自動同期 API"""
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from database import get_db
from sync.kakaku_sync import sync_category, sync_all_categories, KAKAKU_CATEGORIES, KAKAKU_SCHEDULED_CATEGORIES
from sync.brands import BRANDS, ALL_BRANDS
from auth import require_admin

router = APIRouter()

# 同期ステータス管理
_sync_status: dict = {
    "running": False,
    "progress": {},
    "last_result": {},
    "error": None,
}


def _load_existing_models() -> set[str]:
    """DB内の既存パーツを (brand|model) セットとして返す"""
    conn = get_db()
    rows = conn.execute("SELECT brand, model FROM parts").fetchall()
    conn.close()
    return {f"{r['brand']}|{r['model'][:80]}" for r in rows}


def _upsert_parts(parts: list[dict]) -> tuple[int, int]:
    """新規パーツのみINSERT。(added, skipped) を返す"""
    conn = get_db()
    c = conn.cursor()

    # UNIQUE インデックスがなければ作成
    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_parts_brand_model
        ON parts(brand, model)
    """)

    added = skipped = 0
    price_updates = []
    for p in parts:
        try:
            c.execute(
                """INSERT OR IGNORE INTO parts
                   (category, brand, name, model, specs, tdp, benchmark_score, reference_price, release_year, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    p["category"], p["brand"], p["name"], p["model"],
                    json.dumps(p.get("specs", {}), ensure_ascii=False),
                    p.get("tdp", 0), p.get("benchmark_score", 0),
                    p.get("reference_price", 0), p.get("release_year"),
                    p.get("notes", ""),
                ),
            )
            if c.rowcount > 0:
                added += 1
                new_price = p.get("reference_price", 0)
                if new_price > 0:
                    part_row = c.execute(
                        "SELECT id FROM parts WHERE brand=? AND model=?",
                        (p["brand"], p["model"])
                    ).fetchone()
                    if part_row:
                        price_updates.append((part_row["id"], new_price))
            else:
                skipped += 1
        except Exception:
            skipped += 1

    # 価格履歴を一括記録
    for part_id, price in price_updates:
        c.execute(
            "INSERT INTO price_history (part_id, price, source) VALUES (?,?,'sync')",
            (part_id, price)
        )

    conn.commit()
    conn.close()
    return added, skipped


async def _run_sync(categories: list[str], max_pages: int, trigger: str = "manual"):
    """バックグラウンドで実行される同期処理"""
    global _sync_status
    _sync_status["running"] = True
    _sync_status["error"] = None
    _sync_status["progress"] = {cat: "待機中" for cat in categories}
    _sync_status["last_result"] = {}

    try:
        # 同期開始前にDB既存モデルセットを一括取得（早期終了判定に使用）
        existing_models = _load_existing_models()

        for cat in categories:
            started_at = datetime.now().isoformat()
            _sync_status["progress"][cat] = "取得中..."
            added = skipped = 0
            error = None
            try:
                parts = await sync_category(cat, max_pages, existing_models)
                added, skipped = _upsert_parts(parts)
                _sync_status["progress"][cat] = f"完了 ({added}件追加, {skipped}件スキップ)"
                _sync_status["last_result"][cat] = {"added": added, "skipped": skipped, "total": len(parts)}
            except Exception as e:
                error = str(e)
                _sync_status["progress"][cat] = f"エラー: {error[:60]}"
                _sync_status["last_result"][cat] = {"error": error}

            # sync_history に記録
            _save_sync_history(cat, started_at, added, skipped, error, trigger)
            await asyncio.sleep(2)
    except Exception as e:
        _sync_status["error"] = str(e)
    finally:
        _sync_status["running"] = False


def _save_sync_history(category, started_at, added, skipped, error, trigger):
    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO sync_history (category, started_at, completed_at, added, skipped, error, trigger)
               VALUES (?, ?, datetime('now'), ?, ?, ?, ?)""",
            (category, started_at, added, skipped, error, trigger)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


class SyncRequest(BaseModel):
    categories: list[str] | None = None
    max_pages: int = 150


@router.post("/start", dependencies=[Depends(require_admin)])
async def start_sync(background_tasks: BackgroundTasks, req: SyncRequest = SyncRequest()):
    """同期を開始する（バックグラウンド実行、管理者のみ）"""
    if _sync_status["running"]:
        return {"message": "すでに同期中です", "status": _sync_status}

    all_valid = {**KAKAKU_CATEGORIES, **KAKAKU_SCHEDULED_CATEGORIES}
    targets = req.categories or list(KAKAKU_CATEGORIES.keys())
    targets = [c for c in targets if c in all_valid]

    background_tasks.add_task(_run_sync, targets, req.max_pages, "manual")
    return {"message": f"{len(targets)}カテゴリの同期を開始しました", "categories": targets}


@router.get("/status")
def get_sync_status():
    return _sync_status


@router.get("/history")
def get_sync_history():
    """直近20件の同期履歴を返す"""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM sync_history ORDER BY id DESC LIMIT 20"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/brands")
def get_all_brands(category: str | None = None):
    """カテゴリ別ブランド一覧を返す"""
    if category:
        return {"brands": BRANDS.get(category, []), "category": category}
    return {"brands": BRANDS, "all": ALL_BRANDS}


@router.get("/categories")
def get_sync_categories():
    return list(KAKAKU_CATEGORIES.keys())


@router.post("/recalc-benchmarks", dependencies=[Depends(require_admin)])
def recalc_benchmarks():
    """全パーツのベンチマークスコアを spec_parser で再計算して DB に保存（管理者のみ）"""
    import json as _json
    from sync.spec_parser import parse_cpu, parse_gpu, estimate_benchmark
    conn = get_db()
    rows = conn.execute("SELECT id, category, name, specs FROM parts").fetchall()
    updated = 0
    for row in rows:
        cat  = row["category"]
        name = row["name"]
        try:
            specs = _json.loads(row["specs"] or "{}")
        except Exception:
            specs = {}
        if cat == "cpu":
            specs.update(parse_cpu(name))
        elif cat == "gpu":
            specs.update(parse_gpu(name))
        score = estimate_benchmark(cat, specs, name)
        if score > 0:
            conn.execute("UPDATE parts SET benchmark_score=? WHERE id=?", (score, row["id"]))
            updated += 1
    conn.commit()
    conn.close()
    return {"updated": updated, "total": len(rows)}


@router.get("/export-seed", dependencies=[Depends(require_admin)])
def export_seed():
    """現在のDBを initial_parts.json 形式でエクスポート（管理者のみ）
    ダウンロードしてリポジトリの backend/data/initial_parts.json に上書きすると
    デプロイ後もパーツデータが維持される。
    """
    import json as _json
    from fastapi.responses import JSONResponse
    conn = get_db()
    rows = conn.execute(
        "SELECT category, brand, name, model, specs, tdp, benchmark_score, reference_price, release_year, notes FROM parts ORDER BY category, brand, name"
    ).fetchall()
    conn.close()
    parts = []
    for r in rows:
        d = dict(r)
        try:
            d["specs"] = _json.loads(d["specs"] or "{}")
        except Exception:
            d["specs"] = {}
        parts.append(d)
    return JSONResponse(
        content=parts,
        headers={"Content-Disposition": "attachment; filename=initial_parts.json"},
    )


@router.get("/debug-scrape", dependencies=[Depends(require_admin)])
async def debug_scrape(category: str = "cpu"):
    """スクレイパーデバッグ用（管理者のみ）"""
    from sync.kakaku_sync import _fetch, _parse_page, KAKAKU_CATEGORIES as KC
    url = KC.get(category, "")
    html = await _fetch(url)
    if not html:
        return {"error": "fetch failed", "url": url}
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    tables = soup.select("table.tbl-compare02")
    table = next((t for t in tables if "fixedHeader" not in (t.get("class") or [])), None)
    tr_borders = table.find_all("tr", class_="tr-border") if table else []
    parts = _parse_page(html, category)
    return {
        "url": url,
        "html_len": len(html),
        "tables_found": len(tables),
        "data_table": table is not None,
        "tr_borders": len(tr_borders),
        "parts_parsed": len(parts),
        "first_3": parts[:3],
    }
