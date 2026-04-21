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
**Fase actual:** Phase 8 — League Context (Phases 5, 6 y 7 completas)
**Benchmark random questions:** 19/21 faithfulness — run `phase6_postfix` (2026-04-20)
**Multi-turn:** Cadena de 4 turnos de Agust validada (2026-04-21)

Para ver el estado completo: [STATE.md](./STATE.md)
Para ver la hoja de ruta: [ROADMAP.md](./ROADMAP.md)

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

Para probar multi-turn manualmente:
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

**Phase 8 — League Context** *(siguiente)*

Inyectar clasificaciones dinámicas de equipos en el system prompt desde DuckDB — top 4,
top 6, zona de descenso — calculadas a partir de la tabla `league_standings`. Eliminar
cualquier lista hardcodeada de equipos en el código. Esto también resuelve RQ_17
(London clubs): el agente conocerá qué equipos son de Londres porque el contexto lo
especifica, no por una regla Python.

**Phase 9 — Natural Language Polish** *(última)*

Respuestas más fluidas: sin claves de métricas crudas, con reglas de insight
("finishing above xG expectation"), templates de verbalización para comparaciones
y ventanas temporales.

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
  judges/
    faithfulness_judge.py    ← juez: verifica que los números estén en la respuesta

tests/
  test_fuzzy_resolve.py      ← resolución de entidades (19 casos, sin LLM)
  test_duckdb_vss_stubs.py   ← stubs Phase 5 (3 fallos conocidos, pendiente limpieza)

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
