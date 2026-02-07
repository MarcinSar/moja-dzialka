"""
Tool Executor v4 - 16 consolidated tools for the single-agent architecture.

Each tool method:
1. Receives params from Claude API tool_use
2. Has access to notepad (session state)
3. Returns (result_dict, notepad_updates) tuple
4. Reuses existing services (graph_service, spatial_service, hybrid_search)

No propose/approve ceremony. No state machine transitions.
Agent calls tools directly. Gates are checked by tool_gates middleware.
"""

from __future__ import annotations

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from loguru import logger

from app.engine.notepad import Notepad, LocationState, SearchResults
from app.engine import result_store
from app.services import (
    spatial_service,
    graph_service,
    hybrid_search,
    SearchPreferences,
)
from app.services.database import neo4j, mongodb


# Type alias
ToolResult = Tuple[Dict[str, Any], Dict[str, Any]]  # (result, notepad_updates)


class ToolExecutorV4:
    """Execute 16 consolidated tools with notepad-driven state.

    Usage:
        executor = ToolExecutorV4(notepad, session_id)
        result, updates = await executor.execute("tool_name", params)
        # Apply updates to notepad
    """

    def __init__(self, notepad: Notepad, session_id: str):
        self.notepad = notepad
        self.session_id = session_id
        # Build parcel index map from search results for reference resolution
        self._parcel_index_map: Dict[int, str] = {}

    async def execute(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name."""
        logger.info(f"Executing tool: {tool_name}")
        logger.debug(f"Tool params: {json.dumps(params, ensure_ascii=False, default=str)[:500]}")

        try:
            dispatch = {
                "location_search": self._location_search,
                "location_confirm": self._location_confirm,
                "search_count": self._search_count,
                "search_execute": self._search_execute,
                "search_refine": self._search_refine,
                "search_similar": self._search_similar,
                "search_adjacent": self._search_adjacent,
                "parcel_details": self._parcel_details,
                "parcel_compare": self._parcel_compare,
                "market_prices": self._market_prices,
                "market_map": self._market_map,
                "results_load_page": self._results_load_page,
                "notepad_update": self._notepad_update,
                "lead_capture": self._lead_capture,
                "lead_summary": self._lead_summary,
            }

            handler = dispatch.get(tool_name)
            if not handler:
                return {"error": f"Nieznane narzędzie: {tool_name}"}, {}

            return await handler(params)

        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)
            return {"error": str(e)}, {}

    # =========================================================================
    # REFERENCE RESOLUTION
    # =========================================================================

    def _resolve_parcel_ref(self, ref: str) -> Optional[str]:
        """Resolve parcel reference (number, ordinal, or ID) to actual ID."""
        if not ref:
            return None

        ref = ref.strip()

        # Already a parcel ID (contains underscore)
        if "_" in ref:
            return ref

        # Polish ordinal words
        ordinal_map = {
            "pierwsza": 1, "pierwszą": 1, "pierwszy": 1, "1.": 1,
            "druga": 2, "drugą": 2, "drugi": 2, "2.": 2,
            "trzecia": 3, "trzecią": 3, "trzeci": 3, "3.": 3,
            "czwarta": 4, "czwartą": 4, "czwarty": 4, "4.": 4,
            "piąta": 5, "piątą": 5, "piąty": 5, "5.": 5,
        }

        ref_lower = ref.lower()
        if ref_lower in ordinal_map:
            idx = ordinal_map[ref_lower]
            return self._parcel_index_map.get(idx)

        # Numeric string
        if ref.isdigit():
            idx = int(ref)
            return self._parcel_index_map.get(idx)

        return ref

    # =========================================================================
    # LOCATION TOOLS (2)
    # =========================================================================

    async def _location_search(self, params: Dict[str, Any]) -> ToolResult:
        """Multi-step location search: exact → partial → fuzzy → vector."""
        name = params.get("name", "").strip()
        level = params.get("level", "any")
        parent_name = params.get("parent_name")

        if not name:
            return {"error": "Podaj nazwę lokalizacji (name)"}, {}

        results = []

        # STEP 1: Exact match on District nodes
        if level in ("any", "dzielnica"):
            q = "MATCH (d:District)-[:BELONGS_TO]->(c:City) WHERE toLower(d.name) = toLower($name)"
            p = {"name": name}
            if parent_name:
                q += " AND toLower(c.name) = toLower($parent_name)"
                p["parent_name"] = parent_name
            q += """
                OPTIONAL MATCH (parcel:Parcel)-[:LOCATED_IN]->(d)
                RETURN d.name as dzielnica, c.name as gmina, count(parcel) as parcel_count
                ORDER BY parcel_count DESC
            """
            try:
                for r in await neo4j.run(q, p):
                    results.append({
                        "level": "dzielnica", "dzielnica": r["dzielnica"],
                        "gmina": r["gmina"], "parcel_count": r["parcel_count"],
                    })
            except Exception as e:
                logger.debug(f"location_search dzielnica error: {e}")

        # STEP 1b: Exact match on gmina
        if level in ("any", "gmina", "miejscowosc"):
            try:
                q = """
                    MATCH (p:Parcel) WHERE toLower(p.gmina) = toLower($name)
                    WITH p.gmina as gmina, p.powiat as powiat, count(p) as cnt
                    RETURN DISTINCT gmina, powiat, cnt
                """
                for r in await neo4j.run(q, {"name": name}):
                    results.append({
                        "level": "gmina", "gmina": r["gmina"],
                        "powiat": r["powiat"], "parcel_count": r["cnt"],
                    })
            except Exception as e:
                logger.debug(f"location_search gmina error: {e}")

        # STEP 2: Partial match
        if not results:
            try:
                q = """
                    MATCH (d:District)-[:BELONGS_TO]->(c:City)
                    WHERE toLower(d.name) CONTAINS toLower($name)
                       OR toLower($name) CONTAINS toLower(d.name)
                    OPTIONAL MATCH (parcel:Parcel)-[:LOCATED_IN]->(d)
                    RETURN d.name as dzielnica, c.name as gmina, count(parcel) as parcel_count
                    ORDER BY parcel_count DESC LIMIT 10
                """
                for r in await neo4j.run(q, {"name": name}):
                    results.append({
                        "level": "dzielnica", "dzielnica": r["dzielnica"],
                        "gmina": r["gmina"], "parcel_count": r["parcel_count"],
                        "match": "partial",
                    })
            except Exception as e:
                logger.debug(f"location_search partial error: {e}")

        # STEP 3: Fulltext fuzzy search
        if not results:
            try:
                q = """
                    CALL db.index.fulltext.queryNodes('district_names_ft', $search)
                    YIELD node, score WHERE score > 0.5
                    MATCH (node)-[:BELONGS_TO]->(c:City)
                    OPTIONAL MATCH (parcel:Parcel)-[:LOCATED_IN]->(node)
                    RETURN node.name as dzielnica, c.name as gmina,
                           count(parcel) as parcel_count, score
                    ORDER BY score DESC LIMIT 5
                """
                for r in await neo4j.run(q, {"search": f"{name}~"}):
                    results.append({
                        "level": "dzielnica", "dzielnica": r["dzielnica"],
                        "gmina": r["gmina"], "parcel_count": r["parcel_count"],
                        "match": "fuzzy", "score": round(r["score"], 2),
                    })
            except Exception as e:
                logger.debug(f"location_search fulltext error: {e}")

        # STEP 4: Vector semantic search
        if not results:
            try:
                from app.services.embedding_service import EmbeddingService
                embedding = EmbeddingService.encode(name)
                q = """
                    CALL db.index.vector.queryNodes('location_name_embedding_idx', 5, $emb)
                    YIELD node, score WHERE score >= 0.7
                    RETURN node.canonical_name as canonical,
                           node.maps_to_district as dzielnica,
                           node.maps_to_gmina as gmina, score
                    ORDER BY score DESC
                """
                for r in await neo4j.run(q, {"emb": embedding}):
                    results.append({
                        "level": "dzielnica", "dzielnica": r["dzielnica"],
                        "gmina": r["gmina"], "match": "semantic",
                        "canonical_name": r["canonical"],
                        "score": round(r["score"], 2),
                    })
            except Exception as e:
                logger.debug(f"location_search vector error: {e}")

        return {
            "query": name,
            "results": results[:20],
            "count": len(results),
            "note": (
                "Przejrzyj wyniki i potwierdź z użytkownikiem. "
                "Następnie użyj location_confirm z dokładnymi wartościami."
            ) if results else (
                "Brak wyników. Dopytaj użytkownika o gminę lub miasto."
            ),
        }, {}

    async def _location_confirm(self, params: Dict[str, Any]) -> ToolResult:
        """Validate and save location to notepad."""
        gmina = params.get("gmina")
        dzielnica = params.get("dzielnica")
        miejscowosc = params.get("miejscowosc")
        powiat = params.get("powiat")

        if not any([gmina, dzielnica, miejscowosc, powiat]):
            return {"error": "Podaj przynajmniej gmina"}, {}

        # Validate against DB
        conditions = []
        q_params = {}
        if gmina:
            conditions.append("p.gmina = $gmina")
            q_params["gmina"] = gmina
        if dzielnica:
            conditions.append("(p.dzielnica = $dzielnica OR p.dzielnica STARTS WITH $dz_prefix)")
            q_params["dzielnica"] = dzielnica
            q_params["dz_prefix"] = dzielnica + " "
        if powiat:
            conditions.append("p.powiat = $powiat")
            q_params["powiat"] = powiat

        where = " AND ".join(conditions)
        try:
            result = await neo4j.run(
                f"MATCH (p:Parcel) WHERE {where} RETURN count(p) as cnt", q_params
            )
            parcel_count = result[0]["cnt"] if result else 0
        except Exception as e:
            return {"error": f"Błąd zapytania: {e}"}, {}

        if parcel_count == 0:
            return {"error": f"Nie znaleziono działek. Sprawdź nazwy."}, {}

        # Get centroid for spatial search
        centroid = None
        try:
            centroid = await graph_service.get_location_centroid(
                dzielnica=dzielnica, gmina=gmina
            )
        except Exception:
            pass

        # Build location state
        loc = LocationState(
            gmina=gmina,
            dzielnica=dzielnica,
            miejscowosc=miejscowosc,
            powiat=powiat,
            lat=centroid.get("lat") if centroid else None,
            lon=centroid.get("lon") if centroid else None,
            radius_m=3000 if dzielnica else 10000,
            parcel_count=parcel_count,
            validated=True,
        )

        display = ", ".join(x for x in [dzielnica, gmina, powiat] if x)

        return {
            "confirmed": True,
            "location": {"gmina": gmina, "dzielnica": dzielnica, "powiat": powiat},
            "parcel_count": parcel_count,
            "display": display,
            "centroid": centroid,
            "note": f"Lokalizacja '{display}' zapisana ({parcel_count} działek).",
        }, {"location": loc}

    # =========================================================================
    # SEARCH TOOLS (5)
    # =========================================================================

    async def _search_count(self, params: Dict[str, Any]) -> ToolResult:
        """Quick count of matching parcels."""
        loc = self.notepad.location
        conditions = []
        q_params = {}

        if loc and loc.validated:
            if loc.gmina:
                conditions.append("p.gmina = $gmina")
                q_params["gmina"] = loc.gmina
            if loc.dzielnica:
                conditions.append("(p.dzielnica = $dzielnica OR p.dzielnica STARTS WITH $dz_prefix)")
                q_params["dzielnica"] = loc.dzielnica
                q_params["dz_prefix"] = loc.dzielnica + " "

        # Relationship-based filters (EXISTS subquery)
        if params.get("ownership_type"):
            conditions.append("EXISTS { MATCH (p)-[:HAS_OWNERSHIP]->(o:OwnershipType {id: $own}) }")
            q_params["own"] = params["ownership_type"]
        if params.get("build_status"):
            conditions.append("EXISTS { MATCH (p)-[:HAS_BUILD_STATUS]->(bs:BuildStatus {id: $bs}) }")
            q_params["bs"] = params["build_status"]
        if params.get("size_category"):
            conditions.append("EXISTS { MATCH (p)-[:HAS_SIZE]->(sz:SizeCategory) WHERE sz.id IN $sizes }")
            q_params["sizes"] = params["size_category"]
        if params.get("quietness_categories"):
            conditions.append("EXISTS { MATCH (p)-[:HAS_QUIETNESS]->(qc:QuietnessCategory) WHERE qc.id IN $qcats }")
            q_params["qcats"] = params["quietness_categories"]
        if params.get("nature_categories"):
            conditions.append("EXISTS { MATCH (p)-[:HAS_NATURE]->(nc:NatureCategory) WHERE nc.id IN $ncats }")
            q_params["ncats"] = params["nature_categories"]

        # Attribute-based filters (direct property)
        if params.get("min_area_m2"):
            conditions.append("p.area_m2 >= $min_area")
            q_params["min_area"] = params["min_area_m2"]
        if params.get("max_area_m2"):
            conditions.append("p.area_m2 <= $max_area")
            q_params["max_area"] = params["max_area_m2"]

        # Default shape quality filters (match search_execute)
        conditions.append("(p.aspect_ratio IS NULL OR p.aspect_ratio <= 6.0)")
        conditions.append("(p.shape_index IS NULL OR p.shape_index >= 0.15)")
        conditions.append("(p.pog_symbol IS NULL OR NOT p.pog_symbol IN ['SK', 'SI'])")

        where = " AND ".join(conditions) if conditions else "1=1"
        # Build description of active filters for the agent
        filter_desc = []
        if loc and loc.validated and loc.dzielnica:
            filter_desc.append(f"{loc.dzielnica}, {loc.gmina}")
        elif loc and loc.validated and loc.gmina:
            filter_desc.append(loc.gmina)
        for key in ["ownership_type", "build_status"]:
            if params.get(key):
                filter_desc.append(params[key])
        if params.get("min_area_m2") or params.get("max_area_m2"):
            lo = params.get("min_area_m2", "?")
            hi = params.get("max_area_m2", "?")
            filter_desc.append(f"{lo}-{hi}m²")

        try:
            result = await neo4j.run(f"MATCH (p:Parcel) WHERE {where} RETURN count(p) as cnt", q_params)
            count = result[0]["cnt"] if result else 0
            filters_str = ", ".join(filter_desc) if filter_desc else "bez filtrów"
            return {
                "matching_count": count,
                "filters": filters_str,
                "message": f"**{count:,}** pasujących działek ({filters_str}).".replace(",", " "),
            }, {}
        except Exception as e:
            return {"error": str(e)}, {}

    async def _search_execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute hybrid search (graph + vector + spatial)."""
        loc = self.notepad.location
        if not loc or not loc.validated:
            return {"error": "Lokalizacja nie zwalidowana. Użyj location_search + location_confirm."}, {}

        limit = min(params.get("limit", 30), 50)

        # Build query_text for semantic search
        query_parts = []
        if loc.dzielnica:
            query_parts.append(loc.dzielnica)
        if loc.gmina:
            query_parts.append(loc.gmina)
        if params.get("quietness_categories"):
            query_parts.append("cicha spokojna okolica")
        if params.get("nature_categories"):
            query_parts.append("blisko natury zieleni lasu")
        if params.get("build_status") == "niezabudowana":
            query_parts.append("niezabudowana pod budowę")
        if params.get("ownership_type") == "prywatna":
            query_parts.append("prywatna działka do kupienia")
        query_text = params.get("query_text") or (" ".join(query_parts) if query_parts else None)

        search_prefs = SearchPreferences(
            gmina=loc.gmina,
            miejscowosc=loc.dzielnica,
            powiat=loc.powiat,
            lat=loc.lat,
            lon=loc.lon,
            radius_m=loc.radius_m,
            min_area=params.get("min_area_m2"),
            max_area=params.get("max_area_m2"),
            quietness_categories=params.get("quietness_categories"),
            building_density=params.get("building_density"),
            nature_categories=params.get("nature_categories"),
            max_dist_to_forest_m=params.get("max_dist_to_forest_m"),
            max_dist_to_water_m=params.get("max_dist_to_water_m"),
            accessibility_categories=params.get("accessibility_categories"),
            max_dist_to_school_m=params.get("max_dist_to_school_m"),
            max_dist_to_shop_m=params.get("max_dist_to_shop_m"),
            max_dist_to_bus_stop_m=params.get("max_dist_to_bus_stop_m"),
            has_road_access=params.get("has_road_access"),
            pog_residential=params.get("pog_residential"),
            sort_by=params.get("sort_by", "quietness_score"),
            ownership_type=params.get("ownership_type"),
            build_status=params.get("build_status"),
            size_category=params.get("size_category"),
            query_text=query_text,
            # Dimension weights from agent
            w_quietness=params.get("w_quietness", 0.0),
            w_nature=params.get("w_nature", 0.0),
            w_forest=params.get("w_forest", 0.0),
            w_water=params.get("w_water", 0.0),
            w_school=params.get("w_school", 0.0),
            w_shop=params.get("w_shop", 0.0),
            w_transport=params.get("w_transport", 0.0),
            w_accessibility=params.get("w_accessibility", 0.0),
        )

        results = await hybrid_search.search(search_prefs, limit=limit, include_details=True)

        if not results:
            return {
                "status": "no_results",
                "count": 0,
                "message": "Brak wyników. Spróbuj poluzować kryteria.",
                "hint": "Możesz usunąć filtry ciszy/natury lub zwiększyć promień.",
            }, {}

        # Convert to dicts and save to JSONL
        result_dicts = []
        self._parcel_index_map = {}
        for idx, r in enumerate(results, 1):
            d = {
                "index": idx,
                "id": r.parcel_id,
                "gmina": r.gmina,
                "dzielnica": r.miejscowosc,
                "area_m2": r.area_m2,
                "quietness_score": r.quietness_score,
                "nature_score": r.nature_score,
                "accessibility_score": r.accessibility_score,
                "has_mpzp": r.has_mpzp,
                "mpzp_symbol": r.mpzp_symbol,
                "centroid_lat": r.centroid_lat,
                "centroid_lon": r.centroid_lon,
                "dist_to_forest": r.dist_to_forest,
                "dist_to_water": r.dist_to_water,
                "dist_to_school": r.dist_to_school,
                "dist_to_shop": r.dist_to_shop,
                "pct_forest_500m": r.pct_forest_500m,
                "has_road_access": r.has_road_access,
                "shape_index": round(r.shape_index, 2) if getattr(r, "shape_index", None) else None,
                "aspect_ratio": round(r.aspect_ratio, 1) if getattr(r, "aspect_ratio", None) else None,
            }
            result_dicts.append(d)
            self._parcel_index_map[idx] = r.parcel_id

        # Write to JSONL file
        filepath = result_store.write_results(result_dicts, self.session_id)

        # Build search results state
        filters_used = {k: v for k, v in params.items() if v is not None and k != "limit"}
        search_results = SearchResults(
            total_count=len(result_dicts),
            file_path=filepath,
            query_text=query_text,
            filters_used=filters_used,
            executed_at=datetime.now().isoformat(),
        )

        # Return first page inline
        first_page = result_dicts[:10]

        return {
            "status": "success",
            "count": len(result_dicts),
            "parcels": first_page,
            "has_more": len(result_dicts) > 10,
            "message": f"Znaleziono {len(result_dicts)} działek. Pokazuję {len(first_page)} najlepszych.",
        }, {"search_results": search_results}

    async def _search_refine(self, params: Dict[str, Any]) -> ToolResult:
        """Refine search with changed parameters."""
        changes = params.get("changes", {})
        if not changes:
            return {"error": "Podaj changes z nowymi parametrami"}, {}

        sr = self.notepad.search_results
        if not sr:
            return {"error": "Brak poprzedniego wyszukiwania"}, {}

        # Merge changes into previous filters
        prev_filters = sr.filters_used or {}
        new_params = {**prev_filters, **changes}

        return await self._search_execute(new_params)

    async def _search_similar(self, params: Dict[str, Any]) -> ToolResult:
        """Find similar parcels using graph embeddings."""
        raw_ref = params["parcel_id"]
        parcel_id = self._resolve_parcel_ref(raw_ref)
        if not parcel_id:
            return {"error": f"Nie rozpoznano: {raw_ref}"}, {}

        limit = params.get("limit", 10)
        results = await graph_service.find_similar_by_graph_embedding(parcel_id, limit)

        if not results:
            return {"parcel_id": parcel_id, "count": 0, "similar": [], "message": "Brak podobnych"}, {}

        formatted = [{
            "id": r.get("id"), "dzielnica": r.get("dzielnica"), "gmina": r.get("gmina"),
            "area_m2": r.get("area_m2"), "quietness_score": r.get("quietness_score"),
            "similarity": round(r.get("similarity", 0), 3),
        } for r in results]

        return {
            "reference": parcel_id, "count": len(formatted),
            "similar": formatted,
            "message": f"Znaleziono {len(formatted)} podobnych działek",
        }, {}

    async def _search_adjacent(self, params: Dict[str, Any]) -> ToolResult:
        """Find adjacent parcels via ADJACENT_TO relation."""
        raw_ref = params["parcel_id"]
        parcel_id = self._resolve_parcel_ref(raw_ref)
        if not parcel_id:
            return {"error": f"Nie rozpoznano: {raw_ref}"}, {}

        limit = params.get("limit", 20)
        neighbors = await graph_service.find_adjacent_parcels(parcel_id, limit)

        if not neighbors:
            return {"parcel_id": parcel_id, "count": 0, "neighbors": []}, {}

        formatted = [{
            "id": n.get("id"), "dzielnica": n.get("dzielnica"), "gmina": n.get("gmina"),
            "area_m2": n.get("area_m2"), "shared_border_m": round(n.get("shared_border_m", 0), 1),
            "is_built": n.get("is_built"),
        } for n in neighbors]

        total_border = sum(n.get("shared_border_m", 0) for n in neighbors)

        return {
            "parcel_id": parcel_id, "count": len(formatted),
            "neighbors": formatted, "total_shared_border_m": round(total_border, 1),
            "message": f"{len(formatted)} sąsiadów (łączna granica: {total_border:.0f}m)",
        }, {}

    # =========================================================================
    # PARCEL INFO TOOLS (2)
    # =========================================================================

    async def _parcel_details(self, params: Dict[str, Any]) -> ToolResult:
        """Full parcel details from PostGIS + Neo4j relations."""
        raw_ref = params.get("parcel_id", "")
        parcel_id = self._resolve_parcel_ref(raw_ref)
        if not parcel_id:
            return {"error": f"Nie rozpoznano: {raw_ref}"}, {}

        # Get full context from graph service (combines Neo4j relations + attributes)
        result = await graph_service.get_parcel_full_context(parcel_id)
        if "error" in result:
            # Fallback to PostGIS
            details = await spatial_service.get_parcel_details(parcel_id, include_geometry=True)
            if details:
                return {"parcel": details}, {}
            return {"error": f"Działka nie znaleziona: {parcel_id}"}, {}

        return result, {}

    async def _parcel_compare(self, params: Dict[str, Any]) -> ToolResult:
        """Compare 2-5 parcels side-by-side."""
        raw_ids = params.get("parcel_ids", [])
        if len(raw_ids) < 2:
            return {"error": "Min. 2 działki do porównania"}, {}

        parcels = []
        for raw in raw_ids[:5]:
            pid = self._resolve_parcel_ref(str(raw))
            if not pid:
                continue
            details = await spatial_service.get_parcel_details(pid, include_geometry=False)
            if details:
                parcels.append(details)

        if len(parcels) < 2:
            return {"error": "Nie udało się pobrać danych dla min. 2 działek"}, {}

        return {"count": len(parcels), "parcels": parcels, "comparison_ready": True}, {}

    # =========================================================================
    # MARKET TOOLS (2)
    # =========================================================================

    async def _market_prices(self, params: Dict[str, Any]) -> ToolResult:
        """District prices and parcel valuation."""
        from app.engine.price_data import DISTRICT_PRICES, SEGMENT_DESCRIPTIONS

        gmina = params.get("gmina") or (self.notepad.location.gmina if self.notepad.location else None)
        dzielnica = params.get("dzielnica") or (self.notepad.location.dzielnica if self.notepad.location else None)
        parcel_id = params.get("parcel_id")

        if not gmina:
            return {"error": "Podaj gminę lub ustaw lokalizację"}, {}

        city = gmina.title()
        if city.startswith("M. "):
            city = city[3:]

        # Lookup price data
        key = (city, dzielnica)
        if key not in DISTRICT_PRICES:
            key = (city, None)
        if key not in DISTRICT_PRICES:
            # Fuzzy match
            for (c, d), data in DISTRICT_PRICES.items():
                if c.lower() == city.lower() and d and dzielnica and d.lower() == dzielnica.lower():
                    key = (c, d)
                    break

        if key not in DISTRICT_PRICES:
            return {"error": f"Brak danych cenowych dla {city}/{dzielnica or 'średnia'}"}, {}

        data = DISTRICT_PRICES[key]
        result = {
            "city": key[0],
            "district": key[1] or "średnia",
            "price_per_m2": f"{data['min']}-{data['max']} zł/m²",
            "segment": data["segment"],
            "segment_desc": SEGMENT_DESCRIPTIONS.get(data["segment"], ""),
            "description": data["desc"],
        }

        # If parcel_id provided, estimate value
        if parcel_id:
            pid = self._resolve_parcel_ref(parcel_id)
            if pid:
                details = await spatial_service.get_parcel_details(pid, include_geometry=False)
                if details and details.get("area_m2"):
                    area = details["area_m2"]
                    result["parcel_id"] = pid
                    result["area_m2"] = area
                    result["estimated_min"] = int(area * data["min"])
                    result["estimated_max"] = int(area * data["max"])
                    result["estimated_range"] = f"{result['estimated_min']:,}-{result['estimated_max']:,} zł".replace(",", " ")

        result["note"] = "Orientacyjne ceny rynkowe. Zalecamy profesjonalną wycenę."
        return result, {}

    async def _market_map(self, params: Dict[str, Any]) -> ToolResult:
        """Generate GeoJSON map data."""
        parcel_ids = params.get("parcel_ids")
        include_geometry = params.get("include_geometry", True)

        # If no IDs given, use current search results
        if not parcel_ids and self.notepad.search_results and self.notepad.search_results.file_path:
            page_data = result_store.read_page(self.notepad.search_results.file_path, page=0, page_size=20)
            parcel_ids = [item["id"] for item in page_data.get("items", []) if item.get("id")]

        if not parcel_ids:
            return {"error": "Brak działek do wyświetlenia"}, {}

        # Resolve references
        resolved = []
        for raw in parcel_ids[:50]:
            pid = self._resolve_parcel_ref(str(raw))
            if pid:
                resolved.append(pid)

        if not resolved:
            return {"error": "Nie rozwiązano żadnych ID"}, {}

        parcels = await spatial_service.get_parcels_by_ids(resolved, include_geometry=include_geometry)
        if not parcels:
            return {"error": "Nie znaleziono działek"}, {}

        features = []
        for p in parcels:
            if p.get("geojson"):
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(p["geojson"]),
                    "properties": {
                        "id": p["id_dzialki"],
                        "gmina": p.get("gmina"),
                        "area_m2": p.get("area_m2"),
                        "quietness_score": p.get("quietness_score"),
                    }
                })

        lats = [p.get("centroid_lat") for p in parcels if p.get("centroid_lat")]
        lons = [p.get("centroid_lon") for p in parcels if p.get("centroid_lon")]

        return {
            "geojson": {"type": "FeatureCollection", "features": features},
            "center": {
                "lat": sum(lats) / len(lats) if lats else None,
                "lon": sum(lons) / len(lons) if lons else None,
            },
            "count": len(features),
        }, {}

    # =========================================================================
    # PAGINATION & NOTEPAD (2)
    # =========================================================================

    async def _results_load_page(self, params: Dict[str, Any]) -> ToolResult:
        """Load a page from JSONL results file."""
        sr = self.notepad.search_results
        if not sr or not sr.file_path:
            return {"error": "Brak wyników wyszukiwania"}, {}

        page = params.get("page", 0)
        page_size = params.get("page_size", 10)

        data = result_store.read_page(sr.file_path, page=page, page_size=page_size)

        # Update parcel index map
        for item in data.get("items", []):
            if item.get("index") and item.get("id"):
                self._parcel_index_map[item["index"]] = item["id"]

        return data, {}

    async def _notepad_update(self, params: Dict[str, Any]) -> ToolResult:
        """Update agent-managed notepad fields."""
        self.notepad.update_agent_fields(params)
        return {"status": "updated", "fields": list(params.keys())}, {}

    # =========================================================================
    # LEAD TOOLS (2)
    # =========================================================================

    async def _lead_capture(self, params: Dict[str, Any]) -> ToolResult:
        """Capture contact info."""
        email = params.get("email")
        phone = params.get("phone")
        name = params.get("name")

        if not email and not phone:
            return {"error": "Podaj email lub telefon"}, {}

        # Save to MongoDB
        lead_data = {
            "user_id": self.session_id,
            "email": email,
            "phone": phone,
            "name": name,
            "notes": params.get("notes"),
            "favorites": self.notepad.favorites,
            "location": self.notepad.location.to_dict() if self.notepad.location else None if hasattr(self.notepad.location, 'to_dict') else None,
            "created_at": datetime.now().isoformat(),
        }

        try:
            leads = await mongodb.get_collection("leads")
            if leads:
                await leads.insert_one(lead_data)
        except Exception as e:
            logger.warning(f"Failed to save lead to MongoDB: {e}")

        # Update notepad facts
        updates = {}
        if email:
            self.notepad.set_user_fact("email", email)
        if phone:
            self.notepad.set_user_fact("phone", phone)
        if name:
            self.notepad.set_user_fact("name", name)

        return {
            "status": "saved",
            "message": "Dane kontaktowe zapisane.",
            "email": email,
            "phone": phone,
        }, {}

    async def _lead_summary(self, params: Dict[str, Any]) -> ToolResult:
        """Generate session summary."""
        fmt = params.get("format", "text")
        np = self.notepad

        parts = []
        parts.append("Podsumowanie sesji")
        parts.append("=" * 30)

        if np.user_goal:
            parts.append(f"Cel: {np.user_goal}")

        if np.location and np.location.validated:
            loc = np.location
            parts.append(f"Lokalizacja: {loc.dzielnica or ''} {loc.gmina or ''}")

        if np.search_results:
            parts.append(f"Znaleziono: {np.search_results.total_count} działek")

        if np.favorites:
            parts.append(f"Ulubione: {', '.join(np.favorites[:10])}")

        if np.user_facts:
            for k, v in np.user_facts.items():
                parts.append(f"{k}: {v}")

        summary = "\n".join(parts)

        return {"summary": summary, "format": fmt}, {}
