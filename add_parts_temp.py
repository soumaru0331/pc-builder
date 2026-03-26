import json

new_cases = [
  {
    "category": "case", "brand": "Fractal Design", "name": "North", "model": "FD-C-NOR1X-02",
    "specs": {
      "form_factors": ["ATX", "mATX"], "max_gpu_length": 355, "max_cpu_cooler_height": 169,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": True, "colors": ["black", "white"]
    },
    "reference_price": 17000, "release_year": 2023
  },
  {
    "category": "case", "brand": "Fractal Design", "name": "North XL", "model": "FD-C-NOR1X-06",
    "specs": {
      "form_factors": ["ATX", "mATX", "eATX"], "max_gpu_length": 461, "max_cpu_cooler_height": 185,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": True, "colors": ["black", "white"]
    },
    "reference_price": 21000, "release_year": 2023
  },
  {
    "category": "case", "brand": "NZXT", "name": "H6 Flow", "model": "CC-H61FW-01",
    "specs": {
      "form_factors": ["ATX", "mATX"], "max_gpu_length": 365, "max_cpu_cooler_height": 165,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": True, "colors": ["black", "white"]
    },
    "reference_price": 14000, "release_year": 2023
  },
  {
    "category": "case", "brand": "NZXT", "name": "H5 Flow", "model": "CC-H51FW-01",
    "specs": {
      "form_factors": ["ATX", "mATX"], "max_gpu_length": 365, "max_cpu_cooler_height": 165,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": True, "colors": ["black", "white"]
    },
    "reference_price": 10000, "release_year": 2023
  },
  {
    "category": "case", "brand": "Lian Li", "name": "O11 Air Mini", "model": "G99.O11AMX.00",
    "specs": {
      "form_factors": ["mATX", "mITX"], "max_gpu_length": 340, "max_cpu_cooler_height": 155,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": False, "colors": ["black", "white"]
    },
    "reference_price": 11000, "release_year": 2023
  },
  {
    "category": "case", "brand": "Corsair", "name": "7000D Airflow", "model": "CC-9011218-WW",
    "specs": {
      "form_factors": ["ATX", "mATX", "mITX", "eATX"], "max_gpu_length": 420, "max_cpu_cooler_height": 190,
      "front_panel_usb": 2, "front_panel_usbc": 2, "psu_shroud": True, "colors": ["black", "white"]
    },
    "reference_price": 28000, "release_year": 2022
  },
  {
    "category": "case", "brand": "be quiet!", "name": "Pure Base 500DX", "model": "BG020",
    "specs": {
      "form_factors": ["ATX", "mATX", "mITX"], "max_gpu_length": 369, "max_cpu_cooler_height": 190,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": True, "colors": ["black", "white"]
    },
    "reference_price": 12000, "release_year": 2020
  },
  {
    "category": "case", "brand": "DeepCool", "name": "CH510", "model": "R-CH510-BKNNE1-G",
    "specs": {
      "form_factors": ["ATX", "mATX", "mITX"], "max_gpu_length": 380, "max_cpu_cooler_height": 175,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": True, "colors": ["black", "white"]
    },
    "reference_price": 7000, "release_year": 2021
  },
  {
    "category": "case", "brand": "Phanteks", "name": "Enthoo Pro 2", "model": "PH-ES922E-DBK",
    "specs": {
      "form_factors": ["ATX", "eATX"], "max_gpu_length": 503, "max_cpu_cooler_height": 185,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": True, "colors": ["black"]
    },
    "reference_price": 18000, "release_year": 2021
  },
  {
    "category": "case", "brand": "SilverStone", "name": "SG13", "model": "SST-SG13B",
    "specs": {
      "form_factors": ["mITX"], "max_gpu_length": 265, "max_cpu_cooler_height": 83,
      "front_panel_usb": 2, "front_panel_usbc": 0, "psu_shroud": False, "colors": ["black", "white"]
    },
    "reference_price": 4500, "release_year": 2019
  },
  {
    "category": "case", "brand": "Jonsbo", "name": "U4 Plus", "model": "U4-PLUS-BLACK",
    "specs": {
      "form_factors": ["ATX", "mATX"], "max_gpu_length": 360, "max_cpu_cooler_height": 165,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": False, "colors": ["black", "white"]
    },
    "reference_price": 13000, "release_year": 2022
  },
  {
    "category": "case", "brand": "Thermaltake", "name": "View 51 TG", "model": "CA-1Q6-00M1WN-00",
    "specs": {
      "form_factors": ["ATX", "mATX", "eATX"], "max_gpu_length": 410, "max_cpu_cooler_height": 185,
      "front_panel_usb": 2, "front_panel_usbc": 1, "psu_shroud": False, "colors": ["black"]
    },
    "reference_price": 15000, "release_year": 2021
  },
]

