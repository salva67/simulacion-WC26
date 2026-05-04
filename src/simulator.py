
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd


GROUP_FIXTURES_BY_POSITION = [(1, 2), (3, 4), (1, 3), (4, 2), (4, 1), (2, 3)]

# Round of 32 bracket from official published bracket slots.
R32_MATCHES = [
    (73, "2A", "2B"),
    (74, "1C", "2F"),
    (75, "1E", "3ABCDF"),
    (76, "1F", "2C"),
    (77, "2E", "2I"),
    (78, "1I", "3CDFGH"),
    (79, "1A", "3CEFHI"),
    (80, "1L", "3EHIJK"),
    (81, "1G", "3AEHIJ"),
    (82, "1D", "3BEFIJ"),
    (83, "1H", "2J"),
    (84, "2K", "2L"),
    (85, "1B", "3EFGIJ"),
    (86, "2D", "2G"),
    (87, "1J", "2H"),
    (88, "1K", "3DEIJL"),
]

R16_MATCHES = [
    (89, 73, 75),
    (90, 74, 77),
    (91, 76, 78),
    (92, 79, 80),
    (93, 83, 84),
    (94, 81, 82),
    (95, 86, 88),
    (96, 85, 87),
]

QF_MATCHES = [(97, 89, 90), (98, 93, 94), (99, 91, 92), (100, 95, 96)]
SF_MATCHES = [(101, 97, 98), (102, 99, 100)]
FINAL_MATCH = (104, 101, 102)
THIRD_PLACE_MATCH = (103, 101, 102)

THIRD_TOKENS = [token for _, a, b in R32_MATCHES for token in (a, b) if token.startswith("3")]

STAGE_LABELS = {
    0: "Fase de grupos",
    1: "32avos",
    2: "16avos",
    3: "Cuartos",
    4: "Semifinal",
    5: "Final",
    6: "Campeón",
}

PROB_COLUMNS = [
    ("p_r32", "Pasa a 32avos"),
    ("p_r16", "Pasa a 16avos"),
    ("p_qf", "Pasa a cuartos"),
    ("p_sf", "Pasa a semifinal"),
    ("p_final", "Llega a la final"),
    ("p_champion", "Campeón"),
]


@dataclass
class ModelParams:
    n_sims: int = 5000
    base_goals: float = 1.35
    rating_scale: float = 375.0
    host_advantage_points: float = 35.0
    knockout_penalty_scale: float = 450.0
    seed: int = 42


