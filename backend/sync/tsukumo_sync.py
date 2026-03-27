"""ツクモ(shop.tsukumo.co.jp) 商品一覧から自動パーツ収集"""
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

# カテゴリ → ツクモ検索キーワード
TSUKUMO_CATEGORIES = {
    "gpu":         "グラフィックボード RTX RX",
    "cpu":         "CPU プロセッサー Core Ryzen",
    "motherboard": "マザーボード LGA AM5 AM4",
    "memory":      "デスクトップ メモリ DDR5 DDR4",
    "storage":     "SSD M.2 NVMe SATA",
    "psu":         "電源ユニット ATX 80PLUS",
    "case":        "PCケース ATX ミドルタワー",
    "cooler":      "CPUクーラー サイドフロー",
}

_BASE_URL = "https://shop.tsukumo.co.jp/search/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Referer": "https://shop.tsukumo.co.jp/",
}

SPEC_PARSERS = {
    "cpu": parse_cpu, "gpu": parse_gpu, "motherboard": parse_motherboard,
    "memory": parse_memory, "storage": parse_storage, "psu": parse_psu,
    "case": parse_case, "cooler": parse_cooler,
}

_SKIP_KEYWORDS = {
    "gpu": ["ノートPC", "ノート用", "ケーブル", "変換", "Quadro", "Tesla", "FirePro"],
    "cpu": ["ノート用", "BGA", "Threadripper", "EPYC", "Xeon", "Core 2"],
    "memory": ["SO-DIMM", "ノートPC用", "PS5", "PS4", "SDカード", "microSD", "ECC"],
    "storage": ["PS5", "PS4", "外付け", "ポータブル", "USBメモリ", "SDカード", "NAS用"],
    "psu": ["ノートPC", "アダプター", "UPS"],
    "case": ["スマートフォン", "スマホ", "タブレット", "ゲーム機"],
    "cooler": ["ノートPC", "スマホ", "ゲーム機"],
    "motherboard": ["サーバー"],
}


async def _fetch(keyword: str, page: int = 1, timeout: int = 15) -> str | None:
    params = {
        "search_text": keyword,
        "page": page,
        "sort_id": "13",  # 新着順
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

    # ツクモ: /goods/{JANコード}/ へのリンクが商品名
    # 商品カードは div.item_box または li.item_list などに収まる
    goods_links = soup.select("a[href*='/goods/']")
    seen_hrefs: set[str] = set()

    for link in goods_links:
        href = link.get("href", "")
        name = link.get_text(strip=True)

        # 短すぎる・重複・ナビリンクをスキップ
        if not name or len(name) < 6:
            continue
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # 親要素から価格を探す
        parent = link.parent
        for _ in range(4):  # 最大4階層上まで探す
            if parent is None:
                break
            price_text = _find_price_in_element(parent)
            if price_text:
                break
            parent = parent.parent

        price = _parse_price(price_text if price_text else "")

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
            "release_year": None, "notes": "ツクモ",
        })

    return results


def _find_price_in_element(el) -> str:
    """要素内から ¥XX,XXX 形式の価格テキストを探す"""
    text = el.get_text(" ", strip=True)
    m = re.search(r"¥[\d,]+|[\d,]+円", text)
    return m.group() if m else ""


def _parse_price(text: str) -> int:
    m = re.search(r"[\d,]+", text.replace("，", ","))
    if not m:
        return 0
    try:
        v = int(m.group().replace(",", ""))
        return v if 1000 <= v <= 3_000_000 else 0
    except Exception:
        return 0


async def sync_tsukumo_category(
    category: str,
    max_pages: int = 10,
    existing_models: set[str] | None = None,
) -> list[dict]:
    """ツクモから指定カテゴリのパーツを収集"""
    keyword = TSUKUMO_CATEGORIES.get(category)
    if not keyword:
        return []

    all_parts: list[dict] = []
    seen_names: set[str] = set()
    consecutive_existing_pages = 0

    for page in range(1, max_pages + 1):
        html = await _fetch(keyword, page)
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
