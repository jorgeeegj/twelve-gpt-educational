# PLAN.md

## Active plan
Set up a clean Claude Code operating baseline for Basic Stats Analyst, then begin the first brownfield analysis session with minimal token waste.

## Step 1 — Finish tooling baseline
- Confirm GSD local install is working
- Install Everything Claude Code inside Claude Code
- Install ECC rules
- Confirm available commands

### Verification
- GSD commands appear
- ECC plugin appears in plugin list
- ECC namespaced commands are available

## Step 2 — Lock baseline settings
- Set default model to Sonnet
- Reduce thinking tokens
- Enable earlier auto-compact
- Set subagent model to Haiku

### Verification
- `~/.claude/settings.json` reflects the expected values

## Step 3 — Start brownfield mapping
- Run `/gsd:map-codebase`
- Review generated codebase artefacts
- Check whether they correctly capture stack, architecture, conventions, and concerns

### Verification
- Generated codebase docs exist
- They reflect the Basic Stats Analyst core areas accurately

## Step 4 — Initialize controlled project artefacts
- Run `/gsd:new-project`
- Compare generated project/planning artefacts against the curated local files
- Keep the tighter, clearer, less noisy version

### Verification
- `PROJECT.md`, `REQUIREMENTS.md`, `STATE.md` are usable and not bloated
- No important repo-specific context has been lost

## Step 5 — Open the first real working phase
- Choose one small, high-value task
- Create a short approved plan
- Execute only that task
- Verify
- Update `STATE.md`

### Verification
- One narrow task completed end-to-end
- State file updated with outcome and next step