import os
import tempfile

import pytest

# Base de datos SQLite temporal y aislada para las pruebas — nunca la base
# de datos real de desarrollo (sri_notas.db). Se fija ANTES de importar
# cualquier módulo de la app para que database.py la recoja al arrancar.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def crear_antecedente():
    """Inserta un antecedente directo en la base de datos de prueba. No hay
    endpoint de API para esto — los antecedentes se acumulan con el uso real,
    o se sembraban desde un CSV que ahora es opcional (data_store.py arranca
    igual si no existe). Las pruebas que necesitan un antecedente preexistente
    lo insertan directamente en vez de depender de ese seed."""
    from database import SessionLocal
    from db_models import AntecedenteORM

    def _crear(**overrides):
        datos = {
            "ruc": "1791234567001",
            "titular": "Comercial Andina S.A.",
            "numero_titulo_anterior": "SRI-NC-77120",
            "dato": "cuenta_bancaria",
            "valor_dato": "Banco Pichincha - 220456789",
            "fecha_validacion": "2026-05-14",
            "fuente": "Validacion manual anterior",
            "estado": "confiable",
        }
        datos.update(overrides)
        with SessionLocal() as session:
            session.add(AntecedenteORM(**datos))
            session.commit()

    return _crear


def pytest_sessionfinish(session, exitstatus):
    os.close(_db_fd)
    try:
        os.remove(_db_path)
    except OSError:
        pass
