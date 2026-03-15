---
dates: 2026-03-14 / 2026-03-15
author: Ricardo
branch: feature/basic-stats-analyst
---

# LLMQueryEngine v2 — Diseño, Motivación y Resultados

## Contexto

Jorge construyó el `QueryEngine` original junto con el `MetricResolver` e `IntentRouter`.
Funcionan con **keyword matching y regex**: si la pregunta usa un sinónimo no mapeado, el agente falla.
El benchmark arrancó en **10/20**.

Esta sesión (14-15 marzo) exploró primero fixes sobre la arquitectura existente,
luego construyó un enfoque nuevo más robusto: el `LLMQueryEngine v2`.

---

## Progresión del benchmark

| Fase | Score | Qué se hizo |
|------|-------|-------------|
| Baseline (Jorge) | 10/20 | Arquitectura original |
| Fix 1: aliases + per-90 | 12/20 | `metric_resolver.py` — ~150 aliases, detección `_p90` |
| Fix 2: position map + age | 13/20 | `query_engine.py` — mapa completo de posiciones, fecha base 2024-08-01 |
| Fix 3: tie handling | 14/20 | `query_engine.py` — incluir todos los empatados en top-1 |
| LLMQueryEngine v1 (experimental) | 18/20 | LLM genera query completa — demasiado libre |
| **LLMQueryEngine v2 (híbrido)** | **20/20** | LLM decide métrica vía tool use, código aplica filtros |

---

## Por qué un nuevo enfoque

El `QueryEngine` de Jorge es determinista y correcto, pero frágil:
cada pregunta nueva que use un sinónimo distinto requiere editar `metric_resolver.py` manualmente.

David lo anticipa en el enunciado del proyecto:
> *"LLMs are increasingly good at interrogating datasets and producing insights from tabular data."*

El `LLMQueryEngine v2` aplica esto directamente: el LLM **entiende** la pregunta semánticamente
en vez de hacer matching de keywords. Si alguien pregunta "who bagged the most" en vez de "who scored the most",
el LLM lo resuelve sin tocar código.

---

## Arquitectura del LLMQueryEngine v2

Pipeline de 3 pasos con responsabilidades separadas:

```
Pregunta
   ↓
1. LLM (tool use)       → decide qué métrica y tabla usar
   ↓
2. Código (determinista) → aplica filtros (posición, edad, minutos, apariciones)
   ↓
3. LLM (verbalize)      → escribe la respuesta en lenguaje natural
```

### Paso 1 — Tool use: el LLM resuelve la métrica

Se le dan al LLM dos herramientas: `query_players` y `query_teams`.
Cada herramienta tiene un `enum` de columnas reales extraídas del parquet —
el LLM **no puede inventarse una columna que no existe**.

Esto es lo que hacen los LLMs bien: entender semántica.
"wins aerial duels per 90" → `aerial_duels_won_p90`. Sin alias, sin regex.

### Paso 2 — Filtros deterministas (vuestro ground truth)

Los mismos extractores del `QueryEngine` de Jorge, reutilizados:
- `_extract_position` → mapa de posiciones vuestro, no el LLM
- `_extract_under_age` → fecha base 2024-08-01
- `_extract_min_minutes` / `_extract_min_matches` → regex sobre la pregunta
- `_extract_top_n` → regex sobre la pregunta

El LLM no toca los filtros. Vosotros controláis la lógica de negocio.

### Paso 3 — Verbalización

El LLM recibe solo el resultado ya filtrado y ordenado.
El prompt le instruye explícitamente: *"lead with the first row — it is the correct answer"*.
Esto resuelve el bug de Q13 (antes verbalizaba el 2º resultado).

### Intent routing

El routing anterior (`IntentRouter`) usaba regex para detectar si la pregunta era de equipos,
jugadores, filtrada, etc. En v2 esto desaparece: el LLM elige la herramienta correcta (`query_players`
vs `query_teams`) implícitamente. Menos código, más robusto.

---

## Por qué Pydantic para el output estructurado

El tool call devuelve JSON. Sin validación, un campo inesperado causa un `KeyError` silencioso.

Con `MetricResolution(BaseModel)` el contrato es explícito:
```python
class MetricResolution(BaseModel):
    metric:     str   # columna exacta del parquet
    descending: bool  # dirección del ranking
    table:      str   # "players" o "teams"
```

Si el LLM devuelve algo inválido → `ValidationError` inmediato y claro.
Principio del curso (Lesson 4): *"fail-fast behavior is essential for building reliable systems"*.

---

## Organización de directorios añadida

```
utils/basic_stats/
    config.py                    ← AzureOpenAI client, paths a parquets — sin hardcodear en lógica
    models.py                    ← Pydantic models: MetricResolution, QueryResult
    prompts/
        resolve_metric.yaml      ← system prompt + descripciones semánticas de columnas
        verbalize.yaml           ← prompt de verbalización con XML tags
    llm_query_engine_v2.py       ← orquestación de los 3 pasos, solo lógica

docs/
    evals/                       ← resultados de benchmark con breakdown por pregunta
    progress/                    ← logs de sesión para el equipo (este archivo)
```

### `resolve_metric.yaml`
Define el system prompt del tool use y las descripciones semánticas de cada columna
(ej. `aerial_duels_won_p90: "Aerial duels won per 90 minutes"`).
El LLM usa estas descripciones para elegir la columna correcta.
Separar el prompt del código permite iterar sin tocar Python.

### `verbalize.yaml`
Prompt de verbalización con XML tags (`<question>`, `<metric>`, `<data>`, `<instructions>`).
Formato recomendado por el curso para separar tipos de información dentro del contexto.
YAML es más token-efficient que JSON para contexto de entrada.

---

## Eval runner automático

Creado `eval_runner_v2.py` — corre las 20 preguntas del benchmark sin abrir Streamlit:

```bash
.venv/bin/python eval_runner_v2.py
```

Muestra para cada pregunta: expected, respuesta del agente, tabla/métrica/filtros usados.
Permite diagnosticar fallos en segundos sin interacción manual.

Ver breakdown completo en `docs/evals/2026-03-15_llm_engine_v2.md`.

---

## Archivos críticos

| Archivo | Qué hace |
|---------|----------|
| `utils/basic_stats/llm_query_engine_v2.py` | Orquestación completa |
| `utils/basic_stats/config.py` | Credenciales y paths |
| `utils/basic_stats/models.py` | Contratos Pydantic |
| `utils/basic_stats/prompts/resolve_metric.yaml` | Prompt tool use + schema semántico |
| `utils/basic_stats/prompts/verbalize.yaml` | Prompt verbalización |
| `eval_runner_v2.py` | Runner automático 20 preguntas |
| `eval_runner.py` | Runner original (QueryEngine de Jorge, 14/20) |
