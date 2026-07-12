import os

import pytest


def test_extraccion_sin_api_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    archivo = ("nota.png", b"contenido-no-relevante-para-esta-prueba", "image/png")
    respuesta = client.post("/extraccion/documento", files={"archivo": archivo})
    assert respuesta.status_code == 200
    assert "ANTHROPIC_API_KEY" in respuesta.json()["error"]


def test_extraccion_tipo_no_soportado(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-clave-de-prueba-no-real")
    archivo = ("documento.txt", b"contenido de texto plano", "text/plain")
    respuesta = client.post("/extraccion/documento", files={"archivo": archivo})
    assert respuesta.status_code == 200
    assert "no soportado" in respuesta.json()["error"]


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="Requiere una ANTHROPIC_API_KEY real para probar la extracción end-to-end",
)
def test_extraccion_real_con_imagen_de_prueba(client):
    ruta_imagen = os.path.join(os.path.dirname(__file__), "..", "..", "nota_credito_prueba.png")
    with open(ruta_imagen, "rb") as f:
        respuesta = client.post(
            "/extraccion/documento",
            files={"archivo": ("nota_credito_prueba.png", f.read(), "image/png")},
        )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert "error" not in datos
    assert datos["ruc"] == "1792345678001"
