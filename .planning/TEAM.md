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
**Fase actual:** Phase 5 — Function Calling Core ◐ In Progress
**Benchmark:** 51/61 = 83.6% faithfulness gate (2026-04-13) — objetivo ≥58/61

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
src/basic_stats/             ← código del engine (Phase 4 completa)
  agent.py                   ← BasicStatsAgent — loop function-calling (Phase 5)
  agent_tools.py             ← implementación de los 9 tools (Phase 5)
  agent_tool_schemas.py      ← schemas OpenAI strict mode (Phase 5)
  agent_prompt.py            ← build_system_prompt() con contexto dinámico
  config.py                  ← cliente Azure OpenAI + modelo
  duckdb_manager.py          ← todas las queries SQL
  llm_query_engine_v2.py     ← pipeline viejo (v1) — NO tocar, solo referencia
  query_planner.py           ← pipeline viejo (v1) — NO tocar, solo referencia
  models.py
  knowledge_base.py
  prompts/
    agent_system.yaml        ← system prompt del agente (editar con cuidado)

evals/
  questions_benchmark.json   ← 61 preguntas, fuente de verdad
  agent_benchmark.py         ← benchmark del nuevo agente (Phase 5) ← USAR ESTE
  judges/
    faithfulness_judge.py    ← juez determinista: verifica números en respuesta
  smoke_test.py              ← sanity check rápido (pipeline viejo)
  benchmark_runner.py        ← benchmark pipeline viejo (referencia)

tests/
  test_query_planner.py
  test_dual_bucket_hardening.py

docs/
  canonicalization_rules.md  ← reglas del QueryPlanner viejo (referencia)
  progress/                  ← logs de sesión — leer para contexto, no editar
  evals/                     ← resultados de benchmarks anteriores

pages/
  basic_stats.py             ← página Streamlit

.planning/                   ← artefactos GSD (no editar a mano)
  STATE.md                   ← estado actual + fallos pendientes Phase 5
  ROADMAP.md                 ← fases y criterios de éxito
  REQUIREMENTS.md            ← requisitos trazables
  TEAM.md                    ← este archivo
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

**Última ejecución:** `evals/runs/2026-04-13_00-30-05__phase5_final_v2` → 51/61 = 83.6%
