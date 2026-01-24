"""
District Price Data for Tricity (Gdansk, Gdynia, Sopot).

Data sourced from egib/scripts/pipeline/07a_district_prices.py
Based on market report: docs/RAPORT_CENY_GRUNTOW_TROJMIASTO_2025.md
"""

from typing import Dict, Tuple, Any


# District price data: (city, district) -> {min, max, segment, desc}
DISTRICT_PRICES: Dict[Tuple[str, str | None], Dict[str, Any]] = {
    # Gdańsk - Premium
    ("Gdańsk", "Jelitkowo"): {"min": 1500, "max": 2000, "segment": "PREMIUM", "desc": "Najdroższa dzielnica, blisko morza"},
    ("Gdańsk", "Śródmieście"): {"min": 1200, "max": 2000, "segment": "PREMIUM", "desc": "Centrum miasta"},
    ("Gdańsk", "Oliwa"): {"min": 1000, "max": 1500, "segment": "HIGH", "desc": "Prestiżowa dzielnica, las"},
    ("Gdańsk", "Brzeźno"): {"min": 1000, "max": 1500, "segment": "HIGH", "desc": "Blisko plaży"},
    # Gdańsk - Medium
    ("Gdańsk", "Wrzeszcz"): {"min": 600, "max": 750, "segment": "MEDIUM", "desc": "Centrum komunikacyjne"},
    ("Gdańsk", "Zaspa"): {"min": 650, "max": 900, "segment": "MEDIUM", "desc": "Dobra komunikacja"},
    ("Gdańsk", "Przymorze"): {"min": 700, "max": 1000, "segment": "HIGH", "desc": "Blisko morza"},
    ("Gdańsk", "Kokoszki"): {"min": 600, "max": 700, "segment": "MEDIUM", "desc": "Rozwijająca się, popularna"},
    ("Gdańsk", "Osowa"): {"min": 600, "max": 740, "segment": "MEDIUM", "desc": "Przy TPK, spokojna"},
    ("Gdańsk", "Jasień"): {"min": 600, "max": 800, "segment": "MEDIUM", "desc": "Popularna, dużo ofert"},
    ("Gdańsk", "Olszynka"): {"min": 500, "max": 650, "segment": "MEDIUM", "desc": "Dostępna cenowo"},
    ("Gdańsk", "VII Dwór"): {"min": 550, "max": 700, "segment": "MEDIUM", "desc": "Cicha, zielona"},
    ("Gdańsk", "Matemblewo"): {"min": 500, "max": 700, "segment": "MEDIUM", "desc": "Przy TPK, spokój"},
    # Gdańsk - Budget
    ("Gdańsk", "Łostowice"): {"min": 370, "max": 500, "segment": "BUDGET", "desc": "Szybko rozwijająca się"},
    ("Gdańsk", "Ujeścisko-Łostowice"): {"min": 370, "max": 500, "segment": "BUDGET", "desc": "Rozwijająca się"},
    ("Gdańsk", "Chełm"): {"min": 400, "max": 550, "segment": "BUDGET", "desc": "Tańsza alternatywa"},
    ("Gdańsk", "Orunia"): {"min": 400, "max": 550, "segment": "BUDGET", "desc": "Niższe ceny"},
    ("Gdańsk", "Matarnia"): {"min": 450, "max": 600, "segment": "BUDGET", "desc": "Przy lotnisku"},
    # Gdańsk fallback
    ("Gdańsk", None): {"min": 500, "max": 900, "segment": "MEDIUM", "desc": "Średnia dla Gdańska"},

    # Gdynia - Premium
    ("Gdynia", "Kamienna Góra"): {"min": 5000, "max": 15000, "segment": "ULTRA_PREMIUM", "desc": "Najbardziej prestiżowa"},
    ("Gdynia", "Orłowo"): {"min": 1800, "max": 2500, "segment": "PREMIUM", "desc": "Klif, wille, plaża"},
    ("Gdynia", "Śródmieście"): {"min": 1500, "max": 3000, "segment": "PREMIUM", "desc": "Centrum, bulwar"},
    ("Gdynia", "Redłowo"): {"min": 1500, "max": 2500, "segment": "PREMIUM", "desc": "Prestiżowa dzielnica"},
    # Gdynia - High
    ("Gdynia", "Mały Kack"): {"min": 900, "max": 1400, "segment": "HIGH", "desc": "Dobra komunikacja"},
    ("Gdynia", "Działki Leśne"): {"min": 900, "max": 1200, "segment": "HIGH", "desc": "Zieleń, spokój"},
    ("Gdynia", "Grabówek"): {"min": 800, "max": 1200, "segment": "HIGH", "desc": "Blisko centrum"},
    # Gdynia - Medium/Budget
    ("Gdynia", "Wielki Kack"): {"min": 500, "max": 900, "segment": "MEDIUM", "desc": "Tańsza alternatywa"},
    ("Gdynia", "Wiczlino"): {"min": 400, "max": 800, "segment": "BUDGET", "desc": "Rozwijająca się"},
    ("Gdynia", "Chwarzno-Wiczlino"): {"min": 400, "max": 800, "segment": "BUDGET", "desc": "Rozwijająca się"},
    ("Gdynia", "Chylonia"): {"min": 600, "max": 1000, "segment": "MEDIUM", "desc": "Zróżnicowana"},
    ("Gdynia", "Obłuże"): {"min": 600, "max": 1000, "segment": "MEDIUM", "desc": "Tańsza opcja"},
    ("Gdynia", "Pogórze"): {"min": 500, "max": 900, "segment": "MEDIUM", "desc": "Najtańsze w Gdyni"},
    # Gdynia fallback
    ("Gdynia", None): {"min": 600, "max": 1000, "segment": "MEDIUM", "desc": "Średnia dla Gdyni"},

    # Sopot
    ("Sopot", "Dolny Sopot"): {"min": 4000, "max": 8000, "segment": "ULTRA_PREMIUM", "desc": "Przy Monte Cassino"},
    ("Sopot", "Karlikowo"): {"min": 3000, "max": 5000, "segment": "ULTRA_PREMIUM", "desc": "Luksusowa, wille"},
    ("Sopot", "Kamienny Potok"): {"min": 2500, "max": 4000, "segment": "PREMIUM", "desc": "Spokojna lokalizacja"},
    ("Sopot", "Górny Sopot"): {"min": 2000, "max": 3500, "segment": "PREMIUM", "desc": "Rodzinna, zieleń"},
    ("Sopot", "Brodwino"): {"min": 1500, "max": 2500, "segment": "PREMIUM", "desc": "Najtańsza w Sopocie"},
    # Sopot fallback
    ("Sopot", None): {"min": 2000, "max": 3500, "segment": "PREMIUM", "desc": "Średnia dla Sopotu"},

    # Okolice
    ("Chwaszczyno", None): {"min": 400, "max": 550, "segment": "BUDGET", "desc": "14km od Gdyni"},
    ("Pruszcz Gdański", None): {"min": 300, "max": 400, "segment": "BUDGET", "desc": "10km od Gdańska"},
    ("Żukowo", None): {"min": 170, "max": 300, "segment": "ECONOMY", "desc": "20km od Gdyni"},
    ("Rumia", None): {"min": 300, "max": 600, "segment": "BUDGET", "desc": "15km od Gdyni"},
    ("Kolbudy", None): {"min": 150, "max": 350, "segment": "ECONOMY", "desc": "15km od Gdańska"},
}


SEGMENT_DESCRIPTIONS: Dict[str, str] = {
    "ULTRA_PREMIUM": ">3000 zł/m² - najbardziej prestiżowe lokalizacje",
    "PREMIUM": "1500-3000 zł/m² - dzielnice premium",
    "HIGH": "800-1500 zł/m² - drogie dzielnice",
    "MEDIUM": "500-800 zł/m² - średnia półka",
    "BUDGET": "300-500 zł/m² - przystępne ceny",
    "ECONOMY": "<300 zł/m² - najtańsze lokalizacje",
}
