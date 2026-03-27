---
date: 2026-03-25
author: Jorge
scope: Basic Stats Analyst
status: completed
---

# Progress Log — 2026-03-25

## Context

Este progreso continúa directamente desde:

- `docs/progress/2026-03-20-21-22_JorgePorgress_afterAgustMessages_&_nextSteps.md`

El objetivo de este bloque fue **cerrar y blindar los sprints 1–5**, sin rehacer arquitectura, corrigiendo únicamente los fallos restantes del benchmark.

---

## Objetivo

Pasar de **43/50** a **50/50** manteniendo la arquitectura:

- `QueryPlanner`
- canonicalización / post-process
- dispatch por scope
- ejecución grounded con DuckDB

---

## Dónde se metió mano

### Core
- `utils/basic_stats/core/query_planner.py`
- `utils/basic_stats/core/llm_query_engine_v2.py`
- `utils/basic_stats/core/duckdb_manager.py`
- `utils/basic_stats/core/test_query_planner.py`

### Evaluación / debug
- `eval_runner_v5.py`

---

## Qué se hizo

### 1. Refuerzo del planner
Se reforzó la resolución de preguntas contextuales para evitar errores de:

- `entity_type`
- `table_scope`
- `metric`
- filtros contextuales (`top n`, `big six`, `home/away`, rival concreto)

También se generalizó la lógica de ranking contextual tipo:

- `top-n`
- `bottom-n`

en lugar de depender de casos fijos como solo `top-6`.

### 2. Mejor canonicalización / post-process
Se endureció la fase de normalización final para transformar variantes naturales a representación interna estable.

Ejemplos:
- `top-6 teams` → `opponent_rank_lte=6`
- `away goals` de equipo → `team_match` + `team_score`
- `actions in z3 against Manchester City` → `team_match` + `actions_z3` + `opponent_team_name`

### 3. Corrección del gating del planner
Se corrigió la lógica que decidía si usar o no el resultado del planner.

El fallo principal era que algunas preguntas de **jugador con contexto de rival** se rechazaban incorrectamente por contener palabras como `teams` o `equipos` dentro del filtro contextual.

Se pasó a distinguir mejor entre:

- sujeto real de la pregunta
- contexto del rival

### 4. Sanitización de `match_conditions`
Se añadió limpieza de `match_conditions` para evitar que filtros contextuales incorrectos acabaran entrando como condiciones de métricas de partido.

Esto eliminó errores como:
- `opponent_is_big6` tratado como `match_condition`

### 5. Refuerzo del debug
Se añadió un runner focalizado (`eval_runner_v5.py`) para inspeccionar:

- raw plan
- canonical plan
- final plan
- decisión de uso del planner
- resultado de query grounded
- evaluación por caso

Esto permitió localizar la causa real de los últimos fallos sin tocar arquitectura grande.

---

## Qué se corrigió al cerrar este bloque

Se cerraron las preguntas que seguían fallando en el benchmark final:

- player goals vs top-6
- named player goals vs top-6
- midfielder progressive passes vs top-6
- ES shot assists vs Big Six
- team away goals vs top-6
- team actions_z3 vs Manchester City
- under-23 top scorer

---

## Resultado final

### Benchmark oficial
- **50 / 50**

### Desglose final
- baseline: **20/20**
- sprint 1: **12/12**
- sprint 2: **4/4**
- sprint 3: **4/4**
- sprint 4: **5/5**
- sprint 5: **5/5**

---

## Estado al cierre

Queda consolidado un sistema que ya resuelve de forma robusta:

- summary season-level
- ordinal ranking
- rephrases EN/ES
- player match-level context
- player event-level context
- team match context

manteniendo una arquitectura basada en:

- planner estructurado
- guardrails en código
- ejecución grounded sobre DuckDB

---

## Takeaway

Este bloque no añadió nueva arquitectura.

Su función fue **cerrar, estabilizar y blindar** el trabajo ya construido en los sprints 1–5, dejando el benchmark completo en **50/50** y el flujo planner → DuckDB funcionando de forma mucho más consistente en preguntas contextuales.