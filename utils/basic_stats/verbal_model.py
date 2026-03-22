import polars as pl
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

QA_PATH = BASE / "data" / "verbal_model_qa.csv"


class VerbalModel:

    def __init__(self):

        self.qa = pl.read_csv(QA_PATH)

    def search_definition(self, question):

        question_lower = question.lower()

        for row in self.qa.iter_rows(named=True):

            if row["question"].lower() in question_lower:
                return row["answer"]

        return None



"""
De primeras uso más simple, y cambiando el foco para que esté mejor en el ecosistema de twelve pero para no perder este trabajo de ÁLVARO
verbal_model.py
===============
Few-shot Q&A pairs for all 12 qualities.
Each list of dicts is ready to be injected into the LLM messages list
as user/assistant pairs BEFORE the actual user question.

Usage:
    from verbal_model import VERBAL_MODEL_PAIRS, SYSTEM_PROMPT
"""

# ── System prompt (Stage 1: Identity) ─────────────────────────────────────────
'''
DE MOMENTO DEJAMOS ESTE SYSTEM PROMPT MÁS COMPLEJO EN ESPERA Y YA LO IMPLEMENTAREMOS BIEN
SYSTEM_PROMPT = """You are a senior football scout and data analyst with 15+ years in the Premier League.
You write the way a top football analyst speaks — fluent in the game, tactically precise, and direct.

STYLE RULES (always follow):
- Write in flowing prose, as a scout would in a match report or briefing. Never use bullet lists, headers, or table-style comparisons.
- Use proper football vocabulary: press trigger, half-space, third-man run, positional rotation, carry into channel, screen the backline, double pivot, etc.
- When comparing players, tell a story about how they are different types of footballers, not just who scores higher.
- Mention raw numbers only when they genuinely illuminate a point — never dump stats for the sake of it. One telling figure is worth five generic ones.
- Avoid corporate phrasing like "it is worth noting", "in terms of", "this is reflected in", "it should be said".
- Be opinionated but grounded in the data. A good analyst has a point of view.
- Keep answers tight and punchy. Two focused paragraphs beat five vague ones.

PITCH ZONES — always translate these into plain football language when speaking to the user:
- Z1 = own goal area (goalkeeper zone, deepest defensive area)
- Z2 = low block (defensive half, behind the midfield block)
- Z3 = creation zone (central midfield / attacking midfield area, between the lines)
- Z4 = final third (the attacking third, outside the box)
- Z5 = opponent's penalty area (the box)
Never say "Z1", "Z2", etc. in your responses. Always use the plain English equivalent.

SCOUTING PROFILES — you have been trained on the following positional profiles for squad building:
- Full Back: balanced 50/50–60/40; avoid pure wingback profiles lacking defensive discipline; diagonal relationship with CB; immediate press reaction after losing ball; Ball Winning Specialist + High-Intensity Presser + Box Invader + Breaking the Lines
- Centre Back - Positional: organiser, aerial dominance, composure in possession (pass accuracy >84%), manages line, covers when Agile CB steps out; Aerial Powerhouse + Possession Anchor + Zone Skipper
- Centre Back - Agile: drives ball from deep, breaks opposition press through carries, quick turn of pace, covers space behind high line; Breaking the Lines (carry_z2_to_z4) + Zone Skipper + Ball Winning Specialist; NEVER recruit 3 of same CB type
- Defensive Midfielder - Positional: first movement always forward, quality/quantity ratio, comfortable asking for ball under pressure, screens backline, does not bomb forward; Possession Anchor + Ball Winning Specialist + Breaking the Lines
- Defensive Midfielder - Dynamic (box-to-box): wins ball and immediately drives forward, relentless stamina, counterpressing intensity; Transitional Engine + High-Intensity Presser; pair one of each in double pivot
- Wide / Attacking Midfielder: skill and brilliance; peripheral awareness; drops between lines and takes ball forward; fearless through-passing; quality-per-action ratio; avoid inconsistent performers; Creative Playmaker + Between the Lines + Final Third Catalyst
- Winger: balanced, direct, not one-dimensional; dribbling + crossing + weak foot competence; back-post presence; defensive transition alertness; supports full back; Wing Wizard + Vertical Box Threat + Box Invader + High-Intensity Presser; Between the Lines for inverted profiles
- Striker: physically competitive, never luxury; strong aerial game standing and with momentum; intelligent box movement (first/second phase); hold-up game outside box (1-2 touches, simple); between-lines space creation for wingers; presses GK; Vertical Box Threat + Aerial Powerhouse + Link Play + Between the Lines + High-Intensity Presser
When asked about scouting profiles or player recruitment, use this framework to guide your analysis.

CONTEXTUALISATION — always apply when interpreting any metric or quality score:
- Volume before rate: a success rate (aerial duel win %, duel win %, pass accuracy) means little without knowing how many times the action was attempted per 90 compared to the position-group average. A low volume is often a system signal, not an individual weakness.
- Team style affects every metric: a player at a possession-dominant team will show lower aerial duel volume, fewer recoveries, fewer defensive duels, and potentially higher pass accuracy than an equally skilled peer at a direct or low-block team. Always name the team context when explaining an unusual score.
- Distinguish system suppression from individual deficiency: if a metric is low AND the player's team ranks among the lowest in the league for that style of play (pressing, directness, aerial frequency), lead with the system explanation. If the team context does not explain the gap, name it as an individual finding.
- The Z-score labels (outstanding → poor) are relative to position-group peers in the same season. They already normalise for position role but NOT for team style. Flag this whenever interpreting a surprising label.
- NEVER use data alone to deliver a verdict on what a player cannot do. If the data shows low volume in a skill area due to system, the honest position is: we have not seen enough of it to judge. Flag it as something to factor into the recruitment assessment — a question that needs more investigation — not as a liability or a proven weakness. The data tells you what the system asked of him; it cannot tell you what he is capable of.

You never invent statistics. You base all player and team analysis strictly on the processed event data from the 2024/25 Premier League season.
When asked about a quality, explain it using the definitions from your training."""

# ── Verbal Model Q&A pairs (Stage 2) ──────────────────────────────────────────
# Pattern: {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}

VERBAL_MODEL_PAIRS = [

    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 1 — BREAKING THE LINES
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is Breaking the Lines?"},
    {"role": "assistant", "content": "Breaking the Lines measures a player's ability to bypass the opponent's midfield block — either with a pass or a carry — moving the ball from a low or mid-block position directly into the final third. It captures vertical progression that eliminates pressure lines rather than recycling possession sideways."},

    {"role": "user",      "content": "How is Breaking the Lines measured?"},
    {"role": "assistant", "content": "Breaking the Lines is a weighted sum of a player's performance compared to other players in the same position group in: passes from the low block (Z2) reaching the final third (Z4) at 40%, carries from the low block (Z2) reaching the final third (Z4) at 40%, and progressive passes per 90 at 20%."},

    {"role": "user",      "content": "How is Breaking the Lines calculated?"},
    {"role": "assistant", "content": "Breaking the Lines is calculated as the weighted sum of the z-scores of: pass_z2_to_z4_p90 (40%), carry_z2_to_z4_p90 (40%), and progressive_passes_p90 (20%), among other players who play the same position."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding at Breaking the Lines?"},
    {"role": "assistant", "content": "An outstanding Breaking the Lines player is an absolute engine in transition — they constantly bypass the midfield block with aggressive vertical passes or carries that eliminate entire pressure lines in a single action. They are rare because they combine positional depth with the courage and technique to play forward under pressure."},

    {"role": "user",      "content": "What does it mean for a player to be poor at Breaking the Lines?"},
    {"role": "assistant", "content": "A player poor at Breaking the Lines tends to recycle possession sideways or backwards when receiving in deep areas, rarely attempting passes or carries that skip into the final third. This is not always negative — some roles require ball retention rather than vertical progression."},

    {"role": "user",      "content": "Why are zone transitions the main component of Breaking the Lines?"},
    {"role": "assistant", "content": "Because a pass or carry that starts in the low block and lands in the final third is the most direct form of line-breaking possible — the ball bypasses the opponent's entire midfield structure in a single action. This is the clearest signal of vertical intent, and far harder to execute than progressive passing in higher areas."},

    {"role": "user",      "content": "Why are progressive passes included in Breaking the Lines?"},
    {"role": "assistant", "content": "Progressive passes capture vertical passing intent across the whole pitch, not just from deep positions. They complement the zone transition metrics by identifying players who consistently play forward regardless of their starting zone, broadening the quality beyond just deep-lying playmakers."},

    {"role": "user",      "content": "Is Breaking the Lines only relevant for midfielders?"},
    {"role": "assistant", "content": "No. Centre-backs and full-backs who drive or pass the ball from defensive positions into the final third score highly in Breaking the Lines. In modern football, ball-playing defenders are increasingly expected to break lines as the first step of build-up, making this quality relevant across defensive and midfield roles."},

    {"role": "user",      "content": "How does Breaking the Lines differ from Creative Playmaker?"},
    {"role": "assistant", "content": "Breaking the Lines focuses on the vertical progression of the ball — getting it from deep areas into the final third. Creative Playmaker focuses on what happens once in or near the final third: creating shots, finding key passes, threading through balls. A player can be excellent at one and poor at the other."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 2 — VERTICAL BOX THREAT
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is Vertical Box Threat?"},
    {"role": "assistant", "content": "Vertical Box Threat measures a player's tendency and ability to aggressively invade the opponent's penalty area through direct carries and runs. It captures players who attack the box from the final third with pace and directness, rather than combining in wider areas or waiting for the ball to arrive."},

    {"role": "user",      "content": "How is Vertical Box Threat measured?"},
    {"role": "assistant", "content": "Vertical Box Threat is a weighted sum of: carries from the creation zone (Z3) reaching the opponent's box (Z5) at 40%, progressive runs per 90 at 35%, and the percentage of a player's total actions occurring inside the box (Z5) at 25%."},

    {"role": "user",      "content": "How is Vertical Box Threat calculated?"},
    {"role": "assistant", "content": "Vertical Box Threat is calculated as the weighted sum of the z-scores of: carry_z3_to_z5_p90 (40%), progressive_runs_p90 (35%), and pct_actions_z5 (25%), among players in the same position group."},

    {"role": "user",      "content": "What does it mean for a player to have outstanding Vertical Box Threat?"},
    {"role": "assistant", "content": "A player with outstanding Vertical Box Threat has a voracious hunger to invade the central corridor. They consistently make late runs into the box, arrive at pace, and prioritise penetration through carrying and forward movement. They create chaos simply by being in the right place at the right time inside the area."},

    {"role": "user",      "content": "What does it mean for a player to have poor Vertical Box Threat?"},
    {"role": "assistant", "content": "A player with poor Vertical Box Threat operates mostly outside the penalty area. This does not mean they are ineffective — many playmakers and wide creators deliberately avoid the box to maintain width and space for their teammates. Context depends heavily on the player's role."},

    {"role": "user",      "content": "Why is percentage of actions inside the box included in Vertical Box Threat?"},
    {"role": "assistant", "content": "It captures a player's habitual presence inside the penalty area. A player who repeatedly makes themselves available in the danger zone — receiving passes, contesting headers, arriving late — shows an instinctive box mentality that carries a distinct tactical value, separate from how often they carry or run into it."},

    {"role": "user",      "content": "How does Vertical Box Threat differ from Breaking the Lines?"},
    {"role": "assistant", "content": "Breaking the Lines measures the ability to move the ball from deep positions into the final third. Vertical Box Threat measures the final step: the direct penetration into the box itself. A deep-lying midfielder might score highly in Breaking the Lines but very low in Vertical Box Threat."},

    {"role": "user",      "content": "What position profiles score highest in Vertical Box Threat?"},
    {"role": "assistant", "content": "Typically attacking midfielders, second strikers, and inverted wingers who cut inside and run in behind score highest. Centre-forwards who rely on movement and runs rather than hold-up play also score well. Traditional wide players who hug the touchline tend to score lower."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 3 — THE ZONE SKIPPER
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is The Zone Skipper?"},
    {"role": "assistant", "content": "The Zone Skipper measures a player's ability to perform actions that leap two or more pitch zones in a single movement — the most vertical and explosive plays in football. Zone skipping eliminates entire sections of the opponent's structure in one pass or carry, transforming a static build-up into a promising attack instantly."},

    {"role": "user",      "content": "How is The Zone Skipper measured?"},
    {"role": "assistant", "content": "The Zone Skipper is a weighted sum of: carries from the low block (Z2) reaching the opponent's box (Z5) at 35%, passes from the low block (Z2) reaching the final third (Z4+) at 35%, and long passes per 90 at 30%."},

    {"role": "user",      "content": "How is The Zone Skipper calculated?"},
    {"role": "assistant", "content": "The Zone Skipper is calculated as the weighted sum of the z-scores of: carry_z2_to_z5_p90 (35%), pass_z2_to_z4_p90 (35%), and long_passes_p90 (30%), among players in the same position group."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as a Zone Skipper?"},
    {"role": "assistant", "content": "An outstanding Zone Skipper possesses rare verticality. They can clean out two or more pressure zones with a single long ball or driving carry, transforming a static build-up into a promising attack in seconds. This quality is particularly valued in teams that play direct or transition-based football."},

    {"role": "user",      "content": "What does it mean for a player to be poor as a Zone Skipper?"},
    {"role": "assistant", "content": "A player poor at Zone Skipping operates primarily in short, horizontal or slightly progressive actions. They prefer to build gradually through the zones rather than skipping them. This is characteristic of possession-based playmakers who value ball retention over direct verticality."},

    {"role": "user",      "content": "Why are long passes part of The Zone Skipper?"},
    {"role": "assistant", "content": "Long passes are the most natural mechanism for skipping zones — a single switch from deep in your own half all the way to the final third or penalty area is the essence of the quality. While the zone transition metrics capture this precisely, long passes per 90 broadens the measure to include diagonal switches and range passing that may not always be captured by exact zone coordinates."},

    {"role": "user",      "content": "How does The Zone Skipper differ from Breaking the Lines?"},
    {"role": "assistant", "content": "Breaking the Lines is about moving the ball from the low block into the final third — one zone leap. The Zone Skipper demands more: carries or passes that travel from deep in your own half all the way to the penalty area, or across multiple zones in a single action. It is a more extreme, more direct version of vertical intent."},

    {"role": "user",      "content": "What position profiles score highest as a Zone Skipper?"},
    {"role": "assistant", "content": "Ball-playing centre-backs with range, deep-lying midfielders with long passing ability (registas), and goalkeepers who launch direct distribution all score highly. In attack, players who make explosive carrying runs from deep midfield positions can also score well."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 4 — CREATIVE PLAYMAKER
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is Creative Playmaker?"},
    {"role": "assistant", "content": "Creative Playmaker measures a midfielder's ability to create goalscoring opportunities for teammates through intelligent, penetrating passing. It captures players who act as the team's primary chance-creators — threading through balls, finding key passes, and delivering shot assists that others simply cannot see. This quality is assessed only among midfielders."},

    {"role": "user",      "content": "How is Creative Playmaker measured?"},
    {"role": "assistant", "content": "Creative Playmaker is a weighted sum of: smart passes per 90 at 35%, key passes per 90 at 35%, and shot assists per 90 at 30%."},

    {"role": "user",      "content": "How is Creative Playmaker calculated?"},
    {"role": "assistant", "content": "Creative Playmaker is calculated as the weighted sum of the z-scores of: smart_passes_p90 (35%), key_passes_p90 (35%), and shot_assists_p90 (30%), among midfielders only."},

    {"role": "user",      "content": "What is a smart pass?"},
    {"role": "assistant", "content": "A smart pass is a creative, through-ball or line-breaking pass that attempts to find a teammate in a more advanced position by bypassing one or more defenders. It is tagged by Wyscout as a pass that shows particular vision or ingenuity — these are the passes that unlock defences rather than simply circulating possession."},

    {"role": "user",      "content": "What is a key pass?"},
    {"role": "assistant", "content": "A key pass is a pass that directly leads to a shot by a teammate. It is the final action in a passing sequence that creates a goalscoring opportunity, regardless of whether the shot results in a goal. Key passes are the most direct measure of chance creation."},

    {"role": "user",      "content": "What is a shot assist?"},
    {"role": "assistant", "content": "A shot assist is any action — pass, carry, or cross — that directly precedes a shot. It is broader than a key pass because it includes assists by crossing and carrying, not just passing. Shot assists capture all the final contributions that create shooting situations."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as a Creative Playmaker?"},
    {"role": "assistant", "content": "An outstanding Creative Playmaker is the team's architect — they have peripheral vision to find through-balls others cannot see, acting as the principal catalyst for every real goalscoring chance. They consistently unlock compact defences with incisive final-third passing and are irreplaceable in the team's attacking structure."},

    {"role": "user",      "content": "What does it mean for a player to be poor as a Creative Playmaker?"},
    {"role": "assistant", "content": "A midfielder poor at Creative Playmaking rarely creates direct scoring opportunities through their passing. This may reflect a more defensive or transitional role rather than a technical limitation — a holding midfielder, for example, is not expected to be a creative playmaker."},

    {"role": "user",      "content": "How does Creative Playmaker differ from Box Invader?"},
    {"role": "assistant", "content": "Creative Playmaker measures the ability to create for others through passing vision. The Box Invader measures direct personal penetration into the penalty area through carrying and runs. A player can be an elite creative playmaker while rarely entering the box themselves — and vice versa."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 5 — HIGH-INTENSITY PRESSER
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is High-Intensity Presser?"},
    {"role": "assistant", "content": "High-Intensity Presser measures a player's defensive aggression and volume in the opponent's half. It captures players who consistently win the ball back through intense pressing, counterpressing, and defensive duels in dangerous areas of the pitch — keeping the team camped in the rival's territory."},

    {"role": "user",      "content": "How is High-Intensity Presser measured?"},
    {"role": "assistant", "content": "High-Intensity Presser is a weighted sum of: counterpressing recoveries per 90 at 50%, ball recoveries per 90 at 30%, and defensive duels per 90 at 20%."},

    {"role": "user",      "content": "How is High-Intensity Presser calculated?"},
    {"role": "assistant", "content": "High-Intensity Presser is calculated as the weighted sum of the z-scores of: counterpressing_recoveries_p90 (50%), recoveries_p90 (30%), and defensive_duels_p90 (20%), among players in the same position group."},

    {"role": "user",      "content": "What is a counterpressing recovery?"},
    {"role": "assistant", "content": "A counterpressing recovery occurs when a player wins the ball back within 5 seconds of losing possession, in a high position on the pitch. It is the clearest signal of elite defensive pressing — the player immediately hunts the ball after losing it, applying maximum intensity to regain possession before the opponent can reorganise."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as a High-Intensity Presser?"},
    {"role": "assistant", "content": "An outstanding High-Intensity Presser generates elite defensive volume in the opponent's half. Their counterpressing activation is vital to keeping the team camped in the rival's territory and forcing errors on the ball. They are relentless in their work-rate and often act as the engine of the team's defensive shape."},

    {"role": "user",      "content": "What does it mean for a player to be poor as a High-Intensity Presser?"},
    {"role": "assistant", "content": "A player poor at High-Intensity Pressing contributes little to the team's defensive intensity in high areas. They may be excellent in other aspects — such as positional defending or aerial duels — but they are not players who win the ball back through pressing. This is acceptable for deep-defending roles."},

    {"role": "user",      "content": "Why are counterpressing recoveries weighted at 50% in High-Intensity Presser?"},
    {"role": "assistant", "content": "Counterpressing recoveries are the highest-quality defensive action for a high press system. They require both positional awareness — being close enough to press immediately — and physical capacity to execute the recovery instantly. A high volume of counterpressing recoveries is the purest signal of elite pressing behaviour."},

    {"role": "user",      "content": "What position profiles score highest as High-Intensity Pressers?"},
    {"role": "assistant", "content": "Central midfielders and attacking midfielders who play in high-press systems — such as those used by Liverpool, Manchester City, or Chelsea — tend to score highest. Wide forwards in pressing teams also score well. Defensive midfielders in deeper-block systems typically score lower."},

    {"role": "user",      "content": "Is High-Intensity Presser the same as being a good defender?"},
    {"role": "assistant", "content": "No. High-Intensity Presser measures aggressive, high-volume pressing in the opponent's half. A good defender in traditional terms — winning duels, reading the game, organising the backline — is better captured by Ball Winning Specialist. The two qualities measure different aspects of defensive contribution."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 6 — THE BOX INVADER
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is The Box Invader?"},
    {"role": "assistant", "content": "The Box Invader measures a player's ability and tendency to deliver the ball into the opponent's penalty area — through passes, crosses, or direct carries into the box. It captures players who are the primary threat for feeding forwards and creating dangerous situations inside the penalty area."},

    {"role": "user",      "content": "How is The Box Invader measured?"},
    {"role": "assistant", "content": "The Box Invader is a weighted sum of: passes into the penalty area per 90 at 40%, crosses per 90 at 30%, and passes from the creation zone (Z3) directly into the opponent's box (Z5) per 90 at 30%."},

    {"role": "user",      "content": "How is The Box Invader calculated?"},
    {"role": "assistant", "content": "The Box Invader is calculated as the weighted sum of the z-scores of: passes_to_box_p90 (40%), crosses_p90 (30%), and pass_z3_to_z5_p90 (30%), among players in the same position group."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as a Box Invader?"},
    {"role": "assistant", "content": "An outstanding Box Invader is a constant delivery threat who forces the opposition to defend deep. They whip in crosses from wide positions, thread passes through congested areas into the six-yard box, and find teammates in dangerous central positions. Their deliveries consistently create the highest-probability goalscoring situations."},

    {"role": "user",      "content": "What does it mean for a player to be poor as a Box Invader?"},
    {"role": "assistant", "content": "A player poor at Box Invading rarely gets the ball into the penalty area directly. They may prefer to combine in central areas or play in a system that does not involve wide delivery. Possession midfielders and central playmakers who circulate the ball often score low here because their actions are designed to progress possession rather than deliver directly."},

    {"role": "user",      "content": "How does The Box Invader differ from Creative Playmaker?"},
    {"role": "assistant", "content": "The Box Invader measures the act of physically getting the ball into the penalty area — through crosses and direct passes to the box. Creative Playmaker measures the intelligence of passing to create shots, which often happens outside the box. A wide player might be an elite Box Invader with average Creative Playmaker score, while a central midfielder might be the opposite."},

    {"role": "user",      "content": "Why are crosses included in The Box Invader?"},
    {"role": "assistant", "content": "Crosses are the most common delivery mechanism into the penalty area from wide positions. They are a direct measure of a wide player's intent to serve strikers with deliveries into the six-yard box or penalty area. Including crosses ensures that wide attacking players and full-backs who deliver from the touchline are properly captured by this quality."},

    {"role": "user",      "content": "What position profiles score highest as Box Invaders?"},
    {"role": "assistant", "content": "Full-backs and wingers who cross the ball frequently score highest, particularly those who play in attacking systems with clear width. Advanced midfielders who regularly carry the ball to the byline and deliver into the box also score well. Central midfielders score lower unless they play a very direct, forward-passing role."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 7 — POSSESSION ANCHOR
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is Possession Anchor?"},
    {"role": "assistant", "content": "Possession Anchor measures a player's ability to retain the ball reliably under pressure — maintaining composure, passing accurately, and avoiding losses that disrupt the team's build-up. It identifies the players who act as the safe centre of gravity in possession, providing the structural reliability that allows the rest of the team to take risks."},

    {"role": "user",      "content": "How is Possession Anchor measured?"},
    {"role": "assistant", "content": "Possession Anchor is a weighted sum of: pass accuracy percentage at 50%, passes completed under pressure per 90 at 30%, and ball losses per 90 at negative 20% — meaning fewer losses improve the score."},

    {"role": "user",      "content": "How is Possession Anchor calculated?"},
    {"role": "assistant", "content": "Possession Anchor is calculated as the weighted sum of z-scores of: pass_accuracy_pct (50%), passes_under_pressure_p90 (30%), and ball_losses_p90 (-20%), among players in the same position group. Ball losses carry a negative weight — a lower loss rate improves the quality score."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as a Possession Anchor?"},
    {"role": "assistant", "content": "An outstanding Possession Anchor is the heartbeat of the team's build-up. They pass with near-flawless accuracy, are comfortable receiving and distributing under the most intense pressing, and almost never give the ball away carelessly. When the team needs a reliable option under pressure, this player is always available and always executes."},

    {"role": "user",      "content": "What does it mean for a player to be poor as a Possession Anchor?"},
    {"role": "assistant", "content": "A player poor at Possession Anchoring loses the ball frequently, passes inaccurately, or struggles when pressed. This does not mean they are a bad player — high-risk creative players who attempt difficult through-balls will naturally lose the ball more often and may score lower here, even while generating high creative output."},

    {"role": "user",      "content": "Why do ball losses carry a negative weight?"},
    {"role": "assistant", "content": "Because ball losses directly reduce possession quality. A player who keeps the ball reliably, even under intense pressure, is more valuable as an anchor than one who attempts ambitious actions and loses the ball often. The negative weight ensures that the quality penalises unreliable ball-handlers and rewards those who make the team feel secure in possession."},

    {"role": "user",      "content": "Why is pass accuracy weighted most heavily in Possession Anchor?"},
    {"role": "assistant", "content": "Pass accuracy is the most universal and comparable measure of technical reliability. A player who consistently completes passes at a high rate — regardless of how many they attempt — demonstrates that they can be trusted as the base of possession. It is the foundation of any anchoring role."},

    {"role": "user",      "content": "How does Possession Anchor differ from Creative Playmaker?"},
    {"role": "assistant", "content": "Possession Anchor rewards safety and reliability — completing passes and not losing the ball. Creative Playmaker rewards risk and vision — attempting through-balls, key passes, and shot assists. A player who is outstanding in Possession Anchor may score average as a Creative Playmaker because their instinct is to keep the ball rather than take risks with it."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 8 — BALL WINNING SPECIALIST
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is Ball Winning Specialist?"},
    {"role": "assistant", "content": "Ball Winning Specialist measures a player's ability to regain possession through physical and positional means — winning defensive duels, intercepting passes, and recovering loose balls. It identifies the players whose primary contribution is taking the ball away from the opposition."},

    {"role": "user",      "content": "How is Ball Winning Specialist measured?"},
    {"role": "assistant", "content": "Ball Winning Specialist is a weighted sum of: defensive duel success percentage at 40%, interceptions per 90 at 30%, and ball recoveries per 90 at 30%."},

    {"role": "user",      "content": "How is Ball Winning Specialist calculated?"},
    {"role": "assistant", "content": "Ball Winning Specialist is calculated as the weighted sum of the z-scores of: defensive_duel_won_pct (40%), interceptions_p90 (30%), and recoveries_p90 (30%), among players in the same position group."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as a Ball Winning Specialist?"},
    {"role": "assistant", "content": "An outstanding Ball Winning Specialist is a physical and positional defensive powerhouse who consistently wins the ball from opponents. They read passing lines to intercept, win an exceptional percentage of their defensive duels, and vacuum up loose balls in transition. Teams that play with high defensive lines rely heavily on these players to compensate for the space behind."},

    {"role": "user",      "content": "What does it mean for a player to be poor as a Ball Winning Specialist?"},
    {"role": "assistant", "content": "A player poor at Ball Winning rarely wins the ball directly from opponents. This is typical of possession-focused midfielders or technical attackers whose defensive contribution is minimal. It does not indicate a poor player overall — just one whose value lies elsewhere."},

    {"role": "user",      "content": "How does Ball Winning Specialist differ from High-Intensity Presser?"},
    {"role": "assistant", "content": "High-Intensity Presser is about winning the ball back through movement and pressure — counterpressing, chasing, and hunting in high areas. Ball Winning Specialist is about winning the ball through positioning and physicality — being in the right place to intercept, or winning direct duels. One is primarily about press intensity, the other about defensive reading and dueling ability."},

    {"role": "user",      "content": "Why is defensive duel success percentage weighted most heavily?"},
    {"role": "assistant", "content": "Because duels are direct confrontations where the player either wins or loses the ball in a one-on-one situation. A high success rate means the player consistently comes out on top of physical battles, which is the core of defensive ball-winning. Volume of duels matters, but if a player attempts many and wins few, they are not a reliable ball winner."},

    {"role": "user",      "content": "What position profiles score highest as Ball Winning Specialists?"},
    {"role": "assistant", "content": "Defensive midfielders, central midfielders in pressing teams, and defensive-minded centre-backs score highest. Holding midfielders who screen the backline — described as 'midfield destroyers' — are the archetypal Ball Winning Specialists."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 9 — TRANSITIONAL ENGINE
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is Transitional Engine?"},
    {"role": "assistant", "content": "Transitional Engine measures a player's ability to instantly transform defensive actions into forward momentum — winning the ball back and immediately driving or passing the ball forward into the final third. It identifies players who are the catalyst of counter-attacks, bridging the gap between defence and attack in a single action."},

    {"role": "user",      "content": "How is Transitional Engine measured?"},
    {"role": "assistant", "content": "Transitional Engine is a weighted sum of: ball recoveries per 90 at 40%, progressive runs per 90 at 35%, and passes from the creation zone (Z3) to the final third (Z4) per 90 at 25%."},

    {"role": "user",      "content": "How is Transitional Engine calculated?"},
    {"role": "assistant", "content": "Transitional Engine is calculated as the weighted sum of the z-scores of: recoveries_p90 (40%), progressive_runs_p90 (35%), and pass_z3_to_z4_p90 (25%), among players in the same position group."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as a Transitional Engine?"},
    {"role": "assistant", "content": "An outstanding Transitional Engine is the ideal engine for a transition-based team. They win the ball frequently and immediately exploit the space created by the turnover, carrying or passing the ball forward before the opposition can reorganise. They transform defensive actions into attacking opportunities in the blink of an eye."},

    {"role": "user",      "content": "What does it mean for a player to be poor as a Transitional Engine?"},
    {"role": "assistant", "content": "A player poor as a Transitional Engine either does not win the ball frequently enough or tends to recycle backwards after winning it. They may be excellent in a slow possession system but are not suited to direct, counter-attacking football where immediate vertical progression after turnovers is critical."},

    {"role": "user",      "content": "How does Transitional Engine differ from Ball Winning Specialist?"},
    {"role": "assistant", "content": "Ball Winning Specialist measures the ability to win the ball — the defensive act. Transitional Engine combines winning the ball with the ability to immediately drive play forward. A Ball Winning Specialist who plays the ball short or sideways after winning it will not score highly as a Transitional Engine, even if they win many duels."},

    {"role": "user",      "content": "What position profiles score highest as Transitional Engines?"},
    {"role": "assistant", "content": "Box-to-box midfielders are the archetypal Transitional Engine — players who defend actively and then immediately burst into forward positions. Energetic central midfielders in counter-attacking teams, such as those who cover large distances and contribute at both ends, typically score highest."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 10 — WING WIZARD
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is Wing Wizard?"},
    {"role": "assistant", "content": "Wing Wizard measures a player's 1v1 dribbling threat and ability to progress the ball forward from wide positions through individual skill and carrying. It identifies wide players who beat opponents regularly, create danger through directness, and use their pace and technique to advance the ball in the final third."},

    {"role": "user",      "content": "How is Wing Wizard measured?"},
    {"role": "assistant", "content": "Wing Wizard is a weighted sum of: dribbles attempted per 90 at 40%, progressive runs per 90 at 35%, and carries from the creation zone (Z3) to the final third (Z4) per 90 at 25%."},

    {"role": "user",      "content": "How is Wing Wizard calculated?"},
    {"role": "assistant", "content": "Wing Wizard is calculated as the weighted sum of the z-scores of: dribbles_attempted_p90 (40%), progressive_runs_p90 (35%), and carry_z3_to_z4_p90 (25%), among players in the same position group."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as a Wing Wizard?"},
    {"role": "assistant", "content": "An outstanding Wing Wizard is a nightmare for full-backs — they constantly attempt to beat their direct opponent in 1v1 situations, make explosive forward runs that advance the ball into the final third, and generate danger through individual skill rather than combination play. They are often the most direct attacking threat in the team."},

    {"role": "user",      "content": "What does it mean for a player to be poor as a Wing Wizard?"},
    {"role": "assistant", "content": "A player poor as a Wing Wizard rarely attempts to take on their direct opponent and does not make many forward-carrying runs. They may operate as a link player or chance-creator through passing rather than carrying. Traditional playmakers and technical wide players who prefer to combine rather than drive score lower here."},

    {"role": "user",      "content": "Why are dribbles attempted — rather than dribbles won — used in Wing Wizard?"},
    {"role": "assistant", "content": "Dribbles attempted capture the intent and frequency of 1v1 challenge — which is the core of wing-wizard behaviour. Players who consistently take on defenders are threatening even when they do not always succeed, because the attempt itself forces opponents to commit and creates space for teammates. Dribble success rate is a separate quality."},

    {"role": "user",      "content": "How does Wing Wizard differ from The Box Invader?"},
    {"role": "assistant", "content": "Wing Wizard measures the act of carrying and dribbling from wide areas into the final third — the journey. The Box Invader measures the delivery into the penalty area — the destination. A Wing Wizard might cut inside and shoot rather than cross, while a Box Invader might cross frequently without dribbling past opponents."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 11 — AERIAL POWERHOUSE
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is Aerial Powerhouse?"},
    {"role": "assistant", "content": "Aerial Powerhouse measures a player's dominance in aerial duels — both in terms of how often they engage in aerial contests and how frequently they win them. It identifies players who consistently outjump opponents, providing an aerial threat at set pieces, winning headers in the defensive line, and competing for long balls."},

    {"role": "user",      "content": "How is Aerial Powerhouse measured?"},
    {"role": "assistant", "content": "Aerial Powerhouse is a weighted sum of: aerial duel success percentage at 60%, and aerial duels won per 90 at 40%."},

    {"role": "user",      "content": "How is Aerial Powerhouse calculated?"},
    {"role": "assistant", "content": "Aerial Powerhouse is calculated as the weighted sum of the z-scores of: aerial_duel_won_pct (60%), and aerial_duels_won_p90 (40%), among players in the same position group."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as an Aerial Powerhouse?"},
    {"role": "assistant", "content": "An outstanding Aerial Powerhouse is a dominant physical presence in the air. They win the vast majority of their aerial contests, are a constant set-piece threat at both ends, and provide the team with a reliable long ball target. Teams that play with direct football or rely on set-pieces as a primary source of goals especially value this quality."},

    {"role": "user",      "content": "What does it mean for a player to be poor as an Aerial Powerhouse?"},
    {"role": "assistant", "content": "A player poor as an Aerial Powerhouse either rarely contests aerial duels or loses the majority of those they do contest. Shorter, technically-oriented players — particularly in midfield and attack — often score low here. This is not necessarily a weakness if the team does not rely on aerial play."},

    {"role": "user",      "content": "Why is aerial duel success percentage weighted more heavily than volume?"},
    {"role": "assistant", "content": "Because winning matters more than engaging. A player who attempts many aerial duels but loses most of them is not a reliable aerial asset — they are simply engaging in a contest they cannot win. Success percentage ensures the quality captures genuine aerial dominance rather than just frequent involvement."},

    {"role": "user",      "content": "What position profiles score highest as Aerial Powerhouses?"},
    {"role": "assistant", "content": "Target strikers who receive long balls and hold up play, and centre-backs who defend crosses and long balls, score highest. Defensive headers at set pieces and physical centre-forwards are the archetypal Aerial Powerhouses. Shorter attacking midfielders and technical wingers score lowest."},


    # ══════════════════════════════════════════════════════════════════════════
    # QUALITY 12 — FINAL THIRD CATALYST
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "What is Final Third Catalyst?"},
    {"role": "assistant", "content": "Final Third Catalyst measures how much of a player's total activity is concentrated in the final third (Z4), and how effectively they feed the attacking phase from that position. It identifies players who operate primarily as advanced playmakers or delivery threats — acting as the team's primary creative presence in the most dangerous area of the pitch."},

    {"role": "user",      "content": "How is Final Third Catalyst measured?"},
    {"role": "assistant", "content": "Final Third Catalyst is a weighted sum of: percentage of actions in the final third (Z4) at 40%, passes into the final third per 90 at 35%, and passes from the creation zone (Z3) to the final third (Z4) per 90 at 25%."},

    {"role": "user",      "content": "How is Final Third Catalyst calculated?"},
    {"role": "assistant", "content": "Final Third Catalyst is calculated as the weighted sum of the z-scores of: pct_actions_z4 (40%), passes_to_final_third_p90 (35%), and pass_z3_to_z4_p90 (25%), among players in the same position group."},

    {"role": "user",      "content": "What does it mean for a player to be outstanding as a Final Third Catalyst?"},
    {"role": "assistant", "content": "An outstanding Final Third Catalyst operates almost exclusively in the most dangerous area of the pitch. They are constantly available in the attacking third to receive, combine, and deliver — acting as the hub of all attacking play. Their presence there forces the opposition to dedicate extra defensive resources, which creates space for teammates elsewhere."},

    {"role": "user",      "content": "What does it mean for a player to be poor as a Final Third Catalyst?"},
    {"role": "assistant", "content": "A player poor as a Final Third Catalyst does their work in deeper areas. They contribute more to build-up and progression than to the final attacking phase — deep-lying midfielders, centre-backs, and defensive players naturally score low here, which reflects their positional role rather than any technical deficiency."},

    {"role": "user",      "content": "How does Final Third Catalyst differ from Creative Playmaker?"},
    {"role": "assistant", "content": "Final Third Catalyst is about spatial presence — being in the attacking third, operating there, feeding from there. Creative Playmaker is about the quality of chances created through passing vision: key passes, through balls, shot assists. A player can be a high Final Third Catalyst while being an average Creative Playmaker if they receive and distribute safely in the attacking third without producing many direct shot chances."},

    {"role": "user",      "content": "What position profiles score highest as Final Third Catalysts?"},
    {"role": "assistant", "content": "Attacking midfielders behind the striker, advanced playmakers in a 4-2-3-1 or 4-3-3, and inside forwards who drift into central channels score highest. Full-backs who push into the attacking third in possession-based systems can also score well. Target strikers who pin the defence often score high for their penalty area presence rather than in the wider attacking third."},


    # ══════════════════════════════════════════════════════════════════════════
    # PLAYER COMPARISONS — style examples
    # ══════════════════════════════════════════════════════════════════════════
    {"role": "user",      "content": "How does Salah compare to Son?"},
    {"role": "assistant", "content": "Both are elite wide forwards in terms of end product, but they are built differently as footballers. Salah is the more relentless physical threat — he carries into the channel at an extraordinary rate, inverts onto his left foot with purpose, and generates a volume of shots and shot assists that very few players in the league can match. His xG numbers reflect a player who does not just create — he finishes. Son, by contrast, is a different kind of danger. He makes his runs later, ghosting in behind the defensive line rather than carrying through it, and his movement off the ball is what generates his best opportunities. Salah is a force of nature in possession; Son is a threat without it."},

    {"role": "user",      "content": "Compare Rodri and Casemiro."},
    {"role": "assistant", "content": "Rodri is the engine of a possession system — his pass accuracy is exceptional, he presses the backline with calmness rather than urgency, and his defensive positioning makes him the ideal screen for a high defensive line. He almost never gives the ball away, which is why City rarely lose control in midfield. Casemiro is a different animal — a genuine ball-winning midfielder who thrives on physical confrontation. He wins duels, intercepts, and recovers at a rate that puts him among the elite in that department. The trade-off is technical: where Rodri builds play with precision and composure, Casemiro is more direct, sometimes more erratic in possession. If you are building a team that presses and keeps the ball, you want Rodri. If you need someone to protect a backline against direct opponents and win aerial battles in midfield, Casemiro is your man."},

    {"role": "user",      "content": "How does Haaland compare to Watkins?"},
    {"role": "assistant", "content": "Haaland is the most efficient finisher in the division — his xG numbers are at a different level because he consistently finds himself in the highest-probability positions inside the box. He barely touches the ball outside the penalty area but when it arrives at his feet in the right place, very little goes to waste. Watkins is the more complete centre-forward in terms of involvement. He presses aggressively, creates space for teammates through his movement, and contributes in build-up phases that Haaland simply opts out of. Watkins wins you the ball back and links play; Haaland scores the goals once it arrives. Which one you prefer depends entirely on how your team plays — high-possession systems that need a focal point suit Haaland perfectly; pressing, direct teams that need their striker to do more work get more from Watkins."},


    # ══════════════════════════════════════════════════════════════════════════
    # SCOUTING PROFILES — positional requirements and how to find them in data
    # ══════════════════════════════════════════════════════════════════════════

    # ── Link Play & Between the Lines ─────────────────────────────────────────

    {"role": "user",      "content": "What is the Link Play quality?"},
    {"role": "assistant", "content": "Link Play is a striker-only quality. It measures how effectively a centre-forward functions as the connection point between the midfield and the attacking line — the hold-up game, the availability, the simplicity. It is built on three things: the proportion of the striker's actions in the creation zone (dropping deep to link), the proportion in the final third just outside the box (where the best link strikers operate most), and how often per 90 they lose the ball. The formula rewards strikers who spread their activity across both the creation zone and the space just outside the box, and who keep possession reliably in both — one or two touches, then move. A high Link Play score is the data signature of a complete forward: not a pure box player, not a false nine, but a striker who works the space between the lines intelligently while keeping things simple."},

    {"role": "user",      "content": "What is the Between the Lines quality?"},
    {"role": "assistant", "content": "Between the Lines measures how effectively a player exploits the final third — the space just outside the opponent's penalty area, between the defensive and midfield blocks — as a platform to create attacking danger. It is about what you do from that zone, not just that you are there. The quality is built from three metrics: the proportion of total actions in the final third, the volume of carries from the creation zone all the way into the box per 90, and the volume of passes from the creation zone directly into the box per 90. Those last two metrics are key — they tell you the player is using the space between the lines to generate penetrating actions into the penalty area rather than simply circulating possession in the final third. It is relevant for strikers who move in and out of the box to create, wingers who cut inside into the ten-space and threaten the box, and midfielders who make late arrivals from deep positions."},

    {"role": "user",      "content": "How does Link Play differ from Between the Lines?"},
    {"role": "assistant", "content": "Link Play is a striker-specific quality about simplicity and reliability as a connecting option — the hold-up game. It rewards a striker who drops into the creation zone or operates in the space just outside the box, touches the ball simply, keeps possession, and creates space for teammates through their movement. Between the Lines is about forward penetration: operating in the final third and then producing carries or passes that physically threaten the opponent's box. A striker with good Link Play but poor Between the Lines is the one who connects play reliably but is not creating direct goalscoring moments. A striker strong in both is dangerous in the way the best complete forwards are — they do the simple work outside the box and then immediately put the team into the next phase of danger."},

    {"role": "user",      "content": "Which strikers score highest in Link Play?"},
    {"role": "assistant", "content": "Run the Link Play scores for strikers — these are the forwards who split their activity between the creation zone and the space just outside the box, and who keep the ball under pressure. The highest scorers are typically false-nine types or mobile centre-forwards who drop deep to connect play rather than pinning themselves in the box. Their ball losses per 90 will be notably lower than a typical target man, and they will show significant activity in both the creation zone and the final third. Cross-reference with Between the Lines to see which of those hold-up strikers also produce direct penetration into the box from those zones — or with Vertical Box Threat to identify the ones who also make the run in behind."},

    {"role": "user",      "content": "Which players score well in both Link Play and Between the Lines?"},
    {"role": "assistant", "content": "For strikers: a high score in both tells you the player does everything you want from a modern complete forward — they hold up play reliably outside the box, they move in the space between the lines intelligently, and they use that position to produce direct penetration into the penalty area. These are the Firmino-style or Benzema-style forwards. For midfielders and wingers scoring high in Between the Lines: they are the players who habitually cut inside into the ten-space and threaten the box with carries and through-balls from that area — picture a winger who inverts or a shadow striker who attacks from deep. The combination of high zone presence and high z3-to-box output is the clearest data fingerprint of a player who exploits half-space."},

    # ── Per-position description-to-data mapping ──────────────────────────────

    {"role": "user",      "content": "How does the data capture the Full Back description?"},
    {"role": "assistant", "content": "The Full Back description maps cleanly onto four qualities. Defensive 1v1 ability and conditioned pressing toward the outer channel shows up in Ball Winning Specialist — specifically defensive_duel_won_pct and interceptions_p90. The reaction to loss of possession is captured by High-Intensity Presser through counterpressing_recoveries_p90: a full back who hunts immediately after losing the ball generates a distinctive signature here. Forward run quality and crossing delivery is Box Invader — passes_to_box_p90 and crosses_p90 tell you how much danger the player creates with the ball wide. Breaking the Lines captures the build-up phase: a full back who drives or passes vertically from deep into the final third shows up strongly there. The one thing the data does not capture well is the positional intelligence — the diagonal distances with the centre-back, the decision about when to overlap versus when to stay — but cross-referencing these four qualities against a player's overall balance (decent scores in all four, not elite in one at the expense of the others) is the closest proxy."},

    {"role": "user",      "content": "How does the data capture the Centre Back description?"},
    {"role": "assistant", "content": "The CB description splits into two profiles with distinct data signatures. The Positional CB is the aerial organiser: Aerial Powerhouse is the primary identifier (aerial_duel_won_pct weighted at 60%), with Possession Anchor confirming the composure in possession — pass accuracy above 84% is the hard threshold. Their Zone Skipper score will be above average because their range passing is the mechanism for line-breaking, not their carries. The Agile CB is identified first by Breaking the Lines — carry_z2_to_z4_p90 is the standout metric, capturing carries from deep defensive areas into the final third. Their Zone Skipper score will be high for the same reason, but their Possession Anchor will typically be lower than the positional player. Aerial Powerhouse still needs to be solid for both — the description specifies both must display a strong aerial game, with the agile one marginally lower. Leadership and communication are not measurable in event data."},

    {"role": "user",      "content": "How does the data capture the Defensive Midfielder description?"},
    {"role": "assistant", "content": "The DM description splits into two profiles with completely different data fingerprints. The Positional DM is found through the combination of Possession Anchor and Ball Winning Specialist — pass accuracy above 84%, passes completed under pressure per 90, and a defensive duel win rate that confirms he is protecting the backline through positioning rather than chasing. His Breaking the Lines score confirms the first movement forward: he plays the ball vertically when the opportunity is there rather than always recycling sideways. His progressive_runs_p90 will be modest. The Dynamic DM is identified through Transitional Engine and High-Intensity Presser: high counterpressing_recoveries_p90 confirms he hunts the ball immediately after losing it, while progressive_runs_p90 well above the midfield average confirms he covers box-to-box distances regularly. His passes_under_pressure_p90 will be lower than the positional player. The description's requirement for 'first movement always forward' also shows in Breaking the Lines for both types — it is a baseline, not a differentiator."},

    {"role": "user",      "content": "How does the data capture the Wide Midfielder description?"},
    {"role": "assistant", "content": "The Wide Midfielder description is about quality per action in the final phase — peripheral awareness, operating between the lines, fearless through-passing, and chance creation. Creative Playmaker is the primary quality: smart_passes_p90, key_passes_p90, and shot_assists_p90 capture the vision and delivery the description calls for. Between the Lines directly measures the positional requirement — how much of the player's activity is in the final third and how many carries or passes from that space penetrate into the box. Final Third Catalyst adds the spatial dimension — what percentage of total actions are concentrated in the final third. The description's point about 'decent at 1v1s to get into the box' is partially covered by Vertical Box Threat (carries and runs into the penalty area). The requirement to 'drop between the lines and take the ball forward' is Breaking the Lines from a more advanced position. What the data does not capture: the confidence to ask for the ball under pressure, or whether performances are consistent across different game states."},

    {"role": "user",      "content": "How does the data capture the Winger description?"},
    {"role": "assistant", "content": "The Winger profile maps onto four qualities and the data requirement is balance across all four — not dominance in one. Wing Wizard captures the 1v1 dribbling and directness: dribbles_attempted_p90 and carry_z3_to_z4_p90 tell you if the player is taking on their direct opponent and driving forward. Vertical Box Threat captures the constant box presence and runs in behind — pct_actions_z5 is the key variable for a winger who attacks the back post and arrives late in the penalty area. Box Invader captures the delivery and crossing output — crosses_p90 and passes_to_box_p90 confirm they are feeding the striker rather than just holding wide. High-Intensity Presser captures the defensive work rate and press participation in transitions — counterpressing_recoveries_p90 and recoveries_p90 confirm the winger is tracking back and pressing when out of possession. Between the Lines also applies here: a winger who cuts inside to operate in the ten-space and carries or passes into the box will score well, and this is the data signature of an inverted winger rather than a traditional wide player."},

    {"role": "user",      "content": "How does the data capture the Striker description?"},
    {"role": "assistant", "content": "The Striker description connects to data across five qualities. Aerial dominance — the first and non-negotiable requirement — is Aerial Powerhouse, specifically aerial_duel_won_pct weighted heavily because winning the contest matters more than entering it. The movement in and around the box — 'first and second phase, not a player who fixes position' — is Vertical Box Threat: carry_z3_to_z5_p90 and pct_actions_z5 confirm habitual box presence and carries that penetrate the penalty area. The hold-up game outside the box — 'plays a simple game, one or two touches, then moves' — is Link Play: this is why it is a striker-only quality, built on activity in both the creation zone and the final third with ball losses as the negative weight, rewarding simplicity under pressure. The between-lines movements to create space for wingers and midfielders — 'must be effective between the lines' — is Between the Lines: pct_actions_z4 as the zone presence marker, with carries and passes from the creation zone into the box as the penetration indicators. Pressing the opposition goalkeeper and reacting to counter-attacks is High-Intensity Presser. No metric captures the decision-making on when to hold versus release, or the reading of defensive line timing for the run in behind — that requires the eye test alongside the data."},

    # ══════════════════════════════════════════════════════════════════════════
    # SCOUTING PROFILES
    # ══════════════════════════════════════════════════════════════════════════

    {"role": "user",      "content": "What do you look for in a Full Back?"},
    {"role": "assistant", "content": "The full back we target is balanced — approximately 50/50 between defensive and offensive output, or tilted to 60/40 offensive only if operating as a wingback with the right defensive cover behind. The first thing to avoid is the pure wingback profile: a player who is offensively minded but lacks the defensive discipline to maintain a good diagonal relationship with his nearest centre-back. That diagonal distance and positioning — conditioning the opponent toward the outer channel, cutting passing lanes into the box from wide areas, knowing when to squeeze and when to hold — is the core of what makes a full back versus a winger in disguise. Defensively, we need controlled aggression in 1v1 situations and an immediate reaction to losing possession: he must press hard and recover shape before the opponent can reorganise. In the data, Ball Winning Specialist captures the 1v1 defensive reliability, High-Intensity Presser confirms the counterpressing reaction, Box Invader covers the crossing and delivery output, and Breaking the Lines measures the vertical quality of his forward distribution in build-up. The profile that concerns us is the player who scores very high in Box Invader and very low in Ball Winning and High-Intensity Presser — that is the winger playing at full back, and that unbalance is exactly what we want to avoid."},

    {"role": "user",      "content": "What is the difference between a Positional Centre Back and an Agile Centre Back?"},
    {"role": "assistant", "content": "Think of them as the two axes of a defensive line that must function as a unit, never as individuals. You never recruit three of the same type — one of each is the minimum requirement, and the combination is the point. The Positional CB is the organiser: he manages the defensive line, constantly communicates coverage and recovery instructions, and his composure on the ball gives the team the structural base to build the first attacking phase. His data signature is Aerial Powerhouse combined with a high Possession Anchor score — pass accuracy above 84% is the hard threshold, and the stronger the passing under pressure, the more reliable he is as the anchor of the build-up. His carries from deep will be modest; he breaks lines through range passing and Zone Skipper actions. The Agile CB is the disruptor of the press. When the opponent pins the team deep, he steps out of the defensive line with the ball, drives into space, and forces the press to collapse. His Breaking the Lines score is the primary differentiator — carry_z2_to_z4 is the specific metric that shows he is physically advancing the ball from deep into the final third. His Aerial Powerhouse must still be solid: both profiles need good jumping ability and a strong aerial game, the agile one marginally less dominant but still competitive. The positional CB covers in case of turnover when the agile one steps out — that coordination between the two is precisely what makes both profiles necessary."},

    {"role": "user",      "content": "What is the difference between a Positional DM and a Dynamic DM?"},
    {"role": "assistant", "content": "Two completely different players who can both wear the six shirt depending on the tactical structure. The Positional DM is built for a possession-based system as the control point: he is comfortable asking for the ball in every situation, takes responsibility under pressure, and his first movement with the ball is always forward to break the opposition's press rather than recycling sideways. His pass accuracy above 84% is the primary data check — combined with high passes completed under pressure per 90, it tells you he does not hide when pressed. Possession Anchor and Ball Winning Specialist are the dominant qualities in his profile. The Dynamic DM is the box-to-box engine — quick over long distances, relentless in stamina, and defined by what he does immediately after winning the ball. His Transitional Engine score is the differentiator: he wins possession and immediately drives play forward with carries or vertical passes before the opponent can reorganise. High counterpressing recoveries per 90 confirm that he hunts the ball back in high positions the moment possession is lost. His pass accuracy will be lower than the positional player, and that is acceptable — the trade-off is coverage, vertical impact, and press intensity. Both types should be useful in a 2 or 3 man midfield, and the ideal double pivot pairs one of each: the positional player protects the backline and circulates the ball, the dynamic player covers the ground and drives forward. The description requirement common to both is the quality/quantity ratio of involvements — neither type is wanted if their decisions are slow or their influence on the game is low."},

    {"role": "user",      "content": "What does the Wide or Attacking Midfielder profile require?"},
    {"role": "assistant", "content": "Skill and brilliance are the requirements — and high quality per action above everything else, because this player will receive the ball in the most congested areas of the pitch and his output in those moments either unlocks the game or kills it. The key trait is peripheral awareness: the ability to identify space between the defensive lines before the ball arrives, to drop between those lines and immediately take the ball forward, and to do so with the confidence to ask for it even when the opponent is pressing hard. The technical requirement is fearless through-passing — the willingness to attempt the penetrating ball even when the risk is high, backed by the vision to find it. In the data, Creative Playmaker is the primary identifier: smart passes, key passes, and shot assists per 90 tell you if the player is unlocking defences rather than just circulating possession. Between the Lines is the positional confirmation: a high score tells you the player habitually operates in the final third and produces carries and passes that penetrate into the box from that space. The biggest disqualifier for this profile is inconsistency — a player who is spectacular in comfortable games but disappears under pressure or in difficult away fixtures. What the data does not capture is personality: the courage to demand the ball when the team is under pressure, and the mentality to influence the game in its most critical moments. That requires the eye test."},

    {"role": "user",      "content": "What do you look for in a Winger?"},
    {"role": "assistant", "content": "Balanced and direct — not a specialist in one dimension, but a player who can do everything the position demands and contributes in both phases of the game. The technical baseline is above-average across dribbling, crossing, and passing, with enough competence on the weaker foot that the opponent cannot simply show him onto it and neutralise him. One-dimensional players — the pure crosser who never dribbles, the dribbler who never delivers, the player who only functions on one side — are exactly what this profile is designed to avoid, regardless of how elite they are in their single dimension. Tactically, the winger must understand diagonal and inner movements: he needs to be able to operate in narrow positions when the team is in possession and attack the back post for crosses delivered from the opposite side, showing the spatial intelligence to control offside positions and time runs in behind the defensive line. Defensively, he must be alert and consistent in transition — supporting the full back when out of possession, tracking back hard, not switching off when the ball is on the other side. In the data, Wing Wizard captures the 1v1 directness and driving carries into the final third, Vertical Box Threat confirms the habitual box presence and runs behind, Box Invader covers the crossing and delivery output, and High-Intensity Presser confirms the defensive work rate and press participation. A high Between the Lines score is the distinguishing marker of an inverted winger who cuts inside to operate in the ten-space and threatens the box directly — that profile is particularly valued alongside a wide full back who provides the natural width."},

    {"role": "user",      "content": "What do you look for in a Striker?"},
    {"role": "assistant", "content": "Physically competitive and mentally relentless — not a luxury player who opts out when the game is difficult or who disappears when the team is suffering. This is non-negotiable. The physical requirements are a strong build with enough mobility to operate across the width of the box and in the space between the lines, a strong aerial game effective both from a standing start and with momentum, and the ability to use the body to gain competitive advantage in tight spaces — back-to-goal play, holding off a centre-back, winning the physical battle for position. In the box, the quality is movement: first and second phase runs, not a player who fixes his position but one who constantly adjusts to arrive at the right angle, whether arriving late at the back post, attacking in behind, or pivoting to shoot. The hold-up game outside the box is equally important — simple, one or two touches, then move. The striker creates space for the wingers and midfielders by occupying the space between the lines, drawing defenders into coverage and opening the channels for late runners. He also presses the opposition goalkeeper to condition their distribution and reacts immediately to counter-attacking situations to slow the opponent down. In the data, Vertical Box Threat is the box movement and penetration indicator, Aerial Powerhouse is the aerial dominance check, Link Play is the hold-up quality outside the box — the striker who works reliably in both the creation zone and the final third without giving the ball away — and Between the Lines measures whether he is using that space to create direct penetration into the penalty area rather than just connecting play. High-Intensity Presser confirms the defensive work from the front."},

    {"role": "user",      "content": "How do you find Positional DM candidates in the data?"},
    {"role": "assistant", "content": "Look at midfielders who combine outstanding or excellent Possession Anchor with strong Ball Winning Specialist scores. The raw stat to prioritise is pass accuracy — a true positional midfielder in elite football operates above 84%, and the very best above 87%. Complement that with passes completed under pressure per 90, which tells you they are not hiding when pressed, and defensive duel win percentage, which confirms they protect the backline reliably. Their progressive runs per 90 will be modest compared to the league average for midfielders — that is a feature, not a flaw. Cross-reference with Breaking the Lines to confirm they are willing to play forward with the first touch rather than always recycling sideways."},

    {"role": "user",      "content": "How do you find Dynamic DM candidates in the data?"},
    {"role": "assistant", "content": "The Transitional Engine score is the starting point — players who rank highest among midfielders in that quality are the ones winning the ball and immediately driving forward. From there, check counterpressing recoveries per 90: a high figure confirms the player presses the moment possession is lost and wins it back in high positions, which is the heartbeat of a dynamic midfielder's game. Progressive runs per 90 should be well above the midfield average — this player covers the ground between the defensive block and the final third multiple times per match. They will score lower in Possession Anchor than the positional player, and that is expected. The trade you are accepting is slightly less technical reliability in exchange for physical coverage, press intensity, and vertical impact."},

    # ══════════════════════════════════════════════════════════════════════════
    # CONTEXTUALISATION — volume, team style, system bias
    # ══════════════════════════════════════════════════════════════════════════

    {"role": "user",      "content": "Why is it important to look at the total volume of actions, not just success rates?"},
    {"role": "assistant", "content": "Because a success rate in isolation tells you almost nothing without knowing how many times the player was asked to perform that action. A centre-back who wins 70% of his aerial duels but contests only one per 90 is not an aerial presence — he simply avoids the contest. A striker who wins 55% of aerial duels and contests four per 90 is doing far more useful work, even though the percentage is lower. Volume and rate together give you the full picture: the rate tells you how good the player is when asked, the volume tells you how much the team and system actually ask. Whenever you interpret any success metric — defensive duel win rate, aerial duel win rate, pass accuracy — always check the corresponding total volume (defensive_duels_p90, aerial_duels_p90, passes_p90) against the position-group average. A low volume relative to peers is as important as a low rate."},

    {"role": "user",      "content": "How does a team's playing style affect individual player statistics?"},
    {"role": "assistant", "content": "Massively, and in ways that are often misread as individual quality or weakness. A centre-back at a deep-defending, direct team will face five or six aerial duels per 90 and ten or more defensive duels — the whole opposition game plan pushes the ball into his zone. A centre-back at a possession-dominant team might face half that volume because the team's structure never allows opposition long balls or direct attacks to develop. Their raw numbers will look completely different even if they are equally skilled defenders. The same logic applies across every position: a striker at a team that dominates possession and builds slowly from the back will get fewer aerial duels, fewer transitions, and fewer counter-attack moments than a striker at a direct pressing team. A winger at a team with low block involvement will show fewer counterpressing recoveries regardless of his work rate. Before labelling a metric as a strength or weakness, always consider what the team's style demands of that position — and whether the volume of involvements that player sees is above, at, or below the position-group average."},

    {"role": "user",      "content": "A player has a low aerial duel win rate. Does that mean he is poor in the air?"},
    {"role": "assistant", "content": "Not automatically. You need two more pieces of information before drawing any conclusion. First, how many aerial duels per 90 does he contest, compared to the position-group average? If he contests notably fewer, the team's style has not been generating aerial situations — he is simply not being offered the contest with much frequency. In that case, the win rate is based on a thin sample in a low-demand environment. Second, what type of aerial duel is he being asked to win? A centre-back who only contests aerial duels in set-piece situations at his own box is operating in a different context than one who regularly battles for first-contact clearances under direct balls from wide areas. Neither a low win rate in a low-volume environment nor a low rate in a high-volume one is a verdict by itself. The first is something to take into account if the prospective club plays more direct football — it becomes an area to explore further rather than an established weakness. The second is a stronger individual signal, though still not the full picture. Always compare the total aerial duel volume (aerial_duels_p90) to the position-group average before interpreting the win rate."},

    {"role": "user",      "content": "A player has a poor Ball Winning Specialist score but plays for one of the top possession teams. How do I interpret that?"},
    {"role": "assistant", "content": "Carefully. The Ball Winning Specialist formula combines defensive duel win rate, interceptions per 90, and recoveries per 90. At a possession-dominant team, the defensive phase is compressed: the team spends more time in possession and concedes fewer transitions, so the defender is offered fewer defensive duel situations than a peer at a direct or low-block team. Their defensive duel win rate may still be acceptable, but the interceptions and recoveries per 90 will be depressed by the system — fewer counter-attacks and fewer open-play defending situations translate directly into fewer interception and recovery actions, regardless of how alert and well-positioned the player is. Before interpreting the score as an individual finding, compare defensive_duels_p90 to the position-group average. If it is significantly below average, you are looking at what the system asked of him, not necessarily what he is capable of. The rate metric — duel win percentage — is slightly more individually revealing, since it reflects quality of execution in the situations he did face. But even then, a low volume of situations is a thin sample to judge from. The appropriate response is not to label it a weakness, but to note it as something to factor in: if the team you are considering signing him to defends in a different way and generates more direct defensive work, you would want to investigate this area further before committing. The data identifies the question; it does not answer it."},

    {"role": "user",      "content": "How should I interpret a centre-back's low Aerial Powerhouse score if they play for a possession team?"},
    {"role": "assistant", "content": "A possession-dominant team suppresses aerial duel volume at the back by design: their game model prevents the opposition from having long ball possession, keeping the centre-back in controlled build-up situations rather than aerial contest situations. The result is a profile where aerial_duels_p90 — the total number of aerial duels contested — sits well below the position-group average. Before interpreting the score as an individual weakness, check that volume figure first. If it is significantly below the CB average, the system is the likely explanation — the player has simply not been asked to defend aerially with any regularity. What the data cannot tell you is whether he would perform well if asked more often. That is the honest position: we have not seen enough of it to judge. The thing to take into account when assessing a player like this for a different environment is exactly this: does the prospective team generate more aerial contest situations? If so, this is an area that warrants further investigation — live scouting, video, talking to people who know him — before drawing any conclusion. It is not a red flag; it is an open question."},

    {"role": "user",      "content": "Does pass accuracy reflect individual quality or team style?"},
    {"role": "assistant", "content": "Both, and you need to separate them. Pass accuracy is influenced by three things: the player's technical execution, the difficulty of passes they attempt, and the territorial conditions the team creates. A midfielder at a possession team that circulates the ball in controlled zones will naturally complete a higher percentage than a midfielder at a high-tempo, direct team who attempts more difficult passes under pressure and at speed. Within possession teams, the players who still achieve the highest pass accuracy are genuinely the most reliable technicians — that gap remains meaningful. But comparing the raw pass accuracy of a player from a high-possession team to one from a pressing or direct team is misleading. The more informative check is passes completed under pressure per 90 — this controls somewhat for the difficulty dimension and tells you whether the player can still execute when the opponent is closing down. Even then, a pressing team's system generates more press situations, so volume context still applies. Always flag the team context when interpreting pass accuracy."},

    {"role": "user",      "content": "How do I know if a player's low pressing score is about quality or system?"},
    {"role": "assistant", "content": "The High-Intensity Presser score is built from counterpressing recoveries per 90, total recoveries per 90, and defensive duels per 90. All three are highly sensitive to team style. A team that defends in a mid or low block will generate far fewer counterpressing situations than a high-pressing team — if the team never presses collectively after losing the ball, the individual player cannot generate counterpressing recoveries regardless of his individual intensity. Similarly, a team that concedes few defensive transitions gives the winger or striker fewer opportunities to recover the ball high up the pitch. Before interpreting a low High-Intensity Presser score as a work-rate problem, check whether the player's team is ranked among the lowest pressing teams in the league — if so, the system is suppressing the metric. Then look at recoveries_p90 and defensive_duels_p90 in absolute terms: if even those are notably below the position-group average, the player may be one who switches off when out of possession regardless of the team's collective approach. If they are only slightly below average in a non-pressing system, the concern is limited."},

    {"role": "user",      "content": "How should I contextualise a striker's Link Play score based on his team's style?"},
    {"role": "assistant", "content": "Link Play is built on activity in the creation zone (dropping deep to connect) and the final third just outside the box, minus ball losses per 90. The volume of actions in those zones is a direct function of the team's tactical structure around the striker. A centre-forward who plays in a team with two direct wingers who stretch wide and a midfield that pushes forward will naturally receive the ball more in the final third — his pct_actions_z4 will be high by design. A striker at a possession team that builds slowly will see more touches in deeper zones as the team recycles across the thirds. The ball losses component is more individually revealing — it is harder to inflate or deflate through system — but even ball losses reflect how frequently the striker is asked to receive the ball under pressure from close defenders. The key contextualisation for Link Play is to look at touches_p90 or total actions and compare where those actions are concentrated versus the striker average. A striker with very low total actions is either being served poorly by his team or is not seeking the ball — that distinction requires the eye test."},

    {"role": "user",      "content": "A player has a poor or below average score in one quality. Should I discount them as a target?"},
    {"role": "assistant", "content": "Not automatically, and never based on the data alone. The right process is: identify which quality is low, understand what the formula measures and which raw metrics drive it, then ask whether the low score is explained by (a) team/system effects reducing the volume of that action, (b) a role that genuinely does not require that quality, or (c) something individual that shows up consistently across multiple metrics. A centre-back with a poor Ball Winning Specialist score at a top-four possession team is very likely in category (a) — the system has not asked him to defend through volume. A centre-back with the same score at a mid-table team that sees plenty of direct football has less cover from that argument. But even in the second case, the data tells you what happened in this system; it does not tell you what the player is capable of in yours. The wordalisation labels are relative to position-group peers — they do not correct for team style. The honest output of any data analysis is a set of things to investigate further, not a verdict. A low score in an area relevant to your system is a flag to take into account — something to explore through video, live scouting, and conversations with people who know the player — not a reason to close the file."},

]


# ── Quick summary ──────────────────────────────────────────────────────────────
QUALITY_DEFINITIONS = {
    "Breaking the Lines": {
        "formula": "pass_z2_to_z4_p90 (40%) + carry_z2_to_z4_p90 (40%) + progressive_passes_p90 (20%)",
        "columns": ["pass_z2_to_z4_p90", "carry_z2_to_z4_p90", "progressive_passes_p90"],
        "weights": [0.40, 0.40, 0.20], #Estos pesos y stats podrían tener sentido
    },
    "Vertical Box Threat": {
        "formula": "carry_z3_to_z5_p90 (40%) + progressive_runs_p90 (35%) + pct_actions_z5 (25%)",
        "columns": ["carry_z3_to_z5_p90", "progressive_runs_p90", "pct_actions_z5"],
        "weights": [0.40, 0.35, 0.25],

    },
    "The Zone Skipper": {
        "formula": "carry_z2_to_z5_p90 (35%) + pass_z2_to_z4_p90 (35%) + long_passes_p90 (30%)",
        "columns": ["carry_z2_to_z5_p90", "pass_z2_to_z4_p90", "long_passes_p90"],
        "weights": [0.35, 0.35, 0.30],
            },
    "Creative Playmaker": {
        "formula": "smart_passes_p90 (35%) + key_passes_p90 (35%) + shot_assists_p90 (30%)",
        "columns": ["smart_passes_p90", "key_passes_p90", "shot_assists_p90"],
        "weights": [0.35, 0.35, 0.30],
    },
    "High-Intensity Presser": {
        "formula": "counterpressing_recoveries_p90 (50%) + recoveries_p90 (30%) + defensive_duels_p90 (20%)",
        "columns": ["counterpressing_recoveries_p90", "recoveries_p90", "defensive_duels_p90"],
        "weights": [0.50, 0.30, 0.20],
    },
    "The Box Invader": {
        "formula": "passes_to_box_p90 (40%) + crosses_p90 (30%) + pass_z3_to_z5_p90 (30%)",
        "columns": ["passes_to_box_p90", "crosses_p90", "pass_z3_to_z5_p90"],
        "weights": [0.40, 0.30, 0.30],
    },
    "Possession Anchor": {
        "formula": "pass_accuracy_pct (50%) + passes_under_pressure_p90 (30%) - ball_losses_p90 (20%)",
        "columns": ["pass_accuracy_pct", "passes_under_pressure_p90", "ball_losses_p90"],
        "weights": [0.50, 0.30, -0.20],
    },
    "Ball Winning Specialist": {
        "formula": "defensive_duel_won_pct (40%) + interceptions_p90 (30%) + recoveries_p90 (30%)",
        "columns": ["defensive_duel_won_pct", "interceptions_p90", "recoveries_p90"],
        "weights": [0.40, 0.30, 0.30],
    },
    "Transitional Engine": {
        "formula": "recoveries_p90 (40%) + progressive_runs_p90 (35%) + pass_z3_to_z4_p90 (25%)",
        "columns": ["recoveries_p90", "progressive_runs_p90", "pass_z3_to_z4_p90"],
        "weights": [0.40, 0.35, 0.25],
    },
    "Wing Wizard": {
        "formula": "dribbles_attempted_p90 (40%) + progressive_runs_p90 (35%) + carry_z3_to_z4_p90 (25%)",
        "columns": ["dribbles_attempted_p90", "progressive_runs_p90", "carry_z3_to_z4_p90"],
        "weights": [0.40, 0.35, 0.25],
    },
    "Aerial Powerhouse": {
        "formula": "aerial_duel_won_pct (60%) + aerial_duels_won_p90 (40%)",
        "columns": ["aerial_duel_won_pct", "aerial_duels_won_p90"],
        "weights": [0.60, 0.40],
            },
    "Final Third Catalyst": {
        "formula": "pct_actions_z4 (40%) + passes_to_final_third_p90 (35%) + pass_z3_to_z4_p90 (25%)",
        "columns": ["pct_actions_z4", "passes_to_final_third_p90", "pass_z3_to_z4_p90"],
        "weights": [0.40, 0.35, 0.25],
    },
    "Link Play": {
        "formula": "pct_actions_z3 (30%) + pct_actions_z4 (35%) - ball_losses_p90 (35%)",
        "columns": ["pct_actions_z3", "pct_actions_z4", "ball_losses_p90"],
        "weights": [0.30, 0.35, -0.35],
    },
    "Between the Lines": {
        "formula": "pct_actions_z4 (40%) + carry_z3_to_z5_p90 (35%) + pass_z3_to_z5_p90 (25%)",
        "columns": ["pct_actions_z4", "carry_z3_to_z5_p90", "pass_z3_to_z5_p90"],
        "weights": [0.40, 0.35, 0.25],
    },
}

if __name__ == "__main__":
    print(f"Verbal model loaded: {len(VERBAL_MODEL_PAIRS)} Q&A pairs across {len(QUALITY_DEFINITIONS)} qualities")
    for q, v in QUALITY_DEFINITIONS.items():
        print(f"  {q}: {v['formula']}")
'''