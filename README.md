# 📊 Sistema de Inteligencia Competitiva — Rappi Mexico

> Sistema automatizado de monitoreo competitivo de **precios, delivery fees, service fees, ETAs, promociones y disponibilidad** entre **Rappi**, **Uber Eats** y **DiDi Food** en México.

**Cadena ancla:** McDonald's
**Cobertura:** 24 direcciones en 3 ciudades y 5 tipos de zona
**Ciudades:** Ciudad de México, Guadalajara, Monterrey
**Salidas principales:** Dataset CSV + Reporte ejecutivo HTML + Dashboard Streamlit

---

## 🧭 Contexto del problema

Rappi opera en un mercado altamente dinámico donde **precios, fees, tiempos de entrega y promociones varían constantemente por plataforma y zona geográfica**. Este proyecto provee un **pipeline de inteligencia competitiva sistemático, reproducible y orientado al negocio** para comparar Rappi contra Uber Eats y DiDi Food usando productos estandarizados, direcciones representativas y análisis estructurado.

El sistema fue diseñado para apoyar a los equipos de **Pricing, Operations y Strategy** respondiendo preguntas clave de negocio:

| Pregunta de negocio | Cómo la responde el sistema |
|---|---|
| ¿Es Rappi más o menos caro que la competencia? | Comparación de precio de producto y total final por plataforma, ciudad y zona |
| ¿Los tiempos de entrega son competitivos? | Comparación de ETA por ciudad y tipo de zona |
| ¿Cómo difieren los fees? | Desglose de delivery fee y service fee por plataforma y geografía |
| ¿La competencia es más agresiva con promociones? | Análisis de visibilidad de descuentos y labels de promociones |
| ¿La competitividad varía por zona geográfica? | Segmentación por tipo de zona y análisis comparativo |

---

## 🎯 Alcance

Esta implementación prioriza intencionalmente **comparabilidad, reproducibilidad y robustez** sobre cobertura excesiva.

### Plataformas
- 🟠 Rappi
- 🟢 Uber Eats
- 🟡 DiDi Food

### 🍔 Cadena ancla
**McDonald's** — seleccionada por su amplia disponibilidad en las tres plataformas y un menú relativamente estandarizado que permite comparación directa a nivel de producto.

### 🛒 Productos monitoreados
- Big Mac
- McTrio Big Mac Mediano
- McNuggets 10 piezas
- Papas a la Francesa Medianas

Estos productos cubren una hamburguesa ancla, un combo, un producto por unidad y un acompañamiento de bajo precio.

### 🌎 Cobertura geográfica

| Ciudad | Direcciones | Justificación |
|---|---:|---|
| Ciudad de México | 12 | Mayor mercado y mayor densidad de delivery |
| Guadalajara | 6 | Gran mercado urbano con fuerte competencia entre plataformas |
| Monterrey | 6 | Mercado norte de alto valor con fuerte presencia de Uber Eats |

### 📍 Tipos de zona
Cada dirección está clasificada en uno de cinco tipos de zona:

- `premium`
- `residential_premium`
- `commercial`
- `residential_medium`
- `peripheral`

Esta segmentación permite identificar si la competitividad varía por contexto socioeconómico u operacional.

---

## 📋 Qué recolecta el sistema

Cada observación corresponde a **plataforma × dirección × producto**.

| Campo | Descripción |
|---|---|
| `platform` | Nombre de la plataforma de delivery |
| `city` | Ciudad de la dirección objetivo |
| `address_id` | Identificador único de la dirección |
| `zone_type` | Etiqueta del segmento geográfico |
| `product_name` | Nombre canónico del producto |
| `product_price` | Precio del producto mostrado en la plataforma |
| `delivery_fee` | Costo de envío mostrado por la plataforma |
| `service_fee` | Tarifa de servicio/plataforma, cuando es visible |
| `discount_visible` | Si hay una promoción visible |
| `discount_label` | Texto de la etiqueta de promoción |
| `eta_min / eta_max` | Rango de tiempo de entrega estimado (minutos) |
| `final_total` | Total estimado que paga el usuario |
| `store_available` | Si la tienda aparece disponible |
| `status` | `success`, `partial`, `not_found`, `blocked`, `timeout` |
| `screenshot_path` | Ruta a la evidencia en pantalla capturada |

**Salida principal:** `data/processed/competitive_prices_latest.csv`

---

## 🚀 Inicio rápido (ruta recomendada para evaluadores)

> **No se requiere scraping en vivo.**
> Se incluye un dataset demo realista para que el pipeline completo pueda evaluarse siempre, incluso sin acceso a internet o cuando las protecciones anti-bot de las plataformas bloquen la ejecución en vivo.

### 1️⃣ Generar el dataset demo
```bash
python analysis/generate_demo_data.py
```

