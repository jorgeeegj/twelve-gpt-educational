---
phase: phase-8
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/basic_stats/agent_prompt.py
  - src/basic_stats/prompts/agent_system.yaml
  - scripts/verify_league_context.py
  - tests/test_agent_prompt.py
autonomous: true
requirements:
  - CTX-01
  - CTX-02
  - CTX-03
must_haves:
  truths:
    - "LLM answers 'which teams are in the top 4?' using actual 2024-25 standings, not a hardcoded list"
    - "LLM answers 'which teams were relegated?' correctly (Leicester, Ipswich, Southampton)"
    - "LLM answers 'who are the Big Six?' with historical definition, noting their actual 2024-25 positions"
    - "LLM answers 'which teams qualified for the Champions League?' including Newcastle (5th, extra CL spot)"
    - "LLM answers 'which team finished 7th?' correctly (Nottingham Forest, Europa League via league)"
    - "No Python source file contains a hardcoded list of team tier/group assignments (Big Six, top 4, relegation zone)"
  artifacts:
    - path: "src/basic_stats/agent_prompt.py"
      provides: "Reads docs/premier_league_2024_25_context.md and passes its content as {league_context} to template.format()"
      exports: ["build_system_prompt"]
    - path: "src/basic_stats/prompts/agent_system.yaml"
      provides: "YAML system prompt template with {league_context} placeholder replacing the old LEAGUE TIER CONVENTIONS hardcoded block"
    - path: "scripts/verify_league_context.py"
      provides: "5+ verification questions run against live agent, pass/fail result printed"
  key_links:
    - from: "src/basic_stats/agent_prompt.py"
      to: "docs/premier_league_2024_25_context.md"
      via: "Path(__file__).parent.parent.parent / 'docs' / 'premier_league_2024_25_context.md'"
      pattern: "league_context"
    - from: "src/basic_stats/prompts/agent_system.yaml"
      to: "build_system_prompt() return value"
      via: "{league_context} placeholder interpolated in template.format()"
      pattern: "\\{league_context\\}"
---

<objective>
Inject the static 2024-25 Premier League league context (standings, team categories, season narrative) into the agent's system prompt by reading docs/premier_league_2024_25_context.md at init time. Remove the hardcoded LEAGUE TIER CONVENTIONS block from agent_system.yaml and replace it with a {league_context} placeholder. Verify 5+ league-context questions are answered correctly.

Purpose: The LLM needs accurate knowledge of "top 6", "relegation zone", "Champions League spots", and "Big Six" for this specific season without any hardcoded team group lists in code.
Output: Updated agent_prompt.py, updated agent_system.yaml, new scripts/verify_league_context.py.
</objective>

<execution_context>
@/Users/ricardoheredia/Twelve-GPT-Educational/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@/Users/ricardoheredia/Twelve-GPT-Educational/.planning/ROADMAP.md

# Key source files — read before touching anything
@/Users/ricardoheredia/Twelve-GPT-Educational/src/basic_stats/agent_prompt.py
@/Users/ricardoheredia/Twelve-GPT-Educational/src/basic_stats/prompts/agent_system.yaml
@/Users/ricardoheredia/Twelve-GPT-Educational/docs/premier_league_2024_25_context.md

<interfaces>
<!-- Current agent_prompt.py signature — do not change the function signature -->
def build_system_prompt(duck: DuckDBManager) -> str:
    """Build the full system prompt by interpolating live DB values into the YAML template."""
    # Currently calls template.format(max_gw=, team_count=, team_names=, positions=, player_count=)
    # Task 1 adds: league_context=<contents of docs/premier_league_2024_25_context.md>

<!-- Current agent_system.yaml block to REMOVE (lines 66-76): -->
  LEAGUE TIER CONVENTIONS (apply these definitions whenever the question uses these terms)
  - "Big Six" or "top 6 teams" (by club identity): Arsenal, Chelsea, Liverpool,
    Manchester City, Manchester United, Tottenham Hotspur
    → use filters.opponent_is_big6=true ...
  - "mid-table" or "mid-table teams": ranks 7–14 ...
  - "bottom 5 teams": ranks 16–20 ...
  - "top N opponents" ...
  - "bottom N opponents" ...

<!-- Replace that block with: -->
  {league_context}

