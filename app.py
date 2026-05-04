
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.simulator import ModelParams, PROB_COLUMNS, run_monte_carlo, clean_teams


st.set_page_config(
    page_title="Simulador Mundial 2026 - Monte Carlo",
    page_icon="⚽",
    layout="wide",
)

DATA_PATH = Path(__file__).parent / "data" / "teams_2026.csv"


@st.cache_data
def load_default_teams() -> pd.DataFrame:
    return clean_teams(pd.read_csv(DATA_PATH))


@st.cache_data(show_spinner=True)
def cached_simulation(csv_data: str, params_dict: dict):
    from io import StringIO

    teams_df = clean_teams(pd.read_csv(StringIO(csv_data)))
    params = ModelParams(**params_dict)
    return run_monte_carlo(teams_df, params)


def pct(x: float) -> str:
    return f"{100*x:.1f}%"


def render_probability_chart(df: pd.DataFrame, metric: str, title: str):
    chart_df = df.nlargest(20, metric).copy()
    chart_df["prob"] = chart_df[metric] * 100
    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("prob:Q", title="Probabilidad (%)"),
            y=alt.Y("team:N", sort="-x", title="Selección"),
            tooltip=["team", "group", "fifa_rank", alt.Tooltip("prob:Q", format=".2f")],
        )
        .properties(height=520, title=title)
    )
    st.altair_chart(chart, use_container_width=True)


def main():
    st.title("⚽ Simulador Monte Carlo — Copa Mundial FIFA 2026")
    st.caption(
        "Motor probabilístico para simular todo el torneo: fase de grupos, mejores terceros, 32avos, bracket y campeón."
    )

    default_teams = load_default_teams()

    with st.sidebar:
        st.header("Parámetros")
        n_sims = st.slider("Cantidad de simulaciones", 500, 50000, 5000, step=500)
        seed = st.number_input("Seed", value=42, min_value=0, step=1)
        base_goals = st.slider("Goles promedio base por equipo", 0.8, 2.2, 1.35, step=0.05)
        rating_scale = st.slider("Sensibilidad a diferencia de ranking", 250.0, 650.0, 375.0, step=25.0)
        host_adv = st.slider("Ventaja local para México/USA/Canadá en puntos FIFA", 0.0, 100.0, 35.0, step=5.0)
        ko_scale = st.slider("Aleatoriedad en alargue/penales", 250.0, 800.0, 450.0, step=25.0)

        st.divider()
        st.subheader("Datos")
        uploaded = st.file_uploader(
            "Reemplazar teams_2026.csv",
            type=["csv"],
            help="Debe tener: group, position, team, team_code, confederation, fifa_rank, fifa_points, is_host.",
        )

    if uploaded is not None:
        teams = clean_teams(pd.read_csv(uploaded))
    else:
        teams = default_teams

    params = ModelParams(
        n_sims=int(n_sims),
        base_goals=float(base_goals),
        rating_scale=float(rating_scale),
        host_advantage_points=float(host_adv),
        knockout_penalty_scale=float(ko_scale),
        seed=int(seed),
    )

    csv_data = teams.to_csv(index=False)
    params_dict = params.__dict__.copy()

    probs, group_probs, sample_trace = cached_simulation(csv_data, params_dict)

    c1, c2, c3, c4 = st.columns(4)
    champion = probs.iloc[0]
    c1.metric("Favorito al título", champion["team"], pct(champion["p_champion"]))
    c2.metric("Mayor prob. de final", probs.sort_values("p_final", ascending=False).iloc[0]["team"],
              pct(probs["p_final"].max()))
    c3.metric("Simulaciones", f"{n_sims:,}".replace(",", "."))
    c4.metric("Equipos", len(teams))

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["🏆 Título", "📊 Rondas", "🧩 Grupos", "🗺️ Simulación ejemplo", "🧾 Datos"]
    )

    with tab1:
        st.subheader("Probabilidad de campeón")
        render_probability_chart(probs, "p_champion", "Top 20 — probabilidad de campeón")
        show_cols = ["team", "group", "fifa_rank", "fifa_points", "p_champion", "p_final", "p_sf", "p_qf", "p_r16", "p_r32"]
        table = probs[show_cols].copy()
        for col in ["p_champion", "p_final", "p_sf", "p_qf", "p_r16", "p_r32"]:
            table[col] = table[col].map(pct)
        st.dataframe(table, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Probabilidades acumuladas por ronda")
        metric_name = st.selectbox(
            "Métrica",
            options=[col for col, _ in PROB_COLUMNS],
            format_func=lambda x: dict(PROB_COLUMNS)[x],
            index=0,
        )
        render_probability_chart(probs, metric_name, dict(PROB_COLUMNS)[metric_name])
        st.download_button(
            "Descargar probabilidades por ronda",
            probs.to_csv(index=False).encode("utf-8"),
            file_name="probabilidades_mundial_2026.csv",
            mime="text/csv",
        )

    with tab3:
        st.subheader("Probabilidades de posición en grupo")
        group_selected = st.selectbox("Grupo", sorted(group_probs["group"].unique()))
        gdf = group_probs[group_probs["group"] == group_selected].copy()

        view = gdf.copy()
        for col in ["p_group_1", "p_group_2", "p_group_3", "p_group_4", "p_top2"]:
            view[col] = view[col].map(pct)
        st.dataframe(view, use_container_width=True, hide_index=True)

        melted = gdf.melt(
            id_vars=["team", "group"],
            value_vars=["p_group_1", "p_group_2", "p_group_3", "p_group_4"],
            var_name="position",
            value_name="probability",
        )
        melted["position"] = melted["position"].str.replace("p_group_", "Puesto ")
        melted["probability"] = melted["probability"] * 100
        chart = (
            alt.Chart(melted)
            .mark_bar()
            .encode(
                x=alt.X("team:N", title="Selección"),
                y=alt.Y("probability:Q", title="Probabilidad (%)"),
                color=alt.Color("position:N", title="Posición"),
                tooltip=["team", "position", alt.Tooltip("probability:Q", format=".2f")],
            )
            .properties(height=380)
        )
        st.altair_chart(chart, use_container_width=True)

    with tab4:
        st.subheader("Una simulación individual del torneo")
        st.caption("Sirve para auditar el camino simulado: resultados de grupo y cruces.")
        st.dataframe(sample_trace, use_container_width=True, hide_index=True)

    with tab5:
        st.subheader("Dataset base")
        st.write(
            "El modelo usa grupos oficiales y ranking/puntos FIFA como fuerza base. "
            "Podés reemplazar el CSV por uno propio con forma reciente, ELO externo, odds o lesiones."
        )
        st.dataframe(teams, use_container_width=True, hide_index=True)

        st.download_button(
            "Descargar teams_2026.csv",
            teams.to_csv(index=False).encode("utf-8"),
            file_name="teams_2026.csv",
            mime="text/csv",
        )

        st.markdown(
            """
            **Columnas esperadas para cargar datos propios**
            - `group`: A-L
            - `position`: 1-4, posición en el fixture del grupo
            - `team`: nombre de la selección
            - `team_code`: código corto
            - `confederation`: confederación
            - `fifa_rank`: ranking FIFA
            - `fifa_points`: puntos FIFA o rating equivalente
            - `is_host`: 1 para anfitrión, 0 para el resto

            **Notas metodológicas**
            - Fase de grupos: goles simulados con Poisson usando puntos FIFA ajustados.
            - Empates de grupo: se ordena por puntos, diferencia de gol, goles a favor y rating.
            - 32avos: se respetan los slots oficiales y los conjuntos elegibles de terceros.
            - Eliminatorias: si hay empate, se define por una probabilidad tipo Elo para alargue/penales.
            """
        )


if __name__ == "__main__":
    main()
