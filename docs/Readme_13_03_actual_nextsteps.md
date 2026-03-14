# Twelve GPT Educational — Extended Football Analytics Workspace

This repository extends the original **Twelve GPT Educational** project with a more data-driven football analytics workflow focused on:

- building **player and team statistical datasets**
- creating custom **qualities**
- exposing those datasets through a **Streamlit app**
- developing a **Basic Stats Analyst** that answers factual football data questions from structured sources of truth

The goal is not to build a generic dashboard, but to build tools that generate **clear, explainable insight** from football data.

---

## Project philosophy

This project follows the spirit of the Twelve course:

- start from a clear football question
- define what is being measured
- define what it is being compared against
- build around **metrics**, **qualities**, and **insight**
- avoid building “dashboard for dashboard’s sake”
- use the LLM only where it adds value, not as the source of truth

In practice, this repo is evolving around three core layers:

1. **Data layer**  
   Clean, structured player and team datasets built from Wyscout-style event data and reference parquets.

2. **Quality layer**  
   A system to create custom football qualities from selected metrics and weights.

3. **Application / analyst layer**  
   Streamlit pages that expose these datasets and qualities, including a Basic Stats Analyst that answers factual questions.

---

## Main additions made in this repo

Compared with the original educational repo, the following custom developments have been added or extended:

### 1. Player data pipeline
We built a full player pipeline:

- `player_stats_summary.parquet`
- `player_full_stats.parquet`

These datasets include:

- raw event counts
- per-90 metrics
- percentages
- z-scores
- positional contextualisation
- biographical player info
- team info

### 2. Team data pipeline
We also built an analogous team pipeline:

- `team_stats_summary.parquet`
- `team_full_stats.parquet`

This allows the project to answer not only player questions, but also club/team questions such as:

- Which team has scored the most goals?
- Which team concedes the most goals?
- Which team wins the most aerial duels?
- Which team provokes the most offsides?

### 3. Quality Builder page
A new Streamlit page was added to create custom football qualities.

This page allows the user to:

- select metrics
- inspect correlations
- assign weights
- preview results with filters
- create and save a new custom quality
- persist it in the dataset and in a YAML file

### 4. Basic Stats Analyst page
A new Streamlit page was developed to answer factual data questions.

Its current design is:

- deterministic query over structured data first
- knowledge base lookup for definitions
- internal tabular result as source of truth
- LLM only used to verbalize the result naturally

This avoids hallucination-heavy behaviour and keeps the system grounded in the data.

---

## Repository structure

Below is a simplified explanation of the most relevant custom files and folders.

### `data/`
Contains source and reference files used to build the datasets.

Typical files include:

- `players.parquet`
- `teams.parquet`
- `minutes.parquet`
- `matches.parquet`
- `event_data/*.json`
- `verbal_model_qa.csv`

#### Important file
`verbal_model_qa.csv`

This is the current knowledge base for definitional questions, such as:

- What is Breaking the Lines?
- How is Creative Playmaker calculated?
- What does it mean for a player to be outstanding in a quality?

---

### `output/`
Contains generated datasets used by the application.

Current important outputs:

- `player_stats_summary.parquet`
- `player_full_stats.parquet`
- `team_stats_summary.parquet`
- `team_full_stats.parquet`

These are the main structured sources of truth for the app.

---

### `pages/`
Contains Streamlit app pages.

Important pages include:

- `about.py`
- `football_scout.py`
- `embedder.py`
- `quality_builder.py`
- `basic_stats.py`

#### `quality_builder.py`
Custom page to create new qualities from selected metrics.

#### `basic_stats.py`
Custom page to query factual information from the player/team datasets.

---

### `utils/basic_stats/`
Custom backend for the Basic Stats Analyst.

Important modules:

- `agent.py`
- `knowledge_base.py`
- `intent_router.py`
- `metric_resolver.py`
- `query_engine.py`
- `response_generator.py`

#### `agent.py`
Main orchestrator.

It decides whether a question should go to:

- the knowledge base
- a deterministic query on player data
- a deterministic query on team data
- filtered player queries
- response verbalization

#### `knowledge_base.py`
Loads and searches `verbal_model_qa.csv`.

Used for definitional / conceptual football questions.

#### `intent_router.py`
Classifies the question type, for example:

- definition
- top player metric
- bottom player metric
- top team metric
- bottom team metric
- filtered player metric

#### `metric_resolver.py`
Maps natural language to actual dataset columns.

Examples:

- “goals” → `total_goals`
- “successful passes” → `pass_accuracy_pct`
- “conceded goals” → `total_goals_against`
- “play more backwards” → `back_passes`

#### `query_engine.py`
Executes deterministic queries on:

- `player_full_stats.parquet`
- `team_full_stats.parquet`

It handles:

