from datetime import date

from fastapi import FastAPI, HTTPException, UploadFile, File

from data_store import CASOS_NUEVOS, get_or_crear_expediente, registrar_evento
from models import ConfirmacionRequest, AprobarBorradorRequest, NuevoCasoRequest
import services

app = FastAPI(title="Asistente de notas de crédito tributarias - Track 4")


# ---------------------------------------------------------------------------
# HU1: ingreso asistido y reutilización de antecedentes
# ---------------------------------------------------------------------------

@app.get("/casos")
def listar_casos():
    """Lista los casos entrantes (equivalente a lo que el operador ve al abrir el sistema)."""
    return list(CASOS_NUEVOS.values())


@app.post("/casos")
def crear_caso(body: NuevoCasoRequest):
    """Crea el caso inicial a partir de datos extraídos de un documento (o
    ingresados manualmente). Es el punto de entrada de HU1: 'extrae o recibe
    datos... para que no tenga que reingresar información'."""
    anio = date.today().year
    existentes = [c for c in CASOS_NUEVOS if c.startswith(f"NC-{anio}-")]
    caso_id = f"NC-{anio}-{len(existentes) + 1:04d}"

    nuevo_caso = {
        "caso_id": caso_id,
        "numero_titulo": body.numero_titulo,
        "titular": body.titular,
        "ruc": body.ruc,
        "tipo_nota": body.tipo_nota,
        "valor_nominal": body.valor_nominal,
        "saldo": body.saldo,
        "documento_respaldo": body.documento_respaldo,
        "fecha_ingreso": date.today().isoformat(),
    }
    CASOS_NUEVOS[caso_id] = nuevo_caso
    return nuevo_caso


@app.get("/casos/{caso_id}")
def detalle_caso(caso_id: str):
    caso = CASOS_NUEVOS.get(caso_id)
    if not caso:
        raise HTTPException(404, "Caso no encontrado")
    return caso


@app.get("/casos/{caso_id}/antecedentes")
def antecedentes_del_caso(caso_id: str):
    """Sugerencias de datos reutilizables para este caso, con fecha/fuente/estado."""
    caso = CASOS_NUEVOS.get(caso_id)
    if not caso:
        raise HTTPException(404, "Caso no encontrado")
    return services.buscar_antecedentes(caso["ruc"], caso.get("numero_titulo"))


@app.post("/casos/{caso_id}/confirmar")
def confirmar_datos(caso_id: str, body: ConfirmacionRequest):
    """El operador confirma, edita o rechaza cada dato sugerido.
    Nada se guarda sin pasar por aquí (criterio de aceptación de HU1)."""
    if caso_id not in CASOS_NUEVOS:
        raise HTTPException(404, "Caso no encontrado")

    expediente = get_or_crear_expediente(caso_id)
    for decision in body.decisiones:
        if decision.accion in ("confirmar", "editar"):
            expediente["datos_confirmados"][decision.dato] = decision.valor_final
        # "rechazar" no guarda nada, solo queda en el historial
        registrar_evento(caso_id, f"dato_{decision.accion}", decision.dato)

    expediente["estado"] = "datos_confirmados"
    return expediente


@app.post("/extraccion/documento")
async def extraer_desde_documento(archivo: UploadFile = File(...)):
    """Carga real de un documento (PDF o imagen) de una nota de crédito: Claude
    lee el archivo directamente y devuelve los campos estructurados (criterio
    de 'carga de documentos' de HU1)."""
    contenido = await archivo.read()
    return services.extraer_datos_desde_documento(contenido, archivo.content_type, archivo.filename)


# ---------------------------------------------------------------------------
# HU2: validación y siguiente acción guiada
# ---------------------------------------------------------------------------

@app.post("/casos/{caso_id}/validar")
def validar_caso(caso_id: str):
    if caso_id not in CASOS_NUEVOS:
        raise HTTPException(404, "Caso no encontrado")

    resultado = services.validar_caso(caso_id)
    expediente = get_or_crear_expediente(caso_id)
    expediente["alertas"] = resultado["alertas"]
    expediente["siguiente_paso"] = resultado["siguiente_paso"]
    expediente["estado"] = "validado"
    registrar_evento(caso_id, "validacion_ejecutada", str(len(resultado["alertas"])) + " alertas")
    return resultado


# ---------------------------------------------------------------------------
# HU3: preparación de negociación y cierre asistido
# ---------------------------------------------------------------------------

@app.post("/casos/{caso_id}/borrador")
def generar_borrador(caso_id: str):
    if caso_id not in CASOS_NUEVOS:
        raise HTTPException(404, "Caso no encontrado")

    expediente = get_or_crear_expediente(caso_id)
    resultado = services.generar_borrador(caso_id, expediente["datos_confirmados"])
    expediente["borrador"] = resultado["borrador"]
    expediente["estado"] = resultado["estado"]
    registrar_evento(caso_id, "borrador_generado")
    return resultado


@app.post("/casos/{caso_id}/aprobar")
def aprobar_borrador(caso_id: str, body: AprobarBorradorRequest):
    """El operador aprueba el borrador. Esto NO ejecuta liquidación, transferencia
    ni endoso: solo deja el caso listo como propuesta aprobada (criterio de HU3)."""
    expediente = get_or_crear_expediente(caso_id)
    if not expediente["borrador"]:
        raise HTTPException(400, "No hay borrador generado para aprobar")

    expediente["estado"] = "aprobado_pendiente_liquidacion"
    registrar_evento(caso_id, "borrador_aprobado", body.aprobado_por)
    if body.observaciones:
        registrar_evento(caso_id, "observacion", body.observaciones)
    return expediente


@app.get("/expediente/{caso_id}")
def ver_expediente(caso_id: str):
    """Expediente único del caso: responsable, fecha, observaciones y documentos,
    con el estado actual y la próxima acción visibles (criterio de HU3)."""
    return get_or_crear_expediente(caso_id)
