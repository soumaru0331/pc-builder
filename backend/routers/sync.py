"""パーツDB自動同期 API"""
import json
import asyncio
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from database import get_db
from sync.kakaku_sync import sync_category, sync_all_categories, KAKAKU_CATEGORIES
from sync.brands import BRANDS, ALL_BRANDS

router = APIRouter()

# 同期ステータス管理
_sync_status: dict = {
    "running": False,
    "progress": {},
    "last_result": {},
    "error": None,
}


def _upsert_parts(parts: list[dict]) -> tuple[int, int]:
    """INSERT OR IGNORE で重複を避けて追加。(added, skipped) を返す"""
    conn = get_db()
    c = conn.cursor()

    # UNIQUE インデックスがなければ作成
    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_parts_brand_model
        ON parts(brand, model)
    """)

    added = skipped = 0
    for p in parts:
        try:
            c.execute(
                """INSERT INTO parts
                   (category, brand, name, model, specs, tdp, benchmark_score, reference_price, release_year, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(brand, model) DO UPDATE SET
                       reference_price = CASE WHEN excluded.reference_price > 0
                                              THEN excluded.reference_price
                                              ELSE reference_price END,
                       specs           = CASE WHEN excluded.specs != '{}'
                                              THEN excluded.specs
                                              ELSE specs END,
                       tdp             = CASE WHEN excluded.tdp > 0
                                              THEN excluded.tdp
                                              ELSE tdp END,
                       benchmark_score = CASE WHEN excluded.benchmark_score > 0
                                              THEN excluded.benchmark_score
                                              ELSE benchmark_score END""",
                (
                    p["category"], p["brand"], p["name"], p["model"],
                    json.dumps(p.get("specs", {}), ensure_ascii=False),
                    p.get("tdp", 0), p.get("benchmark_score", 0),
                    p.get("reference_price", 0), p.get("release_year"),
                    p.get("notes", ""),
                ),
            )
            # rowcount==1 は新規挿入、rowcount==0 は競合なし(変化なし)
            # ON CONFLICT DO UPDATE の場合も rowcount==1 になる
            if c.rowcount > 0:
                added += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1

    conn.commit()
    conn.close()
    return added, skipped


async def _run_sync(categories: list[str], max_pages: int):
    """バックグラウンドで実行される同期処理"""
    global _sync_status
    _sync_status["running"] = True
    _sync_status["error"] = None
    _sync_status["progress"] = {cat: "待機中" for cat in categories}
    _sync_status["last_result"] = {}

    try:
        for cat in categories:
            _sync_status["progress"][cat] = "取得中..."
            try:
                parts = await sync_category(cat, max_pages)
                added, skipped = _upsert_parts(parts)
                _sync_status["progress"][cat] = f"完了 ({added}件追加, {skipped}件スキップ)"
                _sync_status["last_result"][cat] = {"added": added, "skipped": skipped, "total": len(parts)}
            except Exception as e:
                _sync_status["progress"][cat] = f"エラー: {str(e)[:60]}"
                _sync_status["last_result"][cat] = {"error": str(e)}
            await asyncio.sleep(2)
    except Exception as e:
        _sync_status["error"] = str(e)
    finally:
        _sync_status["running"] = False


class SyncRequest(BaseModel):
    categories: list[str] | None = None
    max_pages: int = 10


@router.post("/start")
async def start_sync(background_tasks: BackgroundTasks, req: SyncRequest = SyncRequest()):
    """同期を開始する（バックグラウンド実行）"""
    if _sync_status["running"]:
        return {"message": "すでに同期中です", "status": _sync_status}

    targets = req.categories or list(KAKAKU_CATEGORIES.keys())
    # 不正なカテゴリを除外
    targets = [c for c in targets if c in KAKAKU_CATEGORIES]

    background_tasks.add_task(_run_sync, targets, req.max_pages)
    return {"message": f"{len(targets)}カテゴリの同期を開始しました", "categories": targets}


@router.get("/status")
def get_sync_status():
    return _sync_status


@router.get("/brands")
def get_all_brands(category: str | None = None):
    """カテゴリ別ブランド一覧を返す"""
    if category:
        return {"brands": BRANDS.get(category, []), "category": category}
    return {"brands": BRANDS, "all": ALL_BRANDS}


@router.get("/categories")
def get_sync_categories():
    return list(KAKAKU_CATEGORIES.keys())


@router.post("/recalc-benchmarks")
def recalc_benchmarks():
    """全パーツのベンチマークスコアを spec_parser で再計算して DB に保存"""
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


@router.get("/debug-scrape")
async def debug_scrape(category: str = "cpu"):
    """スクレイパーデバッグ用（開発時のみ）"""
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
