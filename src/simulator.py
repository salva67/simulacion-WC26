from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


GROUP_FIXTURES_BY_POSITION = [(1, 2), (3, 4), (1, 3), (4, 2), (4, 1), (2, 3)]

# Round of 32 bracket from the published 2026 bracket slots.
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
    elo_weight: float = 0.50
    seed: int = 42


def clean_teams(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["group"] = out["group"].astype(str)
    out["position"] = out["position"].astype(int)
    out["team"] = out["team"].astype(str)
    out["fifa_rank"] = out["fifa_rank"].astype(int)
    out["fifa_points"] = out["fifa_points"].astype(float)
    if "elo_rating" not in out.columns:
        out["elo_rating"] = np.nan
    out["elo_rating"] = pd.to_numeric(out["elo_rating"], errors="coerce")
    out["is_host"] = out["is_host"].astype(int)
    return out.sort_values(["group", "position"]).reset_index(drop=True)


def _minmax(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce")
    if series.isna().all():
        return pd.Series(0.5, index=series.index)
    series = series.fillna(series.median())
    min_v = float(series.min())
    max_v = float(series.max())
    if abs(max_v - min_v) < 1e-9:
        return pd.Series(0.5, index=series.index)
    return (series - min_v) / (max_v - min_v)


def add_model_rating(teams_df: pd.DataFrame, params: ModelParams) -> pd.DataFrame:
    """Create the common-scale rating used by the simulation engine."""
    out = clean_teams(teams_df)
    elo_weight = float(np.clip(params.elo_weight, 0.0, 1.0))
    fifa_weight = 1.0 - elo_weight

    fifa_norm = _minmax(out["fifa_points"])
    elo_norm = _minmax(out["elo_rating"]) if out["elo_rating"].notna().any() else fifa_norm.copy()

    out["rating_fifa_norm"] = fifa_norm
    out["rating_elo_norm"] = elo_norm
    out["rating_final_norm"] = fifa_weight * fifa_norm + elo_weight * elo_norm
    out["model_rating"] = 1300.0 + out["rating_final_norm"] * 900.0
    return out


def adjusted_rating(row: pd.Series, params: ModelParams) -> float:
    base = float(row.get("model_rating", row.get("fifa_points", 1500.0)))
    return base + float(row.get("is_host", 0)) * params.host_advantage_points


def expected_goals(row_a: pd.Series, row_b: pd.Series, params: ModelParams) -> Tuple[float, float]:
    ra = adjusted_rating(row_a, params)
    rb = adjusted_rating(row_b, params)
    diff = np.clip((ra - rb) / params.rating_scale, -2.2, 2.2)
    lam_a = params.base_goals * np.exp(diff / 2.0)
    lam_b = params.base_goals * np.exp(-diff / 2.0)
    return float(lam_a), float(lam_b)


def simulate_score(row_a: pd.Series, row_b: pd.Series, rng: np.random.Generator, params: ModelParams) -> Tuple[int, int]:
    lam_a, lam_b = expected_goals(row_a, row_b, params)
    return int(rng.poisson(lam_a)), int(rng.poisson(lam_b))


def _expected_from_ratings(rating_a: float, rating_b: float, params: ModelParams) -> Tuple[float, float]:
    diff = float(np.clip((rating_a - rating_b) / params.rating_scale, -2.2, 2.2))
    return params.base_goals * float(np.exp(diff / 2.0)), params.base_goals * float(np.exp(-diff / 2.0))


def _simulate_score_idx(i: int, j: int, ratings: np.ndarray, rng: np.random.Generator, params: ModelParams) -> Tuple[int, int]:
    lam_i, lam_j = _expected_from_ratings(float(ratings[i]), float(ratings[j]), params)
    return int(rng.poisson(lam_i)), int(rng.poisson(lam_j))


def _knockout_winner(i: int, j: int, ratings: np.ndarray, rng: np.random.Generator, params: ModelParams) -> Tuple[int, int, str]:
    gi, gj = _simulate_score_idx(i, j, ratings, rng, params)
    if gi > gj:
        return i, j, f"{gi}-{gj}"
    if gj > gi:
        return j, i, f"{gi}-{gj}"
    p_i = 1.0 / (1.0 + 10.0 ** (-(float(ratings[i]) - float(ratings[j])) / params.knockout_penalty_scale))
    winner = i if rng.random() < p_i else j
    loser = j if winner == i else i
    return winner, loser, f"{gi}-{gj} (pen)"


def assign_third_place_tokens(advanced_groups: List[str]) -> Dict[str, str]:
    """Assign each bracket third-place slot to an actual advancing group."""
    groups = sorted(set(advanced_groups))
    candidates = {token: sorted([g for g in groups if g in set(token[1:])]) for token in THIRD_TOKENS}
    tokens_by_constraint = sorted(THIRD_TOKENS, key=lambda t: (len(candidates[t]), t))
    solution: Dict[str, str] = {}

    def backtrack(i: int, used: set) -> bool:
        if i == len(tokens_by_constraint):
            return True
        token = tokens_by_constraint[i]
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
        # Fallback: deterministic assignment among eligible available groups. This keeps the
        # simulation running if a rare combination is not covered by the simplified slot matrix.
        available = groups.copy()
        solution.clear()
        for token in THIRD_TOKENS:
            elig = [g for g in available if g in set(token[1:])]
            chosen = elig[0] if elig else available[0]
            solution[token] = chosen
            available.remove(chosen)
    return solution


class TournamentEngine:
    def __init__(self, teams_df: pd.DataFrame, params: ModelParams):
        self.params = params
        self.teams_df = add_model_rating(teams_df, params)
        self.n = len(self.teams_df)
        self.names = self.teams_df["team"].tolist()
        self.groups = self.teams_df["group"].tolist()
        self.fifa_rank = self.teams_df["fifa_rank"].to_numpy(dtype=int)
        self.fifa_points = self.teams_df["fifa_points"].to_numpy(dtype=float)
        self.elo_rating = self.teams_df["elo_rating"].to_numpy(dtype=float)
        self.model_rating = self.teams_df["model_rating"].to_numpy(dtype=float)
        self.is_host = self.teams_df["is_host"].to_numpy(dtype=float)
        self.ratings = self.model_rating + self.is_host * params.host_advantage_points
        self.group_to_indices: Dict[str, List[int]] = {
            g: self.teams_df.index[self.teams_df["group"] == g].tolist()
            for g in sorted(self.teams_df["group"].unique())
        }

    def _resolve_slot(self, token: str, group_rankings: Dict[str, List[int]], third_assignment: Dict[str, str]) -> int:
        if token.startswith("1") or token.startswith("2"):
            pos = int(token[0]) - 1
            grp = token[1]
            return group_rankings[grp][pos]
        if token.startswith("3"):
            grp = third_assignment[token]
            return group_rankings[grp][2]
        raise ValueError(f"Token no reconocido: {token}")

    def simulate_once(self, rng: np.random.Generator, keep_trace: bool = False) -> Tuple[np.ndarray, np.ndarray, Optional[pd.DataFrame]]:
        stage = np.zeros(self.n, dtype=np.int8)
        group_pos = np.zeros(self.n, dtype=np.int8)
        trace: List[Dict[str, Any]] = []
        group_rankings: Dict[str, List[int]] = {}
        third_candidates: List[Dict[str, Any]] = []

        for grp, idxs in self.group_to_indices.items():
            pts = {i: 0 for i in idxs}
            gf = {i: 0 for i in idxs}
            ga = {i: 0 for i in idxs}

            pos_to_idx = {pos + 1: idxs[pos] for pos in range(4)}
            for md, (pa, pb) in enumerate(GROUP_FIXTURES_BY_POSITION, start=1):
                i, j = pos_to_idx[pa], pos_to_idx[pb]
                gi, gj = _simulate_score_idx(i, j, self.ratings, rng, self.params)
                gf[i] += gi; ga[i] += gj
                gf[j] += gj; ga[j] += gi
                if gi > gj:
                    pts[i] += 3
                    winner = self.names[i]
                elif gj > gi:
                    pts[j] += 3
                    winner = self.names[j]
                else:
                    pts[i] += 1; pts[j] += 1
                    winner = "Empate"
                if keep_trace:
                    trace.append({
                        "round": "Grupo", "group": grp, "matchday": md,
                        "team_a": self.names[i], "team_b": self.names[j],
                        "score": f"{gi}-{gj}", "winner": winner,
                    })

            random_tie = {i: rng.random() for i in idxs}
            ranking = sorted(
                idxs,
                key=lambda i: (pts[i], gf[i] - ga[i], gf[i], self.model_rating[i], random_tie[i]),
                reverse=True,
            )
            group_rankings[grp] = ranking
            for pos, i in enumerate(ranking, start=1):
                group_pos[i] = pos
                if pos <= 2:
                    stage[i] = max(stage[i], 1)
            third = ranking[2]
            third_candidates.append({
                "group": grp,
                "idx": third,
                "pts": pts[third],
                "gd": gf[third] - ga[third],
                "gf": gf[third],
                "model_rating": self.model_rating[third],
                "rand": rng.random(),
            })

        third_candidates.sort(key=lambda x: (x["pts"], x["gd"], x["gf"], x["model_rating"], x["rand"]), reverse=True)
        advanced_thirds = [x["group"] for x in third_candidates[:8]]
        for x in third_candidates[:8]:
            stage[x["idx"]] = max(stage[x["idx"]], 1)
        third_assignment = assign_third_place_tokens(advanced_thirds)

        winners: Dict[int, int] = {}
        losers: Dict[int, int] = {}

        for match_no, token_a, token_b in R32_MATCHES:
            i = self._resolve_slot(token_a, group_rankings, third_assignment)
            j = self._resolve_slot(token_b, group_rankings, third_assignment)
            winner, loser, score = _knockout_winner(i, j, self.ratings, rng, self.params)
            winners[match_no], losers[match_no] = winner, loser
            stage[winner] = max(stage[winner], 2)
            if keep_trace:
                trace.append({"round": "32avos", "match": match_no, "team_a": self.names[i], "team_b": self.names[j], "score": score, "winner": self.names[winner]})

        for match_no, prev_a, prev_b in R16_MATCHES:
            i, j = winners[prev_a], winners[prev_b]
            winner, loser, score = _knockout_winner(i, j, self.ratings, rng, self.params)
            winners[match_no], losers[match_no] = winner, loser
            stage[winner] = max(stage[winner], 3)
            if keep_trace:
                trace.append({"round": "16avos", "match": match_no, "team_a": self.names[i], "team_b": self.names[j], "score": score, "winner": self.names[winner]})

        for match_no, prev_a, prev_b in QF_MATCHES:
            i, j = winners[prev_a], winners[prev_b]
            winner, loser, score = _knockout_winner(i, j, self.ratings, rng, self.params)
            winners[match_no], losers[match_no] = winner, loser
            stage[winner] = max(stage[winner], 4)
            if keep_trace:
                trace.append({"round": "Cuartos", "match": match_no, "team_a": self.names[i], "team_b": self.names[j], "score": score, "winner": self.names[winner]})

        for match_no, prev_a, prev_b in SF_MATCHES:
            i, j = winners[prev_a], winners[prev_b]
            winner, loser, score = _knockout_winner(i, j, self.ratings, rng, self.params)
            winners[match_no], losers[match_no] = winner, loser
            stage[winner] = max(stage[winner], 5)
            if keep_trace:
                trace.append({"round": "Semifinal", "match": match_no, "team_a": self.names[i], "team_b": self.names[j], "score": score, "winner": self.names[winner]})

        final_no, prev_a, prev_b = FINAL_MATCH
        i, j = winners[prev_a], winners[prev_b]
        champion, runner_up, score = _knockout_winner(i, j, self.ratings, rng, self.params)
        winners[final_no], losers[final_no] = champion, runner_up
        stage[champion] = 6
        if keep_trace:
            trace.append({"round": "Final", "match": final_no, "team_a": self.names[i], "team_b": self.names[j], "score": score, "winner": self.names[champion]})
            i3, j3 = losers[101], losers[102]
            third_winner, _, score3 = _knockout_winner(i3, j3, self.ratings, rng, self.params)
            trace.append({"round": "Tercer puesto", "match": 103, "team_a": self.names[i3], "team_b": self.names[j3], "score": score3, "winner": self.names[third_winner]})

        return stage, group_pos, pd.DataFrame(trace) if keep_trace else None


def simulate_tournament(
    teams_df: pd.DataFrame,
    rng: np.random.Generator,
    params: ModelParams,
    keep_trace: bool = False,
) -> Tuple[Dict[str, int], Dict[str, int], Optional[pd.DataFrame]]:
    engine = TournamentEngine(teams_df, params)
    stage_arr, group_pos_arr, trace = engine.simulate_once(rng, keep_trace=keep_trace)
    stage = {engine.names[i]: int(stage_arr[i]) for i in range(engine.n)}
    group_positions = {engine.names[i]: int(group_pos_arr[i]) for i in range(engine.n)}
    return stage, group_positions, trace


def run_monte_carlo(teams_df: pd.DataFrame, params: ModelParams) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(params.seed)
    engine = TournamentEngine(teams_df, params)

    stage_counts = np.zeros((engine.n, 7), dtype=np.int32)
    group_pos_counts = np.zeros((engine.n, 5), dtype=np.int32)
    sample_trace: Optional[pd.DataFrame] = None

    for sim in range(int(params.n_sims)):
        stage, group_pos, trace = engine.simulate_once(rng, keep_trace=(sim == 0))
        if sim == 0:
            sample_trace = trace
        for i, highest_stage in enumerate(stage):
            stage_counts[i, : int(highest_stage) + 1] += 1
        for i, pos in enumerate(group_pos):
            group_pos_counts[i, int(pos)] += 1

    rows = []
    for i, row in engine.teams_df.iterrows():
        rows.append({
            "team": engine.names[i],
            "group": engine.groups[i],
            "fifa_rank": int(engine.fifa_rank[i]),
            "fifa_points": float(engine.fifa_points[i]),
            "elo_rating": float(engine.elo_rating[i]) if not np.isnan(engine.elo_rating[i]) else np.nan,
            "model_rating": float(engine.model_rating[i]),
            "p_r32": stage_counts[i, 1] / params.n_sims,
            "p_r16": stage_counts[i, 2] / params.n_sims,
            "p_qf": stage_counts[i, 3] / params.n_sims,
            "p_sf": stage_counts[i, 4] / params.n_sims,
            "p_final": stage_counts[i, 5] / params.n_sims,
            "p_champion": stage_counts[i, 6] / params.n_sims,
        })
    probs = pd.DataFrame(rows).sort_values("p_champion", ascending=False).reset_index(drop=True)

    gpos_rows = []
    for i in range(engine.n):
        rec = {"team": engine.names[i], "group": engine.groups[i]}
        for pos in [1, 2, 3, 4]:
            rec[f"p_group_{pos}"] = group_pos_counts[i, pos] / params.n_sims
        rec["p_top2"] = rec["p_group_1"] + rec["p_group_2"]
        gpos_rows.append(rec)
    group_probs = pd.DataFrame(gpos_rows).sort_values(["group", "p_group_1"], ascending=[True, False])
    return probs, group_probs, sample_trace if sample_trace is not None else pd.DataFrame()
