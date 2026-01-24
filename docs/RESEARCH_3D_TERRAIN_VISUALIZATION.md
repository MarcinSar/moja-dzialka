# Research: Wizualizacja 3D terenu z chmury punktów LiDAR

**Data:** 2026-01-22
**Cel:** Zbadać możliwości wizualizacji rzeźby terenu działki w oparciu o dane LiDAR

---

## 1. Podsumowanie wykonawcze

### Rekomendacja dla MVP
**Potree + COPC** - najlepszy stosunek jakości do złożoności implementacji:
- Otwarta licencja (MIT)
- Sprawdzony na miliardach punktów (AHN2 - 640 miliardów punktów)
- Natywne wsparcie dla COPC (streaming z HTTP)
- Możliwość integracji z React/Three.js

### Architektura proponowana
```
GUGiK LAZ → PDAL (konwersja) → COPC → CDN/S3 → Potree Viewer
                                              ↓
                                    React Frontend (iframe/komponent)
```

---

## 2. Źródła danych LiDAR w Polsce

### GUGiK - Geoportal (BEZPŁATNE)

| Typ danych | Format | Gęstość | Dostępność |
|------------|--------|---------|------------|
| **NMT** (Numeryczny Model Terenu) | GeoTIFF, ASC | Grid | Cała Polska |
| **NMPT** (Numeryczny Model Pokrycia Terenu) | GeoTIFF, ASC | Grid | Cała Polska |
| **Dane pomiarowe LiDAR** | LAZ 1.4 | 4-20 pkt/m² | Cała Polska |

### Sposoby pobierania

1. **Geoportal.gov.pl** - ręcznie przez mapę (sekcje ~1km²)
2. **Wtyczka QGIS "Pobieracz danych GUGiK"** - automatyzacja pobierania
3. **WCS** - usługa sieciowa dla NMT/NMPT (max 10 km² na zapytanie)

### Przykładowe adresy usług
```
NMT WMS: https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WMS/SkorowidzeWUkladzieKRON86
NMPT WMS: https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMPT/WMS/SkorowidzeWUkladzieKRON86
```