### 2️⃣ Ejecutar el pipeline de análisis
```bash
python -m app.main --analyze
```

### 3️⃣ Abrir el reporte ejecutivo generado
```
reports/competitive_intelligence_report_latest.html
```

### 4️⃣ Lanzar el dashboard interactivo
```bash
streamlit run app/dashboard.py
```
Luego abrir: http://localhost:8501

---

## ⚙️ Configuración del entorno

**Requisitos:** Python 3.12, Playwright, Chromium (solo para scraping en vivo)

### Windows
```bat
cd competitive-intelligence-rappi
py -3.12 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

### macOS / Linux
```bash
cd competitive-intelligence-rappi
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

---

## 📦 Dependencias principales

El proyecto fue desarrollado y probado con **Python 3.12**.

```
playwright>=1.40.0,<2.0.0      # Scraping de sitios JS-heavy
greenlet>=3.0.0,<4.0.0         # Requerido por Playwright (wheel precompilado en 3.12)
numpy>=1.26.0,<2.0.0           # Procesamiento numérico
pandas>=2.0.0,<3.0.0           # Manipulación de datos
plotly>=5.18.0,<6.0.0          # Visualizaciones interactivas
streamlit>=1.32.0,<2.0.0       # Dashboard ejecutivo
altair>=5.0.0,<6.0.0           # Requerido por Streamlit >= 1.32
python-dotenv>=1.0.0,<2.0.0    # Variables de entorno
requests>=2.31.0,<3.0.0        # HTTP utilities
pytest>=8.0.0,<9.0.0           # Suite de pruebas
```

> Todas las versiones están fijadas en `requirements.txt` para garantizar reproducibilidad.

---

## 🔍 Scraping en vivo (opcional)

El scraping en vivo depende de acceso a internet y del comportamiento actual de la UI de cada plataforma. El dataset demo es el respaldo recomendado.

```bash
# Validar la configuración sin ejecutar scraping
python -m app.main --dry-run

# Pipeline completo: las 3 plataformas, las 24 direcciones
python -m app.main --platforms rappi uber didi

# Prueba rápida: 1 plataforma, 3 direcciones, con navegador visible
python -m app.main --platforms rappi --limit 3 --no-headless

# Re-ejecutar análisis sobre los datos más recientes recolectados
python -m app.main --analyze
```

---

## 🏗️ Arquitectura del proyecto

```
.
├── competitive-intelligence-rappi/
│   ├── app/
│   │   ├── main.py                 Orquestador del pipeline (punto de entrada CLI)
│   │   └── dashboard.py            Dashboard Streamlit ejecutivo (7 pestañas)
│   │
│   ├── scrapers/
│   │   ├── base_scraper.py         Base Playwright compartida: delays, retries, screenshots
│   │   ├── rappi_scraper.py        Implementación Rappi
│   │   ├── uber_scraper.py         Implementación Uber Eats
│   │   ├── didi_scraper.py         Implementación DiDi Food
│   │   ├── config.py               Todas las constantes y configuraciones
│   │   └── models.py               PriceObservation, StoreInfo, ScrapeSession
│   │
│   ├── analysis/
│   │   ├── generate_demo_data.py   Dataset sintético realista (respaldo para demo)
│   │   ├── normalize.py            Limpieza y normalización de datos
│   │   ├── insights.py             Top 5 insights competitivos (basados en datos)
│   │   ├── charts.py               Funciones Plotly reutilizables
│   │   └── report_generator.py     Generador de reporte HTML ejecutivo
│   │
│   ├── data/
│   │   ├── input/
│   │   │   ├── addresses.csv       24 direcciones representativas en México
│   │   │   └── product_map.json    Mapeo canónico de nombres de producto
│   │   ├── processed/              Datasets CSV de salida
│   │   └── screenshots/            Evidencia PNG capturada durante scraping en vivo
│   │
│   ├── reports/                    Reportes HTML ejecutivos
│   ├── tests/
│   │   └── test_pipeline.py        Suite de pruebas completa
│   │
│   └── requirements.txt            Dependencias del proyecto
│
├── README.md
├── competitive_intelligence_report_latest.html
└── competitive_prices_demo.csv
```

---

## 🔄 Diseño del pipeline

La solución está organizada en cuatro capas:

### 1. 🕸️ Capa de scraping

Cada plataforma tiene su propio scraper (`rappi_scraper.py`, `uber_scraper.py`, `didi_scraper.py`) que hereda de `base_scraper.py`, el cual provee:

- inicialización y gestión del ciclo de vida del navegador
- delays aleatorios (rate limiting ético)
- lógica de reintentos con backoff exponencial
- captura de screenshots como evidencia
- utilidades de parsing de precios y ETAs
- logging estructurado de ejecución

### 2. 🗂️ Capa de modelo de datos

Las observaciones estructuradas se representan mediante el dataclass tipado `PriceObservation`, lo que facilita la validación, serialización y normalización aguas abajo.

### 3. 📐 Capa de análisis

El pipeline de análisis:

- carga y limpia las observaciones crudas
- estandariza campos numéricos
- calcula métricas derivadas (total efectivo, midpoint de ETA, delta de precio vs Rappi)
- compara competidores contra el baseline de Rappi
- genera insights de negocio automáticamente

### 4. 📺 Capa de presentación

- **Reporte HTML ejecutivo** autónomo para compartir con stakeholders
- **Dashboard Streamlit** con 7 pestañas para exploración interactiva

---

## 🛡️ Resiliencia y manejo de errores

Diseñado para ser robusto bajo las restricciones reales del scraping web.

| Mecanismo | Propósito |
|---|---|
| Delays aleatorios | Rate limiting ético, reduce el riesgo de detección |
| Reintentos con backoff | Maneja fallas transitorias sin interrumpir el pipeline |
| Selectores centralizados | Un único punto de actualización cuando la UI de la plataforma cambia |
| Evidencia en screenshots | Trazabilidad para cada observación exitosa |
| Manejo de observaciones parciales | El pipeline continúa aunque una dirección o plataforma falle |
| Respaldo con dataset demo | Evaluación completa posible sin scraping en vivo |

### Códigos de estado del scraping
- `success` — observación completa capturada
- `partial` — algunos campos capturados, otros faltantes
- `not_found` — la cadena o tienda no está disponible en esa dirección
- `blocked` — la plataforma aplicó protección anti-bot
- `timeout` — la página no cargó dentro del tiempo configurado

---

## 💡 Insights competitivos

La capa de análisis genera automáticamente **Top 5 insights de negocio**, cada uno con:

- **Hallazgo** — qué se descubrió en los datos
- **Impacto** — por qué es relevante para el negocio
- **Recomendación** — qué debería considerar hacer Rappi

Categorías de insights:

1. Posicionamiento de precios vs competidores
2. Competitividad del delivery fee en zonas periféricas
3. Diferencias en la estructura de service fee
4. Visibilidad de promociones y estrategia de descuentos
5. Variabilidad geográfica de competitividad

---

## 📁 Archivos de salida

| Archivo | Descripción |
|---|---|
| `data/processed/competitive_prices_latest.csv` | Dataset procesado más reciente |
| `data/processed/competitive_prices_demo.csv` | Dataset de respaldo para demo |
| `reports/competitive_intelligence_report_latest.html` | Reporte HTML ejecutivo |
| `data/screenshots/*.png` | Evidencia visual del scraping en vivo |
| `logs/main_*.log` | Logs de ejecución del pipeline |

---

## 🧪 Ejecución de pruebas

```bash
pytest tests/ -v
```

La suite cubre: utilidades de parsing, modelos de datos, generación del dataset demo, lógica de normalización, generación de insights, generación del reporte y consistencia del pipeline.

---

## ⚖️ Consideraciones éticas y prácticas

Este proyecto fue construido como prototipo de evaluación técnica, no como sistema de monitoreo en producción.

**Principios aplicados:**
- Baja frecuencia de scraping con delays aleatorios
- Sin recolección de datos personales
- Sin evasión de autenticación
- Solo información públicamente visible en las plataformas
- Separación clara entre uso de prototipo y despliegue en producción

> En un entorno de producción real, se requeriría revisión legal, gobernanza de proxies, revisión de políticas de plataformas y monitoreo operacional antes del despliegue.

---

## ⚠️ Limitaciones conocidas

| Limitación | Mitigación actual | Mejora futura |
|---|---|---|
| El scraping puede romperse si cambian los selectores | Config centralizada y scrapers modulares | Monitoreo automatizado de salud de selectores |
| Las plataformas pueden aplicar protecciones anti-bot | Reintentos + dataset demo de respaldo | Rotación de proxies administrados (si es legalmente aprobado) |
| Vertical única (fast food) | McDonald's garantiza comparabilidad y consistencia | Expandir a retail, farmacias y otras cadenas |
| Análisis basado en snapshots | Diseño reproducible de una sola ejecución | Recolección programada y recurrente |
| El total final no siempre es completamente visible | Manejo de observaciones parciales | Flujos más profundos a nivel de carrito donde sea viable |

---

## 💰 Estimación de costos

| Componente | Costo |
|---|---|
| Python / pandas / NumPy | $0 |
| Playwright | $0 |
| Streamlit | $0 |
| Modo demo | $0 |
| Capa de proxies para producción (opcional) | Variable |

---

## 🛠️ Stack tecnológico

**Python 3.12** | Playwright | pandas | NumPy | Streamlit | Plotly

---
