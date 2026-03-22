# 2026-03-20 / 2026-03-21 / 2026-03-22 — Jorge Progress after Agust messages & next steps

## Context

Este progreso continúa directamente desde `2026-03-16_JorgeProgress.md`.

Tras:
- los comentarios de Agust sobre narrow the scope, simplificar el enfoque y alinear mejor el proyecto,
- el material/documento de Álvaro,
- y el mensaje posterior de seguimiento donde se explicó mejor la intención del proyecto,

se reorganizó el trabajo para:
1. consolidar bien los **sprints 1, 2 y 3**,
2. rediseñar la arquitectura para soportar **más autonomía del LLM**,
3. incorporar **DuckDB + planner + nuevas tablas contextuales**,
4. y construir los **sprints 4 y 5** sobre una base más escalable.

---

## Objetivo de este bloque

Pasar de un sistema centrado sobre todo en preguntas de summary a una arquitectura más seria y extensible capaz de resolver:

- preguntas de **summary season-level**
- preguntas de **player match-level**
- preguntas de **player event-level contextual**
- preguntas de **team match contextual**

sin depender tanto de rutas hardcodeadas pregunta por pregunta.

---

# Primer progreso realizado

## Sprint 1
Robustez NL básica + rephrases + ordinal ranking.

Capacidades esperadas:
- reformulaciones EN/ES
- top scorer / best attack / fewest conceded
- ordinales tipo 2nd, 7th, 20th

## Sprint 2
Player match-level básico.

Capacidades objetivo:
- goals between matchdays X-Y
- matches with both goal and assist
- matches with 2+ goals

## Sprint 3
Opponent / home-away context.

Capacidades objetivo:
- goals vs top-6
- player away goals
- team away goals

---

# Decisión arquitectónica principal

## Problema detectado

Con sprints 1–3, seguir creciendo con reglas específicas en `llm_query_engine_v2.py` llevaba a:
- demasiadas rutas especiales,
- poca escalabilidad,
- mala mantenibilidad,
- dificultad para incorporar nuevas tablas/contextos.

## Decisión tomada

Introducir arquitectura **planner-first + DuckDB**:

```text
Question
  -> QueryPlanner.resolve()
  -> QueryPlan estructurado
  -> dispatch por scope
  -> DuckDBManager query genérica
  -> rows grounded
  -> verbalización final
```

## Objetivo de esta decisión

* mantener lo que ya funcionaba en summary
* permitir más autonomía al LLM
* pero ejecutar siempre sobre tablas y filtros validados por código
* evitar seguir creciendo a base de queries manuales para cada benchmark

---

# Plan acordado para este bloque siguiente

Se definió este orden:

## Fase 1

Diseñar y crear:

* `resolve_query_intent.yaml`
* `query_planner.py`

## Fase 2

Construir:

* `build_player_match_event_stats.py`

## Fase 3

Ampliar DuckDB:

* registrar `player_match_event_stats`
* query genérica contextual de jugador sobre ese scope

## Fase 4

Añadir 5 preguntas de Sprint 4 al benchmark y medir

## Fase 5

Construir:

* `build_team_match_stats.py`

## Fase 6

Ampliar DuckDB:

* query genérica contextual por equipo

## Fase 7

Añadir 5 preguntas de Sprint 5 al benchmark y medir

---

# Sprint 1 — consolidación y base del planner

## Trabajo realizado

Se diseñó e implementó:

* `resolve_query_intent.yaml`
* `query_planner.py`

## Función del planner

Resolver una pregunta natural a un plan estructurado con:

* `table_scope`
* `entity_type`
* `metric`
* `aggregation`
* `filters`
* `ranking`

más adelante también:

* `match_conditions` (para lógica match-derived)

## Scopes definidos

* `players_summary`
* `teams_summary`
* `player_match`
* `player_match_event`
* `team_match`

## Decisiones importantes

### 1. El LLM decide intención, no SQL

El LLM no genera SQL.
Solo genera un plan validable.

### 2. Código aplica guardrails

El código:

* normaliza aliases
* rellena defaults
* corrige scopes obvios
* valida métricas/scopes
* completa filtros deterministas

### 3. Filtros deterministas aceptados

Se mantuvo como válido extraer por código:

* position
* age_lt
* min_minutes
* min_matches
* is_home
* opponent rank / big6
* matchday range
* player/team name hints

Esto se consideró un compromiso razonable entre flexibilidad y robustez.

## Resultado

Con bastante iteración, el planner acabó resolviendo correctamente las preguntas test de esta fase y quedó listo como nueva base del sistema.

---

# Sprint 2 — player match-level

## Objetivo

Resolver preguntas sobre contexto de partido a nivel jugador, no solo summary season-level.

## Trabajo previo consolidado

