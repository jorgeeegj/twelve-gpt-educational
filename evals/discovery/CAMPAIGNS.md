# Targeted Campaigns

Campaign files live in `evals/discovery/campaigns/<name>.json`. Each file is a JSON array of question dicts conforming to the `seed_questions.json` schema (10-SPEC.md §3). The default generation mode is template-based (zero OpenAI cost).

---

## Generating a campaign

### Template-based mode (default — zero OpenAI cost)

```python
from evals.discovery.campaign_generator import generate_from_category, write_campaign

# Generate 4 questions for the UNSUPPORTED_FUTURE category
questions = generate_from_category("UNSUPPORTED_FUTURE", count=4)
path = write_campaign(questions, "unsupported_future_v1")
# → evals/discovery/campaigns/unsupported_future_v1.json
```

From a backlog cluster entry:

```python
from evals.discovery.campaign_generator import generate_from_cluster, write_campaign
from evals.discovery.failure_backlog import load_backlog, find_by_signature

backlog = load_backlog()
entry = find_by_signature(backlog, "unsupported_future__refuse_expected_but_answered")
questions = generate_from_cluster(entry, count=4)
path = write_campaign(questions, "unsupported_future_v1")
```

### Opt-in LLM mode (placeholder — raises NotImplementedError in v1)

```python
from evals.discovery.campaign_generator import generate_with_llm

# use_llm=False delegates to template mode (default)
questions = generate_with_llm("UNSUPPORTED_FUTURE", count=4, use_llm=False)

# use_llm=True raises NotImplementedError — LLM-assisted generation deferred
questions = generate_with_llm("UNSUPPORTED_FUTURE", count=4, use_llm=True)
# → NotImplementedError: LLM-assisted generation deferred — use template mode
```

---

## Running a campaign

Pass the written campaign path to `iteration_runner.run_campaign` (Plan 11-05):

```python
from evals.discovery.iteration_runner import run_campaign

run_campaign(path, label="unsupported_future_v1")
# Writes output under evals/runs/<ts>__synthetic_<label>/
```

---

## Naming convention

Campaign file names are sanitised to lowercase alphanumerics and underscores, capped at 64 characters. The sanitiser converts any non-alphanumeric run to `_` and strips leading/trailing underscores.

Examples:
- `"unsupported_future_v1"` → `unsupported_future_v1.json`
- `"Bad/Name with Spaces!"` → `bad_name_with_spaces.json`

---

## Worked example: Phase 10 cluster → targeted campaign

The Phase 10 live run produced the cluster `unsupported_future__refuse_expected_but_answered` (SYN_019/SYN_020). To generate a targeted 4-question follow-up campaign:

```python
from evals.discovery.campaign_generator import generate_from_category, write_campaign

questions = generate_from_category("UNSUPPORTED_FUTURE", count=4)
path = write_campaign(questions, "unsupported_future_v1")
print(path)  # evals/discovery/campaigns/unsupported_future_v1.json
```

All emitted questions have `expected_behavior: "refuse"` so the runner's guard correctly flags any answer as a failure. This makes the campaign a precision stress-test for the unsupported_future cluster.

---

## Schema reference

Each question in a campaign JSON must include:

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | `CAMP_<name>_<NNN>` format |
| `category` | str | One of the 12 taxonomy categories |
| `language` | str | `"en"` or `"es"` |
| `question` | str | The question text (multi-turn: `\|`-separated) |
| `expected_behavior` | str | `"answerable"`, `"refuse"`, or `"ambiguous_clarify"` |
| `expected_values` | any | `null` for template-generated campaigns |
| `notes` | any | Optional context; set by `generate_from_cluster` |
