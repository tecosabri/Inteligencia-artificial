# Práctica Data WareHouse & SQL — Resolución

---

## Enunciado 1: exploración del fichero flights

### 1.1) Cuántos registros hay en total

```sql
SELECT COUNT(*) AS total_registros
FROM flights;
```

**Resultado:** 1209 registros.

### 1.2) Cuántos vuelos distintos hay

```sql
SELECT COUNT(DISTINCT unique_identifier) AS vuelos_distintos
FROM flights;
```

**Resultado:** 266 vuelos distintos.

### 1.3) Cuántos vuelos tienen más de un registro

```sql
SELECT COUNT(*) AS vuelos_con_duplicados
FROM (
    SELECT unique_identifier
    FROM flights
    GROUP BY unique_identifier
    HAVING COUNT(*) > 1
) sub;
```

**Resultado:** 250 vuelos tienen más de un registro.

**Interpretación:** de los 266 vuelos, 250 (94%) aparecen más de una vez. Solo 16 vuelos tienen un único registro. Esto indica que el dataset almacena múltiples snapshots (capturas temporales) del estado de cada vuelo a lo largo del tiempo, no duplicados erróneos.

---

## Enunciado 2: ¿Por qué hay registros duplicados?

Para entender la evolución temporal, seleccionamos varios vuelos y ordenamos sus registros por `updated_at`:

```sql
SELECT flight_row_id,
       unique_identifier,
       local_actual_departure,
       local_actual_arrival,
       delay_mins,
       arrival_status,
       updated_at
FROM flights
WHERE unique_identifier IN (
    'IB-100-20240124-MAD-JFK',
    'AA-102-20241001-JFK-MAD',
    'KL-106-20240218-AMS-BCN'
)
ORDER BY unique_identifier, updated_at;
```

**Resultado (ejemplo del vuelo AA-102):**

| updated_at | actual_departure | actual_arrival | delay_mins | status |
|---|---|---|---|---|
| 2024-09-30 11:00:00 | NULL | NULL | NULL | DY |
| 2024-09-30 17:00:00 | NULL | NULL | NULL | DY |
| 2024-09-30 23:00:00 | NULL | NULL | NULL | DY |
| 2024-10-01 05:00:00 | 2024-10-01 11:45:00 | 2024-10-02 05:40:00 | 40 | DY |

### 2.1) Qué información cambia de un registro a otro

Lo que cambia entre registros es:

- **`updated_at`**: cada snapshot tiene un timestamp de actualización diferente. Es el campo que marca la evolución temporal.
- **`local_actual_departure` / `local_actual_arrival`**: inicialmente son NULL (el vuelo aún no ha operado) y se rellenan en el último snapshot cuando el vuelo despega/aterriza.
- **`delay_mins`**: se calcula cuando el vuelo aterriza realmente. Antes es NULL.
- Los campos programados (`local_departure`, `local_arrival`, `departure_airport`, `arrival_airport`, `airline_code`, `arrival_status`, `created_at`) permanecen constantes.

**Conclusión:** el dataset funciona como un sistema de snapshots en eñ que cada registro es una foto del estado del vuelo en un momento dado. El último registro (mayor `updated_at`) contiene la información definitiva.

---

## Enunciado 3: calidad del dato

### 3.1) created_at debe ser único por vuelo

```sql
SELECT unique_identifier,
       COUNT(DISTINCT created_at) AS num_created_distintos
FROM flights
GROUP BY unique_identifier
HAVING COUNT(DISTINCT created_at) > 1;
```

**Resultado:** 0 filas. Todos los vuelos tienen un único valor de `created_at` en todos sus registros. 

**Criterio cumplido.**

### 3.2) updated_at >= created_at

```sql
SELECT COUNT(*) AS registros_inconsistentes
FROM flights
WHERE updated_at < created_at;
```

**Resultado:** 0 registros donde `updated_at < created_at`. 

**Criterio cumplido.** Los datos son coherentes y consistentes: las actualizaciones siempre ocurren después (o en el mismo momento) de la creación del registro.

---

## Enunciado 4: Último estado de cada vuelo

Cada vuelo puede tener múltiples snapshots. Para quedarnos solo con el último (el más reciente), usamos `ROW_NUMBER()` particionando por vuelo y ordenando por `updated_at` descendente:

```sql
CREATE VIEW v_last_flight AS
SELECT *
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY unique_identifier
               ORDER BY updated_at DESC, flight_row_id DESC
           ) AS rn
    FROM flights
) ranked
WHERE rn = 1;
```

Usamos `ROW_NUMBER()` porque si dos registros del mismo vuelo tuvieran el mismo `updated_at`, el JOIN con `MAX` devolvería ambos duplicando filas. Con `ROW_NUMBER()`, siempre obtenemos exactamente un registro por vuelo, desempatando por `flight_row_id DESC`.

