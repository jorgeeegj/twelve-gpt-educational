# Team Guide — Basic Stats v2.0

## Regla de oro

> Un cambio en `src/basic_stats/agent.py`, `agent_tools.py`, `agent_tool_schemas.py`
> o `duckdb_manager.py` **siempre** necesita pasar el benchmark antes del commit.

```bash
python evals/agent_benchmark.py --workers 1 --label my_fix && git add ... && git commit
```

---

## ¿Dónde estamos?

**Milestone:** v2.0 — Function Calling Architecture
**Estado actual:** **Phase 11 completa** — iterative synthetic discovery loop v1 cerrado (2026-04-30)
**Rama activa:** `feature/refactor-v2`
**Último commit:** `d6d0199` — feat(11): close Phase 11 — iterative discovery loop v1
**Test suite:** **231/231 passing** (3 warnings no bloqueantes — permisos `.pytest_cache` en Windows)
**Benchmark 61 preguntas:** **59/61 faithfulness — gate PASS** — run `post_residual_closeout_final` (2026-04-23)
**Benchmark random questions:** 19/21 faithfulness — run `phase6_postfix` (2026-04-20)
**Multi-turn:** Cadena de 4 turnos de Agust validada y preservada
**`src/basic_stats/` diff:** cero — sin cambios de producción desde Phase 9

Para ver el estado completo: [STATE.md](./STATE.md)
Para ver la hoja de ruta: [ROADMAP.md](./ROADMAP.md)

### Próximo paso recomendado

1. Abrir `docs/review/context_gap_unsupported_future__refuse_expected_but_answered.md` y rellenar los stubs `## Summary` y `## Proposed action` (el archivo existe pero tiene TODOs).
2. Añadir una regla de rechazo de predicciones futuras en `src/basic_stats/prompts/agent_system.yaml` (HOW TO USE TOOLS).
3. Reejecutar `evals/discovery/campaigns/unsupported_future_v1.json` para verificar que el cluster se cierra.

> **Aviso:** no modificar `src/basic_stats/` sin un plan de fase explícito. Phase 11 cerró con zero diff en ese directorio — esa garantía debe preservarse.

---

## Brief v2.0 — El qué, cómo y por qué para el equipo

### De dónde venimos (v1)

La v1 era un pipeline clásico: el usuario escribe una pregunta, un `QueryPlanner`
la parsea con regex y heurísticas, construye un plan SQL, y `DuckDBManager` ejecuta
la query. Funcionaba para las 61 preguntas del benchmark original, pero era frágil:
cada nuevo tipo de pregunta requería añadir más regex, más casos especiales, más
código que parchea lo que el sistema no entendía bien.

### La vuelta de tuerca de v2.0

La v2.0 reemplaza el QueryPlanner por un agente de **function calling** con la
Responses API de OpenAI. La idea central es:

> **El LLM entiende la pregunta. El código solo ejecuta.**

En lugar de intentar parsear lenguaje natural con regex, le damos al LLM un conjunto
de herramientas (tools) con descripciones precisas, y él decide qué herramienta
llamar y con qué parámetros. Python solo recibe esa llamada y ejecuta la query en
DuckDB. Ni una línea de if/else para interpretar qué quiso decir el usuario.

Esto no es solo un refactor técnico — es un cambio de responsabilidades:

| Antes (v1) | Ahora (v2) |
|---|---|
| Python parsea la intención | LLM interpreta la intención |
| Regex + heurísticas para entidades | Embeddings para resolución de nombres |
| `_POSITION_MAP` en Python | Descripción en el schema de la herramienta |
| Estado de conversación en memoria local | `previous_response_id` — el servidor lleva el contexto |

### Las fases completadas

**Phase 10 — Self-Generated Robustness / Synthetic UAT** (2026-04-29)

Infraestructura de UAT sintética: `evals/synthetic_runner.py` corre `BasicStatsAgent`
contra `evals/synthetic/seed_questions.json` (24 preguntas en 12 categorías), evalúa
con `raw_key_guard` + `faithfulness_judge`, y produce `failure_clusters.json` + `REPORT.md`.
Live run: 24 preguntas, 2 fallos, 1 cluster — `unsupported_future__refuse_expected_but_answered`
(SYN_019/020). Scaffold de regression tests añadido en `tests/test_synthetic_regressions.py`.

**Phase 11 — Iterative Synthetic Discovery Loop v1** (2026-04-30)

