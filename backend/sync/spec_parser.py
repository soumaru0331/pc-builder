"""商品名・スペック文字列からパーツ情報を自動抽出"""
import re

# ─── CPU ────────────────────────────────────────────────────────────────────

# モデル番号 → ソケット / メモリ規格 の対応表
_CPU_SOCKET_RULES: list[tuple] = [
    # Intel Arrow Lake
    (r"Core Ultra [579]\s*[23]\d{2}",                  "LGA1851", ["DDR5"]),
    # Intel Raptor Lake Refresh / Raptor Lake (12th-14th)
    (r"Core i\d-1[234]\d{3}[KF]{0,2}[SE]?",            "LGA1700", ["DDR4", "DDR5"]),
    (r"Core i\d-13\d{3}[KF]{0,2}",                     "LGA1700", ["DDR4", "DDR5"]),
    (r"Core i\d-12\d{3}[KF]{0,2}",                     "LGA1700", ["DDR4", "DDR5"]),
    # Intel Rocket Lake / Comet Lake (10th-11th)
    (r"Core i\d-1[01]\d{3}[KF]{0,2}",                  "LGA1200", ["DDR4"]),
    # Intel Coffee Lake (8th-9th)
    (r"Core i\d-[89]\d{3}[KF]{0,2}",                   "LGA1151", ["DDR4"]),
    # Intel Kaby/Skylake (6th-7th)
    (r"Core i\d-[67]\d{3}[KF]{0,2}",                   "LGA1151", ["DDR4"]),
    # AMD Ryzen 9000 / 7000 → AM5
    (r"Ryzen \d+ [79][79]\d{2}X?3?D?",                 "AM5",     ["DDR5"]),
    (r"Ryzen \d+ [579][57]\d{2}[XF]?3?D?",             "AM5",     ["DDR5"]),
    # AMD Ryzen 5000 / 3000 / 2000 / 1000 → AM4
    (r"Ryzen \d+ [579][15]\d{2}X?3?D?",                "AM4",     ["DDR4"]),
    (r"Ryzen \d+ [579][0369]\d{2}X?3?D?",              "AM4",     ["DDR4"]),
    # AMD FX → AM3+
    (r"FX-\d{4}",                                       "AM3+",    ["DDR3"]),
]

def parse_cpu(name: str) -> dict:
    specs = {}
    n = name.upper()

    for pattern, socket, mem_types in _CPU_SOCKET_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            specs["socket"]      = socket
            specs["memory_type"] = mem_types
            break

    # コア数・スレッド数を名前から推定（スペック文字列があれば）
    m = re.search(r"(\d+)コア|(\d+)-Core", name, re.IGNORECASE)
    if m:
        specs["cores"] = int(m.group(1) or m.group(2))

    # TDP推定
    specs.setdefault("tdp_estimate", _estimate_cpu_tdp(name))
    return specs


def _estimate_cpu_tdp(name: str) -> int:
    n = name.lower()
    if any(x in n for x in ["i9", "ryzen 9", "threadripper", "fx-9"]):
        return 125
    if any(x in n for x in ["i7", "ryzen 7"]):
        return 105
    if any(x in n for x in ["i5", "ryzen 5"]):
        return 65
    if any(x in n for x in ["i3", "ryzen 3"]):
        return 58
    return 65


# ─── GPU ────────────────────────────────────────────────────────────────────

# GPU チップ名 → {chip_vendor, benchmark_approx, tdp_approx}
_GPU_CHIPS: list[tuple] = [
    # NVIDIA RTX 40 series
    ("RTX 4090",         "NVIDIA", 25000, 450),
    ("RTX 4080 SUPER",   "NVIDIA", 21000, 320),
    ("RTX 4080",         "NVIDIA", 20000, 320),
    ("RTX 4070 TI SUPER","NVIDIA", 18000, 285),
    ("RTX 4070 TI",      "NVIDIA", 16500, 285),
    ("RTX 4070 SUPER",   "NVIDIA", 15000, 220),
    ("RTX 4070",         "NVIDIA", 13500, 200),
    ("RTX 4060 TI",      "NVIDIA", 10500, 165),
    ("RTX 4060",         "NVIDIA",  9000, 115),
    ("RTX 4050",         "NVIDIA",  7000,  70),
    # NVIDIA RTX 30 series
    ("RTX 3090 TI",      "NVIDIA", 19000, 450),
    ("RTX 3090",         "NVIDIA", 17000, 350),
    ("RTX 3080 TI",      "NVIDIA", 15500, 350),
    ("RTX 3080",         "NVIDIA", 14500, 320),
    ("RTX 3070 TI",      "NVIDIA", 12000, 290),
    ("RTX 3070",         "NVIDIA", 11500, 220),
    ("RTX 3060 TI",      "NVIDIA", 10000, 200),
    ("RTX 3060",         "NVIDIA",  8000, 170),
    ("RTX 3050",         "NVIDIA",  6000, 130),
    # NVIDIA RTX 20 series
    ("RTX 2080 TI",      "NVIDIA", 11000, 250),
    ("RTX 2080 SUPER",   "NVIDIA",  9500, 250),
    ("RTX 2080",         "NVIDIA",  9000, 215),
    ("RTX 2070 SUPER",   "NVIDIA",  8500, 215),
    ("RTX 2070",         "NVIDIA",  8000, 175),
    ("RTX 2060 SUPER",   "NVIDIA",  7200, 175),
    ("RTX 2060",         "NVIDIA",  6000, 160),
    # NVIDIA GTX 16 series
    ("GTX 1660 TI",      "NVIDIA",  5800, 120),
    ("GTX 1660 SUPER",   "NVIDIA",  5500, 125),
    ("GTX 1660",         "NVIDIA",  5000, 120),
    ("GTX 1650 SUPER",   "NVIDIA",  4500, 100),
    ("GTX 1650",         "NVIDIA",  3500,  75),
    # NVIDIA GTX 10 series
    ("GTX 1080 TI",      "NVIDIA",  8000, 250),
    ("GTX 1080",         "NVIDIA",  6200, 180),
    ("GTX 1070 TI",      "NVIDIA",  5500, 180),
    ("GTX 1070",         "NVIDIA",  5000, 150),
    ("GTX 1060",         "NVIDIA",  4000, 120),
    ("GTX 1050 TI",      "NVIDIA",  2800,  75),
    ("GTX 1050",         "NVIDIA",  2000,  75),
    # AMD RX 7000 series
    ("RX 7900 XTX",      "AMD",    22000, 355),
    ("RX 7900 XT",       "AMD",    20000, 315),
    ("RX 7900 GRE",      "AMD",    16000, 260),
    ("RX 7800 XT",       "AMD",    13500, 263),
    ("RX 7700 XT",       "AMD",    11500, 245),
    ("RX 7600 XT",       "AMD",    10000, 190),
    ("RX 7600",          "AMD",     8500, 165),
    ("RX 7500",          "AMD",     6000, 100),
    # AMD RX 6000 series
    ("RX 6950 XT",       "AMD",    16500, 335),
    ("RX 6900 XT",       "AMD",    15500, 300),
    ("RX 6800 XT",       "AMD",    14000, 300),
    ("RX 6800",          "AMD",    12500, 250),
    ("RX 6750 XT",       "AMD",    11500, 250),
    ("RX 6700 XT",       "AMD",    10500, 230),
    ("RX 6700",          "AMD",     9500, 220),
    ("RX 6650 XT",       "AMD",     9000, 180),
    ("RX 6600 XT",       "AMD",     8200, 160),
    ("RX 6600",          "AMD",     7500, 132),
    ("RX 6500 XT",       "AMD",     4500,  107),
    # AMD RX 5000 series
    ("RX 5700 XT",       "AMD",     7500, 225),
    ("RX 5700",          "AMD",     6800, 180),
    ("RX 5600 XT",       "AMD",     6200, 150),
    ("RX 5500 XT",       "AMD",     4500, 130),
    # AMD older
    ("RX 590",           "AMD",     4000, 225),
    ("RX 580",           "AMD",     3800, 185),
    ("RX 570",           "AMD",     3200, 150),
    # Intel Arc
    ("ARC A770",         "Intel",   9000, 225),
    ("ARC A750",         "Intel",   7500, 225),
    ("ARC A580",         "Intel",   6800, 185),
    ("ARC A380",         "Intel",   3000,  75),
]