**Verificación:**

```sql
SELECT COUNT(*) FROM v_last_flight;
-- Resultado: 266 (un registro por vuelo)
```

---

## Enunciado 5: validar y reconstruir campos de departure/arrival

Los campos `local_departure` y `local_actual_departure` pueden tener nulos. Aplicamos las reglas de sustitución con `COALESCE`:

```sql
SELECT *,
    -- Si local_departure es nulo, usar created_at
    COALESCE(local_departure, created_at) AS effective_local_departure,

    -- Si local_actual_departure es nulo, usar local_departure.
    -- Si local_departure también es nulo, usar created_at
    COALESCE(local_actual_departure, local_departure, created_at)
        AS effective_local_actual_departure,

    -- EXTRA: misma lógica para arrival
    COALESCE(local_arrival, created_at) AS effective_local_arrival,
    COALESCE(local_actual_arrival, local_arrival, created_at)
        AS effective_local_actual_arrival

FROM v_last_flight;
```

**Explicación de `COALESCE`:** esta función devuelve el primer valor no nulo de la lista de argumentos. Así, `COALESCE(A, B, C)` devuelve A si no es NULL, pero si A es NULL, devuelve B. Si ambos son NULL, devuelve C.

**Resultados de nulos (antes de aplicar COALESCE):**

| Campo | Nulos |
|---|---|
| local_departure | 10 |
| local_actual_departure | 49 |
| local_arrival | 0 |
| local_actual_arrival | 56 |

Tras aplicar COALESCE, los campos `effective_*` tienen 0 nulos.

---

## Enunciado 6: análisis del estado del vuelo

### 6.1) Qué estados de vuelo existen

```sql
SELECT DISTINCT arrival_status
FROM v_last_flight
ORDER BY arrival_status;
```

**Resultado:** Los estados son: `CX`, `DY`, `EY`, `NS`, `OT` y `NULL`.

### 6.2) Cuántos vuelos hay por cada estado

```sql
SELECT arrival_status,
       COUNT(*) AS num_vuelos
FROM v_last_flight
GROUP BY arrival_status
ORDER BY num_vuelos DESC;
```

| Estado | Vuelos | Significado |
|---|---|---|
| DY | 143 | **Delayed** — Retrasado |
| OT | 95 | **On Time** — A tiempo |
| NULL | 11 | Sin estado asignado |
| EY | 9 | **Early** — Llegó antes de lo previsto |
| CX | 5 | **Cancelled** — Cancelado |
| NS | 3 | **No Show / Not Started** — No operado |

**Interpretación:** La mayoría de los vuelos (54%) sufrieron retraso (DY), mientras que un 36% llegó a tiempo (OT). Solo un 2% fue cancelado.

---

## Enunciado 7: país de salida de cada vuelo

### 7.1) De qué país despegan los vuelos

```sql
SELECT DISTINCT a.country
FROM v_last_flight f
LEFT JOIN airports a ON f.departure_airport = a.airport_code
ORDER BY a.country;
```

**Resultado:** France, Germany, Italy, Netherlands, Spain, United Kingdom, United States, y algunos vuelos desde aeropuertos no presentes en la tabla airports (NULL).

### 7.2) Cuántos vuelos despegan por país

```sql
SELECT COALESCE(a.country, 'Desconocido') AS pais_salida,
       COUNT(*) AS num_vuelos
FROM v_last_flight f
LEFT JOIN airports a ON f.departure_airport = a.airport_code
GROUP BY a.country
ORDER BY num_vuelos DESC;
```

| País | Vuelos |
|---|---|
| Spain | 131 |
| Desconocido | 43 |
| France | 27 |
| United States | 26 |
| Netherlands | 19 |
| United Kingdom | 18 |
| Italy | 1 |
| Germany | 1 |

Hay 43 vuelos cuyo aeropuerto de salida no está en la tabla airports (EZE, CPH, DUB, PMI, AGP, etc.). Usamos `LEFT JOIN` para no perder estos vuelos y `COALESCE` para etiquetar el país como 'Desconocido', aunque en el resultado parece que no afecta.

---

## Enunciado 8: delay medio y estado por país de salida

### 8.1) Delay medio por país

```sql
SELECT COALESCE(a.country, 'Desconocido') AS pais_salida,
       ROUND(AVG(f.delay_mins), 2) AS delay_medio,
       COUNT(*) AS num_vuelos
FROM v_last_flight f
LEFT JOIN airports a ON f.departure_airport = a.airport_code
GROUP BY a.country
ORDER BY delay_medio DESC;
```

