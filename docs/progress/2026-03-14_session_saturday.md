---
date: 2026-03-14
participants: Ricardo, Álvaro (benchmark answers), Jorge (base architecture)
branch: feature/basic-stats-analyst
---

# Progress Log — Sábado Fase 1

## Objetivo del día
Llegar a ≥15/20 en el benchmark del Basic Stats Analyst.

## Lo que se hizo

### Setup
- Conflicto de .gitignore resuelto (data files excluidos, se redujo de 385 cambios a 2)
- Dependencias instaladas: scipy, watchdog, plotly, matplotlib, anthropic
- Streamlit corriendo en local (`streamlit run app.py`)
- Credenciales OpenAI actualizadas en `.streamlit/secrets.toml`

### Archivos importados
- `utils/basic_stats/aliases_para_ricardo.json` — ~150 aliases
- `utils/basic_stats/partealvaro.py` — genera `questions_benchmark_raw.json`
- `docs/Readme_13_03_actual_nextsteps.md` — documentación del estado del proyecto

### Fixes aplicados
1. `metric_resolver.py` — aliases completos + detección per-90
2. `query_engine.py` — position map completo
3. `query_engine.py` — age calculation desde 2024-08-01 (fix Palmer bug)
4. `query_engine.py` — tie handling en top-1 queries (fix Raya bug)

### Evaluación
- Creado `eval_runner.py` para testeo automatizado (llama al LLM)
- Score: **14/20** (desde 10/20 baseline)

## Pendiente
- 5-6 preguntas aún fallando (ver `docs/evals/2026-03-14_baseline.md`)
- Push a repo de Jorge (`jorge` remote, branch `jorgeGJ`)

## Archivos críticos modificados
- `utils/basic_stats/metric_resolver.py`
- `utils/basic_stats/query_engine.py`
- `eval_runner.py` (nuevo)
- `utils/basic_stats/partealvaro.py` (nuevo)
