from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
MODELS_DIR = PROJECT_ROOT / "models"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

TOGO_COUNTRY_CODE = "TGO"
TOGO_COUNTRY_NAME = "Togo"

ALL_CROPS = {
    "maïs": {"category": "céréale", "name_en": "Maize", "staple": True},
    "riz_paddy": {"category": "céréale", "name_en": "Rice, paddy", "staple": True},
    "sorgho": {"category": "céréale", "name_en": "Sorghum", "staple": True},
    "mil": {"category": "céréale", "name_en": "Millet", "staple": True},
    "manioc": {"category": "tubercule", "name_en": "Cassava", "staple": True},
    "igname": {"category": "tubercule", "name_en": "Yams", "staple": True},
    "soja": {"category": "oléagineux", "name_en": "Soybeans", "staple": False},
    "arachide": {"category": "oléagineux", "name_en": "Groundnuts", "staple": False},
    "palme": {"category": "oléagineux", "name_en": "Oil palm", "staple": False},
    "coton": {"category": "fibre", "name_en": "Cotton", "staple": False},
    "noix_de_cajou": {"category": "export", "name_en": "Cashew", "staple": False},
    "café": {"category": "export", "name_en": "Coffee", "staple": False},
    "cacao": {"category": "export", "name_en": "Cocoa", "staple": False},
}

CROP_CATEGORIES = {
    "céréale": "Céréales (alimentation de base)",
    "tubercule": "Tubercules (alimentation de base)",
    "oléagineux": "Oléagineux (transformation industrielle)",
    "fibre": "Fibre (textile, export)",
    "export": "Cultures d'exportation (hors fibre)",
}

STRATEGIC_CROPS = list(ALL_CROPS.keys())

WB_INDICATORS = {
    "inflation": "FP.CPI.TOTL.ZG",
    "gdp": "NY.GDP.MKTP.CD",
    "agri_value_added": "NV.AGR.TOTL.ZS",
    "crop_production": "AG.PRD.CROP.XD",
}

PIA_SECTORS = ["agro-industrie", "logistique", "manufacture"]

TOGO_REGIONS = ["Maritime", "Plateaux", "Centrale", "Savanes", "Kara"]