def parse_gpu(name: str) -> dict:
    specs = {}
    n = name.upper()

    for chip, vendor, score, tdp in _GPU_CHIPS:
        if chip in n:
            specs["gpu_chip"]    = chip.title()
            specs["chip_vendor"] = vendor
            specs["_benchmark"]  = score
            specs["_tdp"]        = tdp
            break

    # VRAM
    m = re.search(r"(\d+)\s*GB", name, re.IGNORECASE)
    if m:
        specs["vram"] = int(m.group(1))

    # PCIe バージョン推定
    chip = specs.get("gpu_chip", "")
    if any(x in chip for x in ["40", "30", "RX 6", "RX 7", "Arc"]):
        specs["pcie_version"] = "4.0"
    else:
        specs["pcie_version"] = "3.0"

    return specs


# ─── Motherboard ─────────────────────────────────────────────────────────────

_MB_CHIPSET_RULES: list[tuple] = [
    # Intel Arrow Lake
    (r"Z890",  "LGA1851", ["DDR5"]),
    (r"B860",  "LGA1851", ["DDR5"]),
    (r"H870",  "LGA1851", ["DDR5"]),
    # Intel Raptor Lake
    (r"Z790",  "LGA1700", ["DDR5"]),
    (r"Z690",  "LGA1700", ["DDR4", "DDR5"]),
    (r"B760",  "LGA1700", ["DDR4", "DDR5"]),
    (r"H770",  "LGA1700", ["DDR4", "DDR5"]),
    (r"B660",  "LGA1700", ["DDR4", "DDR5"]),
    (r"H670",  "LGA1700", ["DDR4"]),
    (r"H610",  "LGA1700", ["DDR4"]),
    # Intel older
    (r"Z590|H570|B560",  "LGA1200", ["DDR4"]),
    (r"Z490|H470|B460",  "LGA1200", ["DDR4"]),
    (r"Z390|H370|B365|B360", "LGA1151", ["DDR4"]),
    (r"Z370|H310",       "LGA1151", ["DDR4"]),
    (r"Z270|H270|B250",  "LGA1151", ["DDR4"]),
    # AMD AM5
    (r"X670E", "AM5",    ["DDR5"]),
    (r"X670",  "AM5",    ["DDR5"]),
    (r"B650E", "AM5",    ["DDR5"]),
    (r"B650",  "AM5",    ["DDR5"]),
    (r"A620",  "AM5",    ["DDR5"]),
    # AMD AM4
    (r"X570",  "AM4",    ["DDR4"]),
    (r"X470",  "AM4",    ["DDR4"]),
    (r"B550",  "AM4",    ["DDR4"]),
    (r"B450",  "AM4",    ["DDR4"]),
    (r"B350",  "AM4",    ["DDR4"]),
    (r"A520",  "AM4",    ["DDR4"]),
    (r"A320",  "AM4",    ["DDR4"]),
    # AMD AM3+
    (r"990FX|970|990X",  "AM3+",   ["DDR3"]),
]

_FORM_FACTORS = [
    ("Mini-ITX", "mITX"), ("MiniITX", "mITX"), ("mITX", "mITX"),
    ("Micro-ATX", "mATX"), ("MicroATX", "mATX"), ("mATX", "mATX"), ("M-ATX", "mATX"),
    ("E-ATX", "eATX"), ("EATX", "eATX"),
    ("ATX", "ATX"),
]

