def test_crear_y_listar_caso(client):
    respuesta = client.post("/casos", json={
        "titular": "Empresa Test SA",
        "ruc": "1799999999001",
        "numero_titulo": "SRI-NC-TEST-CASOS",
        "tipo_nota": "Reintegro IVA exportador",
        "valor_nominal": 1000.0,
        "saldo": 1000.0,
    })
    assert respuesta.status_code == 200
    caso = respuesta.json()
    assert caso["caso_id"].startswith("NC-")
    assert caso["titular"] == "Empresa Test SA"

    listado = client.get("/casos").json()
    assert any(c["caso_id"] == caso["caso_id"] for c in listado)


def test_detalle_caso_no_encontrado(client):
    respuesta = client.get("/casos/NC-NO-EXISTE")
    assert respuesta.status_code == 404


def test_expediente_inicial_es_ingresado(client):
    caso = client.post("/casos", json={
        "titular": "Otra Empresa SA",
        "ruc": "1788888888001",
        "numero_titulo": "SRI-NC-TEST-EXPEDIENTE",
        "tipo_nota": "Reintegro renta",
        "valor_nominal": 500.0,
        "saldo": 500.0,
    }).json()

    expediente = client.get(f"/expediente/{caso['caso_id']}").json()
    assert expediente["estado"] == "ingresado"
    assert expediente["historial"][0]["evento"] == "caso_ingresado"
