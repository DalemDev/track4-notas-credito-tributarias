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


def pytest_sessionfinish(session, exitstatus):
    os.close(_db_fd)
    try:
        os.remove(_db_path)
    except OSError:
        pass