Se terminó de soportar correctamente:

* goals between matchdays X-Y
* matches with both a goal and an assist
* matches with 2 or more goals

## Decisión técnica importante

Estas dos preguntas:

* `matches with both a goal and an assist`
* `matches with 2+ goals`

no encajaban bien solo con:

* scope
* metric
* filters
* aggregation

Por eso se añadió en el planner el concepto:

* `match_conditions`

Ejemplos:

* `goals > 0 AND assists > 0`
* `goals >= 2`

## Archivo nuevo

* `scripts/build_player_match_stats.py`

## Tabla nueva

* `output/player_match_stats.parquet`

## Resultado

Sprint 2 quedó integrado dentro de la arquitectura nueva, ya no solo como lógica suelta.

---

# Sprint 3 — opponent + home/away context

## Objetivo

Resolver preguntas contextuales como:

* goals vs top-6
* how many goals has X scored vs top-6
* player away goals
* team away goals



## Decisiones

### 1. Crear `league_table` en DuckDB

Se construyó una view derivada para disponer de:

* `final_rank`
* `is_big6`

y poder filtrar de forma grounded por:

* `opponent_rank_lte`
* `opponent_rank_gte`
* `opponent_is_big6`

### 2. Mantener consultas genéricas

Se evitó, en lo posible, crear una función por benchmark.

Se reforzó la idea de:

* una query contextual genérica por scope
* planner + filtros + agregación

## Estado al cerrar esta parte

Sprint 3 quedó parcialmente consolidado dentro del modelo nuevo y sirvió de base para los sprints 4 y 5.

---

# Sprint 4 — player event-level context

## Objetivo

Añadir contexto de eventos a nivel:

* jugador x partido

para preguntas tipo:

* progressive passes vs top-6
* touches in box away
* key passes between GW X-Y
* shot assists vs Big Six

## Archivo nuevo

* `scripts/build_player_match_event_stats.py`

## Tabla nueva

* `output/player_match_event_stats.parquet`

## Grain

Una fila por:

* `match_id`
* `player_id`

## Métricas incluidas

Entre otras:

* `progressive_passes`
* `key_passes`
* `shot_assists`
* `touches_in_box`
* `actions_z1..z5`
* `pass_z2_to_z4`, `pass_z2_to_z5`
* `pass_z3_to_z4`, `pass_z3_to_z5`
* `carry_z2_to_z4`, `carry_z2_to_z5`
* `carry_z3_to_z4`, `carry_z3_to_z5`

## Incidencia importante resuelta

Durante la construcción apareció un bug por `match_id`:

* no estaba bien en root
* hubo que apoyarse en el `matchId` correcto de eventos

Eso se debuggeó explícitamente y se arregló.

## Validación final

La tabla se generó correctamente:

* 11567 rows
* 63 columns

con valores zonales ya razonables.

## DuckDB

Se registró la nueva view:

* `player_match_event_stats`

y se añadió query contextual genérica para este scope.

## Benchmark

Se añadieron 5 preguntas nuevas de Sprint 4.

---

# Sprint 5 — team contextual match-level

## Objetivo

Resolver preguntas contextuales por equipo como:

* points vs Big Six
* away goals vs top-6
* goal difference between GW X-Y
* away wins
* actions_z3 against Manchester City

## Archivo nuevo

* `scripts/build_team_match_stats.py`

## Tabla nueva

* `output/team_match_stats.parquet`

## Grain

Una fila por:

* `match_id`
* `team_id`

## Métricas relevantes

* `team_score`
* `opponent_score`
* `points`
* `goal_difference`
* `is_win`
* `key_passes`
* `touches_in_box`
* `actions_z3`
* zonales de pases/carries

## Validación final

Tabla generada correctamente:

* 760 rows
* 69 columns

## DuckDB

Se registró:

* `team_match_stats`

y se añadió query genérica contextual por equipo.

## Benchmark

Se añadieron 5 preguntas nuevas de Sprint 5.

---

# DuckDB — diseño final alcanzado en este bloque

## Views registradas

* `players_summary`
* `teams_summary`
* `player_match_stats`
* `player_match_event_stats`
* `team_match_stats`
* `league_table`

## Rol de DuckDB

DuckDB pasa a ser el ejecutor grounded principal para:

* summary scopes
* player match context
* player event context
* team match context

## Métodos genéricos importantes

En `duckdb_manager.py` se consolidaron queries genéricas para:

* `query_summary_context(...)`
* `query_player_match_context(...)`
* `query_player_match_event_context(...)`
* `query_team_match_context(...)`

Esto fue una de las decisiones clave del bloque.

---

# `llm_query_engine_v2.py` — evolución

## Problema inicial

El archivo había crecido demasiado y se estaba volviendo inmanejable.