<!-- CTX-02 note: league_standings DuckDB view exists (created Phase 4) but the
     approach decided is to read the static markdown file — no DB query needed for
     this phase. CTX-02 is satisfied because the markdown was generated FROM the
     standings data and references the view's data. Do not add a DB query. -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update agent_prompt.py to read and inject league_context</name>
  <files>src/basic_stats/agent_prompt.py</files>
  <action>
    In build_system_prompt(), after the existing DB queries and before the return statement:

    1. Add one line to read the markdown file:
       ```python
       _DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
       ```
       Add this constant near the top of the file alongside _PROMPTS_DIR (not inside the function).

    2. Inside build_system_prompt(), add before the return:
       ```python
       league_context = (_DOCS_DIR / "premier_league_2024_25_context.md").read_text(encoding="utf-8")
       ```

    3. Add `league_context=league_context` to the existing template.format() call.

    The final template.format() call must be:
    ```python
    return template.format(
        max_gw=max_gw,
        team_count=len(team_names),
        team_names=", ".join(team_names),
        positions=", ".join(positions),
        player_count=player_count,
        league_context=league_context,
    )
    ```

    No other changes. Do not add error handling — the file is in the repo and will always exist.
    Match existing code style: no type annotations on local variables, no docstrings on constants.
  </action>
  <verify>
    <automated>cd /Users/ricardoheredia/Twelve-GPT-Educational && python -c "
from src.basic_stats.duckdb_manager import DuckDBManager
from src.basic_stats.agent_prompt import build_system_prompt
duck = DuckDBManager()
prompt = build_system_prompt(duck)
assert 'Liverpool' in prompt, 'league_context not injected'
assert '2024/25 Final Standings' in prompt, 'standings table missing'
assert 'Champions League Qualifiers' in prompt, 'team categories missing'
print('OK: league_context injected into prompt')
"
    </automated>
  </verify>
  <done>build_system_prompt() returns a string containing the full contents of docs/premier_league_2024_25_context.md interpolated via {league_context}</done>
</task>

<task type="auto">
  <name>Task 2: Replace hardcoded LEAGUE TIER CONVENTIONS block in agent_system.yaml</name>
  <files>src/basic_stats/prompts/agent_system.yaml</files>
  <action>
    In agent_system.yaml, locate the section starting with:
      "  LEAGUE TIER CONVENTIONS (apply these definitions whenever the question uses these terms)"
    and ending with:
      '  - "bottom N opponents": filters.opponent_rank_min=(21-N) — e.g. bottom 3 → rank_min=18'

    Replace that entire block (lines 66–76 in the current file) with:
      {league_context}

    The replacement must be exactly one line: `  {league_context}` (two leading spaces to match YAML indentation level of the surrounding sections).

    Also remove the existing "PREMIER LEAGUE 2024-25 CONTEXT" intro paragraph (lines 7–15),
    which currently hardcodes: Big Six list, CL/EL spot rules, promoted sides. The injected
    {league_context} block covers all of this more accurately and completely.

    After inserting {league_context}, also add the following one-line routing rule into the
    HOW TO USE TOOLS section, immediately before the existing "- 'How many X has [player] done?'" line:
      - "Big Six" or "top 6 teams" (by historical identity) → use filters.opponent_is_big6=true
        (NOT opponent_rank_max — Man United finished 15th, Tottenham 17th in 2024-25)

    This preserves the tool-routing instruction that was inside the deleted block.

    After the change, the section ordering in the file should be:
    1. TEAMS block
    2. PLAYER POSITIONS block
    3. SEASON STATUS block
    4. AVAILABLE STATS block
    5. {league_context}   ← replaces old LEAGUE TIER CONVENTIONS (and old intro paragraph)
    6. HOW TO USE TOOLS block (with Big Six routing rule added at the top)
    7. HOW TO WRITE YOUR ANSWER block
    8. FOLLOW-UP QUESTIONS block
    9. PLAYERS block
  </action>
  <verify>
    <automated>cd /Users/ricardoheredia/Twelve-GPT-Educational && python -c "
import yaml
from pathlib import Path
text = Path('src/basic_stats/prompts/agent_system.yaml').read_text()
assert '{league_context}' in text, 'placeholder missing'
assert 'LEAGUE TIER CONVENTIONS' not in text, 'hardcoded TIER CONVENTIONS block not removed'
assert 'PREMIER LEAGUE 2024-25 CONTEXT' not in text, 'hardcoded intro paragraph not removed'
assert 'Big Six: Arsenal' not in text, 'hardcoded Big Six list still present'
template = yaml.safe_load(text)['system']
assert 'HOW TO USE TOOLS' in template, 'HOW TO USE TOOLS section missing'
assert 'opponent_is_big6' in template, 'Big Six routing rule missing from HOW TO USE TOOLS'
print('OK: placeholder present, both hardcoded blocks removed, Big Six routing rule preserved')
"
    </automated>
  </verify>
  <done>agent_system.yaml contains {league_context} where LEAGUE TIER CONVENTIONS used to be, and no hardcoded team tier lists remain in the file</done>
</task>

