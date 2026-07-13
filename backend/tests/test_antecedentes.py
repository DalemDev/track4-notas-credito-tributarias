def test_antecedentes_ruc_conocido(client, crear_antecedente):
    crear_antecedente(ruc="1791234567011")
    caso = client.post("/casos", json={
        "titular": "Comercial Andina S.A.",
        "ruc": "1791234567011",  # RUC con antecedente sembrado por la fixture
        "numero_titulo": "SRI-NC-TEST-ANTECEDENTES",
        "tipo_nota": "Reintegro IVA exportador",
        "valor_nominal": 100.0,
        "saldo": 100.0,
    }).json()

    antecedentes = client.get(f"/casos/{caso['caso_id']}/antecedentes").json()
    assert len(antecedentes) > 0
    assert all(a["ruc"] == "1791234567011" for a in antecedentes)


def test_antecedentes_ruc_desconocido(client):
    caso = client.post("/casos", json={
        "titular": "Empresa Sin Historial SA",
        "ruc": "1700000000001",
        "numero_titulo": "SRI-NC-TEST-SIN-HISTORIAL",
        "tipo_nota": "Reintegro renta",
        "valor_nominal": 100.0,
        "saldo": 100.0,
    }).json()

    antecedentes = client.get(f"/casos/{caso['caso_id']}/antecedentes").json()
    assert antecedentes == []


def test_antecedentes_caso_no_encontrado(client):
    respuesta = client.get("/casos/NC-NO-EXISTE/antecedentes")
    assert respuesta.status_code == 404


def test_antecedentes_exactos_estan_etiquetados(client, crear_antecedente):
    crear_antecedente(ruc="1791234567022")
    caso = client.post("/casos", json={
        "titular": "Comercial Andina S.A.",
        "ruc": "1791234567022",
        "numero_titulo": "SRI-NC-TEST-ETIQUETA",
        "tipo_nota": "Reintegro IVA exportador",
        "valor_nominal": 100.0,
        "saldo": 100.0,
    }).json()

    antecedentes = client.get(f"/casos/{caso['caso_id']}/antecedentes").json()
    assert len(antecedentes) > 0
    assert all(a["tipo_coincidencia"] == "exacta" for a in antecedentes)
