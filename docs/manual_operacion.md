# Manual de operación — Simulador Monte Carlo Mundial 2026

Este documento explica cómo usar la app Streamlit del simulador Monte Carlo para la Copa Mundial FIFA 2026.

## 1. Objetivo de la app

La app permite simular miles de veces el Mundial 2026 completo para estimar probabilidades de avance por selección:

- clasificación a 32avos;
- clasificación a 16avos;
- clasificación a cuartos;
- clasificación a semifinal;
- llegada a la final;
- probabilidad de campeón.

El modelo no predice un único resultado determinístico. Ejecuta muchas simulaciones posibles y resume la frecuencia con la que cada selección llega a cada instancia.

## 2. Cómo iniciar la app

Desde la carpeta del proyecto, ejecutar:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Luego abrir la URL local que muestra Streamlit, normalmente:

```text
http://localhost:8501
```

## 3. Flujo recomendado de uso

### Paso 1 — Revisar los datos base

Entrar a la pestaña **Datos** y revisar que estén cargadas las 48 selecciones con estas columnas:

- `group`: grupo A-L;
- `position`: posición 1-4 dentro del fixture del grupo;
- `team`: nombre de la selección;
- `team_code`: código corto;
- `confederation`: confederación;
- `fifa_rank`: ranking FIFA;
- `fifa_points`: puntos FIFA o rating equivalente;
- `is_host`: 1 si es anfitrión, 0 en caso contrario.

Si se quiere usar una fuente propia de fuerza de equipo, se puede cargar otro CSV desde el panel lateral.

### Paso 2 — Configurar los parámetros

En el panel lateral izquierdo se pueden ajustar los parámetros del modelo:

#### Cantidad de simulaciones

Define cuántas veces se simula el torneo completo.

- 1.000 a 5.000 simulaciones: útil para pruebas rápidas.
- 10.000 a 50.000 simulaciones: útil para resultados más estables.

#### Seed

Permite reproducir exactamente el mismo resultado si se mantienen los mismos datos y parámetros.

#### Goles promedio base por equipo

Controla el nivel general de goles simulados por partido.

- Más bajo: partidos más cerrados.
- Más alto: partidos con más goles y más varianza.

#### Sensibilidad a diferencia de ranking

Controla cuánto pesa la diferencia de rating entre dos selecciones.

- Valor bajo: los favoritos tienen más ventaja.
- Valor alto: el torneo se vuelve más aleatorio.

#### Ventaja local

Suma puntos de rating a México, Estados Unidos y Canadá.

- Valor 0: sin ventaja local.
- Valor alto: mayor beneficio para anfitriones.

#### Aleatoriedad en alargue/penales

Controla cuánto pesa el rating en partidos empatados de eliminación directa.

- Valor bajo: el equipo más fuerte tiene más probabilidad de ganar penales/alargue.
- Valor alto: penales/alargue se acercan más a un evento aleatorio.

### Paso 3 — Ejecutar y leer resultados

La app corre la simulación automáticamente cada vez que cambian los datos o parámetros.

En la parte superior se muestran indicadores principales:

- favorito al título;
- equipo con mayor probabilidad de llegar a la final;
- cantidad de simulaciones ejecutadas;
- cantidad de equipos cargados.

## 4. Cómo interpretar cada pestaña

### Pestaña Título

Muestra el ranking de selecciones con mayor probabilidad de salir campeonas.

La tabla incluye también probabilidades acumuladas de llegar a rondas previas. Por ejemplo, si Argentina tiene 12% de campeón y 28% de final, significa que en el 28% de las simulaciones llegó a la final y en el 12% ganó el torneo.

### Pestaña Rondas

Permite elegir una instancia del torneo y ver los 20 equipos con mayor probabilidad de alcanzar esa ronda.

Sirve para analizar preguntas como:

- ¿qué equipos tienen más chances de llegar a semifinales?;
- ¿qué selecciones tienen alto piso pero baja chance de campeón?;
- ¿qué candidatos tienen un camino más favorable?

### Pestaña Grupos

Muestra la probabilidad de cada selección de terminar 1°, 2°, 3° o 4° en su grupo.

También muestra `p_top2`, que representa la probabilidad de clasificar directamente como primero o segundo.

Importante: terminar tercero no implica eliminación automática, porque clasifican los 8 mejores terceros.

### Pestaña Simulación ejemplo

Muestra una simulación individual completa con resultados partido por partido.

Esta pestaña sirve para auditar el comportamiento del motor, no para interpretar probabilidades. Una sola simulación es apenas un escenario posible entre miles.

### Pestaña Datos

Permite revisar y descargar el dataset utilizado por el modelo.

También se puede usar como plantilla para construir un archivo propio con ratings actualizados.

## 5. Cómo cargar datos propios

La opción más simple es descargar `teams_2026.csv`, modificar los valores de ranking o puntos y volver a cargarlo desde el panel lateral.

El archivo debe mantener las mismas columnas obligatorias:

```text
group,position,team,team_code,confederation,fifa_rank,fifa_points,is_host
```

Para mejorar el modelo, `fifa_points` puede reemplazarse por un rating propio. Por ejemplo:

```text
rating_final = 0.55 * puntos_fifa + 0.25 * elo + 0.15 * forma_reciente + 0.05 * valor_plantel
```

En ese caso, cargar ese rating en la columna `fifa_points` para reutilizar el motor sin modificar código.

## 6. Buenas prácticas de análisis

- Usar al menos 10.000 simulaciones para conclusiones finales.
- Comparar escenarios cambiando solo un parámetro por vez.
- Guardar la seed cuando se quiera reproducir un resultado.
- Actualizar el CSV si cambia el ranking FIFA, hay lesiones importantes o se quiere incorporar odds.
- No interpretar una única simulación como pronóstico final.

## 7. Limitaciones actuales

- El modelo usa un enfoque simplificado basado en rating y Poisson.
- No separa explícitamente fuerza ofensiva y defensiva.
- No incorpora lesiones, sede exacta, calendario de descanso ni odds de mercado.
- Los empates de grupo se resuelven con una simplificación de criterios FIFA.
- Los mejores terceros se asignan respetando elegibilidad de slots, pero puede reemplazarse por una matriz oficial completa si se desea máxima precisión normativa.

## 8. Próximas mejoras sugeridas

- Incorporar ELO internacional.
- Separar rating ofensivo y defensivo.
- Agregar odds de apuestas como calibración externa.
- Incorporar forma reciente de últimos partidos.
- Simular sede, viajes y descanso entre partidos.
- Guardar escenarios comparativos para análisis ejecutivo.
