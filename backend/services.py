import os
import json
import base64
import mimetypes
import anthropic
from rapidfuzz import fuzz
import data_store
from data_store import ESTADO_SRI

TIPOS_SOPORTADOS = {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif"}

# Umbral de similitud (0-100, rapidfuzz) para que un antecedente de OTRO
# titular se considere candidato a "coincidencia aproximada". Por debajo de
# esto, ni siquiera se recupera para que Claude lo juzgue.
UMBRAL_SIMILITUD_TITULAR = 82
MAX_CANDIDATOS_COINCIDENCIA = 5

# Esquema de salida para el juicio de relevancia (RAG): Claude solo puede
# referirse a candidatos por su índice dentro de la lista ya recuperada por
# rapidfuzz — nunca puede inventar un antecedente que no fue recuperado. Este
# es el guardrail anti-alucinación de esta funcionalidad.
ESQUEMA_COINCIDENCIAS = {
    "type": "object",
    "properties": {
        "coincidencias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "indice": {"type": "integer", "description": "Índice (0-based) del candidato en la lista proporcionada."},
                    "es_relevante": {"type": "boolean", "description": "True solo si podría tratarse del mismo titular."},
                    "razon": {"type": "string", "description": "Explicación breve (una frase) de la decisión."},
                },
                "required": ["indice", "es_relevante", "razon"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["coincidencias"],
    "additionalProperties": False,
}

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

def buscar_antecedentes(ruc: str, numero_titulo: str | None = None, titular: str | None = None) -> list[dict]:
    """Devuelve cada dato reutilizable con fecha, fuente y estado,
    tal como pide el criterio de aceptación de HU1. Busca por RUC, por
    coincidencia con un número de título anterior, y por coincidencia
    aproximada de titular (RAG, ver más abajo). No aplica nada: solo
    sugiere, el operador confirma/edita/rechaza en el siguiente paso."""
    antecedentes = data_store.listar_antecedentes()
    exactos = [
        {**a, "tipo_coincidencia": "exacta"}
        for a in antecedentes
        if a["ruc"] == ruc or (numero_titulo and a.get("numero_titulo_anterior") == numero_titulo)
    ]
    aproximados = buscar_coincidencias_aproximadas(titular, exactos, antecedentes) if titular else []
    return exactos + aproximados


def _candidatos_por_similitud(titular: str, antecedentes: list[dict], ya_vistos: set[tuple]) -> list[dict]:
    """Retrieval: preselecciona (con coincidencia difusa, no LLM) antecedentes
    de OTROS titulares con nombre similar que aún no fueron devueltos como
    coincidencia exacta — la 'coincidencia relevante' que pide HU1."""
    candidatos = []
    for a in antecedentes:
        clave = (a["ruc"], a.get("numero_titulo_anterior"), a["dato"])
        if clave in ya_vistos:
            continue
        similitud = fuzz.token_sort_ratio(titular, a["titular"])
        if similitud >= UMBRAL_SIMILITUD_TITULAR:
            candidatos.append({**a, "similitud": round(similitud, 1)})
    candidatos.sort(key=lambda c: c["similitud"], reverse=True)
    return candidatos[:MAX_CANDIDATOS_COINCIDENCIA]


def buscar_coincidencias_aproximadas(titular: str, ya_exactos: list[dict], antecedentes: list[dict] | None = None) -> list[dict]:
    """RAG con guardrail anti-alucinación para la 'coincidencia relevante' de
    HU1: primero se RECUPERAN candidatos por coincidencia difusa de nombre
    (rapidfuzz, determinista, sin LLM), y luego Claude juzga cuáles son
    realmente relevantes y por qué. Claude solo puede referirse a un
    candidato por su índice en la lista ya recuperada — si inventa un índice
    fuera de rango, se descarta sin excepción. Si no hay candidatos o no hay
    IA disponible, no se muestra nada (nunca se inventa una coincidencia)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    ya_vistos = {(a["ruc"], a.get("numero_titulo_anterior"), a["dato"]) for a in ya_exactos}
    if antecedentes is None:
        antecedentes = data_store.listar_antecedentes()
    candidatos = _candidatos_por_similitud(titular, antecedentes, ya_vistos)

    if not candidatos or not api_key:
        return []

    lista_candidatos = "\n".join(
        f"{i}. Titular: {c['titular']} | RUC: {c['ruc']} | Dato: {c['dato']} = {c['valor_dato']} | Similitud de nombre: {c['similitud']}%"
        for i, c in enumerate(candidatos)
    )
    prompt = (
        f"Un operador está ingresando un caso nuevo para el titular '{titular}'.\n"
        f"Estos son antecedentes de otros titulares con nombre similar, recuperados por coincidencia "
        f"difusa de texto:\n{lista_candidatos}\n\n"
        "Para cada candidato, indica si realmente podría tratarse del mismo titular (variación de "
        "razón social, error de tipeo, abreviatura) o si es solo una coincidencia de nombre "
        "irrelevante. Responde únicamente sobre los candidatos listados arriba, por su índice."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=800,
            output_config={"format": {"type": "json_schema", "schema": ESQUEMA_COINCIDENCIAS}},
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            return []
        texto_respuesta = "".join(b.text for b in response.content if b.type == "text")
        juicios = json.loads(texto_respuesta)["coincidencias"]
    except (anthropic.APIError, json.JSONDecodeError, KeyError, TypeError):
        # La IA no está disponible o falló: no se bloquea el flujo, solo no
        # se muestran coincidencias aproximadas en este request (las
        # coincidencias exactas, deterministas, se muestran igual).
        return []

    resultado = []
    for juicio in juicios:
        indice = juicio.get("indice")
        # Guardrail: solo se acepta un índice que exista en la lista recuperada.
        if not isinstance(indice, int) or not (0 <= indice < len(candidatos)):
            continue
        if not juicio.get("es_relevante"):
            continue
        candidato = candidatos[indice]
        resultado.append({
            **{k: v for k, v in candidato.items() if k != "similitud"},
            "tipo_coincidencia": "aproximada",
            "similitud": candidato["similitud"],
            "razon": juicio.get("razon", ""),
        })
    return resultado


# ---------------------------------------------------------------------------
# HU2: validación de reglas + siguiente paso sugerido
# ---------------------------------------------------------------------------

def validar_caso(caso_id: str) -> dict:
    caso = data_store.obtener_caso(caso_id)
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
    duplicados = data_store.buscar_duplicados_titulo(caso["numero_titulo"], caso_id)
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
    caso = data_store.obtener_caso(caso_id)
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
