from sqlalchemy import Column, String, Float, Text, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func

from database import Base


class CasoORM(Base):
    """Un caso (nota de crédito) tal como fue ingresado o creado desde un
    documento. Persistente: sobrevive a reinicios del servidor y es visible
    desde cualquier canal que consuma esta misma API."""
    __tablename__ = "casos"

    caso_id = Column(String, primary_key=True)
    numero_titulo = Column(String, nullable=False)
    titular = Column(String, nullable=False)
    ruc = Column(String, nullable=False)
    tipo_nota = Column(String, nullable=False)
    valor_nominal = Column(Float, nullable=False)
    saldo = Column(Float, nullable=False)
    documento_respaldo = Column(String, nullable=True)
    fecha_ingreso = Column(String, nullable=False)


class ExpedienteORM(Base):
    """Expediente único por caso (criterio de HU3): estado actual, datos
    confirmados, alertas y borrador. `datos_confirmados`/`alertas`/
    `siguiente_paso` se guardan como JSON serializado en un campo de texto."""
    __tablename__ = "expedientes"

    caso_id = Column(String, ForeignKey("casos.caso_id"), primary_key=True)
    estado = Column(String, nullable=False, default="ingresado")
    datos_confirmados = Column(Text, nullable=False, default="{}")
    alertas = Column(Text, nullable=True)
    siguiente_paso = Column(Text, nullable=True)
    borrador = Column(Text, nullable=True)


class EventoORM(Base):
    """Historial de eventos del expediente, con marca de tiempo real —
    reemplaza la lista embebida en memoria por un registro auditable y
    consultable de forma independiente."""
    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    caso_id = Column(String, ForeignKey("casos.caso_id"), nullable=False)
    evento = Column(String, nullable=False)
    detalle = Column(Text, nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())


class AntecedenteORM(Base):
    """Antecedentes históricos reutilizables (HU1). A diferencia de
    estado_sri_simulado.csv (fuente externa real simulada), este es el
    propio historial de la organización, por eso vive en la base de datos
    en vez de un CSV estático — se siembra una única vez desde
    antecedentes_historicos.csv la primera vez que se crea la tabla."""
    __tablename__ = "antecedentes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ruc = Column(String, nullable=False)
    titular = Column(String, nullable=False)
    numero_titulo_anterior = Column(String, nullable=True)
    dato = Column(String, nullable=False)
    valor_dato = Column(String, nullable=False)
    fecha_validacion = Column(String, nullable=False)
    fuente = Column(String, nullable=False)
    estado = Column(String, nullable=False)
