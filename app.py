import streamlit as st
from typing import Dict, List, Tuple, Optional

# =============================================================
# CONFIGURE GROUPS HERE
# =============================================================
INITIAL_GROUPS: Dict[str, List[str]] = {
    "A": ["Mexico", "South Africa", "South Korea", "UEFA D (DEN/MKD/CZE/IRL)"],
    "B": ["Canada", "UEFA A (ITA/NIR/WAL/BIH)", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morrocco", "Haiti", "Scotland"],
    "D": ["USA", "Paraguay", "Australia", "UEFA C (SVK/KOS/TUR/ROU)"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "UEFA B (UKR/SWE/POL/ALB)", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cabo Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "IC2 (BOL/SUR/IRQ)", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "IC1 (NCL/JAM/COD)", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

GROUP_NAMES = sorted(list(INITIAL_GROUPS.keys()))

# =============================================================
# UTILITY FUNCTIONS
# =============================================================
def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def validar_permutacao(choices: List[str], empty: str = "-") -> bool:
    if empty in choices:
        return False
    return len(choices) == len(set(choices))


def montar_classificacao_grupos(
    groups: Dict[str, List[str]]
) -> Tuple[Dict[str, List[str]], List[str]]:
    """
    Render group standings UI (1st–4th place) for all groups.
    Inside each group, once a team is selected for a position,
    it is removed from the options of the remaining positions.
    """
    standings: Dict[str, List[str]] = {}
    errors: List[str] = []

    st.header("1. Group Stage Standings")

    for g in GROUP_NAMES:
        teams = groups[g]
        st.subheader(f"Group {g}")
        cols = st.columns(4)
        pos_choices: List[str] = []

        for i in range(4):
            pos_num = i + 1
            already_chosen = [c for c in pos_choices if c != "-"]
            available_teams = [t for t in teams if t not in already_chosen]
            options = ["-"] + available_teams

            key = f"group_{g}_pos_{pos_num}"

            with cols[i]:
                choice = st.selectbox(
                    f"{ordinal(pos_num)} place",
                    options=options,
                    key=key,
                )
            pos_choices.append(choice)

        if validar_permutacao(pos_choices):
            standings[g] = pos_choices
        else:
            standings[g] = []
            errors.append(f"Fill Group {g} correctly (no repetition and no empty fields).")

    return standings, errors


def coletar_terceiros(standings: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    """
    Return list of (group, team) that finished 3rd in each group.
    """
    thirds = []
    for g, pos in standings.items():
        if len(pos) == 4:
            thirds.append((g, pos[2]))  # index 2 = 3rd place
    return thirds


def escolher_top8_terceiros_ui(terceiros: List[Tuple[str, str]]):
    """
    UI to choose exactly 8 third-placed teams that qualify.
    No need to rank all 12 – just mark who goes through.
    """
    errors: List[str] = []
    st.header("2. Third-placed Teams – choose the 8 that qualify")

    if len(terceiros) != 12:
        errors.append("All 12 third-placed teams must be defined first.")
        return [], errors

    selected: List[Tuple[str, str]] = []

    for g, team in terceiros:
        label = f"{g} – {team}"
        checked = st.checkbox(label, key=f"third_{g}")
        if checked:
            selected.append((g, team))

    if len(selected) != 8:
        errors.append(
            f"You must select exactly 8 third-placed teams (currently selected: {len(selected)})."
        )

    return selected, errors


# =============================================================
# ROUND OF 32 RULES (Based on World Cup 2026 format)
# =============================================================
ROUND32_FIXED = {
    "M73": ("2A", "2B"),
    "M75": ("1F", "2C"),
    "M76": ("1C", "2F"),
    "M78": ("2E", "2I"),
    "M83": ("2K", "2L"),
    "M84": ("1H", "2J"),
    "M86": ("1J", "2H"),
    "M88": ("2D", "2G"),
}

# Matches where the second team is one of the best 3rd-placed teams.
# Each value: ("1X", [list of groups from which the 3rd-placed can come])
ROUND32_THIRD_SLOTS = {
    "M74": ("1E", ["A", "B", "C", "D", "F"]),
    "M77": ("1I", ["C", "D", "F", "G", "H"]),
    "M79": ("1A", ["C", "E", "F", "H", "I"]),
    "M80": ("1L", ["E", "H", "I", "J", "K"]),
    "M81": ("1D", ["B", "E", "F", "I", "J"]),
    "M82": ("1G", ["A", "E", "H", "I", "J"]),
    "M85": ("1B", ["E", "F", "G", "I", "J"]),
    "M87": ("1K", ["D", "E", "I", "J", "L"]),
}


def extrair_time(code: str, standings: Dict[str, List[str]]) -> Optional[str]:
    """
    Convert codes like 1A, 2B, 3C into team names based on group standings.
    """
    if len(code) != 2:
        return None
    pos, group = code[0], code[1]
    if group not in standings or len(standings[group]) != 4:
        return None
    idx = {"1": 0, "2": 1, "3": 2, "4": 3}.get(pos)
    if idx is None:
        return None
    return standings[group][idx]


def distribuir_terceiros_nos_jogos(
    qualified: List[Tuple[str, str]],
) -> Tuple[Optional[Dict[str, Tuple[str, str]]], Optional[str]]:
    """
    Assign the 8 qualified 3rd-placed teams to matches M74, M77, M79, M80, M81, M82, M85, M87,
    respecting allowed groups for each match.

    Uses backtracking to guarantee we find a valid assignment if one exists.
    """
    match_ids = list(ROUND32_THIRD_SLOTS.keys())  # 8 matches
    if len(qualified) != 8:
        return None, "Exactly 8 third-placed teams must be qualified."

    assignment: Dict[str, Tuple[str, str]] = {}  # match_id -> (group, team)

    def backtrack(i: int, used_matches: set) -> bool:
        if i == len(qualified):
            return True

        group, team = qualified[i]

        for mid in match_ids:
            if mid in used_matches:
                continue

            _, allowed_groups = ROUND32_THIRD_SLOTS[mid]
            if group not in allowed_groups:
                continue

            # choose
            assignment[mid] = (group, team)
            used_matches.add(mid)

            if backtrack(i + 1, used_matches):
                return True

            # undo
            used_matches.remove(mid)
            del assignment[mid]

        return False

    if not backtrack(0, set()):
        return None, "Unable to assign the selected third-placed teams to the Round of 32."

    return assignment, None


def montar_round32(
    standings: Dict[str, List[str]],
    qualified_thirds: List[Tuple[str, str]],
):
    """
    Build dict:
      match_id -> (team1, team2, textual_description)
    for matches M73..M88.
    """
    jogos_terceiros, err = distribuir_terceiros_nos_jogos(qualified_thirds)
    if err:
        return {}, err

    jogos = {}

    # fixed games (no 3rd-placed teams)
    for mid, (code1, code2) in ROUND32_FIXED.items():
        t1 = extrair_time(code1, standings)
        t2 = extrair_time(code2, standings)
        jogos[mid] = (t1, t2, f"{code1} vs {code2}")

    # games with 3rd-placed teams
    for mid, (code1, _) in ROUND32_THIRD_SLOTS.items():
        t1 = extrair_time(code1, standings)
        group_3, team_3 = jogos_terceiros[mid]
        code2 = f"3{group_3}"
        jogos[mid] = (t1, team_3, f"{code1} vs {code2}")

    return jogos, None


# =============================================================
# BRACKET STRUCTURE
# =============================================================
ROUND16_MATCHES = {
    "M89": ("M74", "M77"),
    "M90": ("M73", "M75"),
    "M91": ("M76", "M78"),
    "M92": ("M79", "M80"),
    "M93": ("M83", "M84"),
    "M94": ("M81", "M82"),
    "M95": ("M86", "M88"),
    "M96": ("M85", "M87"),
}

QUARTERS_MATCHES = {
    "M97": ("M89", "M90"),
    "M98": ("M93", "M94"),
    "M99": ("M91", "M92"),
    "M100": ("M95", "M96"),
}

SEMIS_MATCHES = {
    "M101": ("M97", "M98"),
    "M102": ("M99", "M100"),
}


def escolher_vencedor_ui(match_id: str, t1: Optional[str], t2: Optional[str]) -> Optional[str]:
    if not t1 or not t2:
        st.write("Waiting for teams to be determined…")
        return None
    return st.radio(
        f"Winner of {match_id}",
        options=[t1, t2],
        key=f"winner_{match_id}",
        horizontal=True,
    )


# =============================================================
# STREAMLIT UI
# =============================================================
st.set_page_config(page_title="World Cup 2026 Simulator", layout="wide")

st.title("World Cup 2026 Simulator – Groups & Knockout Bracket")

st.markdown(
    """
This app allows you to:

1. Set **group stage standings** (1st to 4th) with no repeated teams in a group.
2. Select the **8 best third-placed teams** (no need to rank all 12).
3. Automatically generate the **Knockout Bracket** (Round of 32 to Final).
4. Choose winners match by match to simulate the entire tournament.
"""
)

# st.sidebar.header("Group Configuration")
# with st.sidebar.expander("Current Groups", expanded=False):
#     for g in GROUP_NAMES:
#         st.write(f"**Group {g}**: {', '.join(INITIAL_GROUPS[g])}")

# -------------------------------------------------------------
# GROUP STAGE
# -------------------------------------------------------------
standings, errors_groups = montar_classificacao_grupos(INITIAL_GROUPS)
if errors_groups:
    st.warning("⚠️ Issues found in group standings:")
    for e in errors_groups:
        st.write("-", e)
    st.stop()

# -------------------------------------------------------------
# THIRD-PLACED TEAMS (CHOOSE TOP 8)
# -------------------------------------------------------------
thirds = coletar_terceiros(standings)
qualified_thirds, errors_thirds = escolher_top8_terceiros_ui(thirds)
if errors_thirds:
    st.warning("⚠️ Issues in third-placed selection:")
    for e in errors_thirds:
        st.write("-", e)
    st.stop()

# -------------------------------------------------------------
# ROUND OF 32
# -------------------------------------------------------------
jogos_r32, err = montar_round32(standings, qualified_thirds)
if err:
    st.error("❌ Error generating Round of 32:")
    st.write(err)
    st.stop()

st.header("3. Round of 32")
order32 = [
    "M73", "M74", "M75", "M76",
    "M77", "M78", "M79", "M80",
    "M81", "M82", "M83", "M84",
    "M85", "M86", "M87", "M88",
]

cols32 = st.columns(4)
winners32: Dict[str, Optional[str]] = {}

for i, mid in enumerate(order32):
    col = cols32[i % 4]
    with col:
        t1, t2, desc = jogos_r32[mid]
        st.markdown(f"**{mid} – {desc}**")
        st.write(f"{t1} vs {t2}")
        winners32[mid] = escolher_vencedor_ui(mid, t1, t2)

# -------------------------------------------------------------
# ROUND OF 16
# -------------------------------------------------------------
st.header("4. Round of 16")
cols16 = st.columns(4)
winners16: Dict[str, Optional[str]] = {}

for i, (mid, (m1, m2)) in enumerate(ROUND16_MATCHES.items()):
    col = cols16[i % 4]
    with col:
        t1 = winners32.get(m1)
        t2 = winners32.get(m2)
        st.markdown(f"**{mid} – Winner {m1} vs Winner {m2}**")
        winners16[mid] = escolher_vencedor_ui(mid, t1, t2)

# -------------------------------------------------------------
# QUARTERFINALS
# -------------------------------------------------------------
st.header("5. Quarterfinals")
colsQ = st.columns(4)
winnersQ: Dict[str, Optional[str]] = {}

for i, (mid, (m1, m2)) in enumerate(QUARTERS_MATCHES.items()):
    col = colsQ[i % 4]
    with col:
        t1 = winners16.get(m1)
        t2 = winners16.get(m2)
        st.markdown(f"**{mid} – Winner {m1} vs Winner {m2}**")
        winnersQ[mid] = escolher_vencedor_ui(mid, t1, t2)

# -------------------------------------------------------------
# SEMIFINALS
# -------------------------------------------------------------
st.header("6. Semifinals")
colsS = st.columns(2)
winnersS: Dict[str, Optional[str]] = {}

for i, (mid, (m1, m2)) in enumerate(SEMIS_MATCHES.items()):
    col = colsS[i % 2]
    with col:
        t1 = winnersQ.get(m1)
        t2 = winnersQ.get(m2)
        st.markdown(f"**{mid} – Winner {m1} vs Winner {m2}**")
        winnersS[mid] = escolher_vencedor_ui(mid, t1, t2)

# -------------------------------------------------------------
# THIRD PLACE & FINAL
# -------------------------------------------------------------
st.header("7. Third Place Match & Final")
col3, colF = st.columns(2)

# Third place: automatically the losers of the semifinals
with col3:
    st.subheader("Third Place Match")

    sf1_m1, sf1_m2 = SEMIS_MATCHES["M101"]  # ("M97", "M98")
    sf1_t1 = winnersQ.get(sf1_m1)
    sf1_t2 = winnersQ.get(sf1_m2)
    sf1_winner = winnersS.get("M101")

    sf2_m1, sf2_m2 = SEMIS_MATCHES["M102"]  # ("M99", "M100")
    sf2_t1 = winnersQ.get(sf2_m1)
    sf2_t2 = winnersQ.get(sf2_m2)
    sf2_winner = winnersS.get("M102")

    if all([sf1_t1, sf1_t2, sf1_winner, sf2_t1, sf2_t2, sf2_winner]):
        sf1_loser = sf1_t2 if sf1_winner == sf1_t1 else sf1_t1
        sf2_loser = sf2_t2 if sf2_winner == sf2_t1 else sf2_t1

        st.write(f"{sf1_loser} vs {sf2_loser}")
        third_place_winner = escolher_vencedor_ui(
            "M103 (Third Place)", sf1_loser, sf2_loser
        )
        if third_place_winner:
            st.success(f"🥉 Third Place: **{third_place_winner}**")
    else:
        st.write("Waiting for semifinal results…")

# Final: winners of the semifinals
with colF:
    st.subheader("Final")
    tf1 = winnersS.get("M101")
    tf2 = winnersS.get("M102")
    champion = escolher_vencedor_ui("M104 (Final)", tf1, tf2)
    if champion:
        st.success(f"🏆 World Cup 2026 Champion: **{champion}**")

# -------------------------------------------------------------
# SUMMARY
# -------------------------------------------------------------
st.markdown("---")
# st.header("Tournament Summary")

# if not('champion' in locals() and champion):
#     st.write("Complete all selections to see the tournament winner.")

st.markdown("Made by ArthurAAM")