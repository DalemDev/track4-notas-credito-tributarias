import json
import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# --- Carga inicial desde los archivos generados en la etapa de dataset ---

with open(DATA_DIR / "notas_credito_nuevas.json", encoding="utf-8") as f:
    CASOS_NUEVOS = {c["caso_id"]: c for c in json.load(f)}

with open(DATA_DIR / "antecedentes_historicos.csv", encoding="utf-8") as f:
    ANTECEDENTES = list(csv.DictReader(f))

with open(DATA_DIR / "estado_sri_simulado.csv", encoding="utf-8") as f:
    ESTADO_SRI = {row["numero_titulo"]: row for row in csv.DictReader(f)}

# --- Estado mutable en memoria (se reinicia si se reinicia el servidor) ---
# En un entorno real esto viviría en una base de datos (ej. SQLite/Postgres).

EXPEDIENTES: dict[str, dict] = {}


def get_or_crear_expediente(caso_id: str) -> dict:
    """Cada caso tiene un expediente único que acumula responsable, fecha,
    observaciones y documentos a lo largo de HU1 -> HU2 -> HU3 (criterio de HU3)."""
    if caso_id not in EXPEDIENTES:
        caso = CASOS_NUEVOS.get(caso_id)
        EXPEDIENTES[caso_id] = {
            "caso_id": caso_id,
            "estado": "ingresado",
            "datos_confirmados": {},
            "alertas": [],
            "siguiente_paso": None,
            "borrador": None,
            "historial": [
                {"evento": "caso_ingresado", "fecha": caso["fecha_ingreso"] if caso else None}
            ],
        }
    return EXPEDIENTES[caso_id]


def registrar_evento(caso_id: str, evento: str, detalle: str | None = None):
    exp = get_or_crear_expediente(caso_id)
    exp["historial"].append({"evento": evento, "detalle": detalle})
