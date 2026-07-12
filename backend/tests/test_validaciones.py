def _crear_caso(client, **overrides):
    datos = {
        "titular": "Caso de prueba SA",
        "ruc": "1700000000002",
        "numero_titulo": "SRI-NC-DEFAULT",
        "tipo_nota": "Reintegro IVA exportador",
        "valor_nominal": 1000.0,
        "saldo": 1000.0,
    }
    datos.update(overrides)
    return client.post("/casos", json=datos).json()


def test_validacion_titulo_bloqueado(client):
    # SRI-NC-92004 está marcado como bloqueado en estado_sri_simulado.csv
    caso = _crear_caso(client, numero_titulo="SRI-NC-92004", saldo=33750.00)
    resultado = client.post(f"/casos/{caso['caso_id']}/validar").json()
    tipos = {a["tipo"] for a in resultado["alertas"]}
    assert "bloqueo" in tipos
    assert resultado["siguiente_paso"]["accion"] == "enviar_a_cumplimiento"


def test_validacion_saldo_inconsistente(client):
    # SRI-NC-88450 tiene saldo_disponible_sri = 9600.00; enviamos un saldo distinto
    caso = _crear_caso(client, numero_titulo="SRI-NC-88450", saldo=1.0)
    resultado = client.post(f"/casos/{caso['caso_id']}/validar").json()
    tipos = {a["tipo"] for a in resultado["alertas"]}
    assert "inconsistencia_saldo" in tipos


def test_validacion_no_encontrado_en_sri(client):
    caso = _crear_caso(client, numero_titulo="SRI-NC-NO-EXISTE-999")
    resultado = client.post(f"/casos/{caso['caso_id']}/validar").json()
    tipos = {a["tipo"] for a in resultado["alertas"]}
    assert "no_encontrado_en_sri" in tipos
    assert resultado["siguiente_paso"]["accion"] == "solicitar_documento"


def test_validacion_duplicado(client):
    numero_titulo = "SRI-NC-DUPLICADO-TEST"
    caso_1 = _crear_caso(client, numero_titulo=numero_titulo)
    caso_2 = _crear_caso(client, numero_titulo=numero_titulo)

    resultado = client.post(f"/casos/{caso_2['caso_id']}/validar").json()
    alertas_duplicado = [a for a in resultado["alertas"] if a["tipo"] == "duplicado"]
    assert len(alertas_duplicado) == 1
    assert caso_1["caso_id"] in alertas_duplicado[0]["detalle"]
    assert resultado["siguiente_paso"]["accion"] == "solicitar_revision_duplicado"


def test_validacion_sin_hallazgos(client):
    # SRI-NC-90112: vigente, sin bloqueo, saldo coincide exactamente.
    # No se reutiliza en ninguna otra prueba para no disparar la alerta de duplicado.
    caso = _crear_caso(client, numero_titulo="SRI-NC-90112", saldo=78900.00)
    resultado = client.post(f"/casos/{caso['caso_id']}/validar").json()
    assert resultado["alertas"] == []
    assert resultado["siguiente_paso"]["accion"] == "continuar"


def test_validar_caso_no_encontrado(client):
    respuesta = client.post("/casos/NC-NO-EXISTE/validar")
    assert respuesta.status_code == 404
