import csv
import json
from pathlib import Path

from sqlalchemy import select

from database import Base, SessionLocal, engine
from db_models import AntecedenteORM, CasoORM, EventoORM, ExpedienteORM

DATA_DIR = Path(__file__).parent / "data"

# --- Fuente de referencia externa simulada (no es "estado" de la app) ---
# En un entorno real sería una consulta al SRI, por eso sigue siendo un
# dato estático de solo lectura en vez de vivir en la base de datos propia
# del sistema.

with open(DATA_DIR / "estado_sri_simulado.csv", encoding="utf-8") as f:
    ESTADO_SRI = {row["numero_titulo"]: row for row in csv.DictReader(f)}

# --- Estado propio de la aplicación: persistente en SQLite vía SQLAlchemy ---
# Sobrevive a reinicios del servidor y es consistente sin importar el canal
# (Streamlit hoy, cualquier otro cliente de la API mañana) que la consuma.
# A diferencia del SRI, los antecedentes históricos SÍ son propiedad de la
# organización (su propio historial), así que viven en la base de datos:
# antecedentes_historicos.csv solo se usa como semilla inicial, una única vez.

Base.metadata.create_all(bind=engine)


def _sembrar_antecedentes_si_vacio():
    with SessionLocal() as session:
        si_ya_hay_datos = session.scalars(select(AntecedenteORM)).first()
        if si_ya_hay_datos:
            return
        with open(DATA_DIR / "antecedentes_historicos.csv", encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        for fila in filas:
            session.add(AntecedenteORM(**fila))
        session.commit()


_sembrar_antecedentes_si_vacio()


def _caso_a_dict(caso: CasoORM) -> dict:
    return {
        "caso_id": caso.caso_id,
        "numero_titulo": caso.numero_titulo,
        "titular": caso.titular,
        "ruc": caso.ruc,
        "tipo_nota": caso.tipo_nota,
        "valor_nominal": caso.valor_nominal,
        "saldo": caso.saldo,
        "documento_respaldo": caso.documento_respaldo,
        "fecha_ingreso": caso.fecha_ingreso,
    }


def listar_casos() -> list[dict]:
    with SessionLocal() as session:
        casos = session.scalars(select(CasoORM)).all()
        return [_caso_a_dict(c) for c in casos]


def obtener_caso(caso_id: str) -> dict | None:
    with SessionLocal() as session:
        caso = session.get(CasoORM, caso_id)
        return _caso_a_dict(caso) if caso else None


def existe_caso(caso_id: str) -> bool:
    return obtener_caso(caso_id) is not None


def contar_casos_del_anio(anio: int) -> int:
    with SessionLocal() as session:
        casos = session.scalars(
            select(CasoORM).where(CasoORM.caso_id.like(f"NC-{anio}-%"))
        ).all()
        return len(casos)


def crear_caso(datos: dict) -> dict:
    with SessionLocal() as session:
        caso = CasoORM(**datos)
        session.add(caso)
        session.add(ExpedienteORM(caso_id=datos["caso_id"], estado="ingresado", datos_confirmados="{}"))
        session.add(EventoORM(caso_id=datos["caso_id"], evento="caso_ingresado"))
        session.commit()
        session.refresh(caso)
        return _caso_a_dict(caso)


def buscar_duplicados_titulo(numero_titulo: str, excluir_caso_id: str) -> list[str]:
    with SessionLocal() as session:
        casos = session.scalars(
            select(CasoORM).where(
                CasoORM.numero_titulo == numero_titulo,
                CasoORM.caso_id != excluir_caso_id,
            )
        ).all()
        return [c.caso_id for c in casos]


def _expediente_a_dict(expediente: ExpedienteORM, historial: list[dict]) -> dict:
    return {
        "caso_id": expediente.caso_id,
        "estado": expediente.estado,
        "datos_confirmados": json.loads(expediente.datos_confirmados or "{}"),
        "alertas": json.loads(expediente.alertas) if expediente.alertas else [],
        "siguiente_paso": json.loads(expediente.siguiente_paso) if expediente.siguiente_paso else None,
        "borrador": expediente.borrador,
        "historial": historial,
    }


def _historial_del_caso(session, caso_id: str) -> list[dict]:
    eventos = session.scalars(
        select(EventoORM).where(EventoORM.caso_id == caso_id).order_by(EventoORM.id)
    ).all()
    return [
        {
            "evento": ev.evento,
            "detalle": ev.detalle,
            "fecha": ev.fecha.isoformat() if ev.fecha else None,
        }
        for ev in eventos
    ]


def get_or_crear_expediente(caso_id: str) -> dict:
    """Cada caso tiene un expediente único que acumula responsable, fecha,
    observaciones y documentos a lo largo de HU1 -> HU2 -> HU3 (criterio de HU3).
    Persistente: no se pierde al reiniciar el servidor."""
    with SessionLocal() as session:
        expediente = session.get(ExpedienteORM, caso_id)
        if not expediente:
            expediente = ExpedienteORM(caso_id=caso_id, estado="ingresado", datos_confirmados="{}")
            session.add(expediente)
            session.add(EventoORM(caso_id=caso_id, evento="caso_ingresado"))
            session.commit()
            session.refresh(expediente)
        historial = _historial_del_caso(session, caso_id)
        return _expediente_a_dict(expediente, historial)


def actualizar_expediente(caso_id: str, **cambios) -> dict:
    """Persiste cambios sobre el expediente (estado, datos_confirmados,
    alertas, siguiente_paso, borrador) y devuelve el expediente actualizado."""
    with SessionLocal() as session:
        expediente = session.get(ExpedienteORM, caso_id)
        for campo, valor in cambios.items():
            if campo in ("datos_confirmados", "alertas", "siguiente_paso"):
                valor = json.dumps(valor, ensure_ascii=False)
            setattr(expediente, campo, valor)
        session.commit()
        session.refresh(expediente)
        historial = _historial_del_caso(session, caso_id)
        return _expediente_a_dict(expediente, historial)


def registrar_evento(caso_id: str, evento: str, detalle: str | None = None):
    with SessionLocal() as session:
        session.add(EventoORM(caso_id=caso_id, evento=evento, detalle=detalle))
        session.commit()


def _antecedente_a_dict(a: AntecedenteORM) -> dict:
    return {
        "ruc": a.ruc,
        "titular": a.titular,
        "numero_titulo_anterior": a.numero_titulo_anterior,
        "dato": a.dato,
        "valor_dato": a.valor_dato,
        "fecha_validacion": a.fecha_validacion,
        "fuente": a.fuente,
        "estado": a.estado,
    }


def listar_antecedentes() -> list[dict]:
    with SessionLocal() as session:
        antecedentes = session.scalars(select(AntecedenteORM)).all()
        return [_antecedente_a_dict(a) for a in antecedentes]