def parse_motherboard(name: str) -> dict:
    specs = {}
    n = name.upper()

    for pattern, socket, mem_types in _MB_CHIPSET_RULES:
        if re.search(pattern, n):
            specs["socket"]      = socket
            specs["chipset"]     = re.search(pattern, n).group()
            specs["memory_type"] = mem_types
            break

    for label, ff in _FORM_FACTORS:
        if label.upper() in n:
            specs["form_factor"] = ff
            break
    specs.setdefault("form_factor", "ATX")

    return specs


# ─── Memory ──────────────────────────────────────────────────────────────────

def parse_memory(name: str) -> dict:
    specs = {}
    n = name.upper()

    # DDR世代
    for ddr in ["DDR5", "DDR4", "DDR3", "DDR2"]:
        if ddr in n:
            specs["memory_type"] = ddr
            break

    # 速度
    m = re.search(r"(?:DDR\d-?|PC\d-?)(\d{4,5})", n)
    if m:
        val = int(m.group(1))
        # PC規格をMHz換算
        if val > 10000:
            val = val // 8
        specs["speed"] = val

    # 容量
    m = re.search(r"(\d+)\s*GB", name, re.IGNORECASE)
    if m:
        specs["capacity"] = int(m.group(1))

    # モジュール数
    for x2 in ["2x", "×2", "Kit of 2", "2枚組", "デュアル", "Dual"]:
        if x2.lower() in name.lower():
            specs["modules"] = 2
            break
    specs.setdefault("modules", 1)

    return specs


# ─── Storage ─────────────────────────────────────────────────────────────────

def parse_storage(name: str) -> dict:
    specs = {}
    n = name.upper()

    # タイプ
    if "NVME" in n or "M.2" in n or "SSD" in n:
        specs["type"] = "SSD"
        if "PCIE 5" in n or "GEN5" in n or "GEN 5" in n:
            specs["interface"] = "M.2 NVMe PCIe 5.0"
        elif "PCIE 4" in n or "GEN4" in n or "GEN 4" in n:
            specs["interface"] = "M.2 NVMe PCIe 4.0"
        elif "PCIE 3" in n or "GEN3" in n or "GEN 3" in n:
            specs["interface"] = "M.2 NVMe PCIe 3.0"
        elif "SATA" in n:
            specs["interface"] = "SATA"
        elif "M.2" in n:
            specs["interface"] = "M.2 NVMe PCIe 4.0"  # デフォルト
        else:
            specs["interface"] = "SATA"
    elif "HDD" in n or "ハードディスク" in n:
        specs["type"] = "HDD"
        specs["interface"] = "SATA"
        if "7200" in n:
            specs["rpm"] = 7200
        else:
            specs["rpm"] = 5400
    else:
        specs["type"] = "SSD"
        specs["interface"] = "SATA"

    # 容量 (TB / GB) — 標準表記
    m = re.search(r"(\d+(?:\.\d+)?)\s*TB", name, re.IGNORECASE)
    if m:
        specs["capacity"] = int(float(m.group(1)) * 1000)
    else:
        m = re.search(r"(\d+)\s*GB", name, re.IGNORECASE)
        if m:
            specs["capacity"] = int(m.group(1))
    # モデル番号埋め込み容量フォールバック（優先度順）
    if "capacity" not in specs:
        # Samsung MZ系: "1T0B", "2T0B" → xTB
        m = re.search(r"(\d+)T0[BGJNR]", name, re.IGNORECASE)
        if m:
            specs["capacity"] = int(m.group(1)) * 1000
    if "capacity" not in specs:
        # SanDisk/SDSSDE系: "1T00", "2T00" → xTB
        m = re.search(r"[-_](\d+)T0{2}", name, re.IGNORECASE)
        if m:
            specs["capacity"] = int(m.group(1)) * 1000
    if "capacity" not in specs:
        # KIOXIA/ELECOM SSD-CK/PG/SCH: "1.0", "2.0" → float TB
        m = re.search(r"SSD-[A-Z]{2}(\d+\.\d+)[A-Z]", name, re.IGNORECASE)
        if m:
            specs["capacity"] = int(float(m.group(1)) * 1000)
    if "capacity" not in specs:
        # WD WDS100T→1TB, WDS200T→2TB, WDS400T→4TB
        m = re.search(r"WDS?(\d{3})T", name, re.IGNORECASE)
        if m:
            specs["capacity"] = int(m.group(1)) * 10
    if "capacity" not in specs:
        # Crucial CT1000→1TB, CT500→500GB, CT240→240GB
        m = re.search(r"CT(\d{3,4})[A-Z]", name, re.IGNORECASE)
        if m:
            v = int(m.group(1))
            if v >= 120:
                specs["capacity"] = v if v < 500 else v  # 1000=1TB, 500=500GB, 240=240GB
    if "capacity" not in specs:
        # AGI系: "AGI1T0" → 1TB
        m = re.search(r"AGI(\d+)T0", name, re.IGNORECASE)
        if m:
            specs["capacity"] = int(m.group(1)) * 1000
    if "capacity" not in specs:
        # 汎用: "-NxTCS", "-512GCS" などモデル末尾
        m = re.search(r"[-_/](\d+\.?\d*)T[A-Z]", name, re.IGNORECASE)
        if m:
            specs["capacity"] = int(float(m.group(1)) * 1000)
    if "capacity" not in specs:
        m = re.search(r"[-_/](\d{3,4})G[A-Z]", name, re.IGNORECASE)
        if m:
            v = int(m.group(1))
            if v >= 120:
                specs["capacity"] = v

    return specs


# ─── PSU ─────────────────────────────────────────────────────────────────────

def parse_psu(name: str) -> dict:
    specs = {}
    n = name.upper()

    # ワット数: 複数パターンを優先度順に試みる
    def _try_watt(pattern, s=name):
        m = re.search(pattern, s, re.IGNORECASE)
        if m:
            v = int(m.group(1))
            if 300 <= v <= 2000:
                return v
        return None
    # 1) 明示的 W 表記: "850W", "1000 W"
    specs_w = (
        _try_watt(r"(\d{3,4})\s*W")
        # 2) モデル末尾 Gold/Plat/Titan/Bronze: "1000G", "850P", "750T"
        or _try_watt(r"[-_](\d{3,4})[GPTB](?:[-_ ]|$|\b)")
        or _try_watt(r"(\d{3,4})[GPTB](?:[-_ ]|$)")
        # 3) ダッシュ囲み: "SST-SX700-PT" → "700", "GX-850"
        or _try_watt(r"[-_](\d{3,4})[-_]")
        or _try_watt(r"[A-Z]X?[-_](\d{3,4})")
        # 4) スペース囲みの単独数字: "ATLAS 750 CGR"
        or _try_watt(r"(?:^|\s)(\d{3,4})(?:\s|$)")
        # 5) モデル埋め込み: "HX1000i", "SX700", "RM1000x"
        or _try_watt(r"[A-Z]{1,3}(\d{3,4})[iGxX \-]")
    )
    if specs_w:
        specs["wattage"] = specs_w

    # 効率
    for eff in ["80+ Titanium", "80+ Platinum", "80+ Gold", "80+ Silver", "80+ Bronze", "80+ White", "80+"]:
        if eff.upper() in n:
            specs["efficiency"] = eff
            break
    specs.setdefault("efficiency", "80+")

    # モジュラー
    if "FULL" in n or "フルモジュラー" in n:
        specs["modular"] = "Full"
    elif "SEMI" in n or "セミ" in n:
        specs["modular"] = "Semi"
    else:
        specs["modular"] = "Non"

    specs["form_factor"] = "ATX"
    return specs


# ─── Case ─────────────────────────────────────────────────────────────────────

def parse_case(name: str) -> dict:
    specs = {"form_factors": ["ATX", "mATX"], "max_gpu_length": 360, "max_cpu_cooler_height": 165}
    n = name.upper()

    if "MINI-ITX" in n or "MINIITX" in n or "M-ITX" in n:
        specs["form_factors"] = ["mITX"]
        specs["max_gpu_length"] = 320
        specs["max_cpu_cooler_height"] = 140
    elif "MICRO" in n or "M-ATX" in n or "MATX" in n:
        specs["form_factors"] = ["mATX", "mITX"]
    elif "E-ATX" in n or "EATX" in n:
        specs["form_factors"] = ["eATX", "ATX", "mATX", "mITX"]
        specs["max_gpu_length"] = 420
        specs["max_cpu_cooler_height"] = 185
    elif "FULL" in n or "フルタワー" in n:
        specs["form_factors"] = ["eATX", "ATX", "mATX", "mITX"]
        specs["max_gpu_length"] = 450
        specs["max_cpu_cooler_height"] = 200

    return specs


# ─── Cooler ──────────────────────────────────────────────────────────────────

_COMMON_SOCKETS = ["LGA1851", "LGA1700", "LGA1200", "LGA1151", "AM5", "AM4", "AM3+"]

def parse_cooler(name: str) -> dict:
    specs = {"sockets": _COMMON_SOCKETS, "type": "Air", "max_tdp": 150}
    n = name.upper()

    # AIO判定
    aio_match = re.search(r"(\d{3})\s*MM|(\d{3})\s*AIO", n)
    if aio_match or "AIO" in n or "液冷" in n or "水冷" in n:
        specs["type"] = "AIO"
        size = int(aio_match.group(1) or aio_match.group(2)) if aio_match else 240
        specs["aio_size"] = size
        specs["max_tdp"] = 350 if size >= 360 else 280
        specs["height"] = 0
    else:
        # 空冷
        specs["type"] = "Air"
        m = re.search(r"(\d{3})\s*MM", n)
        specs["height"] = 155
        specs["max_tdp"] = 200
        # デュアルタワー系は高TDP
        if any(x in n for x in ["DUO", "DUAL", "D15", "D14", "PRO4"]):
            specs["max_tdp"] = 250
            specs["height"] = 162

    return specs


# ─── ベンチマーク / TDP 推定 ─────────────────────────────────────────────────

