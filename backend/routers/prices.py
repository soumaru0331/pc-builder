import json
import asyncio
import urllib.parse
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from database import get_db
from scrapers.kakaku import search_kakaku
from scrapers.mercari import search_mercari
from scrapers.yahooauction import search_yahoo_auction, search_yahoo_flea

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

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


def _save_price_history(conn, part_id: int, results: list[dict]):
    """スクレイプで取得した最安値を price_history に記録"""
    new_prices = [r for r in results if not r.get("is_used")]
    if new_prices:
        cheapest = min(new_prices, key=lambda x: x["price"])
        conn.execute(
            "INSERT INTO price_history (part_id, price, source) VALUES (?, ?, 'scrape')",
            (part_id, cheapest["price"])
        )
        conn.commit()


def _make_search_links(query: str) -> dict:
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
@limiter.limit("10/minute")
async def get_prices(request: Request, part_id: int, force_refresh: bool = False):
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

    # タイムアウト5秒に短縮
    async def safe(coro):
        try:
            return await asyncio.wait_for(coro, timeout=5)
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
        _save_price_history(conn, part_id, all_results)

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
            sale_message  = f"参考価格より {int(discount * 100)}% 安い！"

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
        "search_links":  search_links,
        "scrape_success": len(results) > 0,
    }


@router.get("/check-sales/{build_id}")
async def check_build_sales(request: Request, build_id: int):
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
            # check-sales はレートリミット対象外の内部呼び出し
            conn2 = get_db()
            part = dict(conn2.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone())
            query = f"{part['brand']} {part['name']}"
            search_links = _make_search_links(query)
            cached = _get_cached(conn2, part_id)
            conn2.close()
            if cached:
                return _format_results(cached, part, search_links)
            return None
        except Exception:
            return None

    results = await asyncio.gather(*[safe_price(r["id"]) for r in rows])
    sales = [r for r in results if r and r.get("sale_detected")]
    return {"sales": sales, "count": len(sales)}
