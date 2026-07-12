def test_flujo_completo_hu1_hu2_hu3(client):
    # HU1: crear caso
    caso = client.post("/casos", json={
        "titular": "Flujo Completo SA",
        "ruc": "1791234567001",
        "numero_titulo": "SRI-NC-88231",
        "tipo_nota": "Reintegro IVA exportador",
        "valor_nominal": 45230.50,
        "saldo": 45230.50,
    }).json()
    caso_id = caso["caso_id"]

    # HU1: antecedentes reutilizables + confirmar
    antecedentes = client.get(f"/casos/{caso_id}/antecedentes").json()
    assert len(antecedentes) > 0

    decisiones = [
        {"dato": a["dato"], "accion": "confirmar", "valor_final": a["valor_dato"]}
        for a in antecedentes
    ]
    expediente = client.post(f"/casos/{caso_id}/confirmar", json={"decisiones": decisiones}).json()
    assert expediente["estado"] == "datos_confirmados"
    assert len(expediente["datos_confirmados"]) == len(antecedentes)

    # HU2: validar (título vigente, saldo coincide -> sin hallazgos)
    resultado_validacion = client.post(f"/casos/{caso_id}/validar").json()
    assert resultado_validacion["alertas"] == []

    # HU3: generar borrador
    resultado_borrador = client.post(f"/casos/{caso_id}/borrador").json()
    assert resultado_borrador["estado"] == "pendiente_de_aprobacion"
    assert "PROPUESTA" in resultado_borrador["borrador"]

    # HU3: aprobar
    resultado_aprobar = client.post(f"/casos/{caso_id}/aprobar", json={
        "aprobado_por": "Operador Test",
        "observaciones": "Todo en orden",
    }).json()
    assert resultado_aprobar["estado"] == "aprobado_pendiente_liquidacion"

    # El expediente persiste el historial completo, con marca de tiempo por evento
    expediente_final = client.get(f"/expediente/{caso_id}").json()
    eventos = [e["evento"] for e in expediente_final["historial"]]
    assert "caso_ingresado" in eventos
    assert "validacion_ejecutada" in eventos
    assert "borrador_generado" in eventos
    assert "borrador_aprobado" in eventos
    assert all(e.get("fecha") for e in expediente_final["historial"])


def test_aprobar_sin_borrador_falla(client):
    caso = client.post("/casos", json={
        "titular": "Sin Borrador SA",
        "ruc": "1700000000003",
        "numero_titulo": "SRI-NC-SIN-BORRADOR",
        "tipo_nota": "Reintegro renta",
        "valor_nominal": 100.0,
        "saldo": 100.0,
    }).json()

    respuesta = client.post(f"/casos/{caso['caso_id']}/aprobar", json={"aprobado_por": "Operador Test"})
    assert respuesta.status_code == 400