_CPU_SCORE_TABLE: list[tuple[str, int]] = [
    # AMD Ryzen 9000 series
    ("9950X3D",  3400), ("9950X",   3000), ("9900X3D",  3100),
    ("9850X3D",  2600), ("9800X3D", 2300), ("9700X",    1900),
    ("9600X",    1700), ("9600",    1600), ("9500F",    1400),
    # AMD Ryzen 7000 series
    ("7950X3D",  3200), ("7950X",   2900), ("7900X3D",  2700),
    ("7900X",    2500), ("7900",    2400), ("7800X3D",  2200),
    ("7700X",    1900), ("7700",    1800), ("7600X",    1700),
    ("7600",     1600), ("7500F",   1400),
    # AMD Ryzen 8000 series (Hawk Point APU)
    ("8700G",    1800), ("8700F",   1700), ("8600G",    1500),
    ("8500G",    1200), ("8400F",   1100),
    # AMD Ryzen 5000 series
    ("5950X",    2100), ("5900X",   2000), ("5800X3D",  1900),
    ("5800X",    1700), ("5700X3D", 1700), ("5700X",    1600),
    ("5700G",    1500), ("5600X",   1400), ("5600G",    1300),
    ("5600",     1300), ("5500",    1100), ("5300G",     900),
    # AMD Ryzen 3000 series
    ("3950X",    1800), ("3900XT",  1500), ("3900X",    1400),
    ("3800XT",   1300), ("3800X",   1200), ("3700X",    1100),
    ("3600XT",   1050), ("3600X",   1000), ("3600",      950),
    ("3500X",     850), ("3300X",    800), ("3100",      700),
    # AMD Ryzen 2000 / 1000
    ("2700X",     900), ("2700",     850), ("1800X",     700),
    ("1700X",     650), ("1600X",    600), ("1600",      580),
    # Intel Core Ultra (Arrow Lake)
    ("Ultra 9 285K",  3100), ("Ultra 7 265K",  2600),
    ("Ultra 7 265KF", 2600), ("Ultra 5 245K",  2100),
    ("Ultra 5 245KF", 2100), ("Ultra 5 235",   1800),
    # Intel 14th gen
    ("i9-14900KS", 2900), ("i9-14900K",  2800), ("i9-14900KF", 2800),
    ("i9-14900F",  2700), ("i9-14900",   2700),
    ("i7-14700K",  2400), ("i7-14700KF", 2400), ("i7-14700F",  2300),
    ("i7-14700",   2200),
    ("i5-14600K",  2000), ("i5-14600KF", 2000),
    ("i5-14500",   1800), ("i5-14400F",  1700), ("i5-14400",   1700),
    ("i3-14100F",  1100), ("i3-14100",   1100),
    # Intel 13th gen
    ("i9-13900KS", 2900), ("i9-13900K",  2750), ("i9-13900KF", 2750),
    ("i9-13900F",  2600), ("i9-13900",   2600),
    ("i7-13700K",  2300), ("i7-13700KF", 2300), ("i7-13700F",  2200),
    ("i7-13700",   2200),
    ("i5-13600K",  1900), ("i5-13600KF", 1900),
    ("i5-13500",   1700), ("i5-13400F",  1600), ("i5-13400",   1600),
    ("i3-13100F",   700), ("i3-13100",    750),
    # Intel 12th gen
    ("i9-12900KS", 2500), ("i9-12900K",  2400), ("i9-12900KF", 2400),
    ("i9-12900F",  2300), ("i9-12900",   2300),
    ("i7-12700K",  2100), ("i7-12700KF", 2100), ("i7-12700F",  2000),
    ("i7-12700",   2000),
    ("i5-12600K",  1700), ("i5-12600KF", 1700),
    ("i5-12500",   1500), ("i5-12400F",  1400), ("i5-12400",   1400),
    ("i3-12100F",   900), ("i3-12100",    950),
    # Intel 11th gen
    ("i9-11900K",  1600), ("i9-11900KF", 1600), ("i9-11900",   1500),
    ("i7-11700K",  1400), ("i7-11700KF", 1400), ("i7-11700",   1300),
    ("i5-11600K",  1200), ("i5-11400F",  1100), ("i5-11400",   1100),
    ("i3-11100",    750),
    # Intel 10th gen
    ("i9-10900K",  1500), ("i9-10900KF", 1500), ("i9-10900",   1400),
    ("i7-10700K",  1300), ("i7-10700KF", 1300), ("i7-10700",   1200),
    ("i5-10600K",  1100), ("i5-10400F",  1000), ("i5-10400",   1000),
    ("i3-10100F",   700), ("i3-10100",    700),
    # Intel 8th/9th gen (Coffee Lake)
    ("i9-9900K",   1100), ("i9-9900KF",  1100),
    ("i7-9700K",    900), ("i7-9700",     850),
    ("i5-9600K",    800), ("i5-9500",     750), ("i5-9400F",    720),
    ("i7-8700K",    800), ("i7-8700",     750),
    ("i5-8600K",    720), ("i5-8400",     680),
    # AMD Athlon / FX
    ("Athlon 3000G", 500), ("FX-8350",  400), ("FX-6300",  350),
]

def estimate_benchmark(category: str, specs: dict, name: str) -> int:
    if category == "gpu":
        return specs.get("_benchmark", 5000)
    if category == "cpu":
        # ダッシュとスペースを統一して比較（例: "i9-14900K" と "i9 14900K BOX" 両対応）
        n_up = name.upper().replace("-", " ")
        for keyword, score in _CPU_SCORE_TABLE:
            if keyword.upper().replace("-", " ") in n_up:
                return score
        # ソケット世代でざっくり推定
        socket = specs.get("socket", "")
        if socket == "LGA1851": return 2000
        if socket == "AM5":     return 1800
        if socket == "LGA1700": return 1500
        if socket == "AM4":     return 1200
        if socket == "LGA1200": return 1000
        if socket == "LGA1151": return  800
        return 600
    return 0


def estimate_tdp(category: str, specs: dict, name: str) -> int:
    if category == "gpu":
        return specs.get("_tdp", 150)
    if category == "cpu":
        return specs.get("tdp_estimate", 65)
    return 0
