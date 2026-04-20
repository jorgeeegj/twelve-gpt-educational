# Briefing para Opus — Basic Stats Analyst: Análisis de Phase 6 y próximos pasos

## Contexto del proyecto

Estamos construyendo un agente LLM que responde preguntas en lenguaje natural sobre estadísticas
de la Premier League 2024-25. El objetivo principal (dado por Agust, el instructor del curso):
**"Answer any factual question about the Premier League 2024-25 season using available data."**

### Stack técnico
- **Agente**: `src/basic_stats/agent.py` — `BasicStatsAgent` usa OpenAI Responses API
  (`client.responses.create`) con `previous_response_id` para conversación multi-turn
- **4 mother tools**: `query_player_stats`, `query_team_stats`, `query_ranking`, `get_league_standings`
- **Base de datos**: DuckDB + Parquet — 5 vistas: `players_summary`, `teams_summary`,
  `player_match_stats`, `player_match_event_stats`, `team_match_stats`
- **Fuzzy resolution**: embeddings `text-embedding-3-large` en tabla DuckDB VSS con HNSW index.
  `fuzzy_resolve_entity(user_input, entity_type)` — threshold 0.75
- **Benchmark**: `evals/agent_benchmark.py` con jueces de faithfulness (determinístico),
  naturalness y completeness (LLM-as-judge)

### Archivos clave
- `src/basic_stats/agent.py` — loop principal, `_MAX_ITERATIONS=6`
- `src/basic_stats/agent_tools.py` — 4 mother tools + herramientas internas
- `src/basic_stats/agent_tool_schemas.py` — schemas de tools para Responses API
- `src/basic_stats/duckdb_manager.py` — queries, `fuzzy_resolve_entity`, `store_entity_embeddings`
- `src/basic_stats/prompts/agent_system.yaml` — system prompt (142 líneas)
- `src/basic_stats/agent_prompt.py` — `build_system_prompt(duck)` inyecta contexto dinámico

---

## Lo que se hizo en Phase 6 (Random Question Robustness)

Phase 6 implementó:
1. `store_entity_embeddings()` — genera y persiste embeddings para 444 jugadores y 20 equipos
2. `fuzzy_resolve_entity(user_input, entity_type)` — resolución semántica antes de la query DB
3. Wiring en 5 entry points de `agent_tools.py`
4. Fix del schema de posiciones en `agent_tool_schemas.py` (ej: `'Defender'` → `'Central Defender'`)
5. 21 preguntas random en `evals/random_questions.json` (7 por Ricardo, 7 por Álvaro, 7 por Jorge)

**El benchmark inicial reportó 21/21 pero era falso** — había un bug: una sola instancia
de `BasicStatsAgent` compartida entre 10 workers paralelos corrompía `_last_response_id`,
causando errores 400 en todas las preguntas. El fix fue crear una instancia por pregunta
dentro del executor.

**Resultado honesto post-fix**: `evals/runs/2026-04-19_21-37-16__agent/results.json`
El benchmark reporta 21/21 faithfulness — pero **ese gate no mide nada real** porque
`random_questions.json` no tiene `expected` values. Faithfulness pasa trivialmente
cuando no hay números esperados para comparar.

---

## Los 3 tipos de problemas identificados en las respuestas

Tras análisis manual de `evals/runs/2026-04-19_21-37-16__agent/results.json`:

### Tipo 1 — Datos que no existen en el dataset
El agente no puede responder lo que no tiene. No hay fix de código posible.

**Ejemplo — RQ_12**:
```
Pregunta: "How many yellow cards has Wolves received this season?"
Respuesta: "Wolverhampton Wanderers have 478 fouls committed this season.
           Note: Yellow cards aren't provided as a direct team-level stat in this dataset."
```
El agente devuelve fouls en lugar de yellow cards. Honesto pero no responde.
**Fix**: O se añaden los datos al dataset, o el agente debe decir explícitamente
"ese dato no está disponible" sin intentar sustituir con otro stat.

---

### Tipo 2 — Bug de resolución de entidades (fuzzy resolve falla en team filter)
El fuzzy resolve funciona para nombres de jugadores pero falla silenciosamente
cuando se usa como filtro de equipo dentro de un ranking.

