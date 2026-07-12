import json
from types import SimpleNamespace

import services

CANDIDATO_FALSO = {
    "ruc": "999",
    "numero_titulo_anterior": None,
    "dato": "x",
    "valor_dato": "y",
    "titular": "Empresa Parecida SA",
    "fecha_validacion": "2026-01-01",
    "fuente": "test",
    "estado": "confiable",
    "similitud": 90.0,
}


class _RespuestaFalsa:
    def __init__(self, contenido_json, stop_reason="end_turn"):
        self.content = [SimpleNamespace(type="text", text=json.dumps(contenido_json))]
        self.stop_reason = stop_reason


class _ClienteFalso:
    def __init__(self, respuesta):
        self.messages = SimpleNamespace(create=lambda **kwargs: respuesta)


def test_guardrail_descarta_indice_fuera_de_rango(monkeypatch):
    """Simula que Claude 'alucina' un índice (2) que no existe en la lista
    recuperada (solo hay un candidato, índice 0) — el guardrail debe
    descartarlo silenciosamente en vez de devolver una coincidencia inventada."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-clave-de-prueba")
    respuesta_falsa = _RespuestaFalsa({"coincidencias": [
        {"indice": 2, "es_relevante": True, "razon": "índice inventado, fuera de rango"},
    ]})
    monkeypatch.setattr(services.anthropic, "Anthropic", lambda api_key: _ClienteFalso(respuesta_falsa))
    monkeypatch.setattr(services, "_candidatos_por_similitud", lambda titular, antecedentes, ya_vistos: [CANDIDATO_FALSO])

    resultado = services.buscar_coincidencias_aproximadas("Empresa Parecida SA", [])
    assert resultado == []


def test_guardrail_acepta_indice_valido_y_relevante(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-clave-de-prueba")
    respuesta_falsa = _RespuestaFalsa({"coincidencias": [
        {"indice": 0, "es_relevante": True, "razon": "mismo nombre con variación menor"},
    ]})
    monkeypatch.setattr(services.anthropic, "Anthropic", lambda api_key: _ClienteFalso(respuesta_falsa))
    monkeypatch.setattr(services, "_candidatos_por_similitud", lambda titular, antecedentes, ya_vistos: [CANDIDATO_FALSO])

    resultado = services.buscar_coincidencias_aproximadas("Empresa Parecida SA", [])
    assert len(resultado) == 1
    assert resultado[0]["tipo_coincidencia"] == "aproximada"
    assert resultado[0]["razon"] == "mismo nombre con variación menor"


def test_guardrail_descarta_si_no_es_relevante(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-clave-de-prueba")
    respuesta_falsa = _RespuestaFalsa({"coincidencias": [
        {"indice": 0, "es_relevante": False, "razon": "nombre distinto, coincidencia irrelevante"},
    ]})
    monkeypatch.setattr(services.anthropic, "Anthropic", lambda api_key: _ClienteFalso(respuesta_falsa))
    monkeypatch.setattr(services, "_candidatos_por_similitud", lambda titular, antecedentes, ya_vistos: [CANDIDATO_FALSO])

    resultado = services.buscar_coincidencias_aproximadas("Empresa Parecida SA", [])
    assert resultado == []


def test_sin_candidatos_no_llama_a_claude(monkeypatch):
    """Sin candidatos recuperados por similitud, nunca se llama a Claude —
    la ausencia de retrieval implica ausencia total de generación."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-clave-de-prueba")
    monkeypatch.setattr(services, "_candidatos_por_similitud", lambda titular, antecedentes, ya_vistos: [])

    def _no_deberia_llamarse(**kwargs):
        raise AssertionError("no debería llamarse a Claude sin candidatos recuperados")

    monkeypatch.setattr(
        services.anthropic, "Anthropic",
        lambda api_key: SimpleNamespace(messages=SimpleNamespace(create=_no_deberia_llamarse)),
    )

    resultado = services.buscar_coincidencias_aproximadas("Cualquiera", [])
    assert resultado == []


def test_sin_api_key_no_muestra_coincidencias_aproximadas(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(services, "_candidatos_por_similitud", lambda titular, antecedentes, ya_vistos: [CANDIDATO_FALSO])

    resultado = services.buscar_coincidencias_aproximadas("Empresa Parecida SA", [])
    assert resultado == []