| País | Delay medio (min) | Vuelos |
|---|---|---|
| United States | 12.71 | 26 |
| France | 9.23 | 27 |
| Spain | 8.54 | 131 |
| Desconocido | 5.82 | 43 |
| United Kingdom | 2.82 | 18 |
| Netherlands | -1.18 | 19 |
| Italy | -5.00 | 1 |

**Interpretación:** Estados Unidos y Francia presentan los mayores retrasos medios (~13 y ~9 min), mientras que Países Bajos e Italia tienen delay negativo, lo que significa que los vuelos tienden a llegar antes de lo previsto.

### 8.2) Distribución de estados por país

```sql
SELECT COALESCE(a.country, 'Desconocido') AS pais_salida,
       f.arrival_status,
       COUNT(*) AS num_vuelos
FROM v_last_flight f
LEFT JOIN airports a ON f.departure_airport = a.airport_code
GROUP BY a.country, f.arrival_status
ORDER BY pais_salida, num_vuelos DESC;
```

| País | Estado | Vuelos |
|---|---|---|
| Spain | DY | 67 |
| Spain | OT | 57 |
| France | DY | 23 |
| France | OT | 3 |
| United States | DY | 17 |
| United States | OT | 8 |
| United Kingdom | DY | 11 |
| United Kingdom | OT | 7 |
| Netherlands | OT | 9 |
| Netherlands | DY | 9 |

**Interpretación:** Francia tiene una proporción muy alta de retrasos (85% DY), mientras que Países Bajos es el más equilibrado (50/50). España, pese a ser el país con más vuelos, mantiene una distribución más repartida.

---

## Enunciado 9: Estado de vuelo por país y época del año

```sql
SELECT COALESCE(a.country, 'Desconocido') AS pais_salida,
       CASE
           WHEN EXTRACT(MONTH FROM f.local_departure) IN (12, 1, 2)  THEN 'Invierno'
           WHEN EXTRACT(MONTH FROM f.local_departure) IN (3, 4, 5)   THEN 'Primavera'
           WHEN EXTRACT(MONTH FROM f.local_departure) IN (6, 7, 8)   THEN 'Verano'
           WHEN EXTRACT(MONTH FROM f.local_departure) IN (9, 10, 11) THEN 'Otoño'
       END AS estacion,
       ROUND(AVG(f.delay_mins), 2) AS delay_medio,
       COUNT(*) AS num_vuelos
FROM v_last_flight f
LEFT JOIN airports a ON f.departure_airport = a.airport_code
WHERE f.local_departure IS NOT NULL
GROUP BY a.country,
         CASE
             WHEN EXTRACT(MONTH FROM f.local_departure) IN (12, 1, 2)  THEN 'Invierno'
             WHEN EXTRACT(MONTH FROM f.local_departure) IN (3, 4, 5)   THEN 'Primavera'
             WHEN EXTRACT(MONTH FROM f.local_departure) IN (6, 7, 8)   THEN 'Verano'
             WHEN EXTRACT(MONTH FROM f.local_departure) IN (9, 10, 11) THEN 'Otoño'
         END
ORDER BY pais_salida,
         CASE estacion
             WHEN 'Invierno'  THEN 1
             WHEN 'Primavera' THEN 2
             WHEN 'Verano'    THEN 3
             WHEN 'Otoño'     THEN 4
         END;
```

**Resultados destacados:**

| País | Estación | Delay medio | Vuelos |
|---|---|---|---|
| Spain | Invierno | 3.96 | 34 |
| Spain | Primavera | 9.62 | 28 |
| Spain | Verano | 13.13 | 28 |
| Spain | Otoño | 7.59 | 31 |
| United States | Otoño | 23.13 | 10 |
| United States | Invierno | 10.00 | 7 |
| France | Verano | 11.88 | 8 |
| Netherlands | Verano | -2.50 | 6 |

**Interpretación:** En España, el verano es la estación con mayor retraso medio (13 min), en Estados Unidos, el otoño presenta retrasos muy altos (23 min) y Países Bajos destaca por tener delay negativo incluso en verano.

---

## Enunciado 10: frecuencia de actualización de los vuelos

### Número medio de snapshots por aeropuerto de salida

```sql
SELECT departure_airport,
       ROUND(AVG(num_updates), 2) AS media_snapshots,
       COUNT(*) AS num_vuelos
FROM (
    SELECT unique_identifier,
           departure_airport,
           COUNT(*) AS num_updates
    FROM flights
    GROUP BY unique_identifier, departure_airport
) sub
GROUP BY departure_airport
ORDER BY media_snapshots DESC;
```

### Tiempo medio entre actualizaciones por aeropuerto

