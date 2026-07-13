# Track 4 — Asistente de Notas de Crédito Tributarias

Asistente inteligente para operadores que reciben e ingresan notas de crédito tributarias del SRI (Ecuador). Reutiliza antecedentes ya validados, extrae datos directamente de documentos cargados (PDF/imagen) con IA, detecta errores contra la fuente del SRI y guía los siguientes pasos hasta la negociación y el cierre — siempre con aprobación humana explícita.

Proyecto para el **Hackathon de Agentes Financieros IA — Track 4**.

## Índice

- [Track 4 — Asistente de Notas de Crédito Tributarias](#track-4--asistente-de-notas-de-crédito-tributarias)
  - [Índice](#índice)
  - [Problema que resuelve](#problema-que-resuelve)
  - [Arquitectura](#arquitectura)
  - [Funcionalidades por historia de usuario](#funcionalidades-por-historia-de-usuario)
    - [HU1 — Ingreso asistido y reutilización de antecedentes](#hu1--ingreso-asistido-y-reutilización-de-antecedentes)
    - [HU2 — Validación y siguiente acción guiada](#hu2--validación-y-siguiente-acción-guiada)
    - [HU3 — Preparación de negociación y cierre asistido](#hu3--preparación-de-negociación-y-cierre-asistido)
  - [Integración con Claude (Anthropic API)](#integración-con-claude-anthropic-api)
  - [Coincidencias aproximadas (RAG con guardrails)](#coincidencias-aproximadas-rag-con-guardrails)
  - [Persistencia](#persistencia)
  - [Pruebas automatizadas](#pruebas-automatizadas)
  - [Estructura del proyecto](#estructura-del-proyecto)
  - [Cómo levantar el proyecto](#cómo-levantar-el-proyecto)
    - [1. Backend](#1-backend)
    - [2. Frontend](#2-frontend)
  - [Flujo de demo sugerido](#flujo-de-demo-sugerido)

## Problema que resuelve

Los operadores que reciben notas de crédito tributarias del SRI reingresan manualmente datos que ya existen en casos anteriores, validan a mano contra fuentes externas y preparan la negociación sin un registro único del proceso. Este asistente:

- Extrae los campos de la nota directamente del documento cargado (sin OCR intermedio: Claude lee el PDF/imagen).
- Sugiere datos reutilizables de casos anteriores por RUC, número de título, o **coincidencia aproximada de nombre** (RAG), con fecha, fuente y estado — el operador siempre confirma, edita o rechaza antes de guardar.
- Valida existencia, saldo, estado y bloqueos contra una fuente SRI simulada, y sugiere el siguiente paso (nunca lo ejecuta).
- Genera un borrador de ficha de negociación y deja liquidación/transferencia/endoso como propuesta pendiente de aprobación humana — ninguna acción regulada se ejecuta en producción.

## Arquitectura

```
┌──────────────────────┐        HTTP/JSON        ┌───────────────────────┐
│  Frontend (Streamlit) │ ───────────────────────▶│   Backend (FastAPI)   │
│  frontend/app.py      │◀─────────────────────── │   backend/main.py     │
└──────────────────────┘                          └───────────┬───────────┘
                                                                │
                                    ┌───────────────────────────┼───────────────────────────┐
                                    ▼                            ▼                            ▼
                          SQLite (SQLAlchemy)             CSV simulado                  Anthropic API
                          casos + expedientes +          (solo lectura)                (Claude Sonnet 5)
                          antecedentes, persistentes    estado_sri_simulado.csv          extracción de
                          entre reinicios y canales      — única fuente externa          documentos +
                          (database.py, db_models.py)    real (el SRI)                  RAG con guardrails
```

- **Backend**: FastAPI expuesto como servicio REST con endpoints claros y documentados (Swagger en `/docs`), independiente del canal que lo consuma.
- **Persistencia**: SQLite vía SQLAlchemy — casos, expedientes (con historial con timestamp) y **antecedentes** sobreviven a reinicios del servidor y son consistentes sin importar el canal (hoy Streamlit; cualquier otro cliente de la misma API mañana). Solo `estado_sri_simulado.csv` se mantiene como dato externo de solo lectura (representa al SRI, un sistema fuera de esta aplicación) — los antecedentes históricos son propiedad de la organización, así que viven en la base de datos.
- **Frontend**: Streamlit, una sola página con un stepper visual que refleja el estado real del backend.
- **IA**: SDK oficial `anthropic`. Dos usos concretos, ambos con guardrails explícitos contra alucinación — ver [Integración con Claude](#integración-con-claude-anthropic-api) y [RAG](#coincidencias-aproximadas-rag-con-guardrails).
- **Calidad**: suite de pruebas automatizadas con `pytest` sobre una base de datos aislada (ver [Pruebas automatizadas](#pruebas-automatizadas)).

## Funcionalidades por historia de usuario

### HU1 — Ingreso asistido y reutilización de antecedentes
- Carga de documento (PDF, PNG, JPG, WEBP) → Claude extrae automáticamente titular, RUC, tipo de nota, valor nominal, saldo y número de título, sin pasos de OCR intermedios.
- El operador revisa y edita los campos extraídos antes de crear el caso — nada se guarda sin su confirmación.
- Búsqueda de antecedentes reutilizables por RUC, por coincidencia de número de título anterior, y por **coincidencia aproximada de nombre de titular** (RAG con guardrails), mostrando fecha, fuente y estado de cada dato.
- Cada dato sugerido se puede **confirmar**, **editar** o **rechazar** individualmente antes de guardarse en el expediente.

### HU2 — Validación y siguiente acción guiada
- Valida el caso contra una fuente SRI simulada (`estado_sri_simulado.csv`): existencia del título, bloqueos, inconsistencia de saldo, estado de vigencia.
- Detecta duplicados por número de título entre casos ya ingresados.
- Sugiere un siguiente paso (`enviar_a_cumplimiento`, `solicitar_revision_duplicado`, `actualizar_dato`, `solicitar_documento`, `continuar`) — siempre como sugerencia, nunca como ejecución automática.

### HU3 — Preparación de negociación y cierre asistido
- Genera un borrador de ficha de negociación con los datos confirmados del caso.
- El operador aprueba el borrador con su nombre y observaciones opcionales.
- Expediente único por caso con historial completo de eventos, cada uno con marca de tiempo real (ingreso, confirmaciones, validación, borrador, aprobación).
- La liquidación, transferencia y endoso quedan **siempre** como propuesta pendiente — el sistema nunca ejecuta acciones reguladas.

## Integración con Claude (Anthropic API)

- SDK oficial `anthropic` (no llamadas HTTP crudas), modelo `claude-sonnet-5`.
- El documento cargado (PDF o imagen) se envía directamente a Claude como bloque `document`/`image` en base64 — no hay paso de OCR separado.
- La respuesta se fuerza a un JSON Schema fijo vía `output_config` (*structured outputs*), lo que garantiza una respuesta siempre parseable en vez de depender de que el modelo "obedezca" una instrucción de texto — este es el primer guardrail anti-alucinación del sistema.
- Manejo explícito de errores: clave no configurada, conexión fallida, límite de solicitudes, error de la API y rechazo del modelo (`stop_reason == "refusal"`).
- Requiere la variable de entorno `ANTHROPIC_API_KEY` (ver instrucciones en [`backend/README.md`](backend/README.md)).

## Coincidencias aproximadas (RAG con guardrails)

Para la "coincidencia relevante" que pide HU1 (más allá del match exacto de RUC/título), el sistema implementa un patrón RAG deliberadamente simple y verificable:

1. **Retrieval** (determinista, sin LLM): `rapidfuzz` compara el nombre del titular del caso nuevo contra todos los antecedentes históricos y preselecciona los que superan un umbral de similitud — esto nunca alucina porque es comparación de texto, no generación.
2. **Generation**: solo esos candidatos recuperados se le pasan a Claude, que juzga con *structured outputs* cuáles son realmente relevantes (variación de razón social, error de tipeo) y por qué.
3. **Guardrail**: Claude solo puede referirse a un candidato por su **índice** dentro de la lista ya recuperada — nunca por texto libre. Si el modelo "inventa" un índice fuera de rango, el backend lo descarta sin excepción. Este comportamiento está cubierto por pruebas automatizadas que simulan exactamente ese intento de alucinación (`backend/tests/test_rag_coincidencias.py`).

Sin candidatos recuperados, o sin `ANTHROPIC_API_KEY`, el sistema simplemente no muestra coincidencias aproximadas — las exactas (100% deterministas) se siguen mostrando de todas formas. El frontend distingue visualmente ambos tipos de coincidencia.

## Persistencia

Casos, expedientes y **antecedentes históricos** viven en **SQLite vía SQLAlchemy**, no en memoria — sobreviven a reinicios del servidor y son consistentes para cualquier canal que consuma esta misma API (hoy el frontend Streamlit; cualquier otro cliente HTTP mañana vería el mismo estado). El historial de cada expediente queda registrado con marca de tiempo real por evento, no solo en memoria de proceso.

Solo `estado_sri_simulado.csv` sigue siendo un archivo de solo lectura — representa una fuente externa (el SRI), no algo que la aplicación posea. `antecedentes_historicos.csv`, en cambio, ya no se lee en tiempo de ejecución: es el propio historial de la organización, así que se migra a la base de datos una única vez al arrancar por primera vez (semilla inicial); de ahí en adelante, la base de datos es la única fuente de verdad. Detalle técnico en [`backend/README.md`](backend/README.md#persistencia).

## Pruebas automatizadas

Suite de `pytest` sobre una base de datos SQLite temporal y aislada (nunca la de desarrollo). Cubre creación de casos, antecedentes (exactos y el guardrail del RAG con un caso que simula una alucinación deliberada), las 5 reglas de validación de HU2, el flujo end-to-end HU1→HU2→HU3, y el manejo de errores de extracción:

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

## Estructura del proyecto

```
track4_proyecto/
├── backend/
│   ├── main.py                 # Endpoints FastAPI (HU1, HU2, HU3)
│   ├── services.py             # Lógica de negocio + integración con Claude (extracción y RAG)
│   ├── models.py                # Modelos Pydantic de request/response
│   ├── database.py              # Engine y sesión de SQLAlchemy
│   ├── db_models.py             # Modelos ORM (Caso, Expediente, Evento)
│   ├── data_store.py            # Capa de acceso a datos (persistente) + semilla inicial de antecedentes
│   ├── data/                     # estado_sri_simulado.csv (fuente externa) + antecedentes_historicos.csv (solo semilla inicial)
│   ├── tests/                    # Suite de pruebas automatizadas (pytest)
│   ├── requirements.txt
│   ├── requirements-dev.txt      # + pytest, httpx (solo para pruebas)
│   └── README.md                 # Instrucciones detalladas del backend
├── frontend/
│   ├── app.py                    # UI Streamlit (stepper, creación de caso, HU1-HU3)
│   ├── .streamlit/config.toml    # Tema claro forzado
│   ├── requirements.txt
│   └── README.md                 # Instrucciones detalladas del frontend
├── nota_credito_prueba.png       # Imagen de prueba sintética para la extracción
├── nota_credito_prueba2.png      # Imagen de prueba real (nota de crédito SRI)
└── README.md                     # Este archivo
```

## Cómo levantar el proyecto

### 1. Backend

```bash
cd backend
pip install -r requirements.txt

# Configura tu API key de Anthropic (requerida para extracción y RAG)
export ANTHROPIC_API_KEY=tu_clave        # macOS/Linux
$env:ANTHROPIC_API_KEY = "tu_clave"      # Windows PowerShell

uvicorn main:app --reload o python -m uvicorn main:app --reload
```
Backend disponible en `http://127.0.0.1:8000` (Swagger UI en `/docs`). Crea `sri_notas.db` automáticamente en el primer arranque.

### 2. Frontend

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py o python -m streamlit run app.py
```
Frontend disponible en `http://localhost:8501`.

## Flujo de demo sugerido

1. Abre `http://localhost:8501` con el backend ya corriendo.
2. En **"Crear caso nuevo desde un documento"**, sube `nota_credito_prueba.png` (o `nota_credito_prueba2.png`) — los campos se extraen automáticamente al cargar el archivo.
3. Revisa/edita los campos extraídos y crea el caso.
4. **Paso 1**: revisa antecedentes reutilizables sugeridos (exactos y aproximados) y confirma/edita/rechaza.
5. **Paso 2**: valida el caso contra el SRI simulado y observa las alertas y el siguiente paso sugerido.
6. **Paso 3**: genera el borrador de negociación y apruébalo con tu nombre.
7. Revisa el expediente único al final de la página, con el historial completo del caso.
8. Reinicia el backend (`Ctrl+C` y vuelve a correr `uvicorn`) y confirma que el caso sigue existiendo — la persistencia es real.