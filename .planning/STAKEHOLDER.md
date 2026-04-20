# Stakeholder Feedback — Ágúst

> Source: Slack message from Ágúst (course instructor), received 2026-04-16.
> Read this file at session start. It defines priorities and constraints that override our own judgment.

---

## Priority Order (Ágúst's words)

1. **Random question robustness** — TOP priority. Do this first.
   > "Your priority should definitely be on the 1st point on the picture; improving the random question robustness."

2. **Follow-up questions / conversation memory** — Work on this in parallel with (1).
   > "What you can work on in parallel is improving the chat experience. The next steps of the course are more focused on the chat where you integrate function calling and memory. Here I would like the user to be able to ask follow up questions so that they can dig deeper into the topics."

   Example conversation chain Ágúst gave:
   > "How many goals has Haaland scored in the season"
   > → "But he only scores against the weaker teams. How many has he scored against the top 6 teams?"
   > → "Is that more than against the rest of the teams"
   > → "What about based on playing time?"

3. **League context injection** — Feed a league description paragraph to the LLM so it classifies teams dynamically (e.g. "top 6", "relegation zone") without hardcoded labels.

   Ágúst's example paragraph to inject:
   > "The English Premier League is the top football division in England and is made up by 20 teams. The team play each other twice, home and away, for a total of 38 games each. At the end of the season, the 3 bottom teams get relegated into the Championship and get replaced with the teams that get promoted. Usually, the top 4 teams qualify to the Champions League, but in the 2024/25 season, the Premier League got an extra champions league spot for their success in Europe. The team that finishes highest in the league outside of the teams that qualify for the Champions League earns a Europa League spot..."

   > "Regarding the categories, I would ideally like you to feed some context to the LLM describing the league so it can select the teams without you having to label them. This might be hard to do in scale, but since you only have one league then that should not be a problem."

4. **Visualization** — Interesting to explore but NOT the next step.
   > "The second point that you raise there might be something interesting for you to look into, but should not be the next step."

5. **Qualities integration** — Out of scope for this course entirely.
   > "The 3rd point is out of scope for the project as a part of this course."

---

## Roadmap Mapping

| Ágúst Priority | REQUIREMENTS.md | Phase |
|----------------|-----------------|-------|
| Robustness     | ROB-01, ROB-02  | Phase 8 |
| Memory / follow-up | MEM-01, MEM-02, MEM-03 | Phase 6 |
| League context | CTX-01, CTX-02, CTX-03 | Phase 7 |
| Visualization  | Backlog         | — |
| Qualities      | Out of scope    | — |

> **Note:** Ágúst said robustness (Phase 8) and memory (Phase 6) can run in parallel.
> The current roadmap sequences them — revisit phase ordering if we have bandwidth to parallelize.

---

## What NOT to Do

- Do not hardcode team labels (e.g. "top 6 = [Man City, Arsenal, ...]"). Let the LLM derive from context.
- Do not prioritize visualization over the first three items.
- Do not add qualities-related features.
- Do not ask Ágúst for clarification on these priorities — they are settled.

---

*Captured: 2026-04-16*
