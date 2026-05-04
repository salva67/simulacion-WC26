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
├── docs/
│   └── manual_operacion.md
└── src/
    ├── __init__.py
    └── simulator.py
```

## Cómo operar la app

La guía completa está en [`docs/manual_operacion.md`](docs/manual_operacion.md).

Resumen de uso:

1. Abrir la app con `streamlit run app.py`.
2. Revisar los equipos cargados en la pestaña **Datos**.
3. Ajustar los parámetros desde el panel lateral.
4. Definir el **Peso ELO** del rating compuesto.
5. Leer probabilidades en las pestañas **Título**, **Rondas** y **Grupos**.
6. Usar **Simulación ejemplo** solo como auditoría de un escenario individual.
7. Descargar resultados o reemplazar el CSV base por uno propio si se quiere usar otro rating.

La interpretación correcta es probabilística: una probabilidad de campeón de 12% significa que esa selección salió campeona en aproximadamente 12 de cada 100 torneos simulados, no que el modelo asegure que será campeona.

## Modelo

El modelo usa un rating compuesto basado en:

- `fifa_points`: puntos del ranking FIFA;
- `elo_rating`: rating World Football Elo;
- `is_host`: ventaja configurable para México, Estados Unidos y Canadá.

Como FIFA y ELO están en escalas distintas, el motor normaliza ambas variables de 0 a 1 dentro del universo de 48 selecciones y luego calcula:

```text
rating_final_norm = (1 - peso_elo) * fifa_points_norm + peso_elo * elo_rating_norm
model_rating = 1300 + rating_final_norm * 900
```

La app permite modificar:

- cantidad de simulaciones;
- peso ELO dentro del rating compuesto;
- goles promedio por equipo;
- sensibilidad a diferencia de rating;
- ventaja local para México, USA y Canadá;
- aleatoriedad en alargue/penales;
- seed para reproducibilidad.

## Datos propios

El CSV `teams_2026.csv` puede reemplazarse por un archivo propio con las mismas columnas. La columna `elo_rating` es recomendada. Si falta, la app sigue corriendo y usa un proxy basado en FIFA.

Columnas esperadas:

```text
group,position,team,team_code,confederation,fifa_rank,fifa_points,elo_rating,is_host
```

También podés adaptar `src/simulator.py` para incluir:

- odds de casas de apuestas;
- forma últimos 10 partidos;
- ventaja por sede/distancia;
- bajas por lesiones;
- ranking de ataque y defensa separado.
