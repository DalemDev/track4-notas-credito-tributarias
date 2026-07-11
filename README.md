# Track 4 — Asistente de Notas de Crédito Tributarias

Asistente inteligente para operadores que reciben e ingresan notas de crédito tributarias del SRI (Ecuador). Reutiliza antecedentes ya validados, extrae datos directamente de documentos cargados (PDF/imagen) con IA, detecta errores contra la fuente del SRI y guía los siguientes pasos hasta la negociación y el cierre — siempre con aprobación humana explícita.

Proyecto para el **Hackathon de Agentes Financieros IA — Track 4**.

## Índice

- [Problema que resuelve](#problema-que-resuelve)
- [Arquitectura](#arquitectura)
- [Funcionalidades por historia de usuario](#funcionalidades-por-historia-de-usuario)
- [Integración con Claude (Anthropic API)](#integración-con-claude-anthropic-api)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Cómo levantar el proyecto](#cómo-levantar-el-proyecto)
- [Flujo de demo sugerido](#flujo-de-demo-sugerido)
- [Limitaciones conocidas](#limitaciones-conocidas)

## Problema que resuelve

Los operadores que reciben notas de crédito tributarias del SRI reingresan manualmente datos que ya existen en casos anteriores, validan a mano contra fuentes externas y preparan la negociación sin un registro único del proceso. Este asistente:

- Extrae los campos de la nota directamente del documento cargado (sin OCR intermedio: Claude lee el PDF/imagen).
- Sugiere datos reutilizables de casos anteriores por RUC o número de título, con fecha, fuente y estado — el operador siempre confirma, edita o rechaza antes de guardar.
- Valida existencia, saldo, estado y bloqueos contra una fuente SRI simulada, y sugiere el siguiente paso (nunca lo ejecuta).
- Genera un borrador de ficha de negociación y deja liquidación/transferencia/endoso como propuesta pendiente de aprobación humana — ninguna acción regulada se ejecuta en producción.

## Arquitectura

```
┌─────────────────────┐        HTTP/JSON        ┌──────────────────────┐
│  Frontend (Streamlit)│ ───────────────────────▶│  Backend (FastAPI)   │
│  frontend/app.py      │◀─────────────────────── │  backend/main.py      │
└─────────────────────┘                          └──────────┬───────────┘
                                                              │
                                          ┌───────────────────┼───────────────────┐
                                          ▼                   ▼                   ▼
                                 Datos en memoria      CSV/JSON simulados   Anthropic API
                                 (data_store.py)        (backend/data/)      (Claude Sonnet 5)
```

- **Backend**: FastAPI, sin base de datos — el estado de cada caso (`expediente`) vive en memoria y se reinicia con el servidor.
- **Frontend**: Streamlit, una sola página con un stepper visual que refleja el estado real del backend.
- **IA**: SDK oficial `anthropic`, usado para leer documentos cargados (PDF/imagen) y extraer campos estructurados mediante *structured outputs* (JSON Schema), garantizando una respuesta siempre válida.

## Funcionalidades por historia de usuario

### HU1 — Ingreso asistido y reutilización de antecedentes
- Carga de documento (PDF, PNG, JPG, WEBP) → Claude extrae automáticamente titular, RUC, tipo de nota, valor nominal, saldo y número de título, sin pasos de OCR intermedios.
- El operador revisa y edita los campos extraídos antes de crear el caso — nada se guarda sin su confirmación.
- Búsqueda de antecedentes reutilizables por RUC o por coincidencia de número de título anterior, mostrando fecha, fuente y estado de cada dato.
- Cada dato sugerido se puede **confirmar**, **editar** o **rechazar** individualmente antes de guardarse en el expediente.

### HU2 — Validación y siguiente acción guiada
- Valida el caso contra una fuente SRI simulada (`estado_sri_simulado.csv`): existencia del título, bloqueos, inconsistencia de saldo, estado de vigencia.
- Detecta duplicados por número de título entre casos ya ingresados.
- Sugiere un siguiente paso (`enviar_a_cumplimiento`, `solicitar_revision_duplicado`, `actualizar_dato`, `solicitar_documento`, `continuar`) — siempre como sugerencia, nunca como ejecución automática.

### HU3 — Preparación de negociación y cierre asistido
- Genera un borrador de ficha de negociación con los datos confirmados del caso.
- El operador aprueba el borrador con su nombre y observaciones opcionales.
- Expediente único por caso con historial completo de eventos (ingreso, confirmaciones, validación, borrador, aprobación).
- La liquidación, transferencia y endoso quedan **siempre** como propuesta pendiente — el sistema nunca ejecuta acciones reguladas.

## Integración con Claude (Anthropic API)

- SDK oficial `anthropic` (no llamadas HTTP crudas), modelo `claude-sonnet-5`.
- El documento cargado (PDF o imagen) se envía directamente a Claude como bloque `document`/`image` en base64 — no hay paso de OCR separado.
- La respuesta se fuerza a un JSON Schema fijo vía `output_config` (*structured outputs*), lo que garantiza una respuesta siempre parseable en vez de depender de que el modelo "obedezca" una instrucción de texto.
- Manejo explícito de errores: clave no configurada, conexión fallida, límite de solicitudes, error de la API y rechazo del modelo (`stop_reason == "refusal"`).
- Requiere la variable de entorno `ANTHROPIC_API_KEY` (ver instrucciones en [`backend/README.md`](backend/README.md)).

## Estructura del proyecto

```
track4_proyecto/
├── backend/
│   ├── main.py              # Endpoints FastAPI (HU1, HU2, HU3)
│   ├── services.py          # Lógica de negocio + integración con Claude
│   ├── models.py            # Modelos Pydantic de request/response
│   ├── data_store.py        # Carga de datos simulados + expedientes en memoria
│   ├── data/                # CSV/JSON simulados (antecedentes, estado SRI)
│   ├── requirements.txt
│   └── README.md            # Instrucciones detalladas del backend
├── frontend/
│   ├── app.py                # UI Streamlit (stepper, creación de caso, HU1-HU3)
│   ├── .streamlit/config.toml # Tema claro forzado
│   ├── requirements.txt
│   └── README.md             # Instrucciones detalladas del frontend
├── nota_credito_prueba.png   # Imagen de prueba sintética para la extracción
├── nota_credito_prueba2.png  # Imagen de prueba real (nota de crédito SRI)
└── README.md                 # Este archivo
```

## Cómo levantar el proyecto

### 1. Backend

```bash
cd backend
pip install -r requirements.txt

# Configura tu API key de Anthropic (requerida para la extracción con IA)
export ANTHROPIC_API_KEY=tu_clave        # macOS/Linux
$env:ANTHROPIC_API_KEY = "tu_clave"      # Windows PowerShell

uvicorn main:app --reload
```
Backend disponible en `http://127.0.0.1:8000` (Swagger UI en `/docs`).

### 2. Frontend

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```
Frontend disponible en `http://localhost:8501`.

Más detalle en [`backend/README.md`](backend/README.md) y [`frontend/README.md`](frontend/README.md).

## Flujo de demo sugerido

1. Abre `http://localhost:8501` con el backend ya corriendo.
2. En **"Crear caso nuevo desde un documento"**, sube `nota_credito_prueba.png` (o `nota_credito_prueba2.png`) — los campos se extraen automáticamente al cargar el archivo.
3. Revisa/edita los campos extraídos y crea el caso.
4. **Paso 1**: revisa antecedentes reutilizables sugeridos (si el RUC o número de título coincide con algo previo) y confirma/edita/rechaza.
5. **Paso 2**: valida el caso contra el SRI simulado y observa las alertas y el siguiente paso sugerido.
6. **Paso 3**: genera el borrador de negociación y apruébalo con tu nombre.
7. Revisa el expediente único al final de la página, con el historial completo del caso.

## Limitaciones conocidas

- **Sin persistencia real**: los expedientes viven en memoria y se pierden al reiniciar el backend. Migrar a SQLite/Postgres sería el siguiente paso natural.
- **Fuente SRI simulada**: `estado_sri_simulado.csv` no conoce números de título fuera de su dataset — un caso nuevo casi siempre generará la alerta "no encontrado en la fuente SRI simulada", lo cual es esperado en esta demo.
- **Sin autenticación**: cualquiera que acceda a la API puede operar sobre cualquier caso — aceptable para el alcance de esta demo, no para producción.
