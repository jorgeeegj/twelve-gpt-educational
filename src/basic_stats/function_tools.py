# DEPRECATED — Phase 5 pivot (2026-04-12)
#
# The original 4-tool schemas (query_entity_stats, compare_across_buckets,
# rank_by_metric, query_temporal_window) are deleted. They were a drop-in
# replacement for _canonicalize_raw_plan but kept the same heuristic layer
# one level down. See .planning/phase-5/PHASE_5_NOTES.md for context.
#
# New tool schemas live in src/basic_stats/agent_tool_schemas.py (Task 2).
