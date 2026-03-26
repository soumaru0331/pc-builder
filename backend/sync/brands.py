"""全対応ブランド定義"""

BRANDS = {
    "cpu": ["Intel", "AMD"],

    "gpu": [
        # NVIDIA AIB
        "ASUS", "MSI", "Gigabyte", "ASRock", "ZOTAC", "Palit", "Gainward",
        "INNO3D", "GALAX", "PNY", "Colorful", "Maxsun", "Leadtek", "ELSA",
        "Manli", "AXLE", "Dataland", "Arktek",
        # AMD AIB
        "Sapphire", "PowerColor", "XFX", "Yeston",
        # Intel Arc AIB
        "Intel",
    ],

    "motherboard": [
        "ASUS", "MSI", "Gigabyte", "ASRock", "BIOSTAR", "ECS", "Supermicro",
        "Colorful", "Maxsun", "ONDA", "SOYO", "Jetway", "AFOX", "HUANANZHI",
        "Machinist", "Qiyida", "Jginyue", "SZMZ", "Erying",
    ],

    "memory": [
        "Corsair", "G.Skill", "Kingston", "Crucial", "ADATA", "Team", "Apacer",
        "Patriot", "Samsung", "SK hynix", "GeIL", "KLEVV", "Netac", "Gloway",
        "Asgard", "JUHOR", "Timetec", "OLOy", "Kllisre", "RZX", "Tanbassh", "Teclast",
    ],

    "storage": [
        "Samsung", "WD", "Seagate", "Crucial", "Kingston", "ADATA", "Solidigm",
        "KIOXIA", "PNY", "Sabrent", "Lexar", "Netac", "Gloway", "Asgard",
        "Fanxiang", "Hiksemi", "Movespeed", "KingSpec", "Goldenfir", "Reeinno",
        "Walram", "ORICO", "Biwin", "Dahua",
    ],

    "psu": [
        "Corsair", "Seasonic", "Cooler Master", "Thermaltake", "SilverStone",
        "Antec", "FSP", "Super Flower", "be quiet!", "ENERMAX", "Segotep",
        "GameMax", "Raidmax", "Aresgame", "Apevia", "Huntkey", "Great Wall",
        "Andyson", "AcBel", "HKC", "1STPLAYER", "Redragon",
    ],

    "case": [
        "Fractal Design", "NZXT", "Corsair", "Cooler Master", "Thermaltake",
        "Lian Li", "Phanteks", "Antec", "SilverStone", "ZALMAN", "JONSBO",
        "COUGAR", "DEEPCOOL", "darkFlash", "SAMA", "Segotep", "GameMax",
        "DIYPC", "Kolink", "Inter-Tech", "Xigmatek", "Raijintek", "Apevia",
        "PowerTrain", "InWin",
    ],

    "cooler": [
        "Noctua", "Cooler Master", "DEEPCOOL", "Thermalright", "be quiet!",
        "Scythe", "NZXT", "Corsair", "ARCTIC", "ID-COOLING", "PCCOOLER",
        "Vetroo", "upHere", "Aigo", "Alseye", "Bykski", "Barrow",
        "FormulaMod", "Syscooling",
    ],

    "fan": [
        "Noctua", "Corsair", "ARCTIC", "NZXT", "Cooler Master", "Thermaltake",
        "Scythe", "upHere", "EZDIY-FAB", "AsiaHorse", "Jungle Leopard", "Aigo",
        "Vetroo", "PCCOOLER", "ID-COOLING", "Alseye", "DS", "YGT",
    ],
}

# 日本系ブランドは全カテゴリで扱う
JP_BRANDS = [
    "玄人志向", "アイネックス", "AINEX", "親和産業", "サイズ", "Century",
    "AREA", "Dirac", "NOVAC", "Groovy",
]

# 全ブランドをフラットに（重複除去）
ALL_BRANDS: list[str] = sorted(set(
    b for brands in BRANDS.values() for b in brands
) | set(JP_BRANDS))


def detect_brand(name: str, category: str) -> str:
    """商品名からブランドを判定する"""
    candidates = BRANDS.get(category, []) + JP_BRANDS
    name_lower = name.lower()

    # 長いブランド名を先に試す（"Cooler Master" が "Cooler" より先にマッチ）
    for brand in sorted(candidates, key=len, reverse=True):
        if brand.lower() in name_lower:
            return brand

    # フォールバック: 最初の単語
    return name.split()[0] if name else "不明"
