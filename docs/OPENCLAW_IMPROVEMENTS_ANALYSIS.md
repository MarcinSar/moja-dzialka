# Analiza Ulepszeń Agenta moja-dzialka na Bazie OpenClaw

> Kompleksowy raport techniczny z rekomendacjami implementacji mechanizmów OpenClaw

---

## Executive Summary

Po szczegółowej analizie OpenClaw (jeden z najlepszych open-source agentów AI) oraz obecnej implementacji moja-dzialka, zidentyfikowałem **12 kluczowych obszarów ulepszeń** które mogą znacząco poprawić działanie naszego agenta nieruchomości.

**Główne problemy obecnej implementacji:**
1. Brak trwałej pamięci długoterminowej (agent "zapomina" między sesjami)
2. Niewystarczające opisy narzędzi (LLM nie wie kiedy ich używać)
3. Brak mechanizmu delegacji do sub-agentów (wszystko w jednym agencie)
4. Brak RAG dla kontekstu domenowego (wiedza hardcoded w core.py)
5. Zbyt płytkie wykorzystanie grafu Neo4j (brak multi-hop reasoning)

**Priorytetowe ulepszenia (Quick Wins):**
- [ ] Przebudowa opisów narzędzi (2-3 dni)
- [ ] System plików workspace (SOUL.md, MEMORY.md) (1-2 dni)
- [ ] Memory flush przed kompakcją (1 dzień)

**Strategiczne ulepszenia (Medium-term):**
- [ ] RAG dla dokumentacji działek (1 tydzień)
- [ ] Sub-agent delegation (1 tydzień)
- [ ] Advanced graph patterns (2 tygodnie)

---

## Spis Treści