- top/bottom queries
- player/team distinction
- filtered player queries
- metric resolution

#### `response_generator.py`
Takes the internal tabular result and asks the LLM to verbalize it naturally.

Important rule:
the LLM is not used as the source of truth.  
It only turns structured result rows into a natural answer.

---

### `scripts/`
Contains scripts to build datasets.

Important scripts include:

- `build_player_stats_summary.py`
- `build_player_full_stats.py`
- `build_team_stats_summary.py`
- `build_team_full_stats.py`

---

## Data pipeline overview

## 1. Player pipeline

### `build_player_stats_summary.py`
Scans all event JSON files and aggregates data per player.

It combines:

- event data
- minutes data
- player metadata
- team metadata

The script currently extracts a broad set of metrics including:

### Passing
- passes attempted
- accurate passes
- progressive passes
- long passes
- forward passes
- back passes
- through passes
- smart passes
- passes to final third
- passes to box
- key passes
- crosses
- passes under pressure
- average pass length

### Shooting
- shots
- shots on target
- goals from events
- xG total

### Carrying / progression
- carries
- progressive carries
- carry meters gained
- progressive runs

### Defensive / possession
- interceptions
- recoveries
- ball losses
- fouls committed
- fouls suffered
- clearances

### Duels / 1v1
- duels
- defensive duels
- defensive duels won
- offensive duels
- offensive duels won
- aerial duels
- aerial duels won
- dribbles attempted
- dribbles won
- dribbled past attempts
- sliding tackles

### Chance creation / context
- shot assists
- assists from events
- second assists
- third assists
- touches in box
- offsides

### Goalkeeper events
- goalkeeper exits
- shots against
- saves
- reflex saves
- conceded goals from keeper events

### Zone usage
- actions in Z1, Z2, Z3, Z4, Z5

### Additional summary fields
- total minutes
- goals
- assists
- own goals
- yellow cards
- red cards
- matches played
- main position
- player bio fields
- team name

It also computes ratio metrics like:

- `pass_accuracy_pct`
- `defensive_duel_won_pct`
- `offensive_duel_won_pct`
- `aerial_duel_won_pct`
- `dribble_success_pct`

---

### `build_player_full_stats.py`
Builds on `player_stats_summary.parquet` and creates:

- `_p90` columns
- `_zscore` columns
- per-position z-scores
- negative metric inversion where needed

This dataset is the main player-level source used by the app.

---

## 2. Team pipeline

### `build_team_stats_summary.py`
Builds a team summary from:

- `minutes.parquet`
- event JSON files
- `teams.parquet`

It creates a team-level equivalent of the player summary.

Important features:

- team minutes are approximated from summed player minutes divided by 11
- goals for / goals against are calculated at match-team level
- raw team event aggregates are extracted from JSON
- team percentages are computed from totals, not from averages of player percentages

This is important because for teams:

- pass accuracy must be  
  `passes_accurate / passes_attempted`
- not the mean of player pass accuracies

Current team metrics include the same main families as the player summary:

- passing
- shooting
- carrying
- defensive actions
- duels
- dribbles
- creation
- offsides
- fouls suffered
- goalkeeper actions
- zone actions
- pass accuracy
- aerial duel win percentage
- dribble success percentage
- average pass length

---

### `build_team_full_stats.py`
Builds on `team_stats_summary.parquet` and creates:

- `_p90`
- `_zscore`
- ratio z-scores
- negative-metric inversion where appropriate

This dataset is the main team-level source used by the app.

---

## Quality Builder

The Quality Builder page was developed to let the user define custom football qualities manually.

### Current behaviour
The page allows the user to:

- select a subset of available metrics
- inspect their correlations
- set metric weights
- define a quality name
- preview the resulting ranking
- filter the preview by position
- filter the preview by minimum minutes
- create the quality if the preview is satisfactory

### Output
When a quality is created:

- a new quality column is added to the dataset
- a YAML file is saved under `qualities/`
- this quality can later be used in the wider ecosystem

### Important design choice
The builder is intended to support the workflow:

1. define football idea
2. choose metrics
3. validate preview
4. create quality
5. reuse that quality in analysis / agent / wordalisation

---

## Basic Stats Analyst

The Basic Stats Analyst is being developed as a factual football data assistant.

### Its intended scope
Answer questions such as:

- Who scored the most goals?
- Which team has scored the most goals?
- Which player has the most recoveries?
- Which team wins the most aerial duels?
- Who are the best midfielders under 23 with progressive passing?
- What is Breaking the Lines?

### Current architecture
The system works in 4 steps:

1. **Intent routing**  
   Detect whether the question is definitional or factual.

2. **Knowledge base or deterministic query**  
   - definitions go to `verbal_model_qa.csv`
   - factual questions go to player/team data

