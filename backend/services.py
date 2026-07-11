import os
import json
import base64
import mimetypes
import anthropic
from data_store import ANTECEDENTES, ESTADO_SRI, CASOS_NUEVOS

TIPOS_SOPORTADOS = {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif"}

# Esquema de salida para la extracción con Claude: usar output_config.format
# garantiza JSON válido en la respuesta, en vez de confiar en que el modelo
# obedezca la instrucción del prompt (evita el caso "Claude no devolvió un
# JSON válido" cuando envuelve la respuesta en texto o bloques de markdown).
ESQUEMA_EXTRACCION = {
    "type": "object",
    "properties": {
        "titular": {"type": "string", "description": "Nombre del titular. Cadena vacía si no aparece."},
        "ruc": {"type": "string", "description": "RUC o identificación. Cadena vacía si no aparece."},
        "tipo_nota": {"type": "string", "description": "Tipo de nota de crédito. Cadena vacía si no aparece."},
        "valor_nominal": {"type": "number", "description": "Valor nominal. 0 si no aparece."},
        "saldo": {"type": "number", "description": "Saldo disponible. 0 si no aparece."},
        "numero_titulo": {"type": "string", "description": "Número de título. Cadena vacía si no aparece."},
    },
    "required": ["titular", "ruc", "tipo_nota", "valor_nominal", "saldo", "numero_titulo"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# HU1: búsqueda de antecedentes reutilizables por RUC
# ---------------------------------------------------------------------------

def buscar_antecedentes(ruc: str, numero_titulo: str | None = None) -> list[dict]:
    """Devuelve cada dato reutilizable con fecha, fuente y estado,
    tal como pide el criterio de aceptación de HU1. Busca por RUC o por
    coincidencia con un número de título anterior. No aplica nada:
    solo sugiere, el operador confirma/edita/rechaza en el siguiente paso."""
    return [
        a for a in ANTECEDENTES
        if a["ruc"] == ruc or (numero_titulo and a.get("numero_titulo_anterior") == numero_titulo)
    ]


# ---------------------------------------------------------------------------
# HU2: validación de reglas + siguiente paso sugerido
# ---------------------------------------------------------------------------

def validar_caso(caso_id: str) -> dict:
    caso = CASOS_NUEVOS.get(caso_id)
    if not caso:
        return {"error": "caso no encontrado"}

    alertas = []
    estado_sri = ESTADO_SRI.get(caso["numero_titulo"])

    # Regla 1: existencia contra la fuente (real/simulada)
    if not estado_sri:
        alertas.append({
            "tipo": "no_encontrado_en_sri",
            "detalle": f"El título {caso['numero_titulo']} no existe en la fuente SRI simulada.",
        })
    else:
        # Regla 2: bloqueos
        if estado_sri["bloqueo"] == "si":
            alertas.append({
                "tipo": "bloqueo",
                "detalle": estado_sri["motivo_bloqueo"],
            })
        # Regla 3: inconsistencia de saldo entre lo ingresado y el SRI
        saldo_sri = float(estado_sri["saldo_disponible_sri"])
        if abs(saldo_sri - float(caso["saldo"])) > 0.01:
            alertas.append({
                "tipo": "inconsistencia_saldo",
                "detalle": f"Saldo ingresado {caso['saldo']} no coincide con saldo SRI {saldo_sri}.",
            })
        # Regla 4: estado del título
        if estado_sri["estado_titulo"] != "vigente":
            alertas.append({
                "tipo": "estado_no_vigente",
                "detalle": f"Estado del título: {estado_sri['estado_titulo']}.",
            })

    # Regla 5: duplicados por número de título entre casos ya ingresados
    duplicados = [
        c["caso_id"] for c in CASOS_NUEVOS.values()
        if c["numero_titulo"] == caso["numero_titulo"] and c["caso_id"] != caso_id
    ]
    if duplicados:
        alertas.append({
            "tipo": "duplicado",
            "detalle": f"Mismo número de título que: {', '.join(duplicados)}.",
        })

    siguiente_paso = _sugerir_siguiente_paso(alertas)

    return {
        "caso_id": caso_id,
        "alertas": alertas,
        "siguiente_paso": siguiente_paso,
    }


def _sugerir_siguiente_paso(alertas: list[dict]) -> dict:
    """Siempre con aprobación humana (criterio explícito de HU2):
    esto es una SUGERENCIA, no una ejecución."""
    tipos = {a["tipo"] for a in alertas}

    if "bloqueo" in tipos:
        return {"accion": "enviar_a_cumplimiento", "motivo": "Título bloqueado, requiere revisión de cumplimiento."}
    if "duplicado" in tipos:
        return {"accion": "solicitar_revision_duplicado", "motivo": "Posible ingreso duplicado del mismo título."}
    if "inconsistencia_saldo" in tipos or "estado_no_vigente" in tipos:
        return {"accion": "actualizar_dato", "motivo": "Hay una discrepancia contra la fuente SRI."}
    if "no_encontrado_en_sri" in tipos:
        return {"accion": "solicitar_documento", "motivo": "No se pudo verificar el título contra el SRI."}
    return {"accion": "continuar", "motivo": "Sin hallazgos. Puede avanzar a preparación de orden."}


# ---------------------------------------------------------------------------
# HU3: borrador de negociación (propuesta, no ejecución)
# ---------------------------------------------------------------------------

def generar_borrador(caso_id: str, datos_confirmados: dict) -> dict:
    caso = CASOS_NUEVOS.get(caso_id)
    texto = (
        f"BORRADOR DE FICHA DE NEGOCIACION - {caso['numero_titulo']}\n"
        f"Titular: {caso['titular']} (RUC {caso['ruc']})\n"
        f"Tipo de nota: {caso['tipo_nota']}\n"
        f"Valor nominal: {caso['valor_nominal']}\n"
        f"Saldo confirmado: {caso['saldo']}\n"
        f"Datos adicionales confirmados por el operador: {json.dumps(datos_confirmados, ensure_ascii=False)}\n"
        f"\nEste documento es una PROPUESTA. Requiere aprobación del operador antes de "
        f"cualquier liquidacion, transferencia o endoso. Ninguna accion regulada se ejecuta en produccion."
    )
    return {"caso_id": caso_id, "borrador": texto, "estado": "pendiente_de_aprobacion"}


# ---------------------------------------------------------------------------
# Extracción de datos con Claude (apoya HU1: carga real de documentos)
# ---------------------------------------------------------------------------

def extraer_datos_desde_documento(contenido: bytes, media_type: str | None, nombre_archivo: str | None) -> dict:
    """Llama a la API de Anthropic para estructurar los campos de una nota de
    crédito a partir de un documento cargado (PDF o imagen); Claude lee el
    archivo directamente, sin paso de OCR intermedio. Requiere la variable de
    entorno ANTHROPIC_API_KEY configurada por el equipo."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "Configura ANTHROPIC_API_KEY para habilitar la extracción con IA."}

    if not media_type or media_type not in TIPOS_SOPORTADOS:
        media_type = mimetypes.guess_type(nombre_archivo or "")[0]
    if media_type not in TIPOS_SOPORTADOS:
        return {"error": f"Tipo de archivo no soportado: {media_type or 'desconocido'}. Usa PDF, PNG, JPEG, WEBP o GIF."}

    bloque_documento = "document" if media_type == "application/pdf" else "image"
    datos_b64 = base64.standard_b64encode(contenido).decode("utf-8")

    prompt = (
        "Extrae estos campos a partir de este documento de una nota de crédito tributaria "
        "ecuatoriana: titular, ruc, tipo_nota, valor_nominal, saldo, numero_titulo."
    )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=500,
            output_config={"format": {"type": "json_schema", "schema": ESQUEMA_EXTRACCION}},
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": bloque_documento,
                        "source": {"type": "base64", "media_type": media_type, "data": datos_b64},
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
    except anthropic.APIConnectionError:
        return {"error": "No se pudo conectar con la API de Anthropic."}
    except anthropic.RateLimitError:
        return {"error": "Límite de solicitudes excedido en la API de Anthropic. Intenta de nuevo en unos segundos."}
    except anthropic.APIStatusError as e:
        return {"error": f"Error de la API de Anthropic ({e.status_code}): {e.message}"}

    if response.stop_reason == "refusal":
        return {"error": "Claude no pudo procesar este documento (rechazado por políticas de seguridad)."}

    texto_respuesta = "".join(bloque.text for bloque in response.content if bloque.type == "text")
    try:
        return json.loads(texto_respuesta)
    except json.JSONDecodeError:
        return {"error": "Claude no devolvio un JSON valido", "respuesta_cruda": texto_respuesta}
