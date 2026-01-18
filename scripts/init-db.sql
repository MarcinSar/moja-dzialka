-- ============================================================================
-- moja-dzialka PostGIS Schema
-- ============================================================================
-- This script initializes the PostGIS database with required extensions
-- and creates the parcels table schema.
-- ============================================================================

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Enable additional useful extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text similarity search
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- For GiST indexes on scalar types

-- ============================================================================
-- PARCELS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS parcels (
    -- Primary identifiers
    id SERIAL PRIMARY KEY,
    id_dzialki VARCHAR(50) UNIQUE NOT NULL,
    teryt_powiat VARCHAR(10),

    -- Geometry (EPSG:2180 - Polish national CRS)
    geom GEOMETRY(Polygon, 2180),

    -- Centroid in WGS84 for frontend display
    centroid_lat DOUBLE PRECISION,
    centroid_lon DOUBLE PRECISION,

    -- Basic attributes
    area_m2 DOUBLE PRECISION,
    compactness DOUBLE PRECISION,

    -- Land cover ratios
    forest_ratio DOUBLE PRECISION,
    water_ratio DOUBLE PRECISION,
    builtup_ratio DOUBLE PRECISION,

    -- Administrative location
    wojewodztwo VARCHAR(100),
    powiat VARCHAR(100),
    gmina VARCHAR(100),
    miejscowosc VARCHAR(200),
    rodzaj_miejscowosci VARCHAR(100),
    charakter_terenu VARCHAR(100),

    -- Distance features (meters)
    dist_to_school DOUBLE PRECISION,
    dist_to_shop DOUBLE PRECISION,
    dist_to_hospital DOUBLE PRECISION,
    dist_to_bus_stop DOUBLE PRECISION,
    dist_to_public_road DOUBLE PRECISION,
    dist_to_main_road DOUBLE PRECISION,
    dist_to_forest DOUBLE PRECISION,
    dist_to_water DOUBLE PRECISION,
    dist_to_industrial DOUBLE PRECISION,

    -- Buffer features (500m radius)
    pct_forest_500m DOUBLE PRECISION,
    pct_water_500m DOUBLE PRECISION,
    count_buildings_500m INTEGER,

    -- MPZP (zoning plan) attributes
    has_mpzp BOOLEAN DEFAULT FALSE,
    mpzp_symbol VARCHAR(50),
    mpzp_przeznaczenie VARCHAR(200),
    mpzp_czy_budowlane BOOLEAN,

    -- Composite scores (0-100)
    quietness_score DOUBLE PRECISION,
    nature_score DOUBLE PRECISION,
    accessibility_score DOUBLE PRECISION,
    has_public_road_access BOOLEAN,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Spatial index (critical for geometry queries)
CREATE INDEX IF NOT EXISTS idx_parcels_geom ON parcels USING GIST(geom);

-- Administrative indexes
CREATE INDEX IF NOT EXISTS idx_parcels_gmina ON parcels(gmina);
CREATE INDEX IF NOT EXISTS idx_parcels_powiat ON parcels(powiat);
CREATE INDEX IF NOT EXISTS idx_parcels_miejscowosc ON parcels(miejscowosc);
CREATE INDEX IF NOT EXISTS idx_parcels_teryt ON parcels(teryt_powiat);

-- Attribute indexes for filtering
CREATE INDEX IF NOT EXISTS idx_parcels_area ON parcels(area_m2);
CREATE INDEX IF NOT EXISTS idx_parcels_has_mpzp ON parcels(has_mpzp);
CREATE INDEX IF NOT EXISTS idx_parcels_mpzp_symbol ON parcels(mpzp_symbol);
CREATE INDEX IF NOT EXISTS idx_parcels_mpzp_budowlane ON parcels(mpzp_czy_budowlane);

-- Composite score indexes for ranking
CREATE INDEX IF NOT EXISTS idx_parcels_quietness ON parcels(quietness_score);
CREATE INDEX IF NOT EXISTS idx_parcels_nature ON parcels(nature_score);
CREATE INDEX IF NOT EXISTS idx_parcels_accessibility ON parcels(accessibility_score);

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_parcels_search ON parcels(gmina, area_m2, has_mpzp);

-- ============================================================================
-- TRIGGER FOR updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS parcels_updated_at ON parcels;
CREATE TRIGGER parcels_updated_at
    BEFORE UPDATE ON parcels
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View for parcels with WGS84 geometry (for GeoJSON export)
CREATE OR REPLACE VIEW parcels_wgs84 AS
SELECT
    id,
    id_dzialki,
    area_m2,
    gmina,
    miejscowosc,
    has_mpzp,
    mpzp_symbol,
    mpzp_czy_budowlane,
    quietness_score,
    nature_score,
    accessibility_score,
    ST_Transform(geom, 4326) as geom_wgs84,
    centroid_lat,
    centroid_lon
FROM parcels;

-- View for parcel statistics by gmina
CREATE OR REPLACE VIEW parcels_stats_by_gmina AS
SELECT
    gmina,
    COUNT(*) as parcel_count,
    AVG(area_m2) as avg_area_m2,
    AVG(quietness_score) as avg_quietness,
    AVG(nature_score) as avg_nature,
    AVG(accessibility_score) as avg_accessibility,
    SUM(CASE WHEN has_mpzp THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as pct_with_mpzp,
    SUM(CASE WHEN mpzp_czy_budowlane THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as pct_buildable
FROM parcels
GROUP BY gmina
ORDER BY parcel_count DESC;

-- ============================================================================
-- SAMPLE QUERIES (for reference)
-- ============================================================================

-- Find parcels within 5km of a point (lat, lon in WGS84)
-- SELECT * FROM parcels
-- WHERE ST_DWithin(
--     geom,
--     ST_Transform(ST_SetSRID(ST_MakePoint(18.6, 54.35), 4326), 2180),
--     5000
-- )
-- AND area_m2 BETWEEN 800 AND 1500
-- AND has_mpzp = true
-- ORDER BY quietness_score DESC
-- LIMIT 20;

-- ============================================================================
-- GRANT PERMISSIONS (for app user)
-- ============================================================================

-- The 'app' user is created by docker-compose environment variables
-- GRANT SELECT, INSERT, UPDATE, DELETE ON parcels TO app;
-- GRANT USAGE, SELECT ON SEQUENCE parcels_id_seq TO app;
-- GRANT SELECT ON parcels_wgs84 TO app;
-- GRANT SELECT ON parcels_stats_by_gmina TO app;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'moja-dzialka PostGIS schema initialized successfully';
    RAISE NOTICE 'Tables: parcels';
    RAISE NOTICE 'Views: parcels_wgs84, parcels_stats_by_gmina';
    RAISE NOTICE 'CRS: EPSG:2180 (PUWG 1992)';
END $$;
