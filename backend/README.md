# Backend Track 4 — Notas de crédito tributarias

## Arrancar
```
pip install -r requirements.txt
uvicorn main:app --reload
```
Abre http://127.0.0.1:8000/docs para probar todos los endpoints desde el navegador (Swagger UI, generado automático por FastAPI).

## Endpoints por historia de usuario

**HU1 — ingreso asistido**
- `GET /casos` — lista los 7 casos ficticios
- `GET /casos/{caso_id}` — detalle de un caso
- `GET /casos/{caso_id}/antecedentes` — datos reutilizables (fecha, fuente, estado)
- `POST /casos/{caso_id}/confirmar` — el operador confirma/edita/rechaza cada dato
- `POST /extraccion/documento` — carga un PDF/imagen y extrae campos con Claude (requiere `ANTHROPIC_API_KEY`)

**HU2 — validación y siguiente acción**
- `POST /casos/{caso_id}/validar` — corre las reglas contra `estado_sri_simulado.csv` y sugiere el siguiente paso

**HU3 — negociación y cierre**
- `POST /casos/{caso_id}/borrador` — genera la ficha de negociación (propuesta)
- `POST /casos/{caso_id}/aprobar` — aprobación humana, nunca ejecuta liquidación/transferencia/endoso
- `GET /expediente/{caso_id}` — expediente único con historial completo


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