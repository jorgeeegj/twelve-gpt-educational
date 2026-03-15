---
date: 2026-03-15
evaluator: Ricardo (automatizado — eval_runner_v2.py)
engine: LLMQueryEngineV2
---

# Eval — LLMQueryEngine v2

## Score: 20 / 20

Comparativa:

| Engine | Score | Enfoque |
|--------|-------|---------|
| QueryEngine (Jorge, baseline) | 10/20 | keyword matching + alias dict |
| QueryEngine + fixes (Ricardo) | 14/20 | aliases ampliados + position map + age fix + tie handling |
| LLMQueryEngine v1 (experimental) | 18/20 | LLM genera query completa — filtros no deterministas |
| **LLMQueryEngine v2 (híbrido)** | **20/20** | Tool use para métrica + filtros deterministas |

## Resultados por pregunta

| Q | Resultado | Métrica resuelta | Filtros aplicados |
|---|-----------|-----------------|-------------------|
| Q01 | ✅ | `total_goals` | — |
| Q02 | ✅ | `total_assists` | — |
| Q03 | ✅ | `total_minutes` | — |
| Q04 | ✅ | `total_yellow_cards` | — |
| Q05 | ✅ | `total_goals_p90` | `min_matches=10` |
| Q06 | ✅ | `total_goals` (teams) | — |
| Q07 | ✅ | `total_goals_against` | — |
| Q08 | ✅ | `aerial_duels_won` (teams) | — |
| Q09 | ✅ | `pass_accuracy_pct` (teams) | — |
| Q10 | ✅ | `offsides` (teams) | — |
| Q11 | ✅ | `progressive_passes_p90` | `position=midfielder` |
| Q12 | ✅ | `dribble_success_pct` | `min_matches=10` |
| Q13 | ✅ | `shots_on_target_p90` | `position=forward` |
| Q14 | ✅ | `recoveries_p90` | — |
| Q15 | ✅ | `aerial_duels_won_p90` | `position=defender` |
| Q16 | ✅ | `total_goals` | `age_lt=23` |
| Q17 | ✅ | `pass_accuracy_pct` | `position=midfielder` |
| Q18 | ✅ | `touches_in_box_p90` | `position=forward` |
| Q19 | ✅ | `progressive_passes_p90` (teams) | — |
| Q20 | ✅ | `key_passes_p90` (teams) | — |

## Cómo reproducir

```bash
.venv/bin/python eval_runner_v2.py
```

Requiere credenciales en `.streamlit/secrets.toml`.
