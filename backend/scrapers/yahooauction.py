"""Yahoo!オークション scraper (中古価格)"""
import re
import urllib.parse
from bs4 import BeautifulSoup
from scrapers.base import fetch_html


async def search_yahoo_auction(query: str, limit: int = 5) -> list[dict]:
    """Search Yahoo Auction and return list of {title, price, url, is_used}"""
    encoded = urllib.parse.quote(query)
    url = f"https://auctions.yahoo.co.jp/search/search?p={encoded}&va={encoded}&exflg=1&b=1&n=20&s1=cbids&o1=d"
    html = await fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    for item in soup.select(".Product")[:limit]:
        try:
            title_el = item.select_one(".Product__title a, .Product__titleLink")
            price_el = item.select_one(".Product__priceValue, .u-fontSize18")
            link_el = item.select_one(".Product__title a, a.Product__titleLink")

            if not title_el or not price_el:
                continue

            title = title_el.get_text(strip=True)
            price = _parse_price(price_el.get_text(strip=True))
            href = link_el["href"] if link_el and link_el.get("href") else ""

            if price:
                results.append({
                    "source": "ヤフオク",
                    "title": title,
                    "price": price,
                    "url": href,
                    "is_used": True,
                })
        except Exception:
            continue

    return results[:limit]


async def search_yahoo_flea(query: str, limit: int = 5) -> list[dict]:
    """Search Yahoo フリマ (PayPay フリマ)"""
    encoded = urllib.parse.quote(query)
    url = f"https://paypayfleamarket.yahoo.co.jp/search/{encoded}"
    html = await fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    for item in soup.select("[class*='ItemCard'], [class*='item-card']")[:limit]:
        try:
            title_el = item.select_one("[class*='title'], [class*='name']")
            price_el = item.select_one("[class*='price']")
            link_el = item.select_one("a[href]")

            if not title_el or not price_el:
                continue

            title = title_el.get_text(strip=True)
            price = _parse_price(price_el.get_text(strip=True))
            href = link_el["href"] if link_el else ""

            if price:
                results.append({
                    "source": "PayPayフリマ",
                    "title": title,
                    "price": price,
                    "url": href,
                    "is_used": True,
                })
        except Exception:
            continue

    return results[:limit]


def _parse_price(text: str) -> int:
    nums = re.sub(r"[^\d]", "", text)
    return int(nums) if nums else 0
