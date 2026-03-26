import json
import asyncio
import urllib.parse
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from database import get_db
from scrapers.kakaku import search_kakaku
from scrapers.mercari import search_mercari
from scrapers.yahooauction import search_yahoo_auction, search_yahoo_flea

router = APIRouter()

CACHE_MINUTES = 30


def _get_cached(conn, part_id: int) -> list[dict] | None:
    cutoff = (datetime.now() - timedelta(minutes=CACHE_MINUTES)).isoformat()
    rows = conn.execute(
        "SELECT * FROM price_cache WHERE part_id=? AND fetched_at > ? ORDER BY price ASC",
        (part_id, cutoff),
    ).fetchall()
    if rows:
        return [dict(r) for r in rows]
    return None


def _save_cache(conn, part_id: int, results: list[dict]):
    conn.execute("DELETE FROM price_cache WHERE part_id=?", (part_id,))
    for r in results:
        conn.execute(
            "INSERT INTO price_cache (part_id,source,price,url,title,is_used) VALUES (?,?,?,?,?,?)",
            (part_id, r["source"], r["price"], r.get("url", ""), r.get("title", ""), 1 if r.get("is_used") else 0),
        )
    conn.commit()


def _make_search_links(query: str) -> dict:
    """Always return search URLs so users can check manually even if scraping fails."""
    enc = urllib.parse.quote(query)
    return {
        "kakaku":      f"https://kakaku.com/search_results/?query={enc}",
        "amazon":      f"https://www.amazon.co.jp/s?k={enc}",
        "mercari":     f"https://jp.mercari.com/search?keyword={enc}&status=on_sale",
        "yahoo_auction": f"https://auctions.yahoo.co.jp/search/search?p={enc}",
        "yahoo_flea":  f"https://paypayfleamarket.yahoo.co.jp/search/{enc}",
        "janpara":     f"https://www.janpara.co.jp/sale/search/?KEYWORDS={enc}",
        "sofmap":      f"https://www.sofmap.com/search_result.aspx?T={enc}",
    }


@router.get("/{part_id}")
async def get_prices(part_id: int, force_refresh: bool = False):
    conn = get_db()
    part = conn.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
    if not part:
        conn.close()
        raise HTTPException(404, "パーツが見つかりません")

    part = dict(part)
    query = f"{part['brand']} {part['name']}"
    search_links = _make_search_links(query)

    if not force_refresh:
        cached = _get_cached(conn, part_id)
        if cached:
            conn.close()
            return _format_results(cached, part, search_links)

    # Fetch from all sources concurrently (with timeout protection)
    async def safe(coro):
        try:
            return await asyncio.wait_for(coro, timeout=12)
        except Exception:
            return []

    fetched = await asyncio.gather(
        safe(search_kakaku(query, 3)),
        safe(search_mercari(query, 3)),
        safe(search_yahoo_auction(query, 3)),
        safe(search_yahoo_flea(query, 2)),
    )

    all_results = []
    for r in fetched:
        if isinstance(r, list):
            all_results.extend(r)

    if all_results:
        _save_cache(conn, part_id, all_results)

    conn.close()
    return _format_results(all_results, part, search_links)


def _format_results(results: list[dict], part: dict, search_links: dict) -> dict:
    new_prices  = sorted([r for r in results if not r.get("is_used")], key=lambda x: x["price"])
    used_prices = sorted([r for r in results if r.get("is_used")],     key=lambda x: x["price"])

    cheapest_new  = new_prices[0]  if new_prices  else None
    cheapest_used = used_prices[0] if used_prices else None

    ref_price = part.get("reference_price", 0)
    sale_detected = False
    sale_message  = ""
    if cheapest_new and ref_price:
        discount = (ref_price - cheapest_new["price"]) / ref_price
        if discount >= 0.05:
            sale_detected = True
            sale_message  = f"🏷️ 参考価格より {int(discount * 100)}% 安い！"

    return {
        "part_id":       part["id"],
        "part_name":     f"{part['brand']} {part['model']}",
        "reference_price": ref_price,
        "new_prices":    new_prices,
        "used_prices":   used_prices,
        "cheapest_new":  cheapest_new,
        "cheapest_used": cheapest_used,
        "sale_detected": sale_detected,
        "sale_message":  sale_message,
        "search_links":  search_links,   # ← 常に返す
        "scrape_success": len(results) > 0,
    }


@router.get("/check-sales/{build_id}")
async def check_build_sales(build_id: int):
    conn = get_db()
    rows = conn.execute(
        """SELECT p.id, p.brand, p.model, p.reference_price
           FROM build_parts bp JOIN parts p ON bp.part_id=p.id
           WHERE bp.build_id=?""",
        (build_id,),
    ).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(404, "構成またはパーツが見つかりません")

    async def safe_price(part_id):
        try:
            return await get_prices(part_id)
        except Exception:
            return None

    results = await asyncio.gather(*[safe_price(r["id"]) for r in rows])
    sales = [r for r in results if r and r.get("sale_detected")]
    return {"sales": sales, "count": len(sales)}
