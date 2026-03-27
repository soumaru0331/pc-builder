"""Mercari scraper (中古価格) — tries multiple approaches"""
import re
import json
import urllib.parse
from bs4 import BeautifulSoup
from scrapers.base import fetch_html, fetch_json, HEADERS
import httpx


async def search_mercari(query: str, limit: int = 5) -> list[dict]:
    # Try unofficial search API first
    results = await _try_mercari_api(query, limit)
    if results:
        return results

    # Fallback: scrape search page (limited due to SPA)
    results = await _try_mercari_scrape(query, limit)
    return results


async def _try_mercari_api(query: str, limit: int) -> list[dict]:
    encoded = urllib.parse.quote(query)
    api_url = (
        f"https://api.mercari.jp/v2/entities:search"
    )
    try:
        async with httpx.AsyncClient(
            headers={
                **HEADERS,
                "X-Platform": "web",
                "DPoP": "eyJ0eXAiOiJkcG9wK2p3dCIsImFsZyI6IkVTMjU2IiwiandrIjp7Imt0eSI6IkVDIiwiY3J2IjoiUC0yNTYiLCJ4IjoiNjIiLCJ5IjoiNjIifX0",
            },
            follow_redirects=True,
            timeout=10,
        ) as client:
            r = await client.post(api_url, json={
                "pageToken": "",
                "searchSessionId": "",
                "indexRouting": "INDEX_ROUTING_UNSPECIFIED",
                "thumbnailTypes": [],
                "searchCondition": {
                    "keyword": query,
                    "excludeKeyword": "",
                    "sort": "SORT_SCORE",
                    "order": "ORDER_DESC",
                    "status": ["STATUS_ON_SALE"],
                    "sizeId": [],
                    "categoryId": [],
                    "brandId": [],
                    "sellerId": [],
                    "priceMin": 0,
                    "priceMax": 0,
                    "itemConditionId": [],
                    "shippingPayerId": [],
                    "shippingFromArea": [],
                    "shippingMethod": [],
                    "colorId": [],
                    "hasCoupon": False,
                    "attributes": [],
                    "itemTypes": [],
                    "skuIds": [],
                    "shopIds": [],
                },
                "defaultDatasets": ["DATASET_TYPE_MERCARI", "DATASET_TYPE_BEYOND"],
                "serviceFrom": "suruga",
                "withItemBrand": True,
                "withItemSize": False,
                "withItemPromotions": True,
                "withItemSizes": False,
                "useDynamicAttribute": False,
                "withSuggestTop": False,
            })
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])
                results = []
                for item in items[:limit]:
                    price = item.get("price", 0)
                    name = item.get("name", "")
                    item_id = item.get("id", "")
                    if price and name:
                        results.append({
                            "source": "メルカリ",
                            "title": name,
                            "price": int(price),
                            "url": f"https://jp.mercari.com/item/{item_id}",
                            "is_used": True,
                        })
                return results
    except Exception:
        pass
    return []


async def _try_mercari_scrape(query: str, limit: int) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://jp.mercari.com/search?keyword={encoded}&status=on_sale"
    html = await fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    # Try JSON-LD embedded data
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else data.get("itemListElement", [])
            for item in items[:limit]:
                if isinstance(item, dict):
                    price = item.get("offers", {}).get("price") or item.get("price", 0)
                    name = item.get("name", "") or item.get("item", {}).get("name", "")
                    item_url = item.get("url", "") or item.get("item", {}).get("url", "")
                    if price and name:
                        results.append({
                            "source": "メルカリ",
                            "title": name,
                            "price": int(price),
                            "url": item_url,
                            "is_used": True,
                        })
        except Exception:
            continue

    # Try Next.js __NEXT_DATA__
    if not results:
        script = soup.find("script", id="__NEXT_DATA__")
        if script:
            try:
                data = json.loads(script.string)
                items = (data.get("props", {}).get("pageProps", {})
                         .get("initialState", {}).get("search", {})
                         .get("items", []))
                for item in items[:limit]:
                    price = item.get("price", 0)
                    name = item.get("name", "")
                    item_id = item.get("id", "")
                    if price and name:
                        results.append({
                            "source": "メルカリ",
                            "title": name,
                            "price": int(price),
                            "url": f"https://jp.mercari.com/item/{item_id}",
                            "is_used": True,
                        })
            except Exception:
                pass

    return results[:limit]


def _parse_price(text: str) -> int:
    m = re.search(r"[\d,]+", text)
    if not m:
        return 0
    try:
        v = int(m.group().replace(",", ""))
        return v if 100 <= v <= 10_000_000 else 0
    except Exception:
        return 0