**Źródła:**
- [GUGiK - dane bezpłatne](https://www.gov.pl/web/gugik/dane-udostepniane-bez-platnie-do-pobrania-z-serwisu-wwwgeoportalgovpl)
- [Geoportal - dane pomiarowe LiDAR](https://www.geoportal.gov.pl/pl/dane/dane-pomiarowe-lidar-lidar/)
- [Wtyczka QGIS Pobieracz](https://plugins.qgis.org/plugins/pobieracz_danych_gugik/)

---

## 3. Formaty danych i kompresja

### LAS vs LAZ

| Cecha | LAS | LAZ |
|-------|-----|-----|
| Kompresja | Brak | Lossless, ~90% redukcja |
| Standard | ASPRS LAS 1.4 | Oparty na LAS |
| Streaming | Wymaga pełnego pobrania | Wymaga pełnego pobrania |
| Wsparcie | Uniwersalne | Bardzo szerokie |

### COPC (Cloud Optimized Point Cloud) - **REKOMENDOWANY**

COPC to LAZ 1.4 z dodatkową strukturą oktree:

| Cecha | COPC |
|-------|------|
| Kompresja | Jak LAZ (~90%) |
| Streaming | **TAK** - HTTP range requests |
| LOD | **TAK** - wbudowane poziomy szczegółowości |
| Kompatybilność | Każde narzędzie LAZ może czytać COPC |
| Serwer | Zwykły HTTP/CDN - bez specjalnego backendu |

**Kluczowa zaleta:** Klient pobiera tylko potrzebny fragment danych bez ładowania całego pliku.

**Źródła:**
- [COPC Specification](https://copc.io/)
- [Cloud Optimized Point Clouds](https://www.gillanscience.com/cloud-native-geospatial/copc/)
- [USGS LAZ Delivery Standards](https://www.usgs.gov/ngp-standards-and-specifications/point-cloud-delivery-laz-format)

---

## 4. Rozwiązania do wizualizacji

### 4.1 Potree - **REKOMENDOWANE dla web**

**Opis:** WebGL viewer dla bardzo dużych chmur punktów, rozwijany od 2014 na TU Wien.

| Aspekt | Wartość |
|--------|---------|
| Max testowana skala | 597 miliardów punktów |
| Licencja | MIT (open source) |
| Renderowanie | WebGL + Three.js |
| LOD | Multi-resolution octree |
| Formaty | LAS, LAZ, COPC, Potree native |
| Lighting | Eye-Dome Lighting (EDL) |

**Zalety:**
- Sprawdzony na ogromnych zbiorach (AHN2 Netherlands - 640B pts)
- Aktywny rozwój
- Integracja z Three.js
- Możliwość embeddowania w React

**Architektura Potree:**
```
┌─────────────────────────────────────────────────┐
│                  BROWSER                         │
│  ┌───────────────────────────────────────────┐  │
│  │              Potree Viewer                 │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │        Three.js Scene               │  │  │
│  │  │  - Points geometry                   │  │  │
│  │  │  - EDL shader                        │  │  │
│  │  │  - Octree traversal                  │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  │            ↑ Progressive loading          │  │
│  └───────────┬───────────────────────────────┘  │
└──────────────┼──────────────────────────────────┘
               │ HTTP Range Requests
┌──────────────▼──────────────────────────────────┐
│           CDN / Object Storage                   │
│  ┌─────────────────────────────────────────────┐│
│  │  terrain_gdansk.copc.laz (chunked octree)   ││
│  └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

**Źródła:**
- [Potree GitHub](https://github.com/potree/potree)
- [Potree Paper - TU Wien](https://www.semanticscholar.org/paper/Potree-:-Rendering-Large-Point-Clouds-in-Web-Thesis-Schuetz/67d860cb57142e88b3f82cd5067964c7ccc89d3d)
- [Potree Demo](https://potree.github.io/)

---

### 4.2 CesiumJS + Eptium

**Opis:** 3D Tiles standard + dedykowany viewer dla COPC.

| Aspekt | Wartość |
|--------|---------|
| Baza | CesiumJS (3D globe) |
| Format | COPC → 3D Tiles (konwersja w przeglądarce) |
| Kontekst | Cesium World Terrain, Bing Maps |
| Licencja | Komercyjna (Cesium) + open (Eptium) |

**Zalety:**
- Pełen kontekst geofizyczny (teren, mapy satelitarne)
- Profesjonalne 3D Tiles
- Skalowalność enterprise

**Wady:**
- Cesium ion wymaga subskrypcji dla niektórych funkcji
- Większa złożoność niż Potree

**Źródła:**
- [Hobu Eptium](https://hobu.co/copc-viewer.html)
- [COPC Viewer](https://viewer.copc.io/)
- [Cesium + Eptium Blog](https://cesium.com/blog/2025/06/20/hobu-eptium-point-clouds-cesiumjs/)

---

### 4.3 Three.js (natywnie)

**Opis:** Niskopoziomowe renderowanie w WebGL.

| Aspekt | Wartość |
|--------|---------|
| Max praktyczny rozmiar | ~3-5 mln punktów |
| Format | PLY, custom buffers |
| Kontrola | Pełna |
| Złożoność | Wysoka |

**Problemy:**
- Brak wbudowanego LOD/octree
- Przy >5M punktów znaczący lag
- Konieczność ręcznej implementacji streamingu

**Kiedy używać:**
- Małe chmury punktów (<5M)
- Potrzeba pełnej kontroli nad renderowaniem
- Integracja z istniejącą sceną Three.js

**Źródła:**
- [Three.js Point Clouds](https://medium.com/better-programming/point-clouds-visualization-with-three-js-5ef2a5e24587)
- [Forum Three.js - Performance](https://discourse.threejs.org/t/performance-issues-rendering-large-ply-point-cloud-in-three-js-downsampling-and-background-loading/69135)

---

### 4.4 Blender (offline rendering)

**Opis:** Profesjonalne narzędzie 3D do pre-renderingu.

**Workflow:**
```
LAZ → CloudCompare/PDAL → PLY → Blender → Mesh/Render
```

**Narzędzia:**
- **Point Cloud Visualizer** (płatny addon) - import LAZ/LAS
- **LiDAR-Importer** (darmowy) - wymaga laspy
- **CloudCompare** (darmowy) - konwersja i preprocessing

**Limity:**
- Praktyczny limit: ~3-5 mln punktów
- Konwersja LAZ→PLY powiększa pliki
- Mesh z chmury punktów = bardzo heavy poly

**Kiedy używać:**
- Pre-renderowane wizualizacje (obrazy, video)
- Materiały marketingowe
- Offline processing

**NIE używać do:**
- Real-time web rendering
- Interaktywnych wizualizacji

**Źródła:**
- [Blender Point Cloud Workflow](https://www.maphustle.co.nz/blogs/pc-blender)
- [LiDAR-Importer GitHub](https://github.com/nittanygeek/LiDAR-Importer)
- [Point Cloud Visualizer](https://superhivemarket.com/products/pcv)

---

## 5. Pipeline dla moja-dzialka

### 5.1 Opcja A: Pre-processed COPC (REKOMENDOWANA)

**Opis:** Przygotować COPC dla regionu Trójmiasta, serwować z CDN.

```
┌─────────────────────────────────────────────────────────────────┐
│                        PIPELINE                                  │
│                                                                  │
│  1. POBRANIE (jednorazowo)                                      │
│     GUGiK LAZ dla Trójmiasta → ~50-100 plików LAZ              │
│                                                                  │
│  2. PREPROCESSING (jednorazowo)                                 │
│     LAZ files → PDAL merge → COPC conversion                   │
│     pdal pipeline trojmiasto_to_copc.json                      │
│                                                                  │
│  3. HOSTING                                                      │
│     trojmiasto.copc.laz → AWS S3 / Hetzner Object Storage      │
│     (prawdopodobnie 1-5 GB skompresowanych)                    │
│                                                                  │
│  4. FRONTEND                                                     │
│     Potree component → React wrapper                            │
│     Na żądanie użytkownika: załaduj widok dla bbox działki     │
└─────────────────────────────────────────────────────────────────┘
```

**Estymowany rozmiar danych:**
- Trójmiasto: ~300 km²
- Gęstość: ~10 pkt/m² (średnio dla miast)
- Surowe punkty: ~3 miliardy
- Po kompresji COPC: ~3-10 GB

**Zalety:**
- Jednorazowy preprocessing
- Szybkie ładowanie (streaming)
- Niskie koszty serwowania (CDN)
- Skalowalne

**Narzędzia:**
```bash
# Instalacja PDAL
conda install -c conda-forge pdal

# Merge i konwersja do COPC
pdal merge gdansk_*.laz merged.laz
pdal translate merged.laz trojmiasto.copc.laz --writers.copc.forward=all
```

---

### 5.2 Opcja B: On-demand z GUGiK WCS

**Opis:** Pobierać NMT/NMPT dla działki w czasie rzeczywistym.

```
┌─────────────────────────────────────────────────────────────────┐
│                     ON-DEMAND FLOW                               │
│                                                                  │
│  1. User wybiera działkę                                        │
│  2. Backend: GET WCS dla bbox działki + buffer 200m             │
│  3. Backend: Konwersja GeoTIFF → mesh/point cloud               │
│  4. Frontend: Three.js rendering                                │
└─────────────────────────────────────────────────────────────────┘
```

**Zalety:**
- Brak preprocessingu
- Zawsze aktualne dane
- Małe zapytania (jedna działka)

**Wady:**
- Latencja przy każdym żądaniu
- Limit 10 km² per request
- NMT to grid, nie surowe punkty (mniejsza szczegółowość)

---

### 5.3 Opcja C: Hybrid (NAJLEPSZA DLA PRODUKCJI)

**Opis:** COPC dla obszarów popularnych + on-demand dla reszty.

```
┌─────────────────────────────────────────────────────────────────┐
│                     HYBRID ARCHITECTURE                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  CACHE LAYER (Redis)                                        ││
│  │  - Sprawdź czy mamy COPC tile dla bbox                      ││
│  └─────────────────────────────────────────────────────────────┘│
│           │                            │                         │
│           ▼ HIT                        ▼ MISS                    │
│  ┌─────────────────┐          ┌─────────────────────────────┐  │
│  │  CDN: COPC tile │          │  GUGiK WCS → process → cache │  │
│  │  (pre-computed) │          │  (on-demand generation)      │  │
│  └─────────────────┘          └─────────────────────────────────┘│
│           │                            │                         │
│           └────────────┬───────────────┘                         │
│                        ▼                                         │
│              Potree/Three.js Viewer                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Integracja z React

### Potree w React

```typescript
// components/TerrainViewer.tsx
import { useEffect, useRef } from 'react';

interface TerrainViewerProps {
  copcUrl: string;
  bbox: [number, number, number, number]; // minX, minY, maxX, maxY
  parcelGeometry?: GeoJSON.Polygon;
}

export function TerrainViewer({ copcUrl, bbox, parcelGeometry }: TerrainViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Potree initialization
    const viewer = new Potree.Viewer(containerRef.current);
    viewerRef.current = viewer;

    // Load COPC
    Potree.loadPointCloud(copcUrl, 'terrain', (e: any) => {
      viewer.scene.addPointCloud(e.pointcloud);

      // Set view to parcel bbox
      viewer.fitToScreen();

      // Highlight parcel boundary
      if (parcelGeometry) {
        // Add parcel outline as 3D polygon
      }
    });

    return () => {
      viewer.destroy();
    };
  }, [copcUrl, bbox]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '400px' }}
    />
  );
}
```

### Alternatywa: iframe

Prostsze podejście - hostować Potree osobno i embeddować:

```typescript
export function TerrainViewerIframe({ parcelId }: { parcelId: string }) {
  const viewerUrl = `https://terrain.mojadziaka.pl/view?parcel=${parcelId}`;

  return (
    <iframe
      src={viewerUrl}
      style={{ width: '100%', height: '400px', border: 'none' }}
      allow="fullscreen"
    />
  );
}
```

---

## 7. Narzędzie dla agenta

### Tool Definition

```python
# backend/app/services/tools/terrain_viewer.py

from typing import Optional
from pydantic import BaseModel

class TerrainViewerInput(BaseModel):
    parcel_id: str
    show_neighbors: bool = False
    highlight_elevation: bool = True

class TerrainViewerOutput(BaseModel):
    viewer_url: str
    bbox: tuple[float, float, float, float]
    elevation_stats: dict  # min, max, mean, std
    slope_category: str  # flat, gentle, moderate, steep

async def get_terrain_view(input: TerrainViewerInput) -> TerrainViewerOutput:
    """
    Generuje widok 3D terenu dla działki.

    Agent może użyć tego narzędzia gdy użytkownik pyta o:
    - Rzeźbę terenu
    - Nachylenie działki
    - Czy działka jest płaska
    - Widok 3D
    """
    # 1. Pobierz geometrię działki z PostGIS
    parcel = await get_parcel(input.parcel_id)

    # 2. Oblicz bbox z buforem
    bbox = parcel.geometry.bounds
    buffered_bbox = buffer_bbox(bbox, 200)  # 200m buffer

    # 3. Pobierz statystyki wysokości (z cache lub oblicz)
    elevation_stats = await get_elevation_stats(parcel.geometry)

    # 4. Wygeneruj URL do viewera
    viewer_url = f"/terrain/{input.parcel_id}?bbox={buffered_bbox}"

    return TerrainViewerOutput(
        viewer_url=viewer_url,
        bbox=buffered_bbox,
        elevation_stats=elevation_stats,
        slope_category=classify_slope(elevation_stats)
    )
```

### Agent prompt fragment

```
## Narzędzie: get_terrain_view

Użyj tego narzędzia gdy użytkownik pyta o:
- "Jak wygląda teren?"
- "Czy działka jest płaska?"
- "Jakie jest nachylenie?"
- "Pokaż mi rzeźbę terenu"
- "Model 3D działki"

Wynik zawiera:
- Link do interaktywnego widoku 3D
- Statystyki wysokości (min, max, średnia)
- Kategorię nachylenia (płaska, łagodna, umiarkowana, stroma)

Prezentuj użytkownikowi:
1. Kategorię nachylenia słownie
2. Link do widoku 3D
3. Ostrzeżenie jeśli teren stromy (>15%)
```

---

## 8. Koszty i wydajność

### Estymowane koszty hostingu COPC

| Komponent | Koszt miesięczny |
|-----------|------------------|
| S3/Object Storage (10 GB) | ~$0.25 |
| CDN transfer (100 GB/msc) | ~$8 |
| **Razem** | ~$8-10/msc |

### Wydajność Potree

| Metryka | Wartość |
|---------|---------|
| Initial load | 2-5 sekund |
| Punkty na ekranie | do 10M |
| FPS (desktop) | 30-60 |
| FPS (mobile) | 15-30 |
| Pamięć GPU | 500MB - 2GB |

---

## 9. Alternatywy do rozważenia

### Hillshade (2D)
Zamiast pełnego 3D, można pokazać cieniowanie terenu:
- Szybsze
- Działa wszędzie
- Mniej "wow effect"

### Mesh zamiast point cloud
Konwersja do siatki trójkątów:
- Mniejszy rozmiar
- Można texturować
- Utrata detali

### Pre-rendered video
Animacja obrotu wokół działki:
- Zero interaktywności
- Działa wszędzie
- Może być generowane offline

---

## 10. Rekomendacje dla MVP

### DECYZJA: Potree 3D (pełna interaktywność)

**Wybrano:** Pełne Potree 3D z COPC zamiast uproszczonego hillshade 2D.

**Uzasadnienie:**
- Dużo większa wartość dla użytkownika ("wow effect")
- Interaktywność: obrót, zoom, pomiary
- COPC streaming rozwiązuje problem ciężkich danych
- Złożoność implementacji akceptowalna

### Plan implementacji

| Krok | Opis | Narzędzia |
|------|------|-----------|
| 1 | Pobranie LAZ dla Trójmiasta z GUGiK | Skrypt + QGIS Pobieracz |
| 2 | Merge i konwersja do COPC | PDAL |
| 3 | Upload na Object Storage | S3 / Hetzner |
| 4 | Integracja Potree z React | potree, three.js |

### Odrzucone alternatywy

| Opcja | Powód odrzucenia |
|-------|------------------|
| Hillshade 2D | Zbyt niski "wow effect", brak interakcji 3D |
| Blender rendering | Offline only, zbyt wolne, limit punktów |
| Własny Three.js viewer | Zbyt dużo pracy, brak LOD/octree |
| Full mesh conversion | Niepotrzebna złożoność, utrata detali |

---

## 11. Źródła

### Narzędzia
- [Potree GitHub](https://github.com/potree/potree)
- [PDAL - Point Data Abstraction Library](https://pdal.io/)
- [CloudCompare](https://www.cloudcompare.org/)
- [LAStools](https://rapidlasso.de/lastools/)

### Formaty
- [COPC Specification](https://copc.io/)
- [LAS 1.4 Specification](https://www.asprs.org/divisions-committees/lidar-division/laser-las-file-format-exchange-activities)

### Dane polskie
- [GUGiK Geoportal](https://www.geoportal.gov.pl/)
- [Wtyczka QGIS Pobieracz](https://plugins.qgis.org/plugins/pobieracz_danych_gugik/)

### Viewery online
- [Potree Demo](https://potree.github.io/)
- [COPC Viewer](https://viewer.copc.io/)
- [Eptium](https://hobu.co/copc-viewer.html)
