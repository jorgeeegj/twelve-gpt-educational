# Project Notes — Basic Stats Analyst
## PL 2024 | TwelveGPT Educational

---

## The Framework: What the Presentation Covers

### Core concept: "Qualities"
Twelve's framework for measuring player/team performance using football-relevant concepts, not raw stats. The 5 key qualities shown are: Run Quality, Finishing, Involvement, Box Threat, Passing Quality.

### The philosophy
- Start with football knowledge, not data — define *what* you want to measure first
- A quality is made of 3–10 metrics with assigned weights
- Metrics are meaningless without the right comparison group (position, age, league, etc.)

### Creating a Scouting Quality — the worked example
Uses **"Passing Quality for midfielders"** as a case study:

1. Define it in football terms: *"ability to deliver threatening passes, evaluated by quality not quantity"*
2. Map to data metrics:
   - Passes (xT) → overall threat
   - Crosses (xT), Passes into final third (xT), Passes in final third (xT) → variety
   - Creative passes (assists, key passes, shot assists) → chance creation
3. Use a correlation matrix to check redundancy between metrics and adjust
4. Final weights: Passes xT (30%), Passes into third xT (20%), Passes third xT (20%), Crosses xT (20%), Creative passes (10%)
5. Result: a distribution plot showing De Bruyne vs. other players

### Team quality
Same process applied to teams — example: "defensive transitions" broken into counterpressing, compactness, and opponent progression metrics.

---

## Available Data

### 4 parquet files (in `data/`)

| File | Description |
|---|---|
| `players.parquet` | 684 players — name, position role, foot, height, birth country |
| `teams.parquet` | 20 PL teams |
| `matches.parquet` | 380 matches, PL 2024 season |
| `minutes.parquet` | Per-appearance data — minutes played, position, goals, assists, cards |

### 380 event JSON files (one per match)

Every event has `x, y` coordinates (start) and `endLocation` (for passes) — 0–100 scale, standard Wyscout format.

**Primary event types:**
`pass`, `shot`, `duel`, `carry`, `clearance`, `interception`, `infraction`, `corner`, `free_kick`, `goal_kick`, `throw_in`, `offside`, `shot_against`, `goalkeeper_exit`, `game_interruption`

**Key secondary tags:**

- **Passes:** `progressive_pass`, `pass_to_final_third`, `pass_to_penalty_area`, `deep_completion`, `smart_pass`, `key_pass`, `assist`, `second_assist`, `shot_assist`, `cross`, `deep_completed_cross`, `under_pressure`, `through_pass`, `long_pass`
- **Shots:** `goal`, `opportunity`, `touch_in_box`, `head_shot`, `xg` value
- **Duels:** `offensive_duel`, `defensive_duel`, `aerial_duel`, `loose_ball_duel`, `dribble`, `sliding_tackle`
- **Other:** `counterpressing_recovery`, `interception`, `progressive_run`, `recovery`

**Positions in the data:** Midfielder, Winger, Full Back, Central Defender, Striker, Goalkeeper

---

## What Qualities You Could Build

| Position | Quality | Key Metrics |
|---|---|---|
| Striker | Goal Threat | Shots per 90, xG per 90, xG per shot, touch_in_box per 90 |
| Midfielder | Progression Quality | progressive_pass, pass_to_final_third, pass_to_penalty_area, progressive_run, smart_pass — all per 90 |
| Winger | Attacking Contribution | deep_completed_cross, key_pass, shot_assist per 90, dribble success rate |
| Defender | Defensive Disruption | interceptions, defensive_duel win rate, aerial_duel win rate, counterpressing_recovery per 90 |

---

## Midfielder Quality Definitions (Valverde / Kroos / Pedri style)

10 football-first definitions for reference when choosing a quality to build:

1. **Progressive Carrying** — advancing the ball by driving forward, beating defensive lines. *Think: Valverde bursting from midfield, Pedri carrying out of pressure.*

2. **Passing Range & Threat** — switching play and advancing into danger through varied passes. Measured by threat, not volume. *Think: Kroos dictating from deep.*

3. **Ball Retention Under Pressure** — receiving in tight spaces and keeping possession when the team needs to breathe. *Think: Pedri shielding, Kroos rarely losing the ball.*

4. **Chance Creation** — the final pass leading directly to a goal opportunity. Key passes, assists, shot assists, second assists. *Think: Kroos crossing, Valverde arriving late.*

5. **Box-to-Box Contribution** — contributing at both ends. Duels won defensively, arrivals in attacking areas. *Think: Valverde covering every blade of grass.*

6. **Press Resistance** — receiving under pressure and finding a solution immediately. *Think: Pedri and Kroos turning under pressure.*

7. **Defensive Engagement** — winning the ball in the middle third through positioning and interceptions. *Think: Valverde's intensity off the ball.*

8. **Set-Piece Delivery** — dangerous corners and free kicks. Evaluated by threat, not quantity. *Think: Kroos.*

9. **Line-Breaking Passing** — passing between or behind defensive lines. Through balls, smart passes. *Think: Kroos threading gaps, Pedri's combinations.*

10. **Transitional Impact** — influencing the game immediately after possession changes. Counterpressing recoveries + quick progression. *Think: Valverde winning it back then driving forward.*

---

## Our Project: Basic Stats Analyst

### What it is
A natural language agent that answers factual questions about the data:

> A user asks a free-form factual question → an LLM figures out what to compute → it queries the data → returns an answer in plain language.

Different from the football scout page (pre-defined metrics + RAG). This is a **data analyst agent** that reasons over tabular data.

### Example questions it should answer

**Player-level:**
- "Which midfielder covered the most ground progressively in the Premier League?"
- "Who created the most chances from open play?"
- "Which player won the most defensive duels per 90 minutes?"

**Team-level:**
- "Which team pressed highest up the pitch?"
- "Which team recovered the ball fastest after losing it?"
- "Which team created the most danger from set pieces?"

**Cross-cutting:**
- "Which team's midfielders contributed most to ball progression?"

### Suggested first quality: "Midfield Progression Quality" (team-level)

**The football question:**
> *What makes a team good at progressing the ball through midfield?*

**Definition:**
> A team's ability to systematically advance the ball from their own half into dangerous areas through purposeful passing and carrying — bypassing opposition pressure and penetrating defensive lines rather than going around them.

**Metrics:**

| Concept | Metric | Event tag |
|---|---|---|
| Breaking lines with passes | Progressive passes per 90 | `progressive_pass` |
| Penetrating the final third | Passes into final third per 90 | `pass_to_final_third` |
| Threatening the box | Passes to penalty area per 90 | `pass_to_penalty_area` |
| Carrying past pressure | Progressive runs per 90 | `progressive_run` |
| Quality not just quantity | Smart passes per 90 | `smart_pass` |

### What we need to decide before building
1. **Scope of questions** — open-ended free-form or a structured set the agent answers reliably?
2. **Data access** — parquet files are tabular and queryable; event JSONs need preprocessing into aggregated stats first
3. **Agent reasoning** — does it write pandas queries on the fly, or search pre-computed stats?

**Most practical path:** preprocess events into a stats table per player/team per 90, then let the LLM query that table to answer questions.
