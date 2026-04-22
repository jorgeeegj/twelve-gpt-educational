# Pre-Phase-9 Robustness Closeout — Plan de Ejecución

**Fecha:** 2026-04-22
**Tipo:** Minifase GSD (no reemplaza Phase 9)
**Referencia backlog:** [pre_phase9_robustness_backlog.md](./pre_phase9_robustness_backlog.md)
**Checklist UAT origen:** [pre_phase9_uat_checklist.md](./pre_phase9_uat_checklist.md)

---

## Resumen Ejecutivo

Plan de ejecución para cerrar 5 work items de robustez detectados en UAT antes de Phase 9. Duración estimada **una sesión**; impacto de código limitado a 3-4 archivos del core (`agent_tools.py`, `duckdb_manager.py`, `prompts/agent_system.yaml`) más dos documentos (`premier_league_2024_25_context.md`, `TEAM.md`). Cada WI tiene su propia verificación mínima ejecutable; el gate de salida es el **checklist UAT repetido con 0 señales rojas**.

**Lo que NO se hace en este plan:** Phase 9 (NLP polish), refactor arquitectónico, cambios en el contrato de las 4 mother tools.

---

## Estado de Partida

Ground truth del código (source: `STATE.md`, confirmado por UAT 2026-04-22):
- Phase 8 — League Context ✓ Complete
- Hotfix BUG-P90-CONTEXT ✓ Complete (cubre sólo goals/assists p90)
- Hotfix BUG-PARALLEL-TOOLS ✓ Complete
- Hotfix BUG-TRUTHFULNESS-APPEARANCES ✓ Complete
- Multi-turn chain de 4 turnos ✓ Validada
- 82/82 tests pasando (`uv run pytest tests/ -q -k "not fuzzy_resolve"`)

Documentación parcialmente desincronizada:
- `TEAM.md` indica "Fase actual: Phase 8" — obsoleto
- `STATE.md` está correcto y actualizado
- `ROADMAP.md` está correcto

---

## Orden Recomendado de Ejecución

El orden no es aleatorio: van **data-layer primero, prompt/doc layer después** para que cuando ajustemos prompt y definiciones ya sepamos que los números subyacentes son correctos.

### Paso 1 — WI-1 Subject Exclusion (P0)

**Por qué primero:** mayor impacto correctness, más crítico que no llegue a Phase 9. Un fix en `agent_tools.py` / `duckdb_manager.py` es bien localizado.

**Bloque de trabajo**
1. Identificar punto único donde construir la exclusión (tentativamente en `_match_value_expr` / helper shared).
2. Añadir `AND opponent_team_name != subject_team_name` condicionalmente cuando hay sujeto (player o team) + filtro de grupo rival.
3. Tests: 2 unitarios (team vs top-N, player vs is_big6).
4. Smoke manual del caso UAT Q9 ("Liverpool vs top 5").

**Gate paso 1:** `uv run pytest tests/ -q -k "not fuzzy_resolve"` → 84/84 (82 baseline + 2 nuevos).

### Paso 2 — WI-2 p90 Event Stats (P0)

**Por qué segundo:** completa el scope del hotfix BUG-P90-CONTEXT que quedó acotado a goals/assists. Fix técnico análogo al hotfix anterior — riesgo bajo, valor alto.

**Bloque de trabajo**
1. Extender `_PLAYER_MATCH_P90_MAP` con los event stats p90 que aparecen como tools-exposed (ver `agent_tool_schemas.py`): `shots_p90`, `xg_p90`, `key_passes_p90`, `progressive_passes_p90`, `touches_in_box_p90`, `aerial_duels_won_p90`, `recoveries_p90`.
2. Validar que `_match_value_expr` con `agg="p90"` soporta cada columna base (si alguna falta en `team_match` o `player_match`, documentar la exclusión).
3. Test parametrizado: 3 event stats × contexto Big Six → ratio decimal no nulo.
4. Actualizar línea "Residual risk" en STATE.md para reflejar el scope ampliado.

**Gate paso 2:** test parametrizado pasa + multi-turn chain sin regresión.

### Paso 3 — WI-3 Arithmetic Consistency (P0 prompt-layer)

**Por qué tercero:** depende de que WI-1 y WI-2 ya devuelvan números correctos. Si forzamos al LLM a "no hacer aritmética" antes de arreglar los datos, tendremos respuestas sin contradicciones... pero con los mismos datos malos.

**Bloque de trabajo**
1. Editar `src/basic_stats/prompts/agent_system.yaml`: añadir una regla corta en la sección de respuestas sobre no inventar diferencias/ratios no devueltos por tool.
2. Si la regla de prompt no basta en UAT, extender outputs de tools comparative para incluir `delta` pre-calculado (fallback plan).
3. Manual re-run de D7, D8, C5, F13 del UAT.

**Gate paso 3:** 4 preguntas comparativas sin cifras no-grounded; multi-turn chain H16 sigue pasando.

### Paso 4 — WI-4 Group Definitions (P1 doc + prompt)

**Por qué cuarto:** requiere que el data-layer esté estable para observar qué ambigüedades quedan del lado del lenguaje. Es el paso que más directamente toca Phase 9, pero se cierra aquí para evitar mezclar scope.

**Bloque de trabajo**
1. Reescribir `docs/premier_league_2024_25_context.md` sección "Team Categories" como **conjuntos disjuntos explícitos**:
   - "Champions League qualifiers (league-based, 2024/25)" = {Liverpool, Arsenal, Man City, Chelsea, Newcastle United}
   - "European competition (any route, 2024/25)" = unión explícita, con nota sobre Tottenham vía Europa League
   - "Top 6 (historical convention)" = {Arsenal, Chelsea, Liverpool, Man City, Man Utd, Tottenham} — diferenciado del Top 5 de standings
   - Crystal Palace asignado a **una sola** categoría (Conference League Qualifier), no ambas
   - "Mid-table" como rango cerrado de standings, disjunto de las categorías europeas
2. `agent_system.yaml`: 1 regla corta — "Para términos de grupo ambiguos, usa exactamente la definición del league context; no re-derives desde los standings."
3. Manual check: 3 preguntas UAT con términos ambiguos × 2 runs → conjuntos idénticos.

**Gate paso 4:** consistencia inter-run en términos ambiguos; no se introducen listas hardcodeadas de equipos en código (mantener regla Phase 8).

### Paso 5 — WI-5 Context Hygiene + TEAM.md (P2)

**Por qué último:** menor riesgo, mayor componente de housekeeping. También sirve como checkpoint de que el resto del trabajo se documenta correctamente.

**Bloque de trabajo**
1. `src/basic_stats/agent.py`: evaluar si basta un tag en el history append para turnos con error/empty tool output, o si requiere cambio en prompt. Decisión tomada tras observar el bug en UAT (si no es reproducible fácilmente, documentar y cerrar sin código).
2. `.planning/TEAM.md`: sync con STATE.md — Phase 8 ✓, hotfixes listados, próximo = Phase 9, fecha actualizada.
3. STATE.md: añadir sección de minifase cerrada con 5 work items y verificación.

**Gate paso 5:** `TEAM.md` y `STATE.md` alineados, UAT secuencia I17→A1 limpia.

---

## Gate Final de la Minifase

1. **Tests:** 82 baseline + 3-5 nuevos, todos en verde (`uv run pytest tests/ -q -k "not fuzzy_resolve"`)
2. **UAT:** batería completa de 22 preguntas de `pre_phase9_uat_checklist.md` ejecutada, **0 señales rojas** en categorías A-J. Señal K (idioma) observada pero no bloqueante (scope Phase 9 parcial).
3. **Docs:** STATE.md, TEAM.md, backlog de minifase marcados como cerrados con fecha.
4. **Commits:** cada WI en su propio commit con formato convencional (`fix:` / `docs:` / `test:`), mensajes explícitos.

---

## Archivos que se Esperan Tocar

| Archivo | WIs | Tipo de cambio |
|---------|-----|---------------|
| `src/basic_stats/agent_tools.py` | WI-1, WI-2, posiblemente WI-3 | Extensiones puntuales |
| `src/basic_stats/duckdb_manager.py` | WI-1, WI-2 (verificación) | Mínimo |
| `src/basic_stats/prompts/agent_system.yaml` | WI-3, WI-4 | 2 reglas cortas |
| `src/basic_stats/agent.py` | WI-5(a) condicional | Edit mínimo o sin cambio |
| `docs/premier_league_2024_25_context.md` | WI-4 | Reestructuración de Team Categories |
| `.planning/TEAM.md` | WI-5(b) | Refresh |
| `.planning/STATE.md` | Todos | Sección de minifase |
| `tests/test_agent_tools.py` | WI-1, WI-2 | 3-5 tests nuevos |

Ningún cambio esperado en: `agent_tool_schemas.py`, `agent_prompt.py`, `config.py`, `pages/basic_stats.py`.

---

## Riesgos si Entramos en Phase 9 sin Cerrar esta Minifase

| Riesgo | Severidad | Escenario |
|--------|-----------|-----------|
| **R1 — Respuestas fluidas con datos incorrectos** | 🔴 Crítica | Phase 9 mejora el tono y la verbalización. Sin WI-1 (subject exclusion) y WI-2 (p90 event stats), el usuario recibe prosa convincente alrededor de números mal calculados. Peor que la v2.0 pre-polish. |
| **R2 — Contradicciones internas amplificadas** | 🔴 Crítica | Los templates de verbalización de Phase 9 generan más texto adicional ("X scored Y, which is roughly Z% more than…"). Sin WI-3, cada frase secundaria es una oportunidad extra de contradicción aritmética. |
| **R3 — Inconsistencia de grupos en prosa natural** | 🟠 Alta | Phase 9 va a citar categorías ("Champions League teams", "top 6") en texto natural. Sin WI-4, el LLM elegirá una definición en T1 y otra en T2, visibilizando la inconsistencia en forma de lenguaje fluido. |
| **R4 — Regresión difícil de atribuir** | 🟠 Alta | Si entramos en Phase 9 con bugs de robustez abiertos, al aparecer un fallo UAT no sabemos si es de NLP o de datos. La superficie de cambio en Phase 9 es grande; la atribución se vuelve costosa. |
| **R5 — Docs stale propagan confusión a nuevos devs** | 🟢 Baja | TEAM.md desactualizado hace que cualquier nuevo integrante arranque con una foto incorrecta del milestone. Fix barato (WI-5b). |

**Conclusión:** R1+R2+R3 son suficientes para justificar la minifase antes de Phase 9. R4 es el multiplicador de coste; R5 es housekeeping.

---

## Checklist de Cierre

- [x] WI-1 merged + tests verdes (2026-04-23)
- [ ] WI-2 merged + tests verdes + residual risk eliminado de STATE.md
- [ ] WI-3 merged + 4 preguntas comparativas UAT limpias
- [ ] WI-4 merged + conjuntos de grupo consistentes entre runs
- [ ] WI-5 merged + TEAM.md sincronizado
- [ ] UAT completo repetido con 0 señales rojas
- [ ] STATE.md actualizado con sección "Pre-Phase-9 Robustness Closeout ✓ Complete"
- [ ] Listos para arrancar Phase 9
