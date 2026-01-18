# Moja Dzialka - Data Pipeline

Pipeline do przygotowania danych dla systemu rekomendacji działek.

## Wymagania

```bash
pip install -r requirements.txt
```

## Struktura

```
scripts/pipeline/
├── config.py              # Konfiguracja ścieżek, thresholdów
├── 01_validate.py         # Walidacja danych wejściowych
├── 02_clean_parcels.py    # Czyszczenie działek
├── 02_clean_bdot10k.py    # Konsolidacja BDOT10k
├── 02_clean_mpzp.py       # Standaryzacja MPZP
├── 03_feature_engineering.py  # Obliczanie cech
├── 04_create_dev_sample.py    # Tworzenie próbki dev
└── utils/
    ├── geometry.py        # Funkcje geometryczne
    ├── spatial.py         # Analiza przestrzenna
    ├── io.py              # Wczytywanie/zapis
    └── logging.py         # Logowanie
```

## Użycie

### Pełny pipeline

```bash
# 1. Walidacja danych
python scripts/pipeline/01_validate.py

# 2. Czyszczenie (można uruchomić równolegle)
python scripts/pipeline/02_clean_parcels.py
python scripts/pipeline/02_clean_bdot10k.py
python scripts/pipeline/02_clean_mpzp.py

# 3. Feature engineering
python scripts/pipeline/03_feature_engineering.py

# 4. Próbka deweloperska
python scripts/pipeline/04_create_dev_sample.py
```

### Wyniki

```
data/
├── cleaned/v1.0.0/
│   ├── parcels_cleaned.gpkg
│   ├── mpzp_cleaned.gpkg
│   └── bdot10k/
│       ├── bdot10k_buildings.gpkg
│       ├── bdot10k_roads.gpkg
│       ├── bdot10k_forest.gpkg
│       ├── bdot10k_water.gpkg
│       ├── bdot10k_poi.gpkg
│       ├── bdot10k_protected.gpkg
│       └── bdot10k_industrial.gpkg
├── processed/v1.0.0/
│   ├── parcel_features.parquet
│   └── parcel_features.gpkg
├── dev/
│   ├── parcels_dev.gpkg
│   ├── bdot10k_dev.gpkg
│   ├── mpzp_dev.gpkg
│   └── sample_info.json
└── reports/
    └── validation_report.json
```

## Features

### Distance Features
- `dist_to_school` - Odległość do szkoły
- `dist_to_shop` - Odległość do sklepu
- `dist_to_hospital` - Odległość do szpitala/przychodni
- `dist_to_bus_stop` - Odległość do przystanku
- `dist_to_public_road` - Odległość do drogi publicznej
- `dist_to_main_road` - Odległość do drogi głównej
- `dist_to_forest` - Odległość do lasu
- `dist_to_water` - Odległość do wody
- `dist_to_industrial` - Odległość do strefy przemysłowej

### Buffer Features (500m)
- `pct_forest_500m` - % lasu w buforze
- `pct_water_500m` - % wody w buforze
- `count_buildings_500m` - Liczba budynków w buforze

### MPZP Features
- `has_mpzp` - Czy ma pokrycie MPZP
- `mpzp_symbol` - Symbol przeznaczenia
- `mpzp_przeznaczenie` - Kategoria przeznaczenia
- `mpzp_czy_budowlane` - Czy teren budowlany

### Composite Features
- `quietness_score` - Wskaźnik ciszy (0-100)
- `nature_score` - Wskaźnik bliskości natury (0-100)
- `accessibility_score` - Wskaźnik dostępności (0-100)
- `has_public_road_access` - Czy ma dostęp do drogi
- `compactness` - Zwartość działki (0-1)

## Konfiguracja

Edytuj `config.py` aby zmienić:
- Ścieżki do danych
- Progi walidacji
- Parametry feature engineeringu
- Gminy do próbki dev