<task type="auto">
  <name>Task 3: Write verify_league_context.py and confirm 5+ questions pass</name>
  <files>scripts/verify_league_context.py</files>
  <action>
    Create scripts/verify_league_context.py that:

    1. Instantiates DuckDBManager and the BasicStatsAgent (same pattern as scripts/verify_multiturn.py — read that file first to match the style).

    2. Defines a list of at least 6 question/keyword-in-answer pairs covering:
       - "Which teams finished in the top 4 this season?" → answer must mention Liverpool, Arsenal, Manchester City, Chelsea
       - "Which teams were relegated from the Premier League in 2024-25?" → answer must mention Leicester, Ipswich, Southampton
       - "Who are the Big Six clubs in the Premier League?" → answer must mention all six: Arsenal, Chelsea, Liverpool, Manchester City, Manchester United, Tottenham
       - "Which teams qualified for the Champions League?" → answer must mention Newcastle (the 5th-place extra spot)
       - "Which team finished 7th and what European competition did they qualify for?" → answer must mention Nottingham Forest and Europa League
       - "How many points did the champions finish with?" → answer must mention 84 (Liverpool's points total)

    3. For each question, calls `agent.ask(question)`, captures the text response, and checks
       that the expected keywords appear (case-insensitive substring match is fine).
       The public method is `ask(self, question: str) -> str` — not `chat()`.

    4. Prints PASS/FAIL per question with the question text.

    5. Prints a summary: "X/N questions passed" and exits with code 0 if ≥5 pass, code 1 otherwise.

    Keep it under 80 lines. No argparse. No logging. Just direct print statements.
    Use `if __name__ == "__main__":` guard.
  </action>
  <verify>
    <automated>cd /Users/ricardoheredia/Twelve-GPT-Educational && python scripts/verify_league_context.py</automated>
  </verify>
  <done>Script runs end-to-end, prints PASS/FAIL per question, exits 0 with at least 5 of 6 questions passing</done>
</task>

<task type="auto">
  <name>Task 4: Add unit test for build_system_prompt() structure</name>
  <files>tests/test_agent_prompt.py</files>
  <action>
    Create tests/test_agent_prompt.py. Read tests/test_agent_tools.py first to match the
    existing test style (imports, fixtures, assertion patterns).

    Write a single test function `test_build_system_prompt_structure` that:
    1. Instantiates DuckDBManager()
    2. Calls build_system_prompt(duck)
    3. Asserts the following (no LLM call — purely structural):
       - "2024/25 Final Standings" in prompt       # league_context injected
       - "Champions League Qualifiers" in prompt    # team categories present
       - "Nottingham Forest" in prompt              # specific team from context
       - "LEAGUE TIER CONVENTIONS" not in prompt   # old hardcoded block removed
       - "Big Six: Arsenal" not in prompt           # intro paragraph removed
       - "opponent_is_big6" in prompt               # routing rule preserved in HOW TO USE TOOLS
       - len(prompt) > 3000                         # sanity: prompt is substantial

    No mocking. No parametrize. One function, under 25 lines.
  </action>
  <verify>
    <automated>cd /Users/ricardoheredia/Twelve-GPT-Educational && python -m pytest tests/test_agent_prompt.py -v</automated>
  </verify>
  <done>test_agent_prompt.py passes with 1 test; python -m pytest tests/ -q still shows all tests green</done>
</task>

</tasks>

<verification>
After all tasks complete, run these checks:

1. Unit tests (including new prompt structure test):
   ```
   python -m pytest tests/ -q
   ```
   Must show all green, including test_agent_prompt.py.

2. No hardcoded team group lists in Python source:
   ```
   grep -rn "Big Six\|top.6.*Arsenal\|top.4.*Liverpool\|relegation.*Leicester" src/basic_stats/*.py
   ```
   Must return zero results.

3. Full end-to-end verification script:
   ```
   python scripts/verify_league_context.py
   ```
   Must exit 0 with ≥5/6 passing.
</verification>

<success_criteria>
- build_system_prompt() injects the full contents of docs/premier_league_2024_25_context.md into the system prompt via {league_context}
- agent_system.yaml has no hardcoded team tier lists — only {league_context} placeholder and opponent_is_big6 routing rule
- tests/test_agent_prompt.py passes (deterministic, no LLM, joins permanent test suite)
- scripts/verify_league_context.py exits 0 with ≥5 of 6 questions passing
- All existing unit tests still pass (no regression)
</success_criteria>

<output>
After completion, create `.planning/phase-8/phase-8-01-SUMMARY.md` with:
- What was changed in each file (1-2 sentences per file)
- Which 6 questions were tested and how many passed
- The grep command result confirming zero hardcoded team lists
</output>
