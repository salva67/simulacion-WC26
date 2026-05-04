# Simulador Monte Carlo — Mundial 2026

Proyecto Streamlit para simular la Copa Mundial FIFA 2026 completa: fase de grupos, mejores terceros, 32avos, bracket y campeón.

## Cómo correrlo localmente

```bash
cd worldcup_2026_montecarlo_streamlit
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Estructura

```text
worldcup_2026_montecarlo_streamlit/
├── app.py
├── requirements.txt
├── data/
│   └── teams_2026.csv
└── src/
    ├── __init__.py
    └── simulator.py
```

## Modelo

El rating base de cada selección se calcula con puntos FIFA. La app permite modificar:

- cantidad de simulaciones
- goles promedio por equipo
- sensibilidad a diferencia de rating
- ventaja local para México, USA y Canadá
- aleatoriedad en alargue/penales
- seed para reproducibilidad

## Cómo mejorar el modelo

El CSV `teams_2026.csv` puede reemplazarse por un archivo propio con un rating más rico, por ejemplo:

```text
rating_final = 0.55 * fifa_points + 0.25 * elo + 0.15 * market_value_index + 0.05 * recent_form
```

También podés sumar columnas y adaptar `src/simulator.py` para incluir:

- odds de casas de apuestas
- ELO internacional
- forma últimos 10 partidos
- ventaja por sede/distancia
- bajas por lesiones
- ranking de ataque y defensa separado
