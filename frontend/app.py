import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Track 4 - Notas de crédito tributarias", layout="wide")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def get(path):
    try:
        r = requests.get(f"{API_URL}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar al backend. ¿Está corriendo `uvicorn main:app --reload`?")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"El backend devolvió un error al consultar {path}: {e}")
        st.stop()


def post(path, json=None):
    try:
        r = requests.post(f"{API_URL}{path}", json=json or {}, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar al backend. ¿Está corriendo `uvicorn main:app --reload`?")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"El backend devolvió un error: {e}")
        st.stop()


def post_archivo(path, archivo_streamlit):
    try:
        archivos = {"archivo": (archivo_streamlit.name, archivo_streamlit.getvalue(), archivo_streamlit.type)}
        r = requests.post(f"{API_URL}{path}", files=archivos, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar al backend. ¿Está corriendo `uvicorn main:app --reload`?")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"El backend devolvió un error: {e}")
        st.stop()


def a_float(valor, default=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


def render_stepper(pasos, indice_actual):
    """Barra de pasos horizontal (lo más cercano a un 'stepper' con los
    componentes nativos de Streamlit): un círculo por paso, conectados por una
    línea, coloreados según su estado (completado/en curso/pendiente)."""
    piezas = []
    for i, titulo in enumerate(pasos):
        if i < indice_actual:
            color, estado, contenido = "#16a34a", "Completado", "&#10003;"
        elif i == indice_actual:
            color, estado, contenido = "#2563eb", "En curso", str(i + 1)
        else:
            color, estado, contenido = "#d1d5db", "Pendiente", str(i + 1)
        color_texto = "#111827" if i <= indice_actual else "#9ca3af"

        piezas.append(f"""
        <div style="display:flex; flex-direction:column; align-items:center; min-width:110px;">
            <div style="width:34px; height:34px; border-radius:50%; background:{color};
                        color:#ffffff; display:flex; align-items:center; justify-content:center;
                        font-weight:600; font-size:0.9rem;">{contenido}</div>
            <div style="margin-top:6px; font-weight:600; font-size:0.85rem; color:{color_texto}; text-align:center;">{titulo}</div>
            <div style="font-size:0.75rem; color:{color};">{estado}</div>
        </div>
        """)
        if i < len(pasos) - 1:
            linea_color = "#16a34a" if i < indice_actual else "#d1d5db"
            piezas.append(f'<div style="flex:1; height:2px; background:{linea_color}; margin-top:17px;"></div>')

    st.markdown(
        f'<div style="display:flex; align-items:flex-start; padding:8px 0 20px 0;">{"".join(piezas)}</div>',
        unsafe_allow_html=True,
    )


# Mapea el estado del expediente (fuente de verdad: el backend) a un índice de
# paso (0-based) del stepper y un mensaje en lenguaje natural sobre qué hacer.
PASOS_STEPPER = ["Antecedentes", "Validación SRI", "Negociación", "Cierre"]
PASO_POR_ESTADO = {
    "ingresado": (0, "Revisa los antecedentes reutilizables sugeridos en el Paso 1 y confirma, edita o rechaza cada uno."),
    "datos_confirmados": (1, "Datos confirmados. Corre la validación contra el SRI en el Paso 2."),
    "validado": (2, "Caso validado. Genera el borrador de la ficha de negociación en el Paso 3."),
    "pendiente_de_aprobacion": (2, "Borrador generado. Revísalo y apruébalo en el Paso 3."),
    "aprobado_pendiente_liquidacion": (3, "Caso aprobado. La liquidación, transferencia o endoso quedan pendientes como acción manual regulada — no se ejecutan en esta demo."),
}


st.title("Asistente de ingreso y negociación de notas de crédito")
st.caption("SRI Ecuador — acompaña al operador de principio a fin, con aprobación humana en cada paso.")

casos = get("/casos")

# ---------------------------------------------------------------------------
# Crear caso nuevo — punto de entrada de HU1: cargar el documento y dejar que
# Claude extraiga los campos automáticamente. El operador siempre revisa/edita
# antes de crear el caso; nada se guarda sin su confirmación.
# ---------------------------------------------------------------------------

with st.expander("Crear caso nuevo desde un documento", expanded=not casos):
    st.caption(
        "Sube el documento de la nota de crédito (PDF o imagen). Claude extrae los campos "
        "estructurados automáticamente; revísalos y edítalos si hace falta antes de crear el caso."
    )

    archivo_nuevo = st.file_uploader(
        "Documento de la nota de crédito",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        key="archivo_nuevo_caso",
    )

    if archivo_nuevo is not None:
        identificador_archivo = f"{archivo_nuevo.name}:{archivo_nuevo.size}"
        if st.session_state.get("archivo_procesado_id") != identificador_archivo:
            with st.spinner("Extrayendo datos con IA..."):
                resultado_extraccion = post_archivo("/extraccion/documento", archivo_nuevo)
            st.session_state.archivo_procesado_id = identificador_archivo
            if "error" in resultado_extraccion:
                st.error(resultado_extraccion["error"])
                st.session_state.pop("datos_extraidos", None)
            else:
                st.session_state.datos_extraidos = resultado_extraccion
                st.session_state.documento_nombre = archivo_nuevo.name
                st.success("Datos extraídos automáticamente. Revísalos abajo antes de crear el caso.")

    datos_previos = st.session_state.get("datos_extraidos", {})

    with st.container(border=True):
        st.subheader("Revisa y confirma los datos del caso")
        st.caption(
            "Puedes editar cualquier campo, o llenarlos manualmente si no subiste un documento. "
            "El caso solo se crea cuando presionas el botón de abajo."
        )
        col_izq, col_der = st.columns(2)
        with col_izq:
            titular = st.text_input("Titular", value=datos_previos.get("titular") or "")
            ruc = st.text_input("RUC", value=datos_previos.get("ruc") or "")
            numero_titulo = st.text_input("Número de título", value=datos_previos.get("numero_titulo") or "")
        with col_der:
            tipo_nota = st.text_input("Tipo de nota", value=datos_previos.get("tipo_nota") or "")
            valor_nominal = st.number_input("Valor nominal", value=a_float(datos_previos.get("valor_nominal")), min_value=0.0)
            saldo = st.number_input("Saldo", value=a_float(datos_previos.get("saldo")), min_value=0.0)

        if st.button("Crear caso con estos datos", type="primary"):
            if not titular or not ruc or not numero_titulo:
                st.error("Titular, RUC y número de título son obligatorios.")
            else:
                nuevo_caso = post("/casos", {
                    "titular": titular,
                    "ruc": ruc,
                    "numero_titulo": numero_titulo,
                    "tipo_nota": tipo_nota,
                    "valor_nominal": valor_nominal,
                    "saldo": saldo,
                    "documento_respaldo": st.session_state.get("documento_nombre"),
                })
                st.session_state.pop("datos_extraidos", None)
                st.session_state.pop("documento_nombre", None)
                st.session_state.pop("archivo_procesado_id", None)
                st.session_state.caso_recien_creado = nuevo_caso["caso_id"]
                st.success(f"Caso {nuevo_caso['caso_id']} creado.")
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Selección de caso (barra lateral) — siempre visible mientras se navega
# ---------------------------------------------------------------------------

if not casos:
    st.info("Aún no hay casos ingresados. Crea el primero con el panel de arriba.")
    st.stop()

st.sidebar.header("Caso de trabajo")
opciones = {f"{c['caso_id']} — {c['titular']}": c["caso_id"] for c in casos}
etiquetas = list(opciones.keys())
ids_por_etiqueta = list(opciones.values())

indice_default = 0
caso_recien_creado = st.session_state.get("caso_recien_creado")
if caso_recien_creado in ids_por_etiqueta:
    indice_default = ids_por_etiqueta.index(caso_recien_creado)

seleccion = st.sidebar.selectbox("Selecciona un caso", etiquetas, index=indice_default)
caso_id = opciones[seleccion]
caso = next(c for c in casos if c["caso_id"] == caso_id)

if "caso_actual" not in st.session_state or st.session_state.caso_actual != caso_id:
    st.session_state.decisiones = {}
    st.session_state.caso_actual = caso_id

expediente = get(f"/expediente/{caso_id}")
indice_paso, mensaje_guia = PASO_POR_ESTADO.get(
    expediente["estado"], (0, "Comienza revisando los antecedentes reutilizables en el Paso 1.")
)

st.sidebar.divider()
st.sidebar.subheader("Progreso del caso")
st.sidebar.progress((indice_paso + 1) / len(PASOS_STEPPER), text=PASOS_STEPPER[indice_paso])
st.sidebar.caption(f"Estado interno: `{expediente['estado']}`")

render_stepper(PASOS_STEPPER, indice_paso)
st.info(f"**Siguiente acción sugerida:** {mensaje_guia}")

st.divider()

# ---------------------------------------------------------------------------
# Paso 1 — HU1: ingreso asistido y reutilización de antecedentes
# ---------------------------------------------------------------------------

st.header("Paso 1 — Ingreso asistido y antecedentes")
st.caption(
    "Estos son los datos recibidos del caso y las coincidencias de casos anteriores por RUC o número "
    "de título. Ningún dato se guarda hasta que lo confirmes, edites o rechaces explícitamente."
)

col_datos, col_antecedentes = st.columns(2)

with col_datos:
    with st.container(border=True):
        st.subheader("Datos de la nota de crédito")
        st.write(f"**Titular:** {caso['titular']}")
        st.write(f"**RUC:** {caso['ruc']}")
        st.write(f"**Número de título:** {caso['numero_titulo']}")
        st.write(f"**Tipo de nota:** {caso['tipo_nota']}")
        st.write(f"**Valor nominal:** {caso['valor_nominal']}")
        st.write(f"**Saldo declarado:** {caso['saldo']}")
        st.caption(f"Ingresado el {caso.get('fecha_ingreso', 'N/D')} · Documento: {caso.get('documento_respaldo', 'N/D')}")

with col_antecedentes:
    with st.container(border=True):
        st.subheader("Antecedentes reutilizables")
        antecedentes = get(f"/casos/{caso_id}/antecedentes")

        if not antecedentes:
            st.info(
                "Sin coincidencias previas por RUC o número de título. Se ingresa como caso nuevo — "
                "puedes continuar directamente al Paso 2."
            )
        else:
            for a in antecedentes:
                with st.container(border=True):
                    st.write(f"**{a['dato']}**: {a['valor_dato']}")
                    st.caption(f"Fecha: {a['fecha_validacion']} · Fuente: {a['fuente']} · Estado: {a['estado']}")
                    accion = st.radio(
                        "Acción del operador",
                        ["confirmar", "editar", "rechazar"],
                        horizontal=True,
                        key=f"accion_{caso_id}_{a['dato']}",
                        help="Confirmar guarda el valor tal cual. Editar te deja escribir uno nuevo. Rechazar no guarda nada.",
                    )
                    valor_final = a["valor_dato"]
                    if accion == "editar":
                        valor_final = st.text_input(
                            "Nuevo valor", value=a["valor_dato"], key=f"valor_{caso_id}_{a['dato']}"
                        )
                    st.session_state.decisiones[a["dato"]] = {"accion": accion, "valor_final": valor_final}

            if st.button("Guardar decisiones de antecedentes", type="primary"):
                decisiones = [
                    {"dato": dato, "accion": d["accion"], "valor_final": d["valor_final"]}
                    for dato, d in st.session_state.decisiones.items()
                ]
                post(f"/casos/{caso_id}/confirmar", {"decisiones": decisiones})
                st.success("Decisiones guardadas en el expediente.")
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Paso 2 — HU2: validación y siguiente acción guiada
# ---------------------------------------------------------------------------

st.header("Paso 2 — Validación contra el SRI")
with st.container(border=True):
    st.caption(
        "Verifica existencia, saldo, estado y posibles bloqueos contra la fuente simulada del SRI, y "
        "sugiere el siguiente paso. La decisión final siempre depende del operador."
    )

    if expediente["estado"] == "ingresado":
        st.caption("Sugerencia: confirma primero los antecedentes del Paso 1 (opcional — también puedes validar directamente).")

    if st.button("Validar caso"):
        resultado = post(f"/casos/{caso_id}/validar")
        if resultado["alertas"]:
            for alerta in resultado["alertas"]:
                st.warning(f"**{alerta['tipo']}**: {alerta['detalle']}")
        else:
            st.success("Sin hallazgos. El caso pasó todas las validaciones.")

        paso = resultado["siguiente_paso"]
        st.info(f"Siguiente paso sugerido: **{paso['accion']}** — {paso['motivo']}")
        st.caption("Esta sugerencia requiere aprobación humana antes de ejecutarse.")
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Paso 3 — HU3: preparación de negociación y cierre asistido
# ---------------------------------------------------------------------------

st.header("Paso 3 — Negociación y cierre")
st.caption(
    "Genera un borrador de la ficha de negociación con los datos confirmados y apruébalo. La "
    "liquidación, transferencia y endoso quedan como propuesta: nunca se ejecutan automáticamente."
)

col_borrador, col_aprobar = st.columns(2)

with col_borrador:
    with st.container(border=True):
        st.subheader("Generar borrador")
        if st.button("Generar borrador de ficha de negociación"):
            post(f"/casos/{caso_id}/borrador")
            st.rerun()
        if expediente.get("borrador"):
            st.text_area("Borrador actual (propuesta, no ejecutado)", expediente["borrador"], height=220)
        else:
            st.caption("Aún no se ha generado un borrador para este caso.")

with col_aprobar:
    with st.container(border=True):
        st.subheader("Aprobar borrador")
        hay_borrador = bool(expediente.get("borrador"))
        if not hay_borrador:
            st.caption("Genera el borrador (columna izquierda) antes de poder aprobarlo.")
        aprobado_por = st.text_input("Nombre del operador que aprueba", disabled=not hay_borrador)
        observaciones = st.text_area("Observaciones", height=80, disabled=not hay_borrador)
        if st.button("Aprobar borrador", type="primary", disabled=not hay_borrador):
            if not aprobado_por:
                st.error("Ingresa el nombre del operador antes de aprobar.")
            else:
                resultado = post(
                    f"/casos/{caso_id}/aprobar",
                    {"aprobado_por": aprobado_por, "observaciones": observaciones or None},
                )
                st.success(f"Estado del caso: {resultado['estado']}")
                st.caption("Liquidación, transferencia y endoso quedan como propuesta pendiente. No se ejecuta nada en producción.")
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Expediente único — responsable, fecha, observaciones e historial completo
# ---------------------------------------------------------------------------

st.header("Expediente del caso")
with st.container(border=True):
    st.caption("Responsable, fecha, observaciones y documentos quedan aquí como respaldo del proceso.")
    st.write(f"**Estado actual:** {expediente['estado']}")
    st.write("**Historial:**")
    for evento in expediente["historial"]:
        st.write(f"- {evento['evento']}" + (f" — {evento['detalle']}" if evento.get("detalle") else ""))
