# Team Guide — Basic Stats v2.0

## Regla de oro

> Un cambio en `query_planner.py`, `llm_query_engine_v2.py` o `duckdb_manager.py`
> **siempre** necesita pasar el smoke test antes del commit.

```bash
python evals/smoke_test.py && git add ... && git commit
```

---

## ¿Dónde estamos?

**Milestone:** v2.0 — Function Calling Architecture
**Fase actual:** Phase 5 — Function Calling Core
**Benchmark:** 61/61 ✓ (verificado 2026-04-12)

Para ver el estado completo: [STATE.md](./STATE.md)
Para ver la hoja de ruta: [ROADMAP.md](./ROADMAP.md)

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
src/basic_stats/        ← código del engine (mover aquí = Phase 4 ya hecho)
  agent.py
  config.py
  duckdb_manager.py
  llm_query_engine_v2.py
  query_planner.py
  models.py
  knowledge_base.py
  prompts/

evals/
  questions_benchmark.json   ← 61 preguntas, fuente de verdad
  smoke_test.py              ← sanity check rápido (10 preguntas)
  benchmark_runner.py        ← benchmark completo en paralelo
  eval_runner.py             ← benchmark completo secuencial (referencia)

tests/
  test_query_planner.py
  test_dual_bucket_hardening.py

docs/
  canonicalization_rules.md  ← cómo funciona el QueryPlanner (leer antes de Phase 5)
  evals/                     ← resultados de benchmarks anteriores

pages/
  basic_stats.py             ← página Streamlit

.planning/                   ← artefactos GSD (no editar a mano)
  STATE.md                   ← estado actual
  ROADMAP.md                 ← fases y criterios de éxito
  REQUIREMENTS.md            ← requisitos trazables
```

---

## Correr el benchmark

```bash
# Smoke test — 10 preguntas, ~2 min
python evals/smoke_test.py

# Benchmark completo — 61 preguntas, paralelo (~5 min)
python evals/benchmark_runner.py --workers 5

# Benchmark completo — secuencial (~20 min)
python evals/eval_runner.py
```
