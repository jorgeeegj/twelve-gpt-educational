# AGENTS.md

## Qué es este proyecto
Basic Stats Analyst: sistema para análisis estadístico y soporte a decisiones sobre datos de fútbol.

## Objetivo principal
Desarrollar y mantener un sistema fiable, modular y eficiente para consultas, análisis y evolución del proyecto con mínimo derroche de contexto y tokens.

## Restricciones duras
- Respetar arquitectura y convenciones existentes.
- Spec first, plan before code.
- Tareas pequeñas y verificables.
- No cambios grandes sin validación.
- Persistir contexto útil en archivos, no en chat.

## Cómo trabajamos
- Primero leer contexto del proyecto.
- Luego producir SPEC/PLAN si la tarea no está cerrada.
- Ejecutar en bloques pequeños.
- Verificar antes de dar por hecho.
- Actualizar STATE.md al terminar.

## Qué significa “hecho”
- Código implementado
- Verificación ejecutada
- Estado/documentación actualizados
- Siguiente paso claro en STATE.md

## Token hygiene defaults
- Modelo por defecto: Sonnet
- /clear entre tareas no relacionadas
- /compact tras planificación o debugging largo
- MCPs mínimos por proyecto