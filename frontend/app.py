import uuid

import streamlit as st
import requests

API_URL = "https://track4-notas-credito-tributarias.onrender.com"

# Webhook del Chat Trigger del workflow de n8n "Asistente de Ayuda - Validacion
# Notas de Credito". El asistente vive en n8n; el frontend solo envia la pregunta
# del operador + el contexto del caso actual y muestra la respuesta.
N8N_CHAT_URL = "https://dasanza.app.n8n.cloud/webhook/3b6f31d2-344d-49c3-9956-d42e7d478071/chat"

st.set_page_config(page_title="Track 4 - Notas de crédito tributarias", layout="wide")

# ---------------------------------------------------------------------------
# Paleta e identidad visual
# ---------------------------------------------------------------------------

NAVY = "#15151F"
NAVY_LIGHT = "#2A2A38"
MINT_BG = "#DCFCE7"
MINT_BORDER = "#86EFAC"
MINT_TEXT = "#166534"
MINT_SOLID = "#22C55E"
GRAY_BG = "#F3F4F6"
GRAY_TEXT = "#9CA3AF"
TEXT_DARK = "#111827"


def inyectar_estilos():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
        }}

        /* Fuerza la paleta clara sin depender de que el tema activo de Streamlit
           sea "light" (algunos entornos de despliegue no leen .streamlit/config.toml
           si el proceso arranca con otro directorio de trabajo, y Streamlit cae
           entonces a su propio tema por defecto según el navegador del visitante). */
        [data-testid="stAppViewContainer"],
        [data-testid="stHeader"],
        [data-testid="stBottomBlockContainer"],
        .main {{
            background-color: #ffffff !important;
        }}

        /* Texto por defecto del área principal (nunca el sidebar, que ya tiene
           su propio contraste explícito, ni los botones, que definen su propio
           par fondo/texto justo abajo — si no se excluyen, un botón con fondo
           oscuro terminaría con texto oscuro encima, ilegible). */
        .main p,
        .main span,
        .main label,
        .main li,
        .main h1, .main h2, .main h3, .main h4, .main h5, .main h6,
        .main [data-testid="stMarkdownContainer"] {{
            color: #111827;
        }}

        /* Botones del área principal: fondo Y texto explícitos por tipo, para
           que sean legibles sin importar el tema activo de Streamlit. */
        .main button[kind="primary"] {{
            background-color: {NAVY} !important;
        }}
        .main button[kind="primary"],
        .main button[kind="primary"] * {{
            color: #ffffff !important;
        }}
        .main button:not([kind="primary"]):not([kind="header"]) {{
            background-color: #ffffff !important;
            border: 1px solid #D1D5DB !important;
        }}
        .main button:not([kind="primary"]):not([kind="header"]),
        .main button:not([kind="primary"]):not([kind="header"]) * {{
            color: #111827 !important;
        }}

        section[data-testid="stSidebar"] {{
            background-color: {NAVY};
        }}
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] h4,
        section[data-testid="stSidebar"] h5,
        section[data-testid="stSidebar"] h6,
        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
            color: #E5E7EB !important;
        }}

        /* Asegurar contraste de inputs y selectbox: fondo Y texto explícitos,
           para que sea legible sin importar el tema activo de Streamlit. */
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
        section[data-testid="stSidebar"] div[role="combobox"],
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] select,
        section[data-testid="stSidebar"] textarea {{
            background-color: #ffffff !important;
            color: #111827 !important;
        }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] *,
        section[data-testid="stSidebar"] div[role="combobox"] * {{
            color: #111827 !important;
        }}

        /* El menú desplegable del selectbox se "portaliza" fuera del sidebar
           (BaseWeb lo monta directo en <body>), así que necesita su propia regla. */
        div[data-baseweb="popover"] ul[role="listbox"] {{
            background-color: #ffffff !important;
        }}
        div[data-baseweb="popover"] ul[role="listbox"] li,
        div[data-baseweb="popover"] ul[role="listbox"] li * {{
            color: #111827 !important;
        }}

        section[data-testid="stSidebar"] hr {{
            border-color: {NAVY_LIGHT};
        }}

        /* Botones del Sidebar */
        section[data-testid="stSidebar"] button {{
            background-color: transparent !important;
            border: 1px solid {NAVY_LIGHT} !important;
            color: #C7C7D1 !important;
            font-weight: 500 !important;
        }}
        section[data-testid="stSidebar"] button:hover {{
            border-color: {MINT_SOLID} !important;
            color: #ffffff !important;
            background-color: transparent !important;
        }}
        section[data-testid="stSidebar"] button * {{
            color: inherit !important;
        }}

        /* Estilos del Stepper Vertical en la pantalla principal */
        div:has(div.stepper-layout-anchor) + div div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child button {{
            display: flex !important;
            align-items: center !important;
            justify-content: flex-start !important;
            width: 100% !important;
            height: auto !important;
            padding: 12px 16px !important;
            margin-bottom: 8px !important;
            border: none !important;
            border-radius: 6px !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            text-align: left !important;
            transition: all 0.2s ease !important;
            box-shadow: none !important;
        }}

        /* Inactivo / Pendiente (Secondary) */
        div:has(div.stepper-layout-anchor) + div div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child button[class*="stBaseButton-secondary"] {{
            background-color: transparent !important;
            color: #4B5563 !important;
        }}

        div:has(div.stepper-layout-anchor) + div div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child button[class*="stBaseButton-secondary"]:hover {{
            background-color: #F3F4F6 !important;
            color: #111827 !important;
        }}

        /* Activo (Primary) */
        div:has(div.stepper-layout-anchor) + div div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child button[class*="stBaseButton-primary"] {{
            background-color: {MINT_BG} !important;
            color: {MINT_TEXT} !important;
            border-left: 4px solid {MINT_SOLID} !important;
            border-radius: 0px 6px 6px 0px !important;
            font-weight: 600 !important;
        }}

        div:has(div.stepper-layout-anchor) + div div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child button[class*="stBaseButton-primary"]:hover {{
            background-color: {MINT_BG} !important;
            color: {MINT_TEXT} !important;
        }}

        /* Sticky Header */
        div:has(div.sticky-header-anchor) + div {{
            position: sticky !important;
            top: 2.875rem !important;
            background-color: #ffffff !important;
            z-index: 99 !important;
            padding: 16px 0 !important;
            border-bottom: 1px solid #E5E7EB !important;
            margin-bottom: 24px !important;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
        }}

        .sticky-header h2 {{
            margin: 0 !important;
            font-size: 1.35rem !important;
            font-weight: 700 !important;
            color: #111827 !important;
            letter-spacing: -0.02em !important;
        }}

        .sticky-header p {{
            margin: 2px 0 0 0 !important;
            font-size: 0.8rem !important;
            color: #4B5563 !important;
        }}

        /* Botón flotante de ayuda (FAB): se fija el CONTENEDOR del popover (único en
           la app) abajo a la derecha — BaseWeb ancla el panel a este contenedor, así
           el chat abre pegado al botón. El cuerpo del popover se portaliza aparte
           (stPopoverBody), por lo que estos selectores NO afectan a los botones del panel. */
        div[data-testid="stPopover"] {{
            position: fixed !important;
            bottom: 24px !important;
            right: 24px !important;
            width: auto !important;
            z-index: 1000 !important;
        }}
        div[data-testid="stPopover"] button {{
            width: auto !important;
            background-color: {MINT_SOLID} !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 999px !important;
            padding: 12px 22px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18) !important;
        }}
        div[data-testid="stPopover"] button:hover {{
            background-color: {MINT_TEXT} !important;
            color: #ffffff !important;
        }}
        div[data-testid="stPopover"] button * {{
            color: inherit !important;
        }}

        /* Panel del chat: popover nativo de Streamlit (posicionado por el framework) */
        div[data-testid="stPopoverBody"] {{
            width: 384px !important;
            max-width: calc(100vw - 40px) !important;
        }}
        .chat-panel-title {{
            font-weight: 700 !important;
            font-size: 1.05rem !important;
            color: {TEXT_DARK} !important;
            margin: 0 0 2px 0 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_encabezado_paso(numero, total, titulo):
    """Etiqueta pequeña en mayúsculas + título grande — jerarquía tipográfica
    de dos niveles, en vez de un único encabezado plano."""
    st.markdown(
        f'<p style="color:{MINT_TEXT}; font-weight:700; letter-spacing:0.08em; '
        f'text-transform:uppercase; font-size:0.78rem; margin-bottom:2px;">'
        f'Paso {numero} de {total}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<h2 style="margin-top:0; color:{TEXT_DARK};">{titulo}</h2>', unsafe_allow_html=True)


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


def post_n8n(mensaje, session_id, contexto):
    """Envía la pregunta del operador al webhook del Chat Trigger de n8n y
    devuelve el texto de la respuesta del agente. A diferencia de get()/post(),
    NO llama a st.stop(): un fallo del asistente no debe tumbar el wizard."""
    payload = {
        "action": "sendMessage",
        "chatInput": mensaje,
        "sessionId": session_id,
        "contexto": contexto or {},
    }
    try:
        r = requests.post(N8N_CHAT_URL, json=payload, timeout=45)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.error(f"No se pudo consultar al asistente de ayuda: {e}")
        return None

    try:
        data = r.json()
    except ValueError:
        return r.text or None

    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict):
        return data.get("output") or data.get("text") or data.get("response") or str(data)
    return str(data)


def render_asistente():
    """Botón flotante de ayuda (FAB) + panel de chat vía st.popover. El asistente
    responde a través del workflow de n8n usando el contexto del caso actual
    (st.session_state['contexto_asistente']). Global a todos los pasos y vistas."""
    st.session_state.setdefault("chat_historia", [])
    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = str(uuid.uuid4())

    # El FAB es el propio disparador del popover; el CSS fija su contenedor abajo-derecha.
    with st.popover("💬  ¿Necesitas ayuda?", use_container_width=False):
        st.markdown('<p class="chat-panel-title">Asistente de validación</p>', unsafe_allow_html=True)
        st.caption("Resuelvo dudas del proceso de validación y de tu caso actual.")

        # Historial en un contenedor scrollable de altura fija (se rellena tras
        # procesar el envío, para que el último intercambio se vea de inmediato).
        hist_box = st.container(height=280)

        with st.form("chat_form", clear_on_submit=True):
            pregunta = st.text_input(
                "Tu pregunta",
                label_visibility="collapsed",
                placeholder="Escribe tu pregunta...",
            )
            enviado = st.form_submit_button("Enviar", type="primary", use_container_width=True)

        if enviado and pregunta.strip():
            st.session_state.chat_historia.append({"role": "user", "content": pregunta.strip()})
            with st.spinner("Consultando al asistente..."):
                respuesta = post_n8n(
                    pregunta.strip(),
                    st.session_state.chat_session_id,
                    st.session_state.get("contexto_asistente", {}),
                )
            if not respuesta:
                respuesta = (
                    "⚠️ No pude conectar con el asistente en este momento. Verifica que el "
                    "workflow de n8n esté publicado e inténtalo de nuevo."
                )
            st.session_state.chat_historia.append({"role": "assistant", "content": respuesta})

        with hist_box:
            if not st.session_state.chat_historia:
                st.info("Hola 👋 Pregúntame sobre las alertas, los pasos del proceso o qué hacer con tu caso.")
            for mensaje in st.session_state.chat_historia:
                with st.chat_message(mensaje["role"]):
                    st.markdown(mensaje["content"])


def ir_al_paso(indice):
    st.session_state.paso_actual = indice


def render_stepper(pasos, indice_actual):
    """Barra de pasos horizontal (lo más cercano a un 'stepper' con los
    componentes nativos de Streamlit): un círculo por paso, conectados por una
    línea, coloreados según su estado (completado/en curso/pendiente)."""
    piezas = []
    for i, titulo in enumerate(pasos):
        if i < indice_actual:
            color, estado, contenido = MINT_SOLID, "Completado", "&#10003;"
        elif i == indice_actual:
            color, estado, contenido = NAVY, "En curso", str(i + 1)
        else:
            color, estado, contenido = "#D1D5DB", "Pendiente", str(i + 1)
        color_texto = TEXT_DARK if i <= indice_actual else GRAY_TEXT

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
            linea_color = MINT_SOLID if i < indice_actual else "#D1D5DB"
            piezas.append(f'<div style="flex:1; height:2px; background:{linea_color}; margin-top:17px;"></div>')

    st.markdown(
        f'<div style="display:flex; align-items:flex-start; padding:8px 0 20px 0;">{"".join(piezas)}</div>',
        unsafe_allow_html=True,
    )


inyectar_estilos()

# Contexto que el asistente de ayuda (n8n) recibe en cada mensaje. Se rellena más
# abajo con el caso en pantalla; por defecto queda vacío (vista sin caso).
st.session_state["contexto_asistente"] = {}

# Mapea el estado del expediente (fuente de verdad: el backend) a un índice de
# paso (0-based) y un mensaje en lenguaje natural sobre qué hacer.
PASOS_STEPPER = ["Antecedentes", "Validación SRI", "Negociación", "Cierre"]
PASO_POR_ESTADO = {
    "ingresado": (0, "Revisa los antecedentes reutilizables sugeridos y confirma, edita o rechaza cada uno."),
    "datos_confirmados": (1, "Datos confirmados. Corre la validación contra el SRI."),
    "validado": (2, "Caso validado. Genera el borrador de la ficha de negociación."),
    "pendiente_de_aprobacion": (2, "Borrador generado. Revísalo y apruébalo."),
    "aprobado_pendiente_liquidacion": (3, "Caso aprobado. La liquidación, transferencia o endoso quedan pendientes como acción manual regulada — no se ejecutan en esta demo."),
}

st.markdown('<div class="sticky-header-anchor"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="sticky-header">
        <h2>Asistente de ingreso y negociación de notas de crédito</h2>
        <p>SRI Ecuador — acompaña al operador de principio a fin, con aprobación humana en cada paso.</p>
    </div>
    """,
    unsafe_allow_html=True
)

casos = get("/casos")

# 1. Definir caso_seleccionado en session_state si no existe
if "caso_seleccionado" not in st.session_state:
    if casos:
        st.session_state.caso_seleccionado = casos[0]["caso_id"]
    else:
        st.session_state.caso_seleccionado = "nuevo"

# 2. Renderizar sidebar
st.sidebar.header("Caso de trabajo")
if casos:
    if st.sidebar.button("➕ Crear nuevo caso", use_container_width=True):
        st.session_state.caso_seleccionado = "nuevo"
        st.session_state.pop("caso_recien_creado", None)
        st.rerun()

    opciones = {f"{c['caso_id']} — {c['titular']}": c["caso_id"] for c in casos}
    etiquetas = list(opciones.keys())
    ids_por_etiqueta = list(opciones.values())
    
    etiquetas_sidebar = ["-- Seleccionar caso --"] + etiquetas
    ids_sidebar = ["nuevo"] + ids_por_etiqueta

    # Determinar el índice por defecto del selectbox
    caso_recien_creado = st.session_state.get("caso_recien_creado")
    if caso_recien_creado in ids_por_etiqueta:
        st.session_state.caso_seleccionado = caso_recien_creado
        st.session_state.pop("caso_recien_creado", None)
        
    if st.session_state.caso_seleccionado == "nuevo":
        indice_default = 0
    else:
        indice_default = ids_sidebar.index(st.session_state.caso_seleccionado) if st.session_state.caso_seleccionado in ids_sidebar else 0

    seleccion = st.sidebar.selectbox("Selecciona un caso", etiquetas_sidebar, index=indice_default)
    caso_id = ids_sidebar[etiquetas_sidebar.index(seleccion)]
    
    if caso_id != st.session_state.caso_seleccionado:
        st.session_state.caso_seleccionado = caso_id
        st.rerun()
else:
    st.sidebar.info("Aún no hay casos ingresados. Sube un documento a la derecha para crear el primero.")
    st.session_state.caso_seleccionado = "nuevo"

# 3. Flujo condicional principal
if st.session_state.caso_seleccionado == "nuevo":
    # ---------------------------------------------------------------------------
    # Crear caso nuevo — punto de entrada de HU1: cargar el documento y dejar que
    # Claude extraiga los campos automáticamente.
    # ---------------------------------------------------------------------------
    st.session_state["contexto_asistente"] = {"vista": "creacion_de_caso_nuevo", "paso_actual": "Crear caso nuevo"}
    st.markdown('<h3 style="color:#111827; font-weight:600; font-size:1.2rem; margin-top:20px;">Crear caso nuevo desde un documento</h3>', unsafe_allow_html=True)
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
                st.session_state.caso_seleccionado = nuevo_caso["caso_id"]
                st.session_state.paso_actual = 0
                st.toast(f"Caso {nuevo_caso['caso_id']} creado.")
                st.rerun()

else:
    # ---------------------------------------------------------------------------
    # Flujo del proceso para el caso seleccionado
    # ---------------------------------------------------------------------------
    caso_id = st.session_state.caso_seleccionado
    caso = next((c for c in casos if c["caso_id"] == caso_id), None)
    if caso is None:
        st.session_state.caso_seleccionado = "nuevo"
        st.rerun()
        
    expediente = get(f"/expediente/{caso_id}")
    indice_sugerido, mensaje_guia = PASO_POR_ESTADO.get(
        expediente["estado"], (0, "Comienza revisando los antecedentes reutilizables.")
    )

    if "caso_actual" not in st.session_state or st.session_state.caso_actual != caso_id:
        st.session_state.decisiones = {}
        st.session_state.caso_actual = caso_id
        st.session_state.paso_actual = indice_sugerido

    paso_actual = st.session_state.get("paso_actual", indice_sugerido)

    # Contexto para el asistente de ayuda: el caso que el operador está viendo.
    st.session_state["contexto_asistente"] = {
        "caso_id": caso_id,
        "titular": caso.get("titular") if caso else None,
        "numero_titulo": caso.get("numero_titulo") if caso else None,
        "tipo_nota": caso.get("tipo_nota") if caso else None,
        "saldo_declarado": caso.get("saldo") if caso else None,
        "paso_actual": PASOS_STEPPER[paso_actual] if 0 <= paso_actual < len(PASOS_STEPPER) else None,
        "estado_expediente": expediente.get("estado"),
        "alertas": expediente.get("alertas") or [],
        "siguiente_paso": expediente.get("siguiente_paso"),
    }

    st.sidebar.divider()
    st.sidebar.caption(f"Estado interno: `{expediente['estado']}`")

    with st.sidebar.expander("Expediente e historial"):
        st.write(f"**Estado actual:** {expediente['estado']}")
        for evento in expediente["historial"]:
            st.write(f"- {evento['evento']}" + (f" — {evento['detalle']}" if evento.get("detalle") else ""))

    st.markdown('<div class="stepper-layout-anchor"></div>', unsafe_allow_html=True)

    col_stepper, col_content = st.columns([1, 2.5], gap="large")

    with col_stepper:
        st.markdown('<h3 style="margin-top:0; color:#111827; font-size:1.1rem; font-weight:600;">Progreso del Expediente</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color:#6B7280; font-size:0.8rem; margin-bottom:16px;">Sigue el flujo de trabajo guiado para procesar este caso.</p>', unsafe_allow_html=True)
        
        # Renderizar el stepper vertical
        for i, nombre_paso in enumerate(PASOS_STEPPER):
            if i < paso_actual:
                label = f"✓  {nombre_paso}"
            elif i == paso_actual:
                label = f"●  {nombre_paso}"
            else:
                label = f"○  {nombre_paso}"
                
            es_actual = (i == paso_actual)
            if st.button(
                label,
                key=f"stepper_btn_{i}",
                use_container_width=True,
                type="primary" if es_actual else "secondary"
            ):
                ir_al_paso(i)
                st.rerun()
                
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(f"**Sugerido:** {mensaje_guia}")

    with col_content:
        if paso_actual == 0:
            # Paso 1 — HU1: ingreso asistido y reutilización de antecedentes
            render_encabezado_paso(1, len(PASOS_STEPPER), "Ingreso asistido y antecedentes")
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
                                if a.get("tipo_coincidencia") == "aproximada":
                                    st.markdown(
                                        f":blue[**Coincidencia aproximada (IA)**] — {a.get('similitud', '?')}% de similitud "
                                        f"con **{a['titular']}** (RUC {a['ruc']})"
                                    )
                                    st.caption(f"Razón: {a.get('razon', 'sin detalle')}")
                                else:
                                    st.markdown(":green[**Coincidencia exacta**]")
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
                            st.toast("Decisiones guardadas en el expediente.")
                            ir_al_paso(1)  # completado -> avanza automáticamente al Paso 2
                            st.rerun()

        elif paso_actual == 1:
            # Paso 2 — HU2: validación y siguiente acción guiada
            render_encabezado_paso(2, len(PASOS_STEPPER), "Validación contra el SRI")
            with st.container(border=True):
                st.caption(
                    "Verifica existencia, saldo, estado y posibles bloqueos contra la fuente simulada del SRI, y "
                    "sugiere el siguiente paso. La decisión final siempre depende del operador."
                )

                if st.button("Validar caso", type="primary"):
                    post(f"/casos/{caso_id}/validar")
                    ir_al_paso(2)  # completado -> avanza automáticamente al Paso 3
                    st.rerun()

                if expediente.get("siguiente_paso") is not None:
                    if expediente["alertas"]:
                        for alerta in expediente["alertas"]:
                            st.warning(f"**{alerta['tipo']}**: {alerta['detalle']}")
                    else:
                        st.success("Sin hallazgos. El caso pasó todas las validaciones.")

                    paso = expediente["siguiente_paso"]
                    st.info(f"Siguiente paso sugerido: **{paso['accion']}** — {paso['motivo']}")
                    st.caption("Esta sugerencia requiere aprobación humana antes de ejecutarse.")
                else:
                    st.caption("Aún no se ha validado este caso.")

        elif paso_actual == 2:
            # Paso 3 — HU3: preparación de negociación y cierre asistido
            render_encabezado_paso(3, len(PASOS_STEPPER), "Negociación y cierre")
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
                            post(
                                f"/casos/{caso_id}/aprobar",
                                {"aprobado_por": aprobado_por, "observaciones": observaciones or None},
                            )
                            st.toast("Borrador aprobado. Liquidación, transferencia y endoso quedan como propuesta pendiente.")
                            ir_al_paso(3)  # completado -> avanza automáticamente al Cierre
                            st.rerun()

        else:
            # Paso 4 — Cierre: expediente final del caso
            render_encabezado_paso(4, len(PASOS_STEPPER), "Cierre del caso")
            with st.container(border=True):
                if expediente["estado"] == "aprobado_pendiente_liquidacion":
                    st.success("Caso aprobado. Liquidación, transferencia y endoso quedan como propuesta pendiente de acción manual regulada.")
                else:
                    st.info("Este caso todavía no ha sido aprobado — vuelve al Paso 3 para generar y aprobar el borrador.")
                st.write(f"**Estado actual:** {expediente['estado']}")
                st.write(f"**Borrador aprobado:**")
                st.text_area("Ficha de negociación", expediente.get("borrador") or "", height=220, disabled=True)
                st.write("**Historial completo:**")
                for evento in expediente["historial"]:
                    st.write(f"- {evento['evento']}" + (f" — {evento['detalle']}" if evento.get("detalle") else ""))

        st.markdown("<br>", unsafe_allow_html=True)
        st.divider()

        # ---------------------------------------------------------------------------
        # Navegación manual entre pasos
        # ---------------------------------------------------------------------------

        col_anterior, col_espacio, col_siguiente = st.columns([1, 3, 1])
        with col_anterior:
            if st.button("Anterior", disabled=paso_actual == 0, use_container_width=True):
                ir_al_paso(paso_actual - 1)
                st.rerun()
        with col_siguiente:
            if st.button("Siguiente", disabled=paso_actual == len(PASOS_STEPPER) - 1, use_container_width=True):
                ir_al_paso(paso_actual + 1)
                st.rerun()


# ---------------------------------------------------------------------------
# Asistente de ayuda flotante (global a todos los pasos y vistas)
# ---------------------------------------------------------------------------
render_asistente()
