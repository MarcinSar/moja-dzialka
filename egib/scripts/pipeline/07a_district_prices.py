#!/usr/bin/env python3
"""
07a_district_prices.py - Import district price data

Creates a reference table of district prices for the agent to use
when advising users about land values in different areas.

Data source: docs/RAPORT_CENY_GRUNTOW_TROJMIASTO_2025.md
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DistrictPrice:
    """Price data for a district."""
    city: str
    district: Optional[str]
    price_min: int
    price_max: int
    segment: str
    description: Optional[str] = None
    confidence: str = "HIGH"


# Price segments as defined in the plan
SEGMENTS = {
    "ULTRA_PREMIUM": ">3000 zł/m²",
    "PREMIUM": "1500-3000 zł/m²",
    "HIGH": "800-1500 zł/m²",
    "MEDIUM": "500-800 zł/m²",
    "BUDGET": "300-500 zł/m²",
    "ECONOMY": "<300 zł/m²",
}


# District price data from RAPORT_CENY_GRUNTOW_TROJMIASTO_2025.md
DISTRICT_PRICES: List[DistrictPrice] = [
    # ========== GDAŃSK ==========
    # Premium districts (>1000 zł/m²)
    DistrictPrice("Gdańsk", "Jelitkowo", 1500, 2000, "PREMIUM", "Najdroższa dzielnica, blisko morza"),
    DistrictPrice("Gdańsk", "Śródmieście", 1200, 2000, "PREMIUM", "Centrum miasta, historyczna zabudowa"),
    DistrictPrice("Gdańsk", "Oliwa", 1000, 1500, "HIGH", "Prestiżowa dzielnica, las, komunikacja"),
    DistrictPrice("Gdańsk", "Brzeźno", 1000, 1500, "HIGH", "Blisko plaży"),

    # Medium districts (600-1000 zł/m²)
    DistrictPrice("Gdańsk", "Wrzeszcz", 600, 750, "MEDIUM", "Centrum komunikacyjne, usługi"),
    DistrictPrice("Gdańsk", "Zaspa", 650, 900, "MEDIUM", "Dobra komunikacja"),
    DistrictPrice("Gdańsk", "Przymorze", 700, 1000, "HIGH", "Blisko morza"),
    DistrictPrice("Gdańsk", "Kokoszki", 600, 700, "MEDIUM", "Rozwijająca się, popularna"),
    DistrictPrice("Gdańsk", "Osowa", 600, 740, "MEDIUM", "Przy Trójmiejskim Parku Krajobrazowym"),
    DistrictPrice("Gdańsk", "Jasień", 600, 800, "MEDIUM", "Popularna, dużo ofert"),
    DistrictPrice("Gdańsk", "Olszynka", 500, 650, "MEDIUM", "Dostępna cenowo"),
    DistrictPrice("Gdańsk", "VII Dwór", 550, 700, "MEDIUM", "Cicha, zielona okolica"),
    DistrictPrice("Gdańsk", "Strzyża", 600, 800, "MEDIUM", "Dobra lokalizacja"),

    # Budget districts (<600 zł/m²)
    DistrictPrice("Gdańsk", "Ujeścisko-Łostowice", 370, 500, "BUDGET", "Szybko rozwijająca się"),
    DistrictPrice("Gdańsk", "Łostowice", 370, 500, "BUDGET", "Szybko rozwijająca się"),
    DistrictPrice("Gdańsk", "Chełm", 400, 550, "BUDGET", "Tańsza alternatywa"),
    DistrictPrice("Gdańsk", "Orunia", 400, 550, "BUDGET", "Niższe ceny"),
    DistrictPrice("Gdańsk", "Matarnia", 450, 600, "BUDGET", "Przy lotnisku"),
    DistrictPrice("Gdańsk", "Matemblewo", 500, 700, "MEDIUM", "Przy TPK, spokojnie"),
    DistrictPrice("Gdańsk", "Suchanino", 500, 700, "MEDIUM", "Cicha okolica"),
    DistrictPrice("Gdańsk", "Piecki-Migowo", 550, 750, "MEDIUM", "Dobra komunikacja"),
    DistrictPrice("Gdańsk", "Siedlce", 500, 700, "MEDIUM", "Zielona okolica"),
    DistrictPrice("Gdańsk", "Aniołki", 700, 1000, "HIGH", "Blisko centrum"),
    DistrictPrice("Gdańsk", "Stogi", 400, 600, "BUDGET", "Portowa okolica"),
    DistrictPrice("Gdańsk", "Przeróbka", 350, 500, "BUDGET", "Tańsze tereny"),
    DistrictPrice("Gdańsk", "Nowy Port", 400, 600, "BUDGET", "Rewitalizacja"),
    DistrictPrice("Gdańsk", "Letnica", 450, 650, "BUDGET", "Rozwijająca się"),
    DistrictPrice("Gdańsk", "Młyniska", 500, 700, "MEDIUM", "Blisko centrum"),

    # Gdańsk fallback for unknown districts
    DistrictPrice("Gdańsk", None, 500, 900, "MEDIUM", "Średnia dla Gdańska", "LOW"),

    # ========== GDYNIA ==========
    # Premium districts (>1500 zł/m²)
    DistrictPrice("Gdynia", "Kamienna Góra", 5000, 27000, "ULTRA_PREMIUM", "Najbardziej prestiżowa, widok na morze"),
    DistrictPrice("Gdynia", "Orłowo", 1800, 2500, "PREMIUM", "Klif, wille, plaża"),
    DistrictPrice("Gdynia", "Śródmieście", 1500, 3000, "PREMIUM", "Centrum, bulwar"),
    DistrictPrice("Gdynia", "Redłowo", 1500, 2500, "PREMIUM", "Prestiżowa, między centrum a Orłowem"),

    # Medium districts (800-1500 zł/m²)
    DistrictPrice("Gdynia", "Mały Kack", 900, 1400, "HIGH", "Dobra komunikacja, blisko plaży"),
    DistrictPrice("Gdynia", "Działki Leśne", 900, 1200, "HIGH", "Zieleń, spokój"),
    DistrictPrice("Gdynia", "Grabówek", 800, 1200, "HIGH", "Blisko centrum"),
    DistrictPrice("Gdynia", "Wzgórze Św. Maksymiliana", 800, 1200, "HIGH", "Cicha okolica"),
    DistrictPrice("Gdynia", "Leszczynki", 700, 1000, "HIGH", "Zielona dzielnica"),

    # Western districts (cheaper)
    DistrictPrice("Gdynia", "Dąbrowa", 310, 1660, "MEDIUM", "Duża rozpiętość cenowa", "MEDIUM"),
    DistrictPrice("Gdynia", "Wiczlino", 400, 800, "BUDGET", "Rozwijająca się"),
    DistrictPrice("Gdynia", "Chwarzno-Wiczlino", 400, 800, "BUDGET", "Rozwijająca się"),
    DistrictPrice("Gdynia", "Wielki Kack", 500, 900, "MEDIUM", "Tańsza alternatywa"),
    DistrictPrice("Gdynia", "Karwiny", 500, 800, "MEDIUM", "Spokojna okolica"),

    # Northern districts
    DistrictPrice("Gdynia", "Chylonia", 600, 1000, "MEDIUM", "Zróżnicowana dzielnica"),
    DistrictPrice("Gdynia", "Cisowa", 550, 900, "MEDIUM", "Blisko kolei"),
    DistrictPrice("Gdynia", "Obłuże", 600, 1000, "MEDIUM", "Tańsza opcja"),
    DistrictPrice("Gdynia", "Oksywie", 500, 900, "MEDIUM", "Zielona, cicha"),
    DistrictPrice("Gdynia", "Pogórze", 500, 900, "MEDIUM", "Najtańsze w Gdyni"),
    DistrictPrice("Gdynia", "Pustki Cisowskie-Demptowo", 450, 750, "BUDGET", "Oddalona od centrum"),
    DistrictPrice("Gdynia", "Witomino", 600, 900, "MEDIUM", "Mieszkaniowa dzielnica"),

    # Gdynia fallback for unknown districts
    DistrictPrice("Gdynia", None, 600, 1000, "MEDIUM", "Średnia dla Gdyni", "LOW"),

    # ========== SOPOT ==========
    DistrictPrice("Sopot", "Dolny Sopot", 4000, 8000, "ULTRA_PREMIUM", "Przy Monte Cassino, najdroższa"),
    DistrictPrice("Sopot", "Karlikowo", 3000, 5000, "ULTRA_PREMIUM", "Luksusowa, wille"),
    DistrictPrice("Sopot", "Kamienny Potok", 2500, 4000, "PREMIUM", "Spokojna, dobra lokalizacja"),
    DistrictPrice("Sopot", "Górny Sopot", 2000, 3500, "PREMIUM", "Rodzinna, zieleń"),
    DistrictPrice("Sopot", "Świemirowo", 2000, 3000, "PREMIUM", "Średnia półka"),
    DistrictPrice("Sopot", "Brodwino", 1500, 2500, "PREMIUM", "Najtańsza dzielnica Sopotu"),

    # Sopot fallback
    DistrictPrice("Sopot", None, 2000, 3500, "PREMIUM", "Średnia dla Sopotu", "LOW"),

    # ========== OKOLICE TRÓJMIASTA ==========
    DistrictPrice("Chwaszczyno", None, 400, 550, "BUDGET", "14km od Gdyni, popularny dojazd"),
    DistrictPrice("Pruszcz Gdański", None, 300, 400, "BUDGET", "10km od Gdańska, rozwijający się"),
    DistrictPrice("Żukowo", None, 170, 300, "ECONOMY", "20km od Gdyni, Kaszuby"),
    DistrictPrice("Rumia", None, 300, 600, "BUDGET", "15km od Gdyni, zróżnicowane"),
    DistrictPrice("Reda", None, 200, 500, "BUDGET", "25km od Gdyni"),
    DistrictPrice("Wejherowo", None, 150, 400, "ECONOMY", "30km od Gdyni, tańsze"),
    DistrictPrice("Kolbudy", None, 150, 350, "ECONOMY", "15km od Gdańska, najtańsze"),
]


def get_district_prices_df() -> pd.DataFrame:
    """Convert district prices to DataFrame."""
    data = []
    for dp in DISTRICT_PRICES:
        data.append({
            "city": dp.city,
            "district": dp.district,
            "price_min": dp.price_min,
            "price_max": dp.price_max,
            "price_avg": (dp.price_min + dp.price_max) // 2,
            "segment": dp.segment,
            "segment_desc": SEGMENTS.get(dp.segment, ""),
            "description": dp.description,
            "confidence": dp.confidence,
        })
    return pd.DataFrame(data)


def get_price_for_district(city: str, district: Optional[str] = None) -> Optional[DistrictPrice]:
    """Get price data for a specific district."""
    # Try exact match first
    for dp in DISTRICT_PRICES:
        if dp.city.lower() == city.lower() and dp.district:
            if district and dp.district.lower() == district.lower():
                return dp

    # Try fallback (district=None)
    for dp in DISTRICT_PRICES:
        if dp.city.lower() == city.lower() and dp.district is None:
            return dp

    return None


def estimate_parcel_value(city: str, district: Optional[str], area_m2: float) -> dict:
    """
    Estimate parcel value based on district prices.

    Returns dict with:
    - price_min: minimum estimated value
    - price_max: maximum estimated value
    - price_per_m2_min/max: price per m²
    - segment: price segment
    - confidence: LOW/MEDIUM/HIGH
    """
    dp = get_price_for_district(city, district)

    if dp is None:
        return {
            "error": f"No price data for {city}/{district}",
            "price_min": None,
            "price_max": None,
        }

    return {
        "city": dp.city,
        "district": dp.district or "średnia",
        "area_m2": area_m2,
        "price_per_m2_min": dp.price_min,
        "price_per_m2_max": dp.price_max,
        "price_min": int(area_m2 * dp.price_min),
        "price_max": int(area_m2 * dp.price_max),
        "segment": dp.segment,
        "segment_desc": SEGMENTS.get(dp.segment, ""),
        "confidence": dp.confidence,
        "description": dp.description,
    }


def import_to_postgis(connection_string: str):
    """Import district prices to PostGIS database."""
    engine = create_engine(connection_string)
    df = get_district_prices_df()

    # Create table
    with engine.begin() as conn:
        conn.execute(text("""
            DROP TABLE IF EXISTS district_prices;
            CREATE TABLE district_prices (
                id SERIAL PRIMARY KEY,
                city VARCHAR(50) NOT NULL,
                district VARCHAR(100),
                price_min INTEGER NOT NULL,
                price_max INTEGER NOT NULL,
                price_avg INTEGER NOT NULL,
                segment VARCHAR(20) NOT NULL,
                segment_desc VARCHAR(50),
                description TEXT,
                confidence VARCHAR(10) DEFAULT 'HIGH'
            );
        """))

    # Insert data
    df.to_sql('district_prices', engine, if_exists='append', index=False)
    logger.info(f"Imported {len(df)} district price records to PostGIS")


def main():
    """Display summary of district prices."""
    df = get_district_prices_df()

    logger.info("="*60)
    logger.info("DISTRICT PRICES SUMMARY")
    logger.info("="*60)

    # Summary by city
    for city in ["Gdańsk", "Gdynia", "Sopot"]:
        city_df = df[df['city'] == city]
        logger.info(f"\n{city}:")
        logger.info(f"  Districts: {len(city_df[city_df['district'].notna()])}")
        logger.info(f"  Price range: {city_df['price_min'].min()}-{city_df['price_max'].max()} zł/m²")

        # By segment
        for segment in ["ULTRA_PREMIUM", "PREMIUM", "HIGH", "MEDIUM", "BUDGET", "ECONOMY"]:
            seg_df = city_df[city_df['segment'] == segment]
            if len(seg_df) > 0:
                districts = seg_df[seg_df['district'].notna()]['district'].tolist()
                if districts:
                    logger.info(f"  {segment}: {', '.join(districts[:3])}" +
                               (f" (+{len(districts)-3} more)" if len(districts) > 3 else ""))

    # Okolice
    okolice_df = df[~df['city'].isin(["Gdańsk", "Gdynia", "Sopot"])]
    if len(okolice_df) > 0:
        logger.info("\nOkolice Trójmiasta:")
        for _, row in okolice_df.iterrows():
            logger.info(f"  {row['city']}: {row['price_min']}-{row['price_max']} zł/m² ({row['segment']})")

    # Example estimation
    logger.info("\n" + "="*60)
    logger.info("EXAMPLE ESTIMATIONS")
    logger.info("="*60)

    examples = [
        ("Gdańsk", "Osowa", 1000),
        ("Gdańsk", "Oliwa", 1000),
        ("Gdynia", "Orłowo", 800),
        ("Sopot", None, 600),
    ]

    for city, district, area in examples:
        est = estimate_parcel_value(city, district, area)
        if "error" not in est:
            logger.info(f"\n{city}/{district or 'średnia'}, {area}m²:")
            logger.info(f"  {est['price_min']:,}-{est['price_max']:,} zł")
            logger.info(f"  ({est['price_per_m2_min']}-{est['price_per_m2_max']} zł/m², {est['segment']})")


if __name__ == "__main__":
    main()
