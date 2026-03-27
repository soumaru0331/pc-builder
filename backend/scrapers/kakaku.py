"""価格.com scraper (新品価格)"""
import re
import urllib.parse
from bs4 import BeautifulSoup
from scrapers.base import fetch_html, HEADERS
import httpx


async def search_kakaku(query: str, limit: int = 5) -> list[dict]:
    encoded = urllib.parse.quote(query)
    urls = [
        f"https://kakaku.com/search_results/?query={encoded}&act=Suggest",
        f"https://kakaku.com/search_results/?query={encoded}",
    ]

    for url in urls:
        try:
            results = await _scrape_kakaku(url, limit)
            if results:
                return results
        except Exception:
            continue

    return []


async def _scrape_kakaku(url: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(
        headers={**HEADERS, "Referer": "https://kakaku.com/"},
        follow_redirects=True,
        timeout=12,
    ) as client:
        r = await client.get(url)
        if r.status_code != 200:
            return []

    soup = BeautifulSoup(r.text, "lxml")
    results = []

    # Try multiple selector patterns (kakaku changes their HTML frequently)
    selectors = [
        (".p-result_item", ".p-result_item__title a", ".p-result_item__price, .p-result_item__priceArea"),
        (".itemUnit", ".itmTtlNmLink, .itmTtl a", ".priceValue, .price_value"),
        ("li.p-item_unit", ".p-item_unit__title a", ".p-item_unit__price"),
        ("[class*='resultItem'], [class*='result-item']", "a[href*='/item/']", "[class*='price']"),
    ]

    for item_sel, title_sel, price_sel in selectors:
        items = soup.select(item_sel)
        if not items:
            continue
        for item in items[:limit]:
            try:
                title_el = item.select_one(title_sel)
                price_el = item.select_one(price_sel)
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                price_text = price_el.get_text(strip=True) if price_el else ""
                price = _parse_price(price_text)
                href = title_el.get("href", "")
                if href and not href.startswith("http"):
                    href = "https://kakaku.com" + href
                if title and price:
                    results.append({
                        "source": "価格.com",
                        "title": title,
                        "price": price,
                        "url": href,
                        "is_used": False,
                    })
            except Exception:
                continue
        if results:
            break

    return results


def _parse_price(text: str) -> int:
    # カンマ区切りの数字を探す（例: "¥57,000" → 57000）
    m = re.search(r"[\d,]+", text)
    if not m:
        return 0
    try:
        v = int(m.group().replace(",", ""))
        return v if 1000 <= v <= 10_000_000 else 0
    except Exception:
        return 0