## Objetivo del refactor

Pasarlo a una lógica más clara:

1. planner
2. dispatch por scope
3. DuckDB query genérica
4. verbalización

## Qué se mantuvo

Se dejó un fallback summary / resolve_metric para robustez.

## Qué se intentó evitar

Seguir ampliando una lógica tipo:

* una ruta por cada pregunta del benchmark

## Estado al final

El archivo quedó bastante más orientado a arquitectura genérica, aunque todavía no perfecto.

---

# Resultados de benchmark durante este bloque

Hubo bastantes regresiones intermedias mientras se estabilizaban:

* planner
* aliases
* canonicalización
* dispatch por scope
* filtros contextuales

Eso era esperable por el cambio fuerte de arquitectura.

## Resultado final más relevante al cerrar este bloque

Última ejecución significativa:

* **43 / 50**

### Breakdown

* baseline: **19/20**
* sprint 1: **12/12**
* sprint 2: **4/4**
* sprint 3: **2/4**
* sprint 4: **3/5**
* sprint 5: **3/5**

---

# Qué quedó funcionando bien

## Summary

Muy sólido:

* goals
* assists
* minutes
* yellow cards
* conceded goals
* pass accuracy
* offsides
* p90 metrics
* ordinal ranking

## Sprint 2

Funcionando:

* goal + assist matches
* 2+ goal matches
* goals between matchdays

## Sprint 3

Funcionando:

* player away goals
* team away goals

## Sprint 4

Funcionando:

* touches_in_box away
* key_passes between matchdays
* shot_assists vs Big Six

## Sprint 5

Funcionando:

* points vs Big Six
* goal difference between matchdays
* away wins

---

# Qué quedó pendiente / dónde fallaba al final

Los fallos finales ya estaban muy concentrados.

## Pendientes principales

### Sprint 3

* player goals vs top-6
* named player goals vs top-6

### Sprint 4

* midfielder progressive passes vs top-6
* versión ES de shot assists vs Big Six

### Sprint 5

* team away goals vs top-6
* team actions_z3 vs Manchester City

### Summary pendiente

* under 23 top scorer

---

# Diagnóstico técnico final

Los problemas que quedaban al final NO eran principalmente de:

* tablas parquet
* extracción de eventos
* agregaciones base de DuckDB

Los problemas restantes estaban sobre todo en:

## 1. Planner / canonicalización

Todavía faltaban aliases y correcciones de:

* métricas
* entity_type
* scope

## 2. Routing por scope

Algunas preguntas aún caían en:

* scope incorrecto
* entity_type incorrecto

## 3. Multilenguaje

Especialmente en queries contextuales mixtas EN/ES.

## 4. Protección contextual

En algunas preguntas el sistema seguía pudiendo derivar a un scope inadecuado si el planner se equivocaba.

---

# Decisiones importantes tomadas

## 1. Mantener planner + DuckDB

Se considera la dirección correcta.

## 2. Mantener filtros deterministas simples

También se considera correcto:

* no todo debe depender del LLM

## 3. No volver al enfoque de una query por benchmark

Eso no escala y no encaja con el scope del proyecto.

## 4. Aceptar `match_conditions`

Como representación limpia de lógica match-derived.

---

# Siguiente trabajo recomendado

## Prioridad 1

No rehacer arquitectura.
Atacar solo las preguntas que aún fallan.

## Prioridad 2

Inspeccionar planner output exacto de esas preguntas:

* raw LLM output
* canonicalized plan
* final dispatch

## Prioridad 3

Reforzar aliases / canonicalización en planner para:

* player vs team
* away goals
* top-6 / big six
* actions in z3
* variantes ES

## Prioridad 4

Después de mejorar benchmark:

* limpieza final
* simplificación adicional
* documentación definitiva

---

# Resumen corto para handoff

## Lo conseguido

* Se consolidó el trabajo de sprints 1–3 dentro de una arquitectura más seria.
* Se introdujo `resolve_query_intent.yaml` + `query_planner.py`.
* Se construyeron dos nuevas tablas:

  * `player_match_event_stats.parquet`
  * `team_match_stats.parquet`
* Se amplió DuckDB para soportar contexto real.
* Se pasó el benchmark a 50 preguntas.
* Se mantuvo muy fuerte summary + sprint 1.
* Se dejó sprint 2 estable.
* Se dejaron partes relevantes de sprint 3, 4 y 5 ya funcionando.

## Estado real al cierre

* arquitectura bastante mejor
* ejecución grounded bastante mejor
* benchmark en **43/50**
* los fallos ya están localizados y son atacables

## Qué debería hacer el siguiente compañero

* no rehacer nada grande
* atacar las pocas preguntas contextuales pendientes
* reforzar planner/canonicalización
* luego limpiar y cerrar