Convierte la infraestructura de Phase 10 en un loop repetible:

| Componente | Archivo | Qué hace |
|---|---|---|
| Failure backlog | `evals/discovery/failure_backlog.py` | Persistencia de clusters con seen_count, idempotente |
| Triage rubric | `evals/discovery/triage_rubric.py` | Clasifica cluster en 7 action types (sin LLM) |
| Campaign generator | `evals/discovery/campaign_generator.py` | Genera preguntas por categoría/cluster |
| Iteration runner | `evals/discovery/iteration_runner.py` | Wrappa synthetic_runner; compare_runs() diff |
| Promotion rules | `evals/discovery/promote.py` | Emite artefactos de propuesta por action type |

Live run Phase 11 (`unsupported_future_v1`, 6 preguntas): 6 fallos, 1 cluster reproducido
→ `BACKLOG_001` con `seen_count=2` → clasificado `context_missing` → promovido a
`docs/review/context_gap_unsupported_future__refuse_expected_but_answered.md`.

Commits relevantes de Phase 11:
- `d8e1c7e` — feat(11): add promotion rules executor (LOOP-06)
- `817a209` — docs(11-06): SUMMARY + roadmap/requirements/state for LOOP-06
- `d6d0199` — feat(11): close Phase 11 — iterative discovery loop v1

**Phase 5 — Function Calling Core**

Implementamos el `BasicStatsAgent`: un loop que llama a `client.responses.create`
con 4 herramientas madre (`query_player_stats`, `query_team_stats`, `query_ranking`,
`get_league_standings`). El LLM recibe la pregunta, elige la herramienta, Python
ejecuta la query, el LLM recibe el resultado y escribe la respuesta final.

**Phase 6 — Random Question Robustness**

El LLM extrae nombres de entidades tal como los escribe el usuario: "Salah", "Spurs",
"Man City". La DB tiene "M. Salah", "Tottenham Hotspur", "Manchester City". Sin
resolución, la query devuelve filas vacías.

Solución: **embeddings de texto** (text-embedding-3-large) para todos los nombres de
jugadores y equipos, almacenados en DuckDB. Cuando el LLM extrae "Salah", el código
calcula la similitud coseno contra todos los nombres embeddingeados y devuelve el
nombre canónico más cercano antes de tocar la DB. Esto maneja alias, abreviaturas y
nombres parciales sin una sola regla hardcodeada.

Benchmark: 19/21 preguntas inéditas — los 2 fallos son RQ_12 (yellow cards, ya corregido
en postfix) y RQ_17 (London clubs, deferido a Phase 8).

**Phase 7 — Conversation Memory**

El agente mantiene historial de conversación entre turnos. El mecanismo anterior usaba
`previous_response_id` del servidor de OpenAI, pero petaba con error 400 cuando un turno
anterior había incluido tool calls intermedias — el servidor las rastrea por `call_id` y
exige que aparezcan completas en el historial.

Solución: historial explícito en el cliente (`self._history`). Al final de cada turno
guardamos el historial completo incluyendo todos los tool call/output pairs, no solo el
mensaje final del asistente. El siguiente turno manda ese historial entero y OpenAI
encuentra todo consistente.

Validado con la cadena de 4 turnos de Agust:
```
"How many goals has Haaland scored?" → 22 ✅
"But against top 6 teams?" → 5 ✅
"Is that more than the rest of his goals?" → No, 17 vs 5 ✅
"What about per 90?" → ~0.72 ✅
```

Validado con la cadena de 4 turnos de Agust y revalidado tras los hotfixes / closeout:
```bash
python3 scripts/verify_multiturn.py
```

### La regla de oro que aprendimos

Durante Phase 6 teníamos un `_POSITION_MAP` en Python que mapeaba "CB" →
"Central Defender", "keeper" → "Goalkeeper", etc. Tiene sentido a primera vista.

Pero Agust ya lo había demostrado en su commit de function calling para el football
scout: **si el LLM tiene la información correcta en la descripción de la herramienta,
no hace falta código que corrija lo que el LLM debería producir bien**.

Quitamos el map de Python, pusimos los valores exactos y el mapeo de aliases en la
descripción del parámetro `position` del schema. Resultado: el LLM mapea
directamente, sin intermediarios. El código hace menos, el sistema es más claro.

La regla: **no meter heurística en Python si la arquitectura agentica (tool
descriptions, system prompt) puede soportarlo. Solo heurística cuando es
estrictamente necesario.**

---

### Lo que queda para cerrar v2.0

**Phase 8 — League Context** ✓ completada a nivel de milestone

La fase quedó cerrada funcionalmente, con contexto de liga integrado y benchmark gate superado.
Persisten algunos gaps no bloqueantes de consistencia semántica (follow-ups conversacionales,
“Champions League teams”), que no bloquean el milestone.

**Pre-Phase-9 Robustness Closeout** ✓ completado

- hotfix truthfulness appearances/minutes
- WI-1 subject exclusion + postfix semántico
- WI-2 event-stat `*_p90` con match context
- residual closeout (QV4_13, QV6_56, QV6_61)

**Phase 9 — Natural Language Polish** ✓ completada (2026-04-27)

61/61 raw-key clean; faithfulness 59/61 (0.967 ≥ gate 0.95). Regla de insight goals vs xG implementada.

**Phase 10 — Synthetic UAT** ✓ completada (2026-04-29)

Runner + clusterer + regression scaffold. Live run: 24 preguntas, 2 fallos, 1 cluster.

**Phase 11 — Iterative Discovery Loop v1** ✓ completada (2026-04-30)

9/9 exit gates. Live run: 6 preguntas, 6 fallos, 1 cluster reproducido, backlog promovido.

**Trabajo pendiente post-Phase 11 (no iniciado)**

- Rellenar `docs/review/context_gap_unsupported_future__refuse_expected_but_answered.md` (tiene stubs TODO).
- Añadir regla de rechazo de predicciones futuras en `agent_system.yaml`.
- Reejecutar `unsupported_future_v1` para verificar el cierre del cluster.
- WI-3, WI-4, WI-5 (robustness items) — pendientes, no bloqueantes.


### Cómo probar lo que tenemos ahora

```bash
# Preguntas del benchmark (21 preguntas inéditas)
python evals/agent_benchmark.py --random

# Preguntas preparadas (61 preguntas clásicas)
python evals/agent_benchmark.py

# Una sola pregunta interactiva
python -c "
from src.basic_stats.agent import BasicStatsAgent
agent = BasicStatsAgent()
print(agent.ask('How many goals has Isak scored this season?'))
print(agent.ask('What about at home?'))   # follow-up — el agente recuerda
"
```

---

## Setup (una sola vez)

```bash
# 1. Pull de la rama activa (o clonar si es la primera vez)
git pull jorge feature/refactor-v2        # si ya tienes el repo
# git clone https://github.com/jorgeeegj/twelve-gpt-educational.git && cd twelve-gpt-educational
# git checkout feature/refactor-v2

# 2. Instalar dependencias — usa lo que prefieras
```

Las dependencias están declaradas en `pyproject.toml` y también en `requirements.txt`.
Usa el gestor que tengas:

| Gestor | Comando |
|---|---|
| uv | `uv sync` |
| pip + venv | `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| pip directo | `pip install -r requirements.txt` |
| conda | `conda create -n basicstats python=3.11 && conda activate basicstats && pip install -r requirements.txt` |

```bash
# 3. Verificar que todo funciona
python evals/smoke_test.py
```

Si el smoke test devuelve `All checks passed` — estás listo.

---

## Trabajar con Claude Code + GSD

Todas las tareas de desarrollo se hacen con tres comandos:

| Comando | Cuándo usarlo |
|---|---|
| `/gsd:progress` | Ver estado actual y qué toca hacer |
| `/gsd:plan-phase N` | Crear el plan para la fase N |
| `/gsd:execute-phase N` | Ejecutar la fase N |

**Flujo normal:**

```
/gsd:progress          → te dice en qué fase estás
/gsd:execute-phase 5   → ejecuta Phase 5
/gsd:progress          → confirma que está completa, te dice qué sigue
```

No hace falta leer los archivos de `.planning/` — GSD los carga solo.

---

## Estructura del repo

```
src/basic_stats/             ← código del engine
  agent.py                   ← BasicStatsAgent — loop function-calling
  agent_tools.py             ← implementación de las 4 herramientas madre
  agent_tool_schemas.py      ← schemas OpenAI Responses API (contratos LLM↔código)
  agent_prompt.py            ← build_system_prompt() con contexto dinámico del DB
  config.py                  ← cliente Azure OpenAI + modelos
  duckdb_manager.py          ← todas las queries SQL + resolución de entidades
  prompts/
    agent_system.yaml        ← system prompt del agente (editar con cuidado)

