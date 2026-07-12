# Backend Track 4 — Notas de crédito tributarias

## Arrancar
```
pip install -r requirements.txt
uvicorn main:app --reload
```
Abre http://127.0.0.1:8000/docs para probar todos los endpoints desde el navegador (Swagger UI, generado automático por FastAPI).

## Endpoints por historia de usuario

**HU1 — ingreso asistido**
- `GET /casos` — lista los casos ingresados
- `POST /casos` — crea el caso inicial (a partir de datos extraídos de un documento, o manuales)
- `GET /casos/{caso_id}` — detalle de un caso
- `GET /casos/{caso_id}/antecedentes` — datos reutilizables (coincidencia exacta por RUC/título + coincidencia aproximada por IA, ver [RAG](#coincidencias-aproximadas-rag-con-guardrails) más abajo)
- `POST /casos/{caso_id}/confirmar` — el operador confirma/edita/rechaza cada dato
- `POST /extraccion/documento` — carga un PDF/imagen y extrae campos con Claude (requiere `ANTHROPIC_API_KEY`)

**HU2 — validación y siguiente acción**
- `POST /casos/{caso_id}/validar` — corre las reglas contra `estado_sri_simulado.csv` y sugiere el siguiente paso

**HU3 — negociación y cierre**
- `POST /casos/{caso_id}/borrador` — genera la ficha de negociación (propuesta)
- `POST /casos/{caso_id}/aprobar` — aprobación humana, nunca ejecuta liquidación/transferencia/endoso
- `GET /expediente/{caso_id}` — expediente único con historial completo (con marca de tiempo por evento)

## Persistencia

El estado de la aplicación (casos y expedientes) vive en **SQLite vía SQLAlchemy** (`database.py`, `db_models.py`), no en memoria. El archivo `sri_notas.db` se crea automáticamente en `backend/` al arrancar el servidor y sobrevive a reinicios.

Las fuentes de referencia simuladas (`data/antecedentes_historicos.csv`, `data/estado_sri_simulado.csv`) siguen siendo archivos estáticos de solo lectura — representan sistemas externos (el SRI, el historial de la casa de valores), no el estado propio de esta aplicación.

Para apuntar a otra base de datos (o una temporal, como hacen las pruebas), usa la variable de entorno `DATABASE_URL`:
```
export DATABASE_URL="sqlite:///./otra_base.db"
```

## Coincidencias aproximadas (RAG con guardrails)

Además de la coincidencia exacta por RUC o número de título, `GET /casos/{caso_id}/antecedentes` incluye coincidencias **aproximadas** cuando el titular del caso nuevo se parece al de otro titular con antecedentes:

1. **Retrieval** (determinista, sin LLM): `rapidfuzz` compara el nombre del titular contra todos los antecedentes y preselecciona los candidatos con similitud ≥ 82%.
2. **Generation**: Claude recibe *solo* esos candidatos y juzga cuáles son realmente relevantes (variación de razón social, error de tipeo) y por qué, usando *structured outputs*.
3. **Guardrail anti-alucinación**: Claude solo puede referirse a un candidato por su índice dentro de la lista ya recuperada — si el índice no existe en esa lista, se descarta sin excepción. Nunca se muestra una coincidencia que no haya sido recuperada primero por el paso determinista.

Cada coincidencia queda etiquetada con `"tipo_coincidencia": "exacta"` o `"aproximada"` para que el frontend las distinga. Sin `ANTHROPIC_API_KEY` configurada, o si la IA falla, simplemente no se muestran coincidencias aproximadas — las exactas (deterministas) se siguen mostrando igual.

## Pruebas automatizadas

```
pip install -r requirements-dev.txt
pytest -v
```
Usan una base de datos SQLite temporal y aislada (nunca `sri_notas.db`). Cubren: creación de casos, búsqueda de antecedentes (exactos y el guardrail del RAG), las 5 reglas de validación de HU2, el flujo completo HU1→HU2→HU3, y el manejo de errores de extracción. Una prueba de extracción real contra la API de Anthropic se salta automáticamente si no hay `ANTHROPIC_API_KEY` en el entorno.

## Para habilitar extracción con IA
La extracción usa el SDK oficial `anthropic` (modelo `claude-sonnet-5`). Configura la clave antes de levantar el servidor:

macOS/Linux:
```
export ANTHROPIC_API_KEY=tu_clave
```

Windows (PowerShell):
```
$env:ANTHROPIC_API_KEY = "tu_clave"
```

Sin esto, el endpoint `/extraccion/documento` devuelve un mensaje explicando que falta la clave, pero el resto del sistema funciona igual (esa parte es un extra, no bloquea el flujo mínimo).