def clean_teams(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["group"] = out["group"].astype(str)
    out["position"] = out["position"].astype(int)
    out["team"] = out["team"].astype(str)
    out["fifa_rank"] = out["fifa_rank"].astype(int)
    out["fifa_points"] = out["fifa_points"].astype(float)
    out["is_host"] = out["is_host"].astype(int)
    return out.sort_values(["group", "position"]).reset_index(drop=True)


def adjusted_rating(row: pd.Series, params: ModelParams) -> float:
    return float(row["fifa_points"]) + float(row.get("is_host", 0)) * params.host_advantage_points


def expected_goals(row_a: pd.Series, row_b: pd.Series, params: ModelParams) -> Tuple[float, float]:
    ra = adjusted_rating(row_a, params)
    rb = adjusted_rating(row_b, params)
    diff = np.clip((ra - rb) / params.rating_scale, -2.2, 2.2)
    lam_a = params.base_goals * np.exp(diff / 2.0)
    lam_b = params.base_goals * np.exp(-diff / 2.0)
    return float(lam_a), float(lam_b)


def simulate_score(row_a: pd.Series, row_b: pd.Series, rng: np.random.Generator, params: ModelParams) -> Tuple[int, int]:
    lam_a, lam_b = expected_goals(row_a, row_b, params)
    goals_a = int(rng.poisson(lam_a))
    goals_b = int(rng.poisson(lam_b))
    return goals_a, goals_b


def knockout_tiebreak(row_a: pd.Series, row_b: pd.Series, rng: np.random.Generator, params: ModelParams) -> str:
    # Logistic/Elo-style probability for extra time + penalties.
    ra = adjusted_rating(row_a, params)
    rb = adjusted_rating(row_b, params)
    p_a = 1.0 / (1.0 + 10.0 ** (-(ra - rb) / params.knockout_penalty_scale))
    return str(row_a["team"]) if rng.random() < p_a else str(row_b["team"])


def simulate_knockout_match(
    row_a: pd.Series,
    row_b: pd.Series,
    rng: np.random.Generator,
    params: ModelParams,
) -> Tuple[str, str, str]:
    ga, gb = simulate_score(row_a, row_b, rng, params)
    if ga > gb:
        winner, loser = str(row_a["team"]), str(row_b["team"])
        score = f"{ga}-{gb}"
    elif gb > ga:
        winner, loser = str(row_b["team"]), str(row_a["team"])
        score = f"{ga}-{gb}"
    else:
        winner = knockout_tiebreak(row_a, row_b, rng, params)
        loser = str(row_b["team"]) if winner == str(row_a["team"]) else str(row_a["team"])
        score = f"{ga}-{gb} (pen)"
    return winner, loser, score


def simulate_group(
    group_df: pd.DataFrame,
    team_lookup: Dict[str, pd.Series],
    rng: np.random.Generator,
    params: ModelParams,
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    teams = group_df.sort_values("position")
    pos_to_team = dict(zip(teams["position"], teams["team"]))
    table = {
        team: {"team": team, "group": str(teams.iloc[0]["group"]), "pts": 0, "gf": 0, "ga": 0, "gd": 0}
        for team in teams["team"]
    }
    matches = []

    for i, (pa, pb) in enumerate(GROUP_FIXTURES_BY_POSITION, start=1):
        ta, tb = pos_to_team[pa], pos_to_team[pb]
        row_a, row_b = team_lookup[ta], team_lookup[tb]
        ga, gb = simulate_score(row_a, row_b, rng, params)

        table[ta]["gf"] += ga
        table[ta]["ga"] += gb
        table[tb]["gf"] += gb
        table[tb]["ga"] += ga
        table[ta]["gd"] = table[ta]["gf"] - table[ta]["ga"]
        table[tb]["gd"] = table[tb]["gf"] - table[tb]["ga"]

        if ga > gb:
            table[ta]["pts"] += 3
        elif gb > ga:
            table[tb]["pts"] += 3
        else:
            table[ta]["pts"] += 1
            table[tb]["pts"] += 1

        matches.append(
            {
                "round": "Grupo",
                "group": str(teams.iloc[0]["group"]),
                "matchday": i,
                "team_a": ta,
                "team_b": tb,
                "score": f"{ga}-{gb}",
                "winner": ta if ga > gb else tb if gb > ga else "Empate",
            }
        )

    standings = pd.DataFrame(table.values())
    standings = standings.merge(
        group_df[["team", "fifa_rank", "fifa_points"]], on="team", how="left"
    )
    standings["_random_tiebreak"] = rng.random(len(standings))
    # Simplified FIFA-style ranking: points, goal difference, goals for, FIFA points/rank as final tie-break proxy.
    standings = standings.sort_values(
        ["pts", "gd", "gf", "fifa_points", "_random_tiebreak"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    standings["group_pos"] = np.arange(1, len(standings) + 1)
    standings = standings.drop(columns=["_random_tiebreak"])
    return standings, matches


def assign_third_place_tokens(advanced_groups: List[str]) -> Dict[str, str]:
    """
    Assign each '3ABC...' token to one of the eight actual third-place groups.

    FIFA publishes a full Annex C matrix. This implementation respects the official
    eligibility set encoded in each bracket token and uses deterministic backtracking
    so every advancing third-placed group is used once.
    """
    groups = sorted(set(advanced_groups))
    candidates = {token: sorted([g for g in groups if g in set(token[1:])]) for token in THIRD_TOKENS}
    tokens_by_constraint = sorted(THIRD_TOKENS, key=lambda t: (len(candidates[t]), t))
    solution: Dict[str, str] = {}

    def backtrack(i: int, used: set) -> bool:
        if i == len(tokens_by_constraint):
            return True
        token = tokens_by_constraint[i]
        # Stable preference: use groups with fewer remaining slots first.
        cand = sorted(
            [g for g in candidates[token] if g not in used],
            key=lambda g: (sum(g in candidates[t] for t in tokens_by_constraint[i + 1 :]), g),
        )
        for g in cand:
            solution[token] = g
            used.add(g)
            if backtrack(i + 1, used):
                return True
            used.remove(g)
            solution.pop(token, None)
        return False

    if not backtrack(0, set()):
        raise RuntimeError(f"No se pudo asignar terceros para grupos: {groups}")
    return solution


def resolve_slot(
    token: str,
    group_rankings: Dict[str, pd.DataFrame],
    third_assignment: Dict[str, str],
) -> str:
    if token.startswith("1") or token.startswith("2"):
        pos = int(token[0])
        grp = token[1]
        return str(group_rankings[grp].query("group_pos == @pos").iloc[0]["team"])
    if token.startswith("3"):
        grp = third_assignment[token]
        return str(group_rankings[grp].query("group_pos == 3").iloc[0]["team"])
    raise ValueError(f"Token no reconocido: {token}")


def simulate_tournament(
    teams_df: pd.DataFrame,
    rng: np.random.Generator,
    params: ModelParams,
    keep_trace: bool = False,
) -> Tuple[Dict[str, int], Dict[str, int], Optional[pd.DataFrame]]:
    teams_df = clean_teams(teams_df)
    team_lookup = {row["team"]: row for _, row in teams_df.iterrows()}

    stage = {team: 0 for team in teams_df["team"]}
    group_positions: Dict[str, int] = {}
    trace: List[Dict[str, Any]] = []

    group_rankings: Dict[str, pd.DataFrame] = {}
    for grp, gdf in teams_df.groupby("group", sort=True):
        standings, matches = simulate_group(gdf, team_lookup, rng, params)
        group_rankings[grp] = standings
        if keep_trace:
            trace.extend(matches)

        for _, row in standings.iterrows():
            team = str(row["team"])
            pos = int(row["group_pos"])
            group_positions[team] = pos
            if pos <= 2:
                stage[team] = max(stage[team], 1)

    third_rows = []
    for grp, standings in group_rankings.items():
        third = standings.query("group_pos == 3").iloc[0].to_dict()
        third["group"] = grp
        third_rows.append(third)

    thirds = pd.DataFrame(third_rows)
    thirds["_random_tiebreak"] = rng.random(len(thirds))
    thirds = thirds.sort_values(
        ["pts", "gd", "gf", "fifa_points", "_random_tiebreak"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    advanced_thirds = list(thirds.head(8)["group"])
    third_assignment = assign_third_place_tokens(advanced_thirds)

    for grp in advanced_thirds:
        team = str(group_rankings[grp].query("group_pos == 3").iloc[0]["team"])
        stage[team] = max(stage[team], 1)

    winners: Dict[int, str] = {}
    losers: Dict[int, str] = {}

    # Round of 32.
    for match_no, token_a, token_b in R32_MATCHES:
        ta = resolve_slot(token_a, group_rankings, third_assignment)
        tb = resolve_slot(token_b, group_rankings, third_assignment)
        winner, loser, score = simulate_knockout_match(team_lookup[ta], team_lookup[tb], rng, params)
        winners[match_no] = winner
        losers[match_no] = loser
        stage[winner] = max(stage[winner], 2)
        if keep_trace:
            trace.append({"round": "32avos", "match": match_no, "team_a": ta, "team_b": tb, "score": score, "winner": winner})

    # Round of 16.
    for match_no, prev_a, prev_b in R16_MATCHES:
        ta, tb = winners[prev_a], winners[prev_b]
        winner, loser, score = simulate_knockout_match(team_lookup[ta], team_lookup[tb], rng, params)
        winners[match_no] = winner
        losers[match_no] = loser
        stage[winner] = max(stage[winner], 3)
        if keep_trace:
            trace.append({"round": "16avos", "match": match_no, "team_a": ta, "team_b": tb, "score": score, "winner": winner})

    # Quarter-finals.
    for match_no, prev_a, prev_b in QF_MATCHES:
        ta, tb = winners[prev_a], winners[prev_b]
        winner, loser, score = simulate_knockout_match(team_lookup[ta], team_lookup[tb], rng, params)
        winners[match_no] = winner
        losers[match_no] = loser
        stage[winner] = max(stage[winner], 4)
        if keep_trace:
            trace.append({"round": "Cuartos", "match": match_no, "team_a": ta, "team_b": tb, "score": score, "winner": winner})

    # Semi-finals.
    for match_no, prev_a, prev_b in SF_MATCHES:
        ta, tb = winners[prev_a], winners[prev_b]
        winner, loser, score = simulate_knockout_match(team_lookup[ta], team_lookup[tb], rng, params)
        winners[match_no] = winner
        losers[match_no] = loser
        stage[winner] = max(stage[winner], 5)
        if keep_trace:
            trace.append({"round": "Semifinal", "match": match_no, "team_a": ta, "team_b": tb, "score": score, "winner": winner})

    # Final.
    final_no, prev_a, prev_b = FINAL_MATCH
    ta, tb = winners[prev_a], winners[prev_b]
    champion, runner_up, score = simulate_knockout_match(team_lookup[ta], team_lookup[tb], rng, params)
    winners[final_no] = champion
    losers[final_no] = runner_up
    stage[champion] = 6
    if keep_trace:
        trace.append({"round": "Final", "match": final_no, "team_a": ta, "team_b": tb, "score": score, "winner": champion})

    # Optional third-place trace.
    if keep_trace:
        ta, tb = losers[101], losers[102]
        winner, loser, score = simulate_knockout_match(team_lookup[ta], team_lookup[tb], rng, params)
        trace.append({"round": "Tercer puesto", "match": 103, "team_a": ta, "team_b": tb, "score": score, "winner": winner})

    trace_df = pd.DataFrame(trace) if keep_trace else None
    return stage, group_positions, trace_df


def run_monte_carlo(
    teams_df: pd.DataFrame,
    params: ModelParams,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    teams_df = clean_teams(teams_df)
    rng = np.random.default_rng(params.seed)

    teams = list(teams_df["team"])
    stage_counts = {team: {level: 0 for level in range(7)} for team in teams}
    group_pos_counts = {team: {pos: 0 for pos in [1, 2, 3, 4]} for team in teams}
    sample_trace = None

    for sim in range(params.n_sims):
        stage, group_positions, trace = simulate_tournament(
            teams_df, rng, params, keep_trace=(sim == 0)
        )
        if sim == 0:
            sample_trace = trace

        for team, highest_stage in stage.items():
            for level in range(highest_stage + 1):
                stage_counts[team][level] += 1
        for team, pos in group_positions.items():
            group_pos_counts[team][pos] += 1

    rows = []
    for _, trow in teams_df.iterrows():
        team = str(trow["team"])
        rows.append(
            {
                "team": team,
                "group": trow["group"],
                "fifa_rank": int(trow["fifa_rank"]),
                "fifa_points": float(trow["fifa_points"]),
                "p_r32": stage_counts[team][1] / params.n_sims,
                "p_r16": stage_counts[team][2] / params.n_sims,
                "p_qf": stage_counts[team][3] / params.n_sims,
                "p_sf": stage_counts[team][4] / params.n_sims,
                "p_final": stage_counts[team][5] / params.n_sims,
                "p_champion": stage_counts[team][6] / params.n_sims,
            }
        )
    probs = pd.DataFrame(rows).sort_values("p_champion", ascending=False).reset_index(drop=True)

    gpos_rows = []
    for _, trow in teams_df.iterrows():
        team = str(trow["team"])
        rec = {"team": team, "group": trow["group"]}
        for pos in [1, 2, 3, 4]:
            rec[f"p_group_{pos}"] = group_pos_counts[team][pos] / params.n_sims
        rec["p_top2"] = rec["p_group_1"] + rec["p_group_2"]
        gpos_rows.append(rec)

    group_probs = pd.DataFrame(gpos_rows).sort_values(["group", "p_group_1"], ascending=[True, False])
    return probs, group_probs, sample_trace if sample_trace is not None else pd.DataFrame()
