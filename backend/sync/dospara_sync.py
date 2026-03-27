"""ドスパラ(dospara.co.jp) 商品グリッドAPIから自動パーツ収集"""
import re
import asyncio
import httpx
from bs4 import BeautifulSoup

from sync.brands import detect_brand
from sync.spec_parser import (
    parse_cpu, parse_gpu, parse_motherboard, parse_memory,
    parse_storage, parse_psu, parse_case, parse_cooler,
    estimate_benchmark, estimate_tdp,
)

# カテゴリ → ドスパラ cgid コード
# Salesforce Commerce Cloud の Search-UpdateGrid API を利用
DOSPARA_CATEGORIES = {
    "gpu":         "BR31",   # グラフィックボード
    "cpu":         "BR11",   # CPU (Intel + AMD 両方含む大カテゴリ)
    "motherboard": "BR21",   # マザーボード
    "memory":      "BR12",   # メモリ
    "storage":     "BR115",  # SSD
    "storage_hdd": "BR13",   # HDD
    "psu":         "BR83",   # 電源ユニット
    "case":        "BR72",   # PCケース
    "cooler":      "BR95",   # CPUクーラー
}

_API_BASE = (
    "https://www.dospara.co.jp/on/demandware.store"
    "/Sites-dospara-Site/ja_JP/Search-UpdateGrid"
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.dospara.co.jp/",
    "X-Requested-With": "XMLHttpRequest",
}

_PAGE_SIZE = 24   # 1リクエストの件数

SPEC_PARSERS = {
    "cpu": parse_cpu, "gpu": parse_gpu, "motherboard": parse_motherboard,
    "memory": parse_memory, "storage": parse_storage, "psu": parse_psu,
    "case": parse_case, "cooler": parse_cooler,
}

# storage_hdd は DB カテゴリ名 "storage" へマッピング
_DB_CATEGORY = {"storage_hdd": "storage"}

_SKIP_KEYWORDS = {
    "gpu": ["Quadro", "Tesla", "FirePro", "Radeon Pro", "ノートPC", "ノート用",
            "ケーブル", "変換"],
    "cpu": ["Threadripper", "EPYC", "Xeon", "ノート用", "BGA", "Core 2",
            "Pentium D", "Pentium 4"],
    "memory": ["SO-DIMM", "ノートPC用", "ECC", "PS5", "PS4", "SDカード"],
    "storage": ["PS4", "PS5", "外付け", "ポータブル", "USBメモリ", "SDカード", "NAS用"],
    "storage_hdd": ["PS4", "PS5", "外付け", "ポータブル", "NAS用"],
    "psu": ["ノートPC", "アダプター", "UPS"],
    "case": ["スマートフォン", "スマホ", "タブレット", "ゲーム機"],
    "cooler": ["ノートPC", "スマホ", "ゲーム機"],
    "motherboard": ["サーバー"],
}


async def _fetch(cgid: str, start: int = 0, timeout: int = 15) -> str | None:
    params = {
        "cgid":  cgid,
        "srule": "08",          # 新着順
        "start": start,
        "sz":    _PAGE_SIZE,
    }
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            r = await client.get(_API_BASE, params=params)
            return r.text if r.status_code == 200 else None
    except Exception:
        return None


def _parse_page(html: str, category: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results = []
    db_cat = _DB_CATEGORY.get(category, category)

    # 商品コンテナ: .product-item
    items = (
        soup.select(".product-item") or
        soup.select("[class*='product-tile']") or
        soup.select("[class*='ProductItem']")
    )

    for item in items:
        # 商品名: .product-name または data-name 属性
        name_el = (
            item.select_one(".product-name") or
            item.select_one("[class*='name']") or
            item.select_one("a[href*='/IC']") or
            item.select_one("a[href*='/SBR']")
        )
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 5:
            continue

        # 価格: .product-price
        price_el = (
            item.select_one(".product-price") or
            item.select_one("[class*='price']") or
            item.find(string=re.compile(r"[\d,]+円"))
        )
        if hasattr(price_el, "get_text"):
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

        brand = detect_brand(name, db_cat) or "不明"
        parser = SPEC_PARSERS.get(db_cat, lambda x: {})
        specs = parser(name)
        benchmark = estimate_benchmark(db_cat, specs, name)
        tdp = estimate_tdp(db_cat, specs, name)
        specs.pop("_benchmark", None)
        specs.pop("_tdp", None)
        specs.pop("tdp_estimate", None)

        model = name[:80]
        clean = name
        if brand != "不明" and clean.upper().startswith(brand.upper()):
            clean = clean[len(brand):].lstrip(" -/")
        clean = clean[:100]

        results.append({
            "category": db_cat, "brand": brand, "name": clean,
            "model": model, "specs": specs, "tdp": tdp,
            "benchmark_score": benchmark, "reference_price": price,
            "release_year": None, "notes": "ドスパラ",
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


async def sync_dospara_category(
    category: str,
    max_pages: int = 20,
    existing_models: set[str] | None = None,
) -> list[dict]:
    """ドスパラから指定カテゴリのパーツを収集"""
    cgid = DOSPARA_CATEGORIES.get(category)
    if not cgid:
        return []

    all_parts: list[dict] = []
    seen_names: set[str] = set()
    consecutive_existing_pages = 0

    for page in range(max_pages):
        start = page * _PAGE_SIZE
        html = await _fetch(cgid, start)
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

        await asyncio.sleep(1.5)

    return all_parts
