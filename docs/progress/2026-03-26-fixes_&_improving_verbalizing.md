---
date: 2026-03-25
author: Jorge
scope: Basic Stats Analyst
status: completed
---

# Progress Log — 2026-03-25

## Context

Este progreso continúa directamente desde:

- `docs/progress/2026-03-25-closing-sprints_benchmark-finish.md`

Tras cerrar el benchmark en **50/50**, el foco de este bloque pasó a ser mejorar la **capa de salida** del Basic Stats Analyst y arreglar varios problemas visibles en la app, sin tocar la arquitectura principal ni rehacer planner + DuckDB.

---

## Objetivo

Mejorar la calidad de las respuestas del sistema en uso real:

- respuestas más naturales y menos “raw”
- mejor manejo de:
  - ordinal ranking
  - top-n
  - preguntas contextuales ya resueltas por planner
- corregir señales erróneas en la UI
- dejar una versión más presentable para demo/exposición

---

## Dónde se metió mano

### Core / salida
- `utils/basic_stats/core/llm_query_engine_v2.py`
- `utils/basic_stats/core/query_planner.py`
- `utils/basic_stats/prompts/verbalize.yaml`

### UI
- `pages/basic_stats.py`

---

## Qué se hizo

### 1. Mejora de la page de Streamlit
Se actualizó `pages/basic_stats.py` para reflejar mejor el estado real del proyecto:

- benchmark status apuntando al resultado correcto
- ejemplos más alineados con el sistema actual
- eliminación del falso mensaje de empate basado solo en `len(rows) > 1`
- separación más limpia entre:
  - resultado textual
  - tabla grounded
  - debug

Esto mejoró la demo y evitó mensajes engañosos para queries tipo `Top 5`.

### 2. Ajustes de verbalización
Se revisó `verbalize.yaml` para forzar respuestas más naturales y menos “CSV-like”.

Se reforzó especialmente que:
- las filas ya son el resultado grounded final
- no debe cuestionarse el ranking si hay rows
- en ordinal ranking se debe responder como resultado definitivo
- en top-n no debe reinterpretarse `top 4 / top 5` como contexto rival salvo que aparezca explícitamente en la pregunta

### 3. Mejora de salida para ordinal ranking
Se corrigió el comportamiento en preguntas tipo:

- `Who is 7th for total minutes played this season?`
- `Who is 13th for total minutes played this season?`

Antes, el modelo podía responder como si no tuviera suficiente contexto al recibir una sola fila.
Ahora entiende que esa fila ya representa exactamente la posición ordinal pedida y debe incluir también el valor de la métrica.

### 4. Mejora de salida para top-n
Se mejoró el comportamiento en preguntas tipo:

- `Top 5 players with the most away goals`

El problema principal era que la salida mezclaba:
- `top 5` como número de resultados pedidos
con
- `top-5 teams` como filtro contextual de rival

Se corrigió el prompting para que la verbalización no confunda ambas cosas y trate `Top N` como ranking solicitado, no como opponent context.

### 5. Ajuste del planner para top-rank contextual
En `query_planner.py` se afinó la extracción de buckets tipo `top-n` para que el filtro contextual de rival solo se active cuando la pregunta realmente lo implica, por ejemplo:

- `against top-4 teams`
- `contra top 6`

y no simplemente por aparecer al inicio expresiones tipo:

- `Top 4 forwards ...`

Esto redujo errores de interpretación entre ranking pedido y contexto rival.

### 6. Compatibilidad entre prompt y código de verbalización
Se ajustó `llm_query_engine_v2.py` para que el prompt de verbalización reciba correctamente toda la información necesaria para responder mejor:

- tipo de respuesta
- contexto
- ordinal solicitado
- top-n solicitado

Con esto se evitó que la app rompiera por desacoples entre placeholders del prompt y el `.format(...)` del engine.

---

## Qué mejoró al cerrar este bloque

### Respuestas más naturales
Ejemplos del estado alcanzado:

- `B. Mbeumo is 7th for total minutes played this season, with 3,413 minutes.`
- `Mohamed Salah of Liverpool leads with 19 shot assists against Big Six teams.`
- `E. Haaland has 8 goals against top-10 teams this season.`
- `L. Díaz, de Liverpool, lidera con 8.0 pases clave entre las jornadas 25 y 30.`

### Mejor comportamiento en:
- ordinal ranking
- entity value
- top-1
- top-n
- preguntas contextuales EN/ES ya soportadas por benchmark

---

## Estado al cierre

El sistema queda en un estado bastante más sólido no solo a nivel benchmark, sino también a nivel de uso real en la app:

- benchmark oficial sigue en **50/50**
- planner + DuckDB se mantienen estables
- la salida textual es más clara y más presentable
- la UI deja de mostrar mensajes engañosos
- queda una base mejor para el siguiente paso: enriquecer respuestas con comentarios grounded sobre el dato

---

## Qué quedó todavía mejorable

Este bloque no intentó resolver todavía toda la futura “wordalisation” del proyecto.

Siguen pendientes para una siguiente fase:
- enriquecer respuestas con insight comparativo
- comparar query-context vs baseline de temporada
- mejorar algunas métricas menos frecuentes sin depender de hardcodeos excesivos
- seguir refinando top-n y formulaciones abiertas muy generales

---

## Takeaway

Este bloque fue un sprint de **fixes + mejora de verbalización + mejora de demo**.

No cambió la arquitectura central del sistema, pero sí mejoró de forma clara:

- la calidad de salida
- la legibilidad de respuestas
- la coherencia de la app
- y la preparación del proyecto para la siguiente fase de wordalisation grounded.