```sql
WITH ordered_flights AS (
    SELECT unique_identifier,
           departure_airport,
           updated_at,
           LAG(updated_at) OVER (
               PARTITION BY unique_identifier
               ORDER BY updated_at
           ) AS prev_updated
    FROM flights
),
diffs AS (
    SELECT unique_identifier,
           departure_airport,
           EXTRACT(EPOCH FROM (updated_at - prev_updated)) / 3600.0 AS hours_between
    FROM ordered_flights
    WHERE prev_updated IS NOT NULL
)
SELECT departure_airport,
       ROUND(AVG(hours_between)::NUMERIC, 2) AS horas_entre_updates,
       COUNT(DISTINCT unique_identifier) AS num_vuelos
FROM diffs
GROUP BY departure_airport
ORDER BY horas_entre_updates DESC;
```

**Resultado:** los principales aeropuertos (MAD, BCN, JFK, LHR, CDG, AMS, EZE) tienen una frecuencia media de actualización de **6 horas** entre snapshots. La función `LAG()` nos permite acceder al valor del registro anterior dentro de la misma partición (mismo vuelo), para calcular la diferencia temporal.

---

## Enunciado 11: Consistencia del unique_identifier

El `unique_identifier` tiene formato: `aerolínea-número-YYYYMMDD-salida-llegada`. Debemos verificar que las partes coinciden con las columnas del dataset.

### 11.1) Crear flag is_consistent

```sql
WITH last_flights AS (
    SELECT *
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY unique_identifier
                   ORDER BY updated_at DESC, flight_row_id DESC
               ) AS rn
        FROM flights
    ) ranked
    WHERE rn = 1
),
parsed AS (
    SELECT *,
           SPLIT_PART(unique_identifier, '-', 1) AS uid_airline,
           SPLIT_PART(unique_identifier, '-', 3) AS uid_date,
           SPLIT_PART(unique_identifier, '-', 4) AS uid_dep,
           SPLIT_PART(unique_identifier, '-', 5) AS uid_arr
    FROM last_flights
)
SELECT *,
       CASE
           WHEN TRIM(airline_code) = uid_airline
                AND TRIM(departure_airport) = uid_dep
                AND TRIM(arrival_airport) = uid_arr
                AND TO_CHAR(local_departure, 'YYYYMMDD') = uid_date
           THEN TRUE
           ELSE FALSE
       END AS is_consistent
FROM parsed;
```

### 11.2) Cuántos vuelos no son consistentes

```sql
-- (Usando la CTE anterior)
SELECT
    SUM(CASE WHEN is_consistent THEN 0 ELSE 1 END) AS vuelos_inconsistentes,
    COUNT(*) AS total_vuelos
FROM (
    -- query anterior que genera is_consistent
) check_result;
```

**Resultado:** 15 vuelos no son consistentes (de 266 totales).

### 11.3) Aerolínea y número de vuelos inconsistentes

```sql
WITH last_flights AS (
    SELECT *
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY unique_identifier
                   ORDER BY updated_at DESC, flight_row_id DESC
               ) AS rn
        FROM flights
    ) ranked
    WHERE rn = 1
),
parsed AS (
    SELECT *,
           SPLIT_PART(unique_identifier, '-', 1) AS uid_airline,
           SPLIT_PART(unique_identifier, '-', 3) AS uid_date,
           SPLIT_PART(unique_identifier, '-', 4) AS uid_dep,
           SPLIT_PART(unique_identifier, '-', 5) AS uid_arr
    FROM last_flights
),
consistency_check AS (
    SELECT *,
           CASE
               WHEN TRIM(airline_code) = uid_airline
                    AND TRIM(departure_airport) = uid_dep
                    AND TRIM(arrival_airport) = uid_arr
                    AND TO_CHAR(local_departure, 'YYYYMMDD') = uid_date
               THEN TRUE
               ELSE FALSE
           END AS is_consistent
    FROM parsed
)
SELECT al.name AS airline_name,
       cc.airline_code,
       COUNT(*) AS vuelos_inconsistentes
FROM consistency_check cc
JOIN airlines al ON TRIM(cc.airline_code) = al.airline_code
WHERE NOT cc.is_consistent
GROUP BY al.name, cc.airline_code
ORDER BY vuelos_inconsistentes DESC;
```

| Aerolínea | Código | Vuelos inconsistentes |
|---|---|---|
| British Airways | BA | 5 |
| Iberia | IB | 5 |
| Vueling | VY | 5 |

**Interpretación:** los 15 vuelos inconsistentes se reparten equitativamente entre 3 aerolíneas (5 cada una). Al analizar los casos concretos, se observan discrepancias significativas porque en algunos vuelos el `unique_identifier` dice BA (British Airways) pero la columna `airline_code` contiene IB (Iberia), o el aeropuerto de salida en el identificador no coincide con `departure_airport`. En este caso no estoy seguro de si la query ha dado el resultado que esperaba.

---
