# core/model_rekrutmen.py
import re


MODEL_REKRUTMEN_KEYWORDS = {
    "Model 1": {
        "keywords": [
            "head of area", "level 3 below", "l3 mp", "creative",
            "fgdp", "fresh graduate", "cimory leadership",
        ],
        "description": "Level 3 Below, FGDP, Head of Area, L3 MP Commercial (Creative Div.)",
    },
    "Model 2": {
        "keywords": [
            "managerial", "manager", "clap", "cimory leadership acceleration program",
        ],
        "description": "Managerial, CLAP",
    },
    "Model 3": {
        "keywords": [
            "area sales supervisor", "ass", "sales supervisor",
        ],
        "description": "Area Sales Supervisor",
    },
    "Model 4": {
        "keywords": [
            "sales taking order", "sales to", "project sales", "sales to chilled",
        ],
        "description": "Project: Sales TO Chilled",
    },
}

MODEL_REKRUTMEN_OPTIONS = ["Model 1", "Model 2", "Model 3", "Model 4"]


def auto_detect_model_rekrutmen(posisi: str, level_number: int = None) -> str:
    if not posisi:
        return ""

    posisi_lower = posisi.lower()

    for model, data in MODEL_REKRUTMEN_KEYWORDS.items():
        for keyword in data["keywords"]:
            if keyword.lower() in posisi_lower:
                return model

    if level_number is not None:
        if level_number >= 4:
            return "Model 2"

    return ""


def get_model_description(model: str) -> str:
    if not model:
        return ""
    data = MODEL_REKRUTMEN_KEYWORDS.get(model, {})
    return data.get("description", "")


def get_model_options() -> list:
    return MODEL_REKRUTMEN_OPTIONS.copy()