1. [Porównanie Architektur](#1-porównanie-architektur)
2. [System Pamięci](#2-system-pamięci)
3. [System Narzędzi](#3-system-narzędzi)
4. [System Skills](#4-system-skills)
5. [Graph Knowledge Base](#5-graph-knowledge-base)
6. [Sub-Agent Delegation](#6-sub-agent-delegation)
7. [Context Management](#7-context-management)
8. [Approval Workflow](#8-approval-workflow)
9. [RAG Integration](#9-rag-integration)
10. [Tool Policies](#10-tool-policies)
11. [Background Execution](#11-background-execution)
12. [Plan Implementacji](#12-plan-implementacji)

---

## 1. Porównanie Architektur

### 1.1 OpenClaw vs moja-dzialka

| Aspekt | OpenClaw | moja-dzialka | Gap |
|--------|----------|--------------|-----|
| **Pamięć długoterminowa** | MEMORY.md + memory/*.md + SQLite RAG | 7-layer model (in-memory/Redis) | ⚠️ Brak persystencji markdown |
| **System prompt** | Jinja2 + dynamic files (SOUL, AGENTS, TOOLS) | Jinja2 templates (core.j2, working.j2) | ✅ Podobne |
| **Tools definitions** | 3-4 zdania + "kiedy używać" + examples | Krótkie opisy | ⚠️ Niewystarczające |
| **Skills** | SKILL.md (YAML frontmatter) + gates | Python classes + templates | ⚠️ Brak gates |
| **Sub-agents** | sessions_spawn (delegacja) | Brak | ❌ Krytyczny gap |
| **RAG** | Hybrid (Vector 70% + BM25 30%) | Vector only (Milvus) | ⚠️ Brak BM25 |
| **Graph DB** | Brak (file-based) | Neo4j 5.x (171k nodes, 5.94M rels) | ✅ Przewaga |
| **Tool policies** | Hierarchia 5 poziomów | Brak | ⚠️ Potrzebne |
| **Background exec** | yieldMs + process tool | Celery tasks | ✅ Podobne |
| **Approval flow** | ask: off/on-miss/always | propose→approve→execute | ✅ Podobne |

### 1.2 Kluczowe Lekcje z OpenClaw

**1. "Memory is identity"**
- OpenClaw traktuje pliki markdown jako "pamięć długoterminową" agenta
- SOUL.md = tożsamość (kim jestem)
- MEMORY.md = trwałe fakty (co wiem o użytkowniku)
- memory/*.md = dzienne logi (co się wydarzyło)

**2. "Tools are APIs with documentation"**
- Opisy narzędzi to DOKUMENTACJA dla LLM
- Minimum 3-4 zdania z jasnym "kiedy używać"
- Przykłady użycia (input_examples)

**3. "Skills are progressive disclosure"**
- Nie ładuj wszystkich skills do kontekstu
- Lazy loading based on requirements (bins, env, config)
- Snapshot eligible skills przy starcie sesji

**4. "Sub-agents for complex tasks"**
- Deleguj złożone zadania do wyspecjalizowanych sub-agentów
- Tańsze modele (Haiku) dla prostych sub-tasks
- Izolacja kontekstu (sub-agent nie ma dostępu do session tools)

---

## 2. System Pamięci

### 2.1 Obecna Implementacja (moja-dzialka)

```python
# 7-warstwowy model pamięci
AgentState:
├── Core (immutable DNA)
├── Working (session state, sliding window 20)
├── Semantic (user profile)
├── Episodic (history)
├── Workflow (funnel progress)
├── Preferences (dialog style)
└── Procedural (skills registry)
```

**Problem:** Cała pamięć jest in-memory lub w Redis. Po restarcie serwera lub po dłuższym czasie - utracona.

### 2.2 Rekomendacja: Hybrid Memory (OpenClaw-style)

```
~/.parcela/
├── workspace/
│   ├── SOUL.md                    # Tożsamość agenta (Constitutional)
│   ├── DOMAIN.md                  # Wiedza domenowa (ceny, dzielnice)
│   ├── TOOLS.md                   # Notatki o narzędziach
│   ├── MEMORY.md                  # Trwałe fakty o użytkownikach (global)
│   └── memory/
│       ├── 2026-02-01.md          # Dzienne logi
│       └── 2026-02-02.md
├── users/<user_id>/
│   ├── profile.md                 # Profil kupującego (Semantic)
│   ├── favorites.md               # Ulubione działki
│   └── sessions/
│       └── <session_id>.jsonl     # Transkrypty
└── knowledge/
    ├── parcels.sqlite             # Embeddings cache
    └── districts.md               # Wiedza o dzielnicach
```

### 2.3 Implementacja SOUL.md

```markdown
---
name: parcela-soul
version: "2.0"
---

# SOUL.md - Kim Jest Parcela

## Tożsamość
Jestem **Parcela** - inteligentny doradca nieruchomości specjalizujący się
w działkach budowlanych Trójmiasta. Mam dostęp do:
- 154,959 działek w bazie Neo4j
- 78,249 działek prywatnych (do kupienia!)
- 407,825 relacji sąsiedztwa

## Moje Wartości
- **Uczciwość** - Nie obiecuję czegoś czego nie mam w danych
- **Precyzja** - Używam dokładnych liczb i źródeł
- **Empatia** - Rozumiem że kupno działki to ważna decyzja

## Moje Granice
- NIE jestem prawnikiem ani notariuszem
- NIE gwarantuję cen (podaję tylko szacunki)
- NIE znam stanu prawnego działek (tylko dane katastralne)

## Workflow
1. DISCOVERY: Poznaję preferencje użytkownika
2. SEARCH: Proponuję kryteria → użytkownik zatwierdza → szukam
3. EVALUATION: Pokazuję wyniki, porównuję opcje
4. NEGOTIATION: Omawiam ceny, szacuję wartość
5. LEAD_CAPTURE: Proponuję kontakt do agenta/notariusza

## Ciągłość
Każda sesja zaczynam od nowa. Te pliki to moja pamięć.
```

### 2.4 Implementacja Memory Flush

```python
# backend/app/memory/logic/flush.py

class MemoryFlushManager:
    """Zapisz ważne fakty przed kompakcją kontekstu."""

    FLUSH_PROMPT = """
    Pre-compaction memory flush.
    Przejrzyj rozmowę i zapisz TRWAŁE fakty o użytkowniku:
    - Preferencje lokalizacyjne (np. "chce Osowę")
    - Budżet (np. "max 500k PLN")
    - Ważne informacje (np. "ma rodzinę z dziećmi")
    - Ulubione działki (np. "polubił 220611_2.0001.1234")

    Zapisz do pliku users/{user_id}/profile.md
    Jeśli nic ważnego - odpowiedz NO_REPLY.
    """

    async def maybe_flush(self, state: AgentState, token_count: int):
        """Flush memory jeśli zbliżamy się do limitu."""
        if token_count > state.core.context_limit * 0.8:
            # Uruchom "cichą turę" agenta
            await self._silent_agent_turn(state, self.FLUSH_PROMPT)

    async def _silent_agent_turn(self, state: AgentState, prompt: str):
        """Wykonaj turę agenta bez wysyłania do użytkownika."""
        response = await claude_client.messages.create(
            model="claude-3-5-haiku-20241022",  # Tani model
            messages=[{"role": "user", "content": prompt}],
            tools=[
                {"name": "write_memory_file", ...},
                {"name": "no_reply", ...}
            ]
        )
        # Wykonaj tool calls (zapis do plików)
```

---

## 3. System Narzędzi

### 3.1 Problem: Niewystarczające Opisy

**Obecny opis (moja-dzialka):**
```python
{
    "name": "execute_search",
    "description": "Wykonaj wyszukiwanie działek z zatwierdzonymi preferencjami",
    ...
}
```

**Problem:** LLM nie wie:
- KIEDY używać tego narzędzia
- Jakie są WYMAGANIA (np. preferences_approved=True)
- Co ZWRACA i jak interpretować wyniki
- Jakie są OGRANICZENIA

### 3.2 Rekomendacja: OpenClaw-style Tool Definitions

```python
AGENT_TOOLS = [
    {
        "name": "execute_search",
        "description": """
Wykonaj hybrydowe wyszukiwanie działek w bazie Neo4j + PostGIS + Milvus.

KIEDY UŻYWAĆ:
- PO zatwierdzeniu preferencji przez użytkownika (approve_search_preferences)
- GDY użytkownik prosi o wyniki wyszukiwania
- NIGDY przed zatwierdzeniem preferencji!

WYMAGANIA:
- preferences_approved MUSI być True
- Preferencje muszą zawierać przynajmniej lokalizację LUB kryteria jakościowe

CO ZWRACA:
- Lista działek (max 20) z: id, area_m2, dzielnica, ownership, scores
- Każda działka ma position (1, 2, 3...) do późniejszego referencowania
- Statystyki: total_count, shown_count, filters_applied

OGRANICZENIA:
- Max 20 wyników na raz (paginacja przez offset)
- Wymaga zatwierdzonych preferencji
- Nie zwraca działek odrzuconych przez użytkownika

PRZYKŁAD UŻYCIA:
User: "Pokaż mi te działki"
Agent: [sprawdza czy preferences_approved=True]
Agent: [wywołuje execute_search]
Agent: "Znalazłem 127 działek. Oto 20 najlepszych:
        1. Osowa, 1200m², prywatna, niezabudowana - 92/100
        2. ..."
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max liczba wyników (1-50, default 20)",
                    "default": 20
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset dla paginacji",
                    "default": 0
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["relevance", "area", "quietness", "nature", "price"],
                    "description": "Kryterium sortowania",
                    "default": "relevance"
                }
            },
            "required": []
        }
    },

    {
        "name": "propose_search_preferences",
        "description": """
Zaproponuj kryteria wyszukiwania na podstawie rozmowy z użytkownikiem.

KIEDY UŻYWAĆ:
- GDY zebrałeś wystarczające informacje o preferencjach
- GDY użytkownik podał lokalizację LUB kryteria jakościowe
- PRZED wyszukiwaniem (to jest GUARD - wymaga potwierdzenia!)

SEKWENCJA:
1. propose_search_preferences → agent proponuje kryteria
2. CZEKAJ na reakcję użytkownika ("tak", "nie", "zmień X")
3. approve_search_preferences → użytkownik zatwierdził
4. execute_search → teraz możesz szukać

CO ZWRACA:
- proposed_preferences: Dict z wszystkimi kryteriami
- missing_info: Lista brakujących informacji (opcjonalne)
- estimated_count: Szacunkowa liczba pasujących działek

WAŻNE:
- NIE wykonuj wyszukiwania po propose! Czekaj na approve!
- Użytkownik może zmodyfikować kryteria (modify_search_preferences)
- Możesz zaproponować wielokrotnie jeśli użytkownik zmienia zdanie

MAPOWANIE JĘZYKA NATURALNEGO:
- "do kupienia" → ownership_type="prywatna"
- "pod budowę domu" → build_status="niezabudowana", size_category="pod_dom"
- "cicha okolica" → quietness_categories=["bardzo_cicha", "cicha"]
- "blisko lasu" → nature_categories=["lesna", "zielona"]
- "dobry dojazd" → accessibility_categories=["doskonala", "bardzo_dobra"]
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "gmina": {"type": "string", "description": "Gmina (np. 'Gdańsk', 'Sopot')"},
                "miejscowosc": {"type": "string", "description": "Miasto/miejscowość"},
                "dzielnica": {"type": "string", "description": "Dzielnica (np. 'Osowa', 'Oliwa')"},
                "ownership_type": {
                    "type": "string",
                    "enum": ["prywatna", "publiczna", "spoldzielcza", "koscielna"],
                    "description": "Typ własności. 'prywatna' = do kupienia!"
                },
                "build_status": {
                    "type": "string",
                    "enum": ["niezabudowana", "zabudowana"],
                    "description": "Status zabudowy"
                },
                "size_category": {
                    "type": "string",
                    "enum": ["mala", "pod_dom", "duza", "bardzo_duza"],
                    "description": "Kategoria wielkości: mala(<500), pod_dom(500-2000), duza(2000-5000), bardzo_duza(>5000)"
                },
                "quietness_categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["bardzo_cicha", "cicha", "umiarkowana", "glosna"]},
                    "description": "Kategorie ciszy (można wybrać wiele)"
                },
                "nature_categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["lesna", "zielona", "miejska", "przemyslowa"]},
                    "description": "Kategorie natury"
                },
                "accessibility_categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["doskonala", "bardzo_dobra", "dobra", "ograniczona"]},
                    "description": "Kategorie dostępności komunikacyjnej"
                },
                "min_area_m2": {"type": "integer", "description": "Min powierzchnia w m²"},
                "max_area_m2": {"type": "integer", "description": "Max powierzchnia w m²"},
                "lat": {"type": "number", "description": "Szerokość geograficzna (centrum wyszukiwania)"},
                "lon": {"type": "number", "description": "Długość geograficzna (centrum wyszukiwania)"},
                "radius_m": {"type": "integer", "description": "Promień wyszukiwania w metrach"}
            },
            "required": []
        }
    },

    {
        "name": "find_adjacent_parcels",
        "description": """
Znajdź działki sąsiadujące z podaną działką.

KIEDY UŻYWAĆ:
- GDY użytkownik pyta "co jest obok tej działki?"
- GDY użytkownik chce powiększyć działkę (kupić sąsiednią)
- GDY chcesz pokazać kontekst przestrzenny

CO ZWRACA:
- Lista sąsiadów z: id, area_m2, shared_border_m, ownership
- Sortowane po długości wspólnej granicy (malejąco)

DANE W GRAFIE:
- 407,825 relacji ADJACENT_TO w Neo4j
- Średnia wspólna granica: 33.8m
- Max sąsiadów per działka: ~15-20

PRZYKŁAD:
User: "Co jest obok działki nr 3?"
Agent: [pobiera parcel_id z parcel_index_map[3]]
Agent: [wywołuje find_adjacent_parcels(parcel_id)]
Agent: "Działka graniczy z 5 innymi:
        - Na północ: 800m², prywatna (50m granicy)
        - Na wschód: 1200m², publiczna (30m granicy)
        ..."
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel_id": {
                    "type": "string",
                    "description": "ID działki (format: 220611_2.0001.1234)"
                },
                "position": {
                    "type": "integer",
                    "description": "Pozycja działki z ostatnich wyników (1, 2, 3...)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max liczba sąsiadów (default 10)",
                    "default": 10
                }
            },
            "required": []  # Wymaga parcel_id LUB position
        }
    },

    {
        "name": "resolve_location",
        "description": """
Rozwiąż nazwę lokalizacji do dokładnej gminy/dzielnicy z bazy.

KIEDY UŻYWAĆ:
- GDY użytkownik podaje nieprecyzyjną lokalizację
- GDY nazwa może mieć wiele znaczeń (np. "Oliwa" = dzielnica Gdańska)
- PRZED propose_search_preferences (aby mieć dokładne dane)

CO ROBI:
- Fuzzy matching nazw (Levenshtein + embeddings)
- Zwraca najbliższe dopasowania z confidence score
- Rozwiązuje aliasy (np. "Trójmiasto" → [Gdańsk, Sopot, Gdynia])

PRZYKŁADY:
- "Matemblewo" → {gmina: "Gdańsk", dzielnica: "Matemblewo", confidence: 0.95}
- "Osowa" → {gmina: "Gdańsk", dzielnica: "Osowa", confidence: 0.98}
- "koło ZOO" → {gmina: "Gdańsk", dzielnica: "Oliwa", context: "blisko ZOO", confidence: 0.85}
- "nad morzem" → {candidates: ["Sopot", "Gdynia Orłowo", "Gdańsk Brzeźno"], confidence: 0.7}

ZWRACA:
- resolved: Dict z gmina, miejscowosc, dzielnica
- confidence: 0.0-1.0
- alternatives: Lista alternatywnych interpretacji
- needs_clarification: bool (czy dopytać użytkownika)
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "location_text": {
                    "type": "string",
                    "description": "Tekst lokalizacji do rozwiązania"
                }
            },
            "required": ["location_text"]
        }
    }
]
```

### 3.3 Tool Input Examples (Beta)

```python
{
    "name": "get_parcel_details",
    "description": "...",
    "input_schema": {...},
    "input_examples": [
        {
            "description": "Pobierz szczegóły działki po ID",
            "input": {"parcel_id": "220611_2.0001.1234"}
        },
        {
            "description": "Pobierz szczegóły działki po pozycji z wyników",
            "input": {"position": 3}
        }
    ]
}
```

---

## 4. System Skills

### 4.1 Obecna Implementacja

```python
# backend/app/skills/_base.py
class ToolCallingSkill(Skill):
    """Skill that uses Claude tool calling."""

    async def execute(self, message: str, state: AgentState):
        prompt = self.render_prompt(state)
        # ... tool calling loop
```

### 4.2 Rekomendacja: SKILL.md Format (OpenClaw-style)

```markdown
---
# backend/app/skills/discovery/SKILL.md
name: discovery
description: "Zbieranie wymagań od użytkownika. Używaj gdy phase=DISCOVERY."
metadata:
  openclaw:
    emoji: "🔍"
    phase: DISCOVERY
    requires:
      state:
        - "current_phase == DISCOVERY"
    transitions_to: SEARCH
    max_turns: 10
---

# Discovery Skill

## Cel
Zebrać od użytkownika wystarczające informacje do wyszukiwania działek.

## Wymagane Informacje (priorytet)
1. **Lokalizacja** (KRYTYCZNE) - gmina/dzielnica/okolica
2. **Przeznaczenie** - pod dom, inwestycja, rolna
3. **Budżet** (opcjonalne) - przedział cenowy
4. **Wielkość** (opcjonalne) - min/max m²

## Strategia Konwersacji

### Otwarcie
```
Cześć! Jestem Parcela - Twój doradca ds. działek w Trójmieście.
W jakiej okolicy szukasz działki?
```

### Pytania Follow-up
- "Rozumiem, że szukasz w [lokalizacja]. Czy to ma być działka pod budowę domu?"
- "Jaki budżet rozważasz na zakup?"
- "Czy wielkość działki jest dla Ciebie istotna?"

### Kiedy Przejść do SEARCH
Gdy masz:
- Lokalizację (gmina LUB dzielnica)
- LUB przynajmniej 2 kryteria jakościowe (cisza, natura, dostępność)

## Dostępne Narzędzia
- `resolve_location` - rozwiąż nieprecyzyjną nazwę
- `get_available_locations` - pokaż dostępne gminy/dzielnice
- `count_matching_parcels_quick` - checkpoint search (ile działek pasuje?)

## Niedozwolone Akcje
- NIE wykonuj pełnego wyszukiwania (execute_search)
- NIE proponuj konkretnych działek
- NIE omawiaj cen szczegółowo

## Przykładowy Flow

```
User: "Szukam czegoś spokojnego koło Gdańska"
Agent: [resolve_location("spokojnego koło Gdańska")]
       → candidates: Osowa, Matemblewo, Kokoszki
Agent: "Rozumiem, że szukasz spokojnej okolicy. Mam kilka propozycji:
        - Osowa - cicha, przy lesie, dobra komunikacja
        - Matemblewo - bardzo spokojna, więcej zieleni
        - Kokoszki - budżetowa, trochę dalej
        Która Cię najbardziej interesuje?"
User: "Osowa brzmi dobrze"
Agent: [count_matching_parcels_quick(dzielnica="Osowa")]
       → 2,847 działek
Agent: "Świetny wybór! W Osowej mam 2,847 działek.
        Czy szukasz działki do kupienia pod budowę domu?"
User: "Tak, pod dom"
Agent: "OK! Działka prywatna, niezabudowana, w kategorii 'pod dom' (500-2000m²).
        [PRZEJŚCIE DO SEARCH - propose_search_preferences]"
```
```

### 4.3 Implementacja SkillLoader z Gates

```python
# backend/app/skills/loader.py

from pathlib import Path
import yaml
import frontmatter

class SkillLoader:
    """Load skills with progressive disclosure (OpenClaw-style)."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._cache: Dict[str, SkillDefinition] = {}

    def load_eligible_skills(self, state: AgentState) -> List[SkillDefinition]:
        """Load only skills that pass gates for current state."""
        eligible = []

        for skill_path in self.skills_dir.glob("*/SKILL.md"):
            skill_def = self._parse_skill(skill_path)

            if self._passes_gates(skill_def, state):
                eligible.append(skill_def)

        return eligible

    def _parse_skill(self, path: Path) -> SkillDefinition:
        """Parse SKILL.md with YAML frontmatter."""
        if path in self._cache:
            return self._cache[path]

        post = frontmatter.load(path)

        skill_def = SkillDefinition(
            name=post.metadata.get("name"),
            description=post.metadata.get("description"),
            emoji=post.metadata.get("metadata", {}).get("openclaw", {}).get("emoji"),
            phase=post.metadata.get("metadata", {}).get("openclaw", {}).get("phase"),
            requires=post.metadata.get("metadata", {}).get("openclaw", {}).get("requires", {}),
            transitions_to=post.metadata.get("metadata", {}).get("openclaw", {}).get("transitions_to"),
            content=post.content
        )

        self._cache[path] = skill_def
        return skill_def

    def _passes_gates(self, skill: SkillDefinition, state: AgentState) -> bool:
        """Check if skill requirements are met."""
        requires = skill.requires

        # State requirements
        if "state" in requires:
            for condition in requires["state"]:
                if not self._eval_condition(condition, state):
                    return False

        # Phase requirements
        if skill.phase and state.working.current_phase.value != skill.phase:
            return False

        return True

    def _eval_condition(self, condition: str, state: AgentState) -> bool:
        """Evaluate condition string against state."""
        # Simple eval for conditions like "current_phase == DISCOVERY"
        # In production: use safe expression parser
        local_vars = {
            "current_phase": state.working.current_phase.value,
            "preferences_approved": state.working.search_state.preferences_approved,
            "search_executed": state.working.search_state.search_executed,
            "DISCOVERY": "DISCOVERY",
            "SEARCH": "SEARCH",
            "EVALUATION": "EVALUATION",
        }
        try:
            return eval(condition, {"__builtins__": {}}, local_vars)
        except:
            return False
```

---

## 5. Graph Knowledge Base

### 5.1 Obecny Stan Neo4j

```
WĘZŁY: 171,000 (25 typów)
RELACJE: 5.94M (26 typów)
EMBEDDINGS: Text (512-dim) + Graph (256-dim)
```

**Problem:** Agent nie wykorzystuje pełnej mocy grafu:
- Brak multi-hop reasoning (np. "działki w pobliżu dobrych szkół")
- Brak community detection (klastry podobnych działek)
- Brak path finding (np. "pokaż drogę do tej działki")

### 5.2 Rekomendacja: Advanced Graph Patterns

#### A) Multi-Hop Queries

```cypher
-- "Prywatne działki pod dom w cichej okolicy blisko dobrej szkoły"
MATCH (p:Parcel)-[:HAS_OWNERSHIP]->(o:OwnershipType {id: 'prywatna'})
MATCH (p)-[:HAS_BUILD_STATUS]->(:BuildStatus {id: 'niezabudowana'})
MATCH (p)-[:HAS_SIZE]->(sz:SizeCategory) WHERE sz.id IN ['pod_dom']
MATCH (p)-[:HAS_QUIETNESS]->(q:QuietnessCategory) WHERE q.id IN ['bardzo_cicha', 'cicha']
MATCH (p)-[r:NEAR_SCHOOL]->(s:School)
WHERE r.distance_m < 1000
  AND s.name CONTAINS 'Szkoła Podstawowa'  -- Tylko SP
RETURN p.id_dzialki, p.area_m2, p.dzielnica,
       s.name AS nearest_school, r.distance_m AS school_dist,
       p.quietness_score
ORDER BY p.quietness_score DESC
LIMIT 20
```

#### B) Community Detection (Louvain)

```python
# Znajdź klastry podobnych działek
async def find_parcel_communities(self):
    """Use Louvain algorithm to find parcel clusters."""

    # 1. Project graph (tylko prywatne, niezabudowane)
    await self.neo4j.run("""
        CALL gds.graph.project(
            'parcel-similarity',
            {
                Parcel: {
                    properties: ['quietness_score', 'nature_score', 'accessibility_score']
                }
            },
            {
                ADJACENT_TO: {type: 'ADJACENT_TO', orientation: 'UNDIRECTED'},
                SIMILAR: {type: 'SIMILAR_GRAPH', orientation: 'UNDIRECTED'}
            }
        )
    """)

    # 2. Run Louvain
    result = await self.neo4j.run("""
        CALL gds.louvain.stream('parcel-similarity')
        YIELD nodeId, communityId
        WITH gds.util.asNode(nodeId) AS parcel, communityId
        RETURN communityId, collect(parcel.id_dzialki) AS parcels, count(*) AS size
        ORDER BY size DESC
        LIMIT 20
    """)

    return result
```

#### C) Graph-Based Recommendations

```python
async def recommend_similar_parcels(self, parcel_id: str, top_k: int = 10):
    """Recommend parcels using graph embeddings."""

    # 1. Get graph embedding of reference parcel
    ref_embedding = await self.neo4j.run("""
        MATCH (p:Parcel {id_dzialki: $parcel_id})
        RETURN p.graph_embedding AS embedding
    """, parcel_id=parcel_id)

    # 2. Find similar by cosine similarity (Neo4j vector index)
    similar = await self.neo4j.run("""
        CALL db.index.vector.queryNodes(
            'parcel_graph_embedding_idx',
            $top_k,
            $embedding
        )
        YIELD node, score
        WHERE node.id_dzialki <> $parcel_id
          AND node.ownership_type = 'prywatna'
        RETURN node.id_dzialki, node.dzielnica, node.area_m2, score
        ORDER BY score DESC
    """, top_k=top_k, embedding=ref_embedding, parcel_id=parcel_id)

    return similar
```

### 5.3 Nowe Narzędzia Graph-Based

```python
NEW_GRAPH_TOOLS = [
    {
        "name": "find_parcels_near_poi_by_name",
        "description": """
Znajdź działki w pobliżu konkretnego POI po nazwie.

KIEDY UŻYWAĆ:
- "działki blisko szkoły nr 45"
- "działki koło przystanku Osowa PKM"
- "działki przy lesie Trójmiejskim"

PRZYKŁAD:
User: "Szukam czegoś blisko przystanku SKM Osowa"
Agent: [find_parcels_near_poi_by_name(poi_name="Osowa", poi_type="bus_stop", max_distance=500)]
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "poi_name": {"type": "string", "description": "Nazwa lub fragment nazwy POI"},
                "poi_type": {"type": "string", "enum": ["school", "shop", "bus_stop", "hospital", "forest", "water"]},
                "max_distance_m": {"type": "integer", "default": 1000}
            },
            "required": ["poi_name"]
        }
    },

    {
        "name": "find_cluster_parcels",
        "description": """
Znajdź działki w tym samym klastrze (community) co podana działka.

KIEDY UŻYWAĆ:
- "pokaż podobne działki w okolicy"
- "jakie inne opcje są w tej części miasta?"
- Gdy użytkownik polubił działkę i chce więcej takich

ZWRACA:
- Działki z tego samego community (Louvain algorithm)
- Posortowane po similarity score
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel_id": {"type": "string"},
                "position": {"type": "integer"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": []
        }
    },

    {
        "name": "explain_parcel_neighborhood",
        "description": """
Wygeneruj narracyjny opis okolicy działki.

KIEDY UŻYWAĆ:
- "opowiedz mi o tej okolicy"
- "jak tam jest?"
- "czy to dobre miejsce do mieszkania?"

ZWRACA:
- Structured narrative z: cisza, natura, dostępność, POI, sąsiedzi
- Oparte na danych z grafu (nie halucynacje!)
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "parcel_id": {"type": "string"},
                "position": {"type": "integer"}
            },
            "required": []
        }
    }
]
```

---

## 6. Sub-Agent Delegation

### 6.1 Problem

Obecny agent robi wszystko sam:
- Zbiera preferencje
- Wykonuje wyszukiwania
- Analizuje wyniki
- Generuje opisy
- Szacuje ceny

**Konsekwencje:**
- Długie odpowiedzi (jeden model robi wszystko)
- Wysokie koszty (Claude Sonnet dla wszystkiego)
- Brak specjalizacji

### 6.2 Rekomendacja: Sub-Agent Architecture (OpenClaw-style)

```
┌─────────────────────────────────────────────────────────────┐
│                    ROOT AGENT (Claude Sonnet 4)             │
│              Orchestrator, routing, user interaction        │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┬───────────────┐
          │               │               │               │
          ▼               ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Discovery  │   │   Search    │   │  Analyst    │   │  Narrator   │
│    Agent    │   │    Agent    │   │    Agent    │   │    Agent    │
│  (Haiku)    │   │  (Haiku)    │   │  (Sonnet)   │   │  (Haiku)    │
│             │   │             │   │             │   │             │
│ - Pytania   │   │ - Cypher    │   │ - Porównania│   │ - Opisy     │
│ - Walidacja │   │ - RRF       │   │ - Ceny      │   │ - Narracje  │
│ - Entities  │   │ - Ranking   │   │ - Trendy    │   │ - Podsumow. │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

### 6.3 Implementacja sessions_spawn

```python
# backend/app/engine/sub_agents.py

class SubAgentManager:
    """Manage sub-agent delegation (OpenClaw sessions_spawn pattern)."""

    # Model selection per task complexity
    MODEL_MAP = {
        "discovery": "claude-3-5-haiku-20241022",    # Proste pytania
        "search": "claude-3-5-haiku-20241022",       # Tool execution
        "analysis": "claude-sonnet-4-20250514",      # Complex reasoning
        "narration": "claude-3-5-haiku-20241022",    # Text generation
    }

    async def spawn_sub_agent(
        self,
        task: str,
        task_type: str,
        context: Dict[str, Any],
        timeout_seconds: int = 60
    ) -> Dict[str, Any]:
        """Spawn a sub-agent for delegated task."""

        model = self.MODEL_MAP.get(task_type, "claude-3-5-haiku-20241022")

        # Build sub-agent prompt
        prompt = self._build_sub_agent_prompt(task, task_type, context)

        # Execute with timeout
        try:
            response = await asyncio.wait_for(
                self._run_sub_agent(model, prompt, task_type),
                timeout=timeout_seconds
            )
            return {"status": "completed", "result": response}
        except asyncio.TimeoutError:
            return {"status": "timeout", "partial": None}

    def _build_sub_agent_prompt(self, task: str, task_type: str, context: Dict) -> str:
        """Build specialized prompt for sub-agent."""

        base = f"""
Jesteś wyspecjalizowanym sub-agentem typu '{task_type}'.

TWOJE ZADANIE:
{task}

KONTEKST:
{json.dumps(context, ensure_ascii=False, indent=2)}

OGRANICZENIA:
- Odpowiedz TYLKO na zadane pytanie
- NIE prowadź rozmowy z użytkownikiem
- NIE używaj narzędzi sesji (sessions_*)
- Zwróć STRUKTURALNY wynik (JSON jeśli możliwe)
"""
        return base

    async def _run_sub_agent(self, model: str, prompt: str, task_type: str):
        """Execute sub-agent with appropriate tools."""

        # Sub-agent tools (restricted)
        tools = self._get_sub_agent_tools(task_type)

        response = await claude_client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            tools=tools
        )

        return self._process_response(response)

    def _get_sub_agent_tools(self, task_type: str) -> List[Dict]:
        """Get restricted tool set for sub-agent."""

        # Sub-agents cannot spawn other sub-agents!
        restricted = ["sessions_spawn", "sessions_send", "sessions_list"]

        if task_type == "search":
            return [t for t in SEARCH_TOOLS if t["name"] not in restricted]
        elif task_type == "analysis":
            return [t for t in ANALYSIS_TOOLS if t["name"] not in restricted]
        elif task_type == "narration":
            return []  # No tools, just text generation
        else:
            return []
```

### 6.4 Przykład Użycia w Root Agent

```python
# W property_advisor_agent.py

async def handle_complex_comparison(self, state: AgentState, parcels: List[str]):
    """Delegate complex comparison to analyst sub-agent."""

    # Spawn analyst sub-agent
    result = await self.sub_agent_manager.spawn_sub_agent(
        task=f"""
Porównaj te {len(parcels)} działek pod kątem:
1. Wartość za pieniądze (cena/m² vs jakość lokalizacji)
2. Potencjał inwestycyjny (MPZP, sąsiedztwo)
3. Lifestyle fit (cisza, natura, komunikacja)

Zwróć ranking 1-{len(parcels)} z uzasadnieniem.
""",
        task_type="analysis",
        context={
            "parcels": parcels,
            "user_preferences": state.working.search_state.approved_preferences,
            "price_data": self.price_data.get_relevant_prices(parcels)
        },
        timeout_seconds=120
    )

    if result["status"] == "completed":
        return result["result"]
    else:
        # Fallback: simple ranking
        return self._simple_ranking(parcels)
```

---

## 7. Context Management

### 7.1 Problem: Context Overflow

Obecna implementacja:
- `conversation_buffer` = sliding window (ostatnie 20 wiadomości)
- `compressor.py` = summarization gdy stale

**Problem:** Brak memory flush przed kompakcją. Ważne informacje mogą zostać utracone.

### 7.2 Rekomendacja: Compaction with Memory Flush

```python
# backend/app/memory/logic/compaction.py

class ContextCompactionManager:
    """Manage context compaction with memory flush (OpenClaw-style)."""

    SOFT_THRESHOLD_TOKENS = 150_000  # 75% of 200k limit
    HARD_THRESHOLD_TOKENS = 180_000  # 90% - force compaction

    async def maybe_compact(self, state: AgentState, token_count: int) -> AgentState:
        """Compact context if approaching limit."""

        if token_count < self.SOFT_THRESHOLD_TOKENS:
            return state

        # 1. MEMORY FLUSH - zapisz ważne fakty
        if token_count >= self.SOFT_THRESHOLD_TOKENS:
            state = await self._memory_flush(state)

        # 2. COMPACTION - jeśli nadal za dużo
        if token_count >= self.HARD_THRESHOLD_TOKENS:
            state = await self._hard_compact(state)

        return state

    async def _memory_flush(self, state: AgentState) -> AgentState:
        """Silent agent turn to save durable memories."""

        flush_prompt = """
Pre-compaction memory flush. Przejrzyj rozmowę i zapisz TRWAŁE fakty:

O UŻYTKOWNIKU:
- Preferencje lokalizacyjne
- Budżet
- Ważne informacje osobiste

O WYSZUKIWANIU:
- Zatwierdzone kryteria
- Ulubione działki
- Odrzucone działki
- Feedback na wyniki

Zapisz do odpowiedniego pliku:
- users/{user_id}/profile.md - profil użytkownika
- users/{user_id}/favorites.md - ulubione działki

Jeśli nic ważnego - odpowiedz NO_REPLY.
"""

        # Run silent turn
        response = await self._silent_agent_turn(state, flush_prompt)

        # Execute any write_memory_file tool calls
        for tool_call in response.tool_calls:
            if tool_call.name == "write_memory_file":
                await self._write_memory_file(
                    state.core.user_id,
                    tool_call.args["path"],
                    tool_call.args["content"]
                )

        return state

    async def _hard_compact(self, state: AgentState) -> AgentState:
        """Force compaction - summarize old messages."""

        # Keep last 10 messages
        recent = state.working.conversation_buffer[-10:]
        old = state.working.conversation_buffer[:-10]

        # Summarize old messages
        summary = await self._summarize_messages(old)

        # Create summary message
        summary_msg = Message(
            role="system",
            content=f"[PODSUMOWANIE WCZEŚNIEJSZEJ ROZMOWY]\n{summary}"
        )

        # Update state
        state.working.conversation_buffer = [summary_msg] + recent

        return state
```

---

## 8. RAG Integration

### 8.1 Problem: Brak RAG dla Wiedzy Domenowej

Obecna implementacja:
- Wiedza domenowa hardcoded w `core.py` (price_segments, district_knowledge)
- Vector search tylko dla działek (Milvus)
- Brak BM25 (keyword search)

### 8.2 Rekomendacja: Hybrid RAG (OpenClaw-style)

```python
# backend/app/services/knowledge_rag.py

class HybridKnowledgeRAG:
    """Hybrid RAG for domain knowledge (Vector + BM25)."""

    VECTOR_WEIGHT = 0.7
    BM25_WEIGHT = 0.3

    def __init__(self, sqlite_path: Path):
        self.db = sqlite3.connect(sqlite_path)
        self._init_schema()
        self.embedder = SentenceTransformer('distiluse-base-multilingual-cased-v1')

    def _init_schema(self):
        """Initialize SQLite schema for RAG."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,     -- 'districts', 'prices', 'mpzp', etc
                path TEXT NOT NULL,       -- file path
                text TEXT NOT NULL,
                embedding BLOB NOT NULL,  -- 512-dim float32
                updated_at INTEGER
            )
        """)

        # BM25 FTS5 virtual table
        self.db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(id, text, content='chunks', content_rowid='rowid')
        """)

    async def search(self, query: str, top_k: int = 6, min_score: float = 0.35) -> List[Dict]:
        """Hybrid search: Vector + BM25."""

        # 1. Vector search
        query_embedding = self.embedder.encode(query)
        vector_results = self._vector_search(query_embedding, top_k * 2)

        # 2. BM25 search
        bm25_results = self._bm25_search(query, top_k * 2)

        # 3. Reciprocal Rank Fusion
        combined = self._rrf_fusion(vector_results, bm25_results)

        # 4. Filter by min_score
        filtered = [r for r in combined if r["score"] >= min_score]

        return filtered[:top_k]

    def _vector_search(self, embedding: np.ndarray, top_k: int) -> List[Dict]:
        """Cosine similarity search."""
        results = []

        for row in self.db.execute("SELECT id, text, embedding FROM chunks"):
            chunk_emb = np.frombuffer(row[2], dtype=np.float32)
            score = np.dot(embedding, chunk_emb) / (
                np.linalg.norm(embedding) * np.linalg.norm(chunk_emb)
            )
            results.append({"id": row[0], "text": row[1], "score": float(score)})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _bm25_search(self, query: str, top_k: int) -> List[Dict]:
        """FTS5 BM25 search."""
        results = []

        for row in self.db.execute("""
            SELECT id, text, bm25(chunks_fts) AS score
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """, (query, top_k)):
            results.append({"id": row[0], "text": row[1], "score": -row[2]})

        return results

    def _rrf_fusion(self, vector_results: List, bm25_results: List, k: int = 60) -> List[Dict]:
        """Reciprocal Rank Fusion."""
        scores = {}

        for rank, r in enumerate(vector_results):
            scores[r["id"]] = scores.get(r["id"], 0) + self.VECTOR_WEIGHT / (rank + k)

        for rank, r in enumerate(bm25_results):
            scores[r["id"]] = scores.get(r["id"], 0) + self.BM25_WEIGHT / (rank + k)

        # Get texts
        id_to_text = {r["id"]: r["text"] for r in vector_results + bm25_results}

        combined = [
            {"id": id, "text": id_to_text[id], "score": score}
            for id, score in scores.items()
        ]
        combined.sort(key=lambda x: x["score"], reverse=True)

        return combined
```

### 8.3 Indeksowanie Wiedzy Domenowej

```python
# backend/app/services/knowledge_indexer.py

class KnowledgeIndexer:
    """Index domain knowledge for RAG."""

    SOURCES = {
        "districts": "docs/RAPORT_CENY_GRUNTOW_TROJMIASTO_2025.md",
        "mpzp": "docs/KNOWLEDGE_BASE_POG.md",
        "parcels": "docs/DATA_PARCELS.md",
        "bdot10k": "docs/DATA_BDOT10K.md",
    }

    async def index_all(self, rag: HybridKnowledgeRAG):
        """Index all knowledge sources."""

        for source_name, path in self.SOURCES.items():
            content = Path(path).read_text()
            chunks = self._chunk_markdown(content)

            for i, chunk in enumerate(chunks):
                chunk_id = f"{source_name}:{i}"
                embedding = rag.embedder.encode(chunk)

                rag.db.execute("""
                    INSERT OR REPLACE INTO chunks (id, source, path, text, embedding, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (chunk_id, source_name, path, chunk, embedding.tobytes(), int(time.time())))

        rag.db.commit()

        # Rebuild FTS index
        rag.db.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        rag.db.commit()

    def _chunk_markdown(self, content: str, max_chars: int = 1000) -> List[str]:
        """Chunk markdown by headers and paragraphs."""
        chunks = []
        current_chunk = ""

        for line in content.split("\n"):
            if line.startswith("#") and current_chunk:
                # New header - save current chunk
                chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            elif len(current_chunk) + len(line) > max_chars:
                # Chunk too long - split
                chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks
```

### 8.4 Narzędzie memory_search

```python
{
    "name": "search_domain_knowledge",
    "description": """
Przeszukaj bazę wiedzy domenowej (dokumenty, raporty, dane).

KIEDY UŻYWAĆ:
- Gdy użytkownik pyta o ogólne informacje o rynku
- Gdy potrzebujesz kontekstu o dzielnicach/cenach
- Gdy chcesz zweryfikować fakty przed odpowiedzią

ŹRÓDŁA:
- districts: Raport cen gruntów Trójmiasta 2025
- mpzp: Wiedza o strefach planistycznych (POG)
- parcels: Dokumentacja danych działek
- bdot10k: Dokumentacja warstw topograficznych

ZWRACA:
- Fragmenty dokumentów posortowane po relevance
- Source i ścieżkę do pliku
- Similarity score
""",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Pytanie / fraza do wyszukania"},
            "sources": {
                "type": "array",
                "items": {"type": "string", "enum": ["districts", "mpzp", "parcels", "bdot10k"]},
                "description": "Źródła do przeszukania (domyślnie: wszystkie)"
            },
            "top_k": {"type": "integer", "default": 6}
        },
        "required": ["query"]
    }
}
```

---

## 9. Tool Policies

### 9.1 Problem: Brak Kontroli Dostępu

Obecna implementacja:
- Wszystkie narzędzia dostępne dla wszystkich
- Brak per-phase restrictions
- Brak per-user restrictions (freemium)

### 9.2 Rekomendacja: Hierarchical Tool Policies

```python
# backend/app/engine/tool_policies.py

class ToolPolicyManager:
    """Manage tool access policies (OpenClaw-style)."""

    # Base profiles
    PROFILES = {
        "discovery": ["resolve_location", "get_available_locations", "count_matching_parcels_quick"],
        "search": ["propose_search_preferences", "approve_search_preferences", "execute_search", "modify_search_preferences"],
        "evaluation": ["get_parcel_details", "get_parcel_neighborhood", "find_adjacent_parcels", "find_similar_parcels"],
        "analysis": ["estimate_parcel_value", "get_district_prices", "search_domain_knowledge"],
        "premium": ["execute_search_unlimited", "export_results", "generate_report"],
    }

    # Phase-based restrictions
    PHASE_POLICIES = {
        FunnelPhase.DISCOVERY: {
            "allow": ["discovery", "search"],
            "deny": ["premium"]
        },
        FunnelPhase.SEARCH: {
            "allow": ["search", "evaluation"],
            "deny": ["premium"]
        },
        FunnelPhase.EVALUATION: {
            "allow": ["evaluation", "analysis"],
            "deny": []
        },
    }

    # User-based restrictions (freemium)
    USER_POLICIES = {
        "free": {
            "deny": ["premium"],
            "limits": {
                "execute_search": 5,  # Max 5 searches per session
                "get_parcel_details": 10,
            }
        },
        "paid": {
            "allow": ["premium"],
            "limits": {}
        }
    }

    def get_allowed_tools(self, state: AgentState) -> List[str]:
        """Get tools allowed for current state."""

        allowed = set()
        denied = set()

        # 1. Phase-based
        phase_policy = self.PHASE_POLICIES.get(state.working.current_phase, {})
        for profile in phase_policy.get("allow", []):
            allowed.update(self.PROFILES.get(profile, []))
        for profile in phase_policy.get("deny", []):
            denied.update(self.PROFILES.get(profile, []))

        # 2. User-based (freemium)
        user_tier = self._get_user_tier(state)
        user_policy = self.USER_POLICIES.get(user_tier, {})
        for profile in user_policy.get("allow", []):
            allowed.update(self.PROFILES.get(profile, []))
        for profile in user_policy.get("deny", []):
            denied.update(self.PROFILES.get(profile, []))

        # 3. Apply limits
        limits = user_policy.get("limits", {})
        for tool, limit in limits.items():
            usage = state.working.tool_usage.get(tool, 0)
            if usage >= limit:
                denied.add(tool)

        # Deny wins
        return list(allowed - denied)

    def _get_user_tier(self, state: AgentState) -> str:
        """Get user tier (free/paid)."""
        if state.semantic.has_paid:
            return "paid"
        return "free"
```

---

## 10. Background Execution

### 10.1 Obecna Implementacja

```python
# Celery tasks for LiDAR processing
# backend/app/tasks/lidar_tasks.py
```

### 10.2 Rekomendacja: yieldMs Pattern

```python
# backend/app/engine/background_executor.py

class BackgroundExecutor:
    """Execute long-running tools with auto-background (OpenClaw yieldMs)."""

    YIELD_MS = 10_000  # 10 seconds before auto-background

    async def execute_with_yield(
        self,
        tool_name: str,
        params: Dict,
        executor: ToolExecutor
    ) -> Dict:
        """Execute tool with automatic backgrounding."""

        try:
            result = await asyncio.wait_for(
                executor.execute(tool_name, params),
                timeout=self.YIELD_MS / 1000
            )
            return {"status": "completed", "result": result}

        except asyncio.TimeoutError:
            # Background the task
            task_id = str(uuid.uuid4())

            # Start background execution
            asyncio.create_task(
                self._background_execute(task_id, tool_name, params, executor)
            )

            return {
                "status": "backgrounded",
                "task_id": task_id,
                "message": f"Zadanie trwa dłużej niż oczekiwano. ID: {task_id}"
            }

    async def _background_execute(
        self,
        task_id: str,
        tool_name: str,
        params: Dict,
        executor: ToolExecutor
    ):
        """Execute in background and store result."""
        try:
            result = await executor.execute(tool_name, params)
            await self._store_result(task_id, {"status": "completed", "result": result})
        except Exception as e:
            await self._store_result(task_id, {"status": "error", "error": str(e)})

    async def poll_result(self, task_id: str) -> Optional[Dict]:
        """Poll for background task result."""
        return await redis.get(f"bg_task:{task_id}")
```

---

## 11. Approval Workflow (Guard Patterns)

### 11.1 Obecna Implementacja

```python
# propose → approve → execute flow
SearchState:
    preferences_proposed: bool
    preferences_approved: bool
    search_executed: bool
```

### 11.2 Ulepszenie: Explicit Guard Definitions

```python
# backend/app/engine/guards.py

class ToolGuard:
    """Define guards for tool execution (OpenClaw pattern)."""

    GUARDS = {
        "execute_search": {
            "requires": ["preferences_approved"],
            "error_message": "Nie możesz wyszukiwać bez zatwierdzonych preferencji. Użyj najpierw propose_search_preferences, potem approve_search_preferences.",
        },
        "approve_search_preferences": {
            "requires": ["preferences_proposed"],
            "error_message": "Nie ma preferencji do zatwierdzenia. Użyj najpierw propose_search_preferences.",
        },
        "get_parcel_details": {
            "requires_any": ["search_executed", "has_parcel_id"],
            "error_message": "Nie ma działek do pokazania. Najpierw wykonaj wyszukiwanie.",
        },
        "estimate_parcel_value": {
            "requires": ["has_parcel_context"],
            "requires_phase": ["EVALUATION", "NEGOTIATION"],
            "error_message": "Szacowanie wartości dostępne po wybraniu działki.",
        },
    }

    def check_guard(self, tool_name: str, state: AgentState) -> Tuple[bool, Optional[str]]:
        """Check if tool can be executed."""

        guard = self.GUARDS.get(tool_name)
        if not guard:
            return True, None

        # Check requires (AND)
        if "requires" in guard:
            for req in guard["requires"]:
                if not self._check_requirement(req, state):
                    return False, guard["error_message"]

        # Check requires_any (OR)
        if "requires_any" in guard:
            if not any(self._check_requirement(req, state) for req in guard["requires_any"]):
                return False, guard["error_message"]

        # Check phase
        if "requires_phase" in guard:
            if state.working.current_phase.value not in guard["requires_phase"]:
                return False, guard["error_message"]

        return True, None

    def _check_requirement(self, req: str, state: AgentState) -> bool:
        """Check single requirement."""
        if req == "preferences_proposed":
            return state.working.search_state.preferences_proposed
        elif req == "preferences_approved":
            return state.working.search_state.preferences_approved
        elif req == "search_executed":
            return state.working.search_state.search_executed
        elif req == "has_parcel_id":
            return len(state.working.search_state.parcel_index_map) > 0
        elif req == "has_parcel_context":
            return bool(state.working.temp_vars.get("current_parcel"))
        return False
```

---

## 12. Plan Implementacji

### Faza 1: Quick Wins (1 tydzień)

| Zadanie | Priorytet | Czas | Wpływ |
|---------|-----------|------|-------|
| Przebudowa opisów narzędzi | P0 | 2-3 dni | 🔥🔥🔥 Agent lepiej używa tools |
| Guard patterns (explicit) | P0 | 1 dzień | 🔥🔥 Mniej błędów sekwencji |
| Memory flush przed kompakcją | P1 | 1 dzień | 🔥🔥 Trwała pamięć |

### Faza 2: Core Improvements (2 tygodnie)

| Zadanie | Priorytet | Czas | Wpływ |
|---------|-----------|------|-------|
| SOUL.md + workspace files | P1 | 2 dni | 🔥🔥 Lepsza tożsamość agenta |
| Hybrid RAG (Vector + BM25) | P1 | 3-4 dni | 🔥🔥🔥 Wiedza domenowa |
| Tool policies (freemium) | P1 | 2 dni | 🔥🔥 Monetyzacja |

### Faza 3: Advanced Features (3-4 tygodnie)

| Zadanie | Priorytet | Czas | Wpływ |
|---------|-----------|------|-------|
| Sub-agent delegation | P2 | 5 dni | 🔥🔥 Specjalizacja, koszty |
| Advanced graph patterns | P2 | 5 dni | 🔥🔥🔥 Multi-hop reasoning |
| SKILL.md format + loader | P2 | 3 dni | 🔥 Modularność |
| Background execution (yieldMs) | P3 | 2 dni | 🔥 UX dla długich operacji |

### Metryki Sukcesu

| Metryka | Baseline | Target | Pomiar |
|---------|----------|--------|--------|
| Tool call accuracy | ~70% | 90%+ | % poprawnych wywołań |
| Search completion rate | ~50% | 80%+ | % sesji z execute_search |
| Lead conversion | ~5% | 15%+ | % sesji z kontaktem |
| Context utilization | ~60% | 85%+ | % kontekstu wykorzystanego |
| User satisfaction | N/A | 4.5/5 | Ankiety po sesji |

---

## Podsumowanie

OpenClaw oferuje wiele sprawdzonych wzorców które możemy zaadaptować do moja-dzialka:

1. **Memory as files** - SOUL.md, MEMORY.md, memory/*.md
2. **Rich tool descriptions** - 3-4 zdania + "kiedy używać" + przykłady
3. **Progressive disclosure** - Skills z gates (requirements)
4. **Sub-agent delegation** - Specjalizowane agenty dla różnych zadań
5. **Hybrid RAG** - Vector (70%) + BM25 (30%)
6. **Memory flush** - Zapis przed kompakcją
7. **Tool policies** - Hierarchia kontroli dostępu
8. **Guard patterns** - Explicit requirements dla tools

**Najważniejsze quick wins:**
- Przebudowa opisów narzędzi (2-3 dni, ogromny wpływ)
- Guard patterns (1 dzień, eliminacja błędów)
- Memory flush (1 dzień, trwała pamięć)

---

*Raport przygotowany: 2026-02-02*
*Autor: Claude Opus 4.5 na podstawie analizy OpenClaw i moja-dzialka*