**Ejemplo — RQ_09**:
```
Pregunta: "Which Nottingham Forest player has the most assists?"
Respuesta: "the data available here doesn't seem to include Nottingham Forest players...
           the top assist figure returned is Mohamed Salah with 16 assists for Liverpool."
```
Paradójicamente, RQ_07 funcionó:
```
Pregunta: "How many goals has Chris Wood scored this season?"
Respuesta: "Chris Wood has scored 20 goals this season (for Nottingham Forest)."
```
La diferencia: RQ_07 busca un jugador por nombre (fuzzy resolve sobre player_name),
RQ_09 filtra por equipo dentro de un ranking (fuzzy resolve sobre team_name como filtro).
El agente probablemente pasó "Nottingham Forest" directamente sin resolver, o lo resolvió
a una cadena que no matchea exactamente con el DB.

**Para investigar**: Correr RQ_09 en aislamiento con logging para ver qué tool args
envía el LLM y qué devuelve DuckDB.

---

### Tipo 3 — Respuestas estadísticamente sospechosas (p90 sin mínimo de minutos)
El agente devuelve datos técnicamente correctos del DB pero sin un filtro mínimo
de minutos jugados. Un jugador con 100 minutos puede liderar en p90 vs uno con 2000.

**Ejemplo — RQ_06**:
```
Pregunta: "Which winger has the most key passes per 90 this season?"
Respuesta: "R. Nelson (Fulham) — 1.53 key passes per 90 this season."
```
Reece Nelson probablemente tiene pocos minutos y un solo partido excepcional
que infla su p90. No es el "mejor winger" en sentido real.

**Ejemplo — RQ_13**:
```
Pregunta: "Which center back has the most clearances per 90?"
Respuesta: "Jorge Cuenca (Fulham) — 3.10 clearances per 90 (377 minutes across 8 matches)."
```
8 partidos / 377 minutos es una muestra pequeña. Cuenca probablemente lidera p90
por un par de partidos excepcionales, no por ser consistentemente el mejor.

**Fix**: El tool `query_ranking` necesita un parámetro `min_minutes` (ej: 900 minutos
= ~10 partidos completos) que se aplique al filtrar rankings p90. El LLM debe
incluirlo por defecto en queries p90, o el tool debe aplicar un mínimo hardcodeado.

---

## Resumen del estado real de Phase 6

| Categoría | Cantidad |
|-----------|----------|
| Claramente correctas | 13/21 |
| Sospechosas (p90 sin min_minutes) | 4/21 — RQ_06, RQ_13, RQ_19, RQ_10 |
| Fallos claros | 2/21 — RQ_09 (team filter), RQ_12 (datos inexistentes) |
| Parcialmente correctas | 2/21 — RQ_11 (nombre duplicado raro), RQ_18 (Trent se fue en enero) |

Phase 6 **no está cerrada** — 2 fallos claros identificados.

---

## Preguntas concretas para Opus

1. **RQ_09 (Tipo 2)**: ¿Cómo debuggear qué tool args envía el LLM cuando filtra por
   team_name en un ranking? ¿El fix está en `fuzzy_resolve_entity` (threshold),
   en `agent_tools.py` (cómo se aplica el filtro), o en el schema de la tool?

2. **RQ_06 / RQ_13 (Tipo 3)**: ¿Dónde es mejor aplicar el `min_minutes` filter para
   rankings p90 — en el schema de la tool (como parámetro opcional con default),
   en `agent_tools.py` (hardcodeado), o en el system prompt (instrucción al LLM)?
   ¿Cuál es el valor correcto para una temporada de 38 GWs (≈3420 minutos totales)?

3. **Phase 7 pendiente**: El plan de Phase 7 existe en `.planning/phase-7/PLAN.md`.
   El step más crítico es el 4-turn chain de Agust:
   "Goals Haaland?" → "Against top 6?" → "Is that more than the rest?" → "What about per 90?"
   Turn 4 probablemente falla porque `query_player_match_context()` en `duckdb_manager.py`
   no devuelve `minutes_in_subset` cuando hay filtros activos. ¿Cómo añadirlo limpiamente?

---

## Archivos de referencia

- Resultados del benchmark: `evals/runs/2026-04-19_21-37-16__agent/results.json`
- Plan Phase 7: `.planning/phase-7/PLAN.md`
- Roadmap completo: `.planning/ROADMAP.md`
- Requisitos: `.planning/REQUIREMENTS.md`
- Estado actual: `.planning/STATE.md`
- Agent tools: `src/basic_stats/agent_tools.py`
- DuckDB manager: `src/basic_stats/duckdb_manager.py`
- Tool schemas: `src/basic_stats/agent_tool_schemas.py`
- System prompt: `src/basic_stats/prompts/agent_system.yaml`
