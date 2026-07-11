from pydantic import BaseModel
from typing import Optional, Literal


class DecisionDato(BaseModel):
    """Una decisión del operador sobre un dato sugerido (HU1).
    Nunca se aplica un dato sin que el operador pase por aquí."""
    dato: str
    accion: Literal["confirmar", "editar", "rechazar"]
    valor_final: Optional[str] = None


class ConfirmacionRequest(BaseModel):
    decisiones: list[DecisionDato]


class AprobarBorradorRequest(BaseModel):
    aprobado_por: str
    observaciones: Optional[str] = None


class NuevoCasoRequest(BaseModel):
    """Datos del caso inicial, extraídos de un documento con IA o ingresados
    manualmente por el operador (criterio de HU1: 'extrae o recibe datos...
    para comenzar el caso con datos confiables')."""
    titular: str
    ruc: str
    numero_titulo: str
    tipo_nota: str
    valor_nominal: float
    saldo: float
    documento_respaldo: Optional[str] = None