db/
  basic_stats.duckdb         ← DB persistente (incluye entity_embeddings — Phase 6)

evals/
  questions_benchmark.json   ← 61 preguntas preparadas
  random_questions.json      ← 21 preguntas inéditas (Phase 6)
  agent_benchmark.py         ← benchmark del agente ← USAR ESTE
  synthetic_runner.py        ← runner de UAT sintética (Phase 10)
  synthetic_clusterer.py     ← agrupa fallos en clusters (Phase 10)
  synthetic/
    seed_questions.json      ← 24 preguntas sintéticas, 12 categorías
  discovery/                 ← loop de discovery (Phase 11)
    failure_backlog.py       ← persistencia de clusters con seen_count
    failure_backlog.json     ← backlog actual (BACKLOG_001 promovido)
    triage_rubric.py         ← clasificador determinista, 7 action types
    triage_rubric.md         ← guía humana de triage
    campaign_generator.py   ← genera campañas por categoría/cluster
    iteration_runner.py      ← wrappa synthetic_runner; compare_runs()
    promote.py               ← emite artefactos de propuesta
    campaigns/
      unsupported_future_v1.json  ← campaña Phase 11 (6 preguntas)
    fixture_fixes/           ← placeholder para diffs de fixture
  runs/                      ← outputs gitignoreados (NUNCA stagear)
  judges/
    faithfulness_judge.py    ← juez: verifica que los números estén en la respuesta

docs/review/                 ← propuestas de seguimiento emitidas por promote.py
  context_gap_unsupported_future__refuse_expected_but_answered.md  ← TODO stubs

tests/
  test_fuzzy_resolve.py      ← resolución de entidades (19 casos, sin LLM)
  test_duckdb_vss_stubs.py   ← stubs Phase 5 (3 fallos conocidos, pendiente limpieza)
  test_failure_backlog.py    ← tests failure backlog (Phase 11)
  test_triage_rubric.py      ← tests rubric classifier (Phase 11)
  test_campaign_generator.py ← tests campaign generator (Phase 11)
  test_iteration_runner.py   ← tests compare_runs (Phase 11)
  test_promote.py            ← tests promotion rules (Phase 11)
  test_synthetic_regressions.py  ← scaffold de regresiones (Phase 10)

pages/
  basic_stats.py             ← página Streamlit

.planning/                   ← artefactos de planificación
  STATE.md                   ← estado actual de fases y benchmark
  ROADMAP.md                 ← fases y criterios de éxito
  TEAM.md                    ← este archivo
  phase-6/COMPLETION.md      ← resumen técnico de Phase 6
```

---

## Correr el benchmark

```bash
# Benchmark del agente (Phase 5) — 61 preguntas con juez de fidelidad
python evals/agent_benchmark.py --workers 1 --label my_label

# Solo contar respuestas (sin juez, más rápido para iteraciones rápidas)
python evals/agent_benchmark.py --skip-judges --workers 1 --label my_label

# Pipeline viejo — solo como referencia/regresión
python evals/benchmark_runner.py --workers 5
python evals/smoke_test.py
```

**Última ejecución (random):** `evals/runs/2026-04-20_00-15-16__phase6_postfix` → 19/21 faithfulness
(RQ_12 corregido en postfix, RQ_17 deferido a Phase 8)

---

## Commit safety — archivos a NUNCA stagear

Los siguientes archivos están sucios de forma permanente o son outputs de ejecución — no stagear nunca:

| Archivo / Patrón | Motivo |
|---|---|
| `.claude/settings.local.json` | Settings locales de Claude Code — no pertenece al repo |
| `.planning/config.json` | Config local de GSD — no pertenece al repo |
| `db/basic_stats.duckdb` | Base de datos binaria con embeddings — nunca se commitea |
| `evals/runs/*` | Outputs de runs gitignoreados — confirmar con `git check-ignore` antes de commitear |
| `docs/review/*` | Artefactos de promote.py — stagear solo cuando el usuario los aprueba explícitamente |

Verificación antes de cualquier commit:

```bash
git diff --cached --name-only   # revisar lo que vas a commitear
git diff --name-only src/basic_stats/ | wc -l   # debe devolver 0
git check-ignore evals/runs/    # debe confirmar gitignored
```

**Nunca usar `git add .` o `git add -A`** — siempre stagear por ruta explícita.
