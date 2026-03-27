"""Yahoo!ショッピング 検索ページから自動パーツ収集"""
import re
import asyncio
import urllib.parse
import httpx
from bs4 import BeautifulSoup

from sync.brands import detect_brand
from sync.spec_parser import (
    parse_cpu, parse_gpu, parse_motherboard, parse_memory,
    parse_storage, parse_psu, parse_case, parse_cooler,
    estimate_benchmark, estimate_tdp,
)

# カテゴリ → 検索キーワード
YAHOO_CATEGORIES = {
    "gpu":         "グラフィックボード RTX RX GPU",
    "cpu":         "CPU プロセッサー Core i Ryzen",
    "motherboard": "マザーボード LGA AM5 AM4 ATX",
    "memory":      "デスクトップ メモリ DDR5 DDR4 DIMM",
    "storage":     "SSD M.2 NVMe SATA 2.5インチ",
    "psu":         "電源ユニット 80PLUS ATX 650W 750W",
    "case":        "PCケース ATX ミドルタワー フルタワー",
    "cooler":      "CPUクーラー 空冷 サイドフロー トップフロー",
}

_BASE_URL = "https://shopping.yahoo.co.jp/search"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://shopping.yahoo.co.jp/",
}

SPEC_PARSERS = {
    "cpu": parse_cpu, "gpu": parse_gpu, "motherboard": parse_motherboard,
    "memory": parse_memory, "storage": parse_storage, "psu": parse_psu,
    "case": parse_case, "cooler": parse_cooler,
}

_SKIP_KEYWORDS = {
    "gpu": ["ノートPC", "ノート用", "ケーブル", "変換", "アダプター", "ゲームソフト",
            "Quadro", "Tesla", "FirePro", "Radeon Pro"],
    "cpu": ["ノート用", "モバイル版", "BGA", "Threadripper", "EPYC", "Xeon", "Core 2",
            "Pentium D", "Pentium 4"],
    "memory": ["SO-DIMM", "ノートPC用", "PS5", "PS4", "Nintendo", "スマホ", "SDカード",
               "microSD", "ECC", "サーバー"],
    "storage": ["PS5", "PS4", "Nintendo", "外付け", "ポータブル", "USBメモリ", "SDカード",
                "microSD", "NAS用", "監視"],
    "psu": ["ノートPC", "アダプター", "ケーブル", "UPS"],
    "case": ["スマートフォン", "スマホ", "タブレット", "ゲーム機", "キーボード"],
    "cooler": ["ノートPC", "スマホ", "タブレット", "ゲーム機"],
    "motherboard": ["ノートPC", "サーバー"],
}


async def _fetch(keyword: str, start: int = 1, timeout: int = 15) -> str | None:
    params = {
        "p": keyword,
        "sort": "sold",       # 売れ筋順
        "minprice": "3000",
        "b": start,           # 開始位置(1, 31, 61...)
    }
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            r = await client.get(_BASE_URL, params=params)
            return r.text if r.status_code == 200 else None
    except Exception:
        return None


def _parse_page(html: str, category: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results = []

    # Yahoo Shopping の商品カードコンテナ
    # class に "ItemCard" を含む div
    items = soup.find_all("div", class_=lambda c: c and "ItemCard" in c)
    if not items:
        # フォールバック: li.Product, .srchListItem など
        items = (
            soup.select("li.Product") or
            soup.select(".srchListItem") or
            soup.select("[class*='Item']")
        )

    for item in items:
        # 商品名リンク
        link = (
            item.select_one("a[href*='store.shopping.yahoo']") or
            item.select_one("a[href*='shopping.yahoo']") or
            item.find("a")
        )
        if not link:
            continue

        name = link.get_text(strip=True)
        if not name or len(name) < 5:
            # aタグの中のテキストが空の場合は子要素を探す
            title_el = item.select_one("[class*='title']") or item.select_one("[class*='Title']")
            if title_el:
                name = title_el.get_text(strip=True)
        if not name or len(name) < 5:
            continue

        # 価格（¥XX,XXX 形式）
        price_el = (
            item.select_one("[class*='price']") or
            item.select_one("[class*='Price']") or
            item.find(string=re.compile(r"[\d,]+円"))
        )
        if hasattr(price_el, 'get_text'):
            price_text = price_el.get_text(strip=True)
        else:
            price_text = str(price_el) if price_el else ""
        price = _parse_price(price_text)

        # スキップチェック
        name_lower = name.lower()
        skip = False
        for kw in _SKIP_KEYWORDS.get(category, []):
            if kw.lower() in name_lower:
                skip = True
                break
        if skip:
            continue

        brand = detect_brand(name, category) or "不明"
        parser = SPEC_PARSERS.get(category, lambda x: {})
        specs = parser(name)
        benchmark = estimate_benchmark(category, specs, name)
        tdp = estimate_tdp(category, specs, name)
        specs.pop("_benchmark", None)
        specs.pop("_tdp", None)
        specs.pop("tdp_estimate", None)

        model = name[:80]
        clean = name
        if brand != "不明" and clean.upper().startswith(brand.upper()):
            clean = clean[len(brand):].lstrip(" -/")
        clean = clean[:100]

        results.append({
            "category": category, "brand": brand, "name": clean,
            "model": model, "specs": specs, "tdp": tdp,
            "benchmark_score": benchmark, "reference_price": price,
            "release_year": None, "notes": "Yahoo",
        })

    return results


def _parse_price(text: str) -> int:
    m = re.search(r"[\d,]+", text.replace("，", ","))
    if not m:
        return 0
    try:
        v = int(m.group().replace(",", ""))
        return v if 1000 <= v <= 3_000_000 else 0
    except Exception:
        return 0


async def sync_yahoo_category(
    category: str,
    max_pages: int = 10,
    existing_models: set[str] | None = None,
) -> list[dict]:
    """Yahoo!ショッピングから指定カテゴリのパーツを収集"""
    keyword = YAHOO_CATEGORIES.get(category)
    if not keyword:
        return []

    all_parts: list[dict] = []
    seen_names: set[str] = set()
    consecutive_existing_pages = 0
    items_per_page = 30

    for page in range(max_pages):
        start = page * items_per_page + 1
        html = await _fetch(keyword, start)
        if not html:
            break

        parts = _parse_page(html, category)
        if not parts:
            break

        new_on_page = 0
        for p in parts:
            key = f"{p['brand']}|{p['name'][:50]}"
            if key in seen_names:
                continue
            seen_names.add(key)

            if existing_models is not None:
                db_key = f"{p['brand']}|{p['model'][:80]}"
                if db_key in existing_models:
                    continue

            all_parts.append(p)
            new_on_page += 1

        if existing_models is not None and new_on_page == 0:
            consecutive_existing_pages += 1
            if consecutive_existing_pages >= 5:
                break
        else:
            consecutive_existing_pages = 0

        await asyncio.sleep(2.0)

    return all_parts