new_mobos = [
  # Z890
  {
    "category": "motherboard", "brand": "ASUS", "name": "ROG Strix Z890-E Gaming WiFi", "model": "ROG-STRIX-Z890-E-GAMING-WIFI",
    "specs": {"socket": "LGA1851", "chipset": "Z890", "form_factor": "ATX", "memory_slots": 4, "max_memory": 256, "max_memory_speed": 9200, "memory_type": ["DDR5"], "m2_slots": 5, "sata_ports": 4, "pcie_slots": 2, "usb_c_rear": 2, "wifi": "WiFi 7", "thunderbolt": True},
    "reference_price": 85000, "release_year": 2024
  },
  {
    "category": "motherboard", "brand": "ASRock", "name": "Z890 Taichi", "model": "Z890-TAICHI",
    "specs": {"socket": "LGA1851", "chipset": "Z890", "form_factor": "ATX", "memory_slots": 4, "max_memory": 256, "max_memory_speed": 9200, "memory_type": ["DDR5"], "m2_slots": 5, "sata_ports": 4, "pcie_slots": 2, "usb_c_rear": 2, "wifi": "WiFi 7", "thunderbolt": False},
    "reference_price": 70000, "release_year": 2024
  },
  {
    "category": "motherboard", "brand": "ASUS", "name": "PRIME Z890-P", "model": "PRIME-Z890-P",
    "specs": {"socket": "LGA1851", "chipset": "Z890", "form_factor": "ATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 8200, "memory_type": ["DDR5"], "m2_slots": 3, "sata_ports": 4, "pcie_slots": 2, "usb_c_rear": 1, "wifi": None, "thunderbolt": False},
    "reference_price": 35000, "release_year": 2024
  },
  {
    "category": "motherboard", "brand": "Gigabyte", "name": "Z890 AORUS Elite WiFi7", "model": "Z890-AORUS-ELITE-WIFI7",
    "specs": {"socket": "LGA1851", "chipset": "Z890", "form_factor": "ATX", "memory_slots": 4, "max_memory": 256, "max_memory_speed": 9200, "memory_type": ["DDR5"], "m2_slots": 5, "sata_ports": 4, "pcie_slots": 2, "usb_c_rear": 1, "wifi": "WiFi 7", "thunderbolt": False},
    "reference_price": 55000, "release_year": 2024
  },
  # B860
  {
    "category": "motherboard", "brand": "ASUS", "name": "PRIME B860M-A WiFi", "model": "PRIME-B860M-A-WIFI",
    "specs": {"socket": "LGA1851", "chipset": "B860", "form_factor": "mATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 6400, "memory_type": ["DDR5"], "m2_slots": 3, "sata_ports": 4, "pcie_slots": 1, "usb_c_rear": 1, "wifi": "WiFi 6E", "thunderbolt": False},
    "reference_price": 22000, "release_year": 2025
  },
  {
    "category": "motherboard", "brand": "ASRock", "name": "B860M Pro RS WiFi", "model": "B860M-PRO-RS-WIFI",
    "specs": {"socket": "LGA1851", "chipset": "B860", "form_factor": "mATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 6400, "memory_type": ["DDR5"], "m2_slots": 3, "sata_ports": 4, "pcie_slots": 1, "usb_c_rear": 1, "wifi": "WiFi 6E", "thunderbolt": False},
    "reference_price": 18000, "release_year": 2025
  },
  {
    "category": "motherboard", "brand": "MSI", "name": "PRO B860M-E", "model": "PRO-B860M-E",
    "specs": {"socket": "LGA1851", "chipset": "B860", "form_factor": "mATX", "memory_slots": 2, "max_memory": 96, "max_memory_speed": 6400, "memory_type": ["DDR5"], "m2_slots": 2, "sata_ports": 4, "pcie_slots": 1, "usb_c_rear": 0, "wifi": None, "thunderbolt": False},
    "reference_price": 14000, "release_year": 2025
  },
  # Z790追加
  {
    "category": "motherboard", "brand": "Gigabyte", "name": "Z790 AORUS Master", "model": "Z790-AORUS-MASTER",
    "specs": {"socket": "LGA1700", "chipset": "Z790", "form_factor": "ATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 7600, "memory_type": ["DDR5"], "m2_slots": 5, "sata_ports": 4, "pcie_slots": 2, "usb_c_rear": 1, "wifi": "WiFi 6E", "thunderbolt": False},
    "reference_price": 65000, "release_year": 2022
  },
  {
    "category": "motherboard", "brand": "ASRock", "name": "Z790 Taichi", "model": "Z790-TAICHI",
    "specs": {"socket": "LGA1700", "chipset": "Z790", "form_factor": "ATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 7600, "memory_type": ["DDR5"], "m2_slots": 5, "sata_ports": 4, "pcie_slots": 2, "usb_c_rear": 2, "wifi": "WiFi 6E", "thunderbolt": False},
    "reference_price": 60000, "release_year": 2022
  },
  # H770
  {
    "category": "motherboard", "brand": "MSI", "name": "PRO H770-P WiFi", "model": "PRO-H770-P-WIFI",
    "specs": {"socket": "LGA1700", "chipset": "H770", "form_factor": "ATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 5600, "memory_type": ["DDR4", "DDR5"], "m2_slots": 3, "sata_ports": 6, "pcie_slots": 2, "usb_c_rear": 1, "wifi": "WiFi 6E", "thunderbolt": False},
    "reference_price": 25000, "release_year": 2023
  },
  {
    "category": "motherboard", "brand": "ASUS", "name": "PRIME H770-Plus D4", "model": "PRIME-H770-PLUS-D4",
    "specs": {"socket": "LGA1700", "chipset": "H770", "form_factor": "ATX", "memory_slots": 4, "max_memory": 128, "max_memory_speed": 4800, "memory_type": ["DDR4"], "m2_slots": 2, "sata_ports": 6, "pcie_slots": 2, "usb_c_rear": 1, "wifi": None, "thunderbolt": False},
    "reference_price": 18000, "release_year": 2023
  },
  # X870E追加
  {
    "category": "motherboard", "brand": "ASRock", "name": "X870E Taichi", "model": "X870E-TAICHI",
    "specs": {"socket": "AM5", "chipset": "X870E", "form_factor": "ATX", "memory_slots": 4, "max_memory": 256, "max_memory_speed": 8000, "memory_type": ["DDR5"], "m2_slots": 5, "sata_ports": 4, "pcie_slots": 2, "usb_c_rear": 3, "wifi": "WiFi 7", "thunderbolt": False},
    "reference_price": 72000, "release_year": 2024
  },
  # B650E
  {
    "category": "motherboard", "brand": "MSI", "name": "MAG B650E TOMAHAWK WiFi", "model": "MAG-B650E-TOMAHAWK-WIFI",
    "specs": {"socket": "AM5", "chipset": "B650E", "form_factor": "ATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 6600, "memory_type": ["DDR5"], "m2_slots": 4, "sata_ports": 4, "pcie_slots": 2, "usb_c_rear": 1, "wifi": "WiFi 6E", "thunderbolt": False},
    "reference_price": 38000, "release_year": 2022
  },
  {
    "category": "motherboard", "brand": "ASUS", "name": "TUF Gaming B650E-F WiFi", "model": "TUF-GAMING-B650E-F-WIFI",
    "specs": {"socket": "AM5", "chipset": "B650E", "form_factor": "ATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 6400, "memory_type": ["DDR5"], "m2_slots": 4, "sata_ports": 4, "pcie_slots": 2, "usb_c_rear": 1, "wifi": "WiFi 6E", "thunderbolt": False},
    "reference_price": 35000, "release_year": 2022
  },
  # B650追加
  {
    "category": "motherboard", "brand": "Gigabyte", "name": "B650M Gaming X AX", "model": "B650M-GAMING-X-AX",
    "specs": {"socket": "AM5", "chipset": "B650", "form_factor": "mATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 6400, "memory_type": ["DDR5"], "m2_slots": 2, "sata_ports": 4, "pcie_slots": 1, "usb_c_rear": 1, "wifi": "WiFi 6E", "thunderbolt": False},
    "reference_price": 20000, "release_year": 2022
  },
  {
    "category": "motherboard", "brand": "ASRock", "name": "B650M PG Lightning WiFi", "model": "B650M-PG-LIGHTNING-WIFI",
    "specs": {"socket": "AM5", "chipset": "B650", "form_factor": "mATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 6400, "memory_type": ["DDR5"], "m2_slots": 2, "sata_ports": 4, "pcie_slots": 1, "usb_c_rear": 1, "wifi": "WiFi 6E", "thunderbolt": False},
    "reference_price": 17000, "release_year": 2022
  },
  # A620
  {
    "category": "motherboard", "brand": "ASUS", "name": "PRIME A620M-A", "model": "PRIME-A620M-A",
    "specs": {"socket": "AM5", "chipset": "A620", "form_factor": "mATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 5200, "memory_type": ["DDR5"], "m2_slots": 2, "sata_ports": 4, "pcie_slots": 1, "usb_c_rear": 0, "wifi": None, "thunderbolt": False},
    "reference_price": 12000, "release_year": 2023
  },
  {
    "category": "motherboard", "brand": "MSI", "name": "PRO A620M-E", "model": "PRO-A620M-E",
    "specs": {"socket": "AM5", "chipset": "A620", "form_factor": "mATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 5200, "memory_type": ["DDR5"], "m2_slots": 2, "sata_ports": 4, "pcie_slots": 1, "usb_c_rear": 0, "wifi": None, "thunderbolt": False},
    "reference_price": 10000, "release_year": 2023
  },
  {
    "category": "motherboard", "brand": "Gigabyte", "name": "A620M DS3H", "model": "A620M-DS3H",
    "specs": {"socket": "AM5", "chipset": "A620", "form_factor": "mATX", "memory_slots": 4, "max_memory": 192, "max_memory_speed": 5200, "memory_type": ["DDR5"], "m2_slots": 2, "sata_ports": 4, "pcie_slots": 1, "usb_c_rear": 0, "wifi": None, "thunderbolt": False},
    "reference_price": 9000, "release_year": 2023
  },
]

PARTS_JSON = "C:/Users/solar/OneDrive/デスクトップ/PC BUILD/pc-builder/backend/data/initial_parts.json"

with open(PARTS_JSON, encoding="utf-8") as f:
    data = json.load(f)

existing_models = {p["model"] for p in data}
added = 0
for p in new_cases + new_mobos:
    if p["model"] not in existing_models:
        data.append(p)
        existing_models.add(p["model"])
        added += 1
    else:
        print(f"SKIP: {p['model']}")

with open(PARTS_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Added {added} parts. Total: {len(data)}")