3. **Internal tabular result**  
   The system builds an internal result table as the source of truth.

4. **LLM verbalization**  
   The LLM turns the structured result into a natural sentence without inventing facts.

### Important principle
The LLM is not doing the data retrieval work.  
It is only verbalizing the result.

---

## Improvements already incorporated in Basic Stats Analyst

During development, several upgrades were added:

### 1. Player vs team distinction
The query engine can now distinguish between player and team questions.

### 2. Deterministic query first
Simple factual questions are answered from the structured datasets directly.

### 3. Knowledge base for definitions
Definitional questions are answered from `verbal_model_qa.csv`.

### 4. Natural language metric mapping
The metric resolver now handles more natural phrasing, for example:

- successful passes
- conceded goals
- shots on target
- more backwards
- commit more fouls

### 5. Hidden table, user-facing text
The user now receives natural language output rather than raw tables by default.

### 6. Better verbalization rules
The response generator was improved so that:

- values are included
- decimals are rounded
- players mention useful context like appearances
- teams do not mention irrelevant context such as matches played when all teams play the same league schedule

---

## Current known limitations

This first version is already useful, but still has limitations.

### 1. Intent routing is still rule-based
It works for many simple questions, but can fail on more unusual formulations.

### 2. Metric resolution still needs broader coverage
Many aliases have already been added, but this will continue to be refined.

### 3. Team semantics can still be ambiguous
Some questions can be phrased in ways that require more semantic understanding than simple alias matching.

### 4. No general comparative reasoning yet
The system is not yet designed to answer more advanced questions like:

- compare player A and player B stylistically
- who is the best build-up midfielder in the league?
- which defenders combine aerial dominance and progression best?

These are planned future steps.

### 5. No full benchmark harness yet
At the moment, evaluation is being done manually through iterative testing.

---

## How to run the project

## 1. Build datasets
Typical order:

```bash
python scripts/build_player_stats_summary.py
python scripts/build_player_full_stats.py
python scripts/build_team_stats_summary.py
python scripts/build_team_full_stats.py
```
## 2. Run the app

```bash
python -m streamlit run app.py
```

## Suggested usage workflow

A productive workflow for this repo is:

1. Build or rebuild the player and team datasets.
2. Test the generated data outputs.
3. Create custom qualities in the Quality Builder.
4. Query metrics and qualities in the Basic Stats Analyst.
5. Refine the language mapping and query behaviour based on observed failures.
6. Later, connect this with richer narrative / wordalisation tools.

## What has been achieved so far

At this stage, the repo already supports:

- a player stats pipeline
- a team stats pipeline
- custom quality creation
- factual football Q&A from structured datasets
- definitional football Q&A from a knowledge base
- LLM verbalization grounded in deterministic results

This means the project already has a strong base for the course requirements.

## Recommended next steps

If we consider this first testing phase closed, the next steps should be:

### 1. Continue refining Basic Stats Analyst pass rate

Focus on:

- broader metric aliases
- stronger intent routing
- more natural phrasings
- player/team semantic disambiguation

### 2. Build a small benchmark set

Create a file or notebook with grouped test questions such as:

- player goals / assists
- team attack / defence
- passing metrics
- duel metrics
- goalkeeper metrics
- filtered queries
- definitional queries

This will make progress measurable.

### 3. Add debug and traceability

It would be useful to expose optional internal debug such as:

- detected intent
- resolved metric
- source used
- filters applied
- structured result rows

This makes failure analysis much easier.

### 4. Expand semantic layer carefully

Future versions can allow the LLM to help map more abstract concepts like:

- build-up midfielder
- press resistant player
- aerial dominance
- creative full-back

But the LLM should still remain constrained by the real structured data.

### 5. Integrate custom qualities more deeply

The next big milestone is to make qualities created in Quality Builder flow naturally into the Basic Stats Analyst.

That would allow questions like:

- Which midfielders rank highest in our custom build-up quality?
- Which defenders score highest in aerial dominance?
- Which teams have the best profile in a selected metric combination?

### 6. Prepare for richer visual analysis

Because both players and teams already have structured summary/full datasets, the project is in a good position later to support:

- distribution charts
- radar-like comparisons
- quality validation plots
- wordalisation backed by statistical context

### 7. Consider a later semantic upgrade

Only once the deterministic version is solid, it may make sense to explore:

- LangChain-style dataframe agents
- richer query planning
- abstract football concept routing

But this should come after the deterministic backbone is stable.

## Final note

This repo is currently evolving from an educational base into a more complete football analytics workspace.

The important thing is that the foundation is now being built in the right order:

1. first, reliable data
2. then, explainable qualities
3. then, deterministic retrieval
4. finally, controlled language generation

That makes the project much more robust, explainable, and aligned with real football analysis needs.