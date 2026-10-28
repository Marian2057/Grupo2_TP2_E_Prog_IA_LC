import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import logica
from main import app

DATOS = Path(__file__).resolve().parent.parent / "data" / "ventas.json"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    copia = tmp_path / "ventas.json"
    shutil.copy(DATOS, copia)
    monkeypatch.setattr(logica, "RUTA", copia)
    return TestClient(app)


def test_listar_y_filtrar(client):
    assert len(client.get("/ventas").json()) == 14
    assert all(v["categoria"] == "Hogar" for v in client.get("/ventas?categoria=hogar").json())
    assert len(client.get("/ventas?producto=gorra").json()) == 2


def test_crear_calcula_total_e_id(client):
    r = client.post("/ventas", json={"producto": " mate ", "categoria": "hogar", "precio": 2500, "cantidad": 4})
    assert r.status_code == 201
    assert r.json()["id"] == 15 and r.json()["total_venta"] == 10000 and r.json()["producto"] == "Mate"


@pytest.mark.parametrize("body", [
    {"producto": "", "categoria": "x", "precio": 1, "cantidad": 1},
    {"producto": "a", "categoria": "x", "precio": -5, "cantidad": 1},
    {"producto": "a", "categoria": "x", "precio": 5, "cantidad": 0},
    {"producto": "a", "categoria": "x", "precio": "abc", "cantidad": 1},
])
def test_crear_invalida_422(client, body):
    assert client.post("/ventas", json=body).status_code == 422


def test_put_delete_y_404(client):
    body = {"producto": "Gorra", "categoria": "Accesorios", "precio": 5000, "cantidad": 2}
    assert client.put("/ventas/3", json=body).json()["total_venta"] == 10000
    assert client.delete("/ventas/3").status_code == 200
    assert client.get("/ventas/3").status_code == 404
    assert client.put("/ventas/999", json=body).status_code == 404
    assert client.delete("/ventas/999").status_code == 404


def test_importar_parcial(client):
    filas = [
        {"producto": "Billetera", "categoria": "Accesorios", "precio": "9000", "cantidad": "6"},
        {"producto": "Malo", "categoria": "Hogar", "precio": "-100", "cantidad": "2"},
    ]
    r = client.post("/ventas/importar", json={"filas": filas}).json()
    assert (r["aceptadas"], r["rechazadas"]) == (1, 1)
    assert r["detalle_rechazadas"][0]["fila"] == 2


def test_anomalias_detecta_televisor(client):
    tipos = {(a["id"], a["tipo"]) for a in client.get("/anomalias").json()["anomalias"]}
    assert (14, "duplicado") in tipos
    assert (13, "valor_atipico") in tipos


def test_indicadores(client):
    ind = client.get("/indicadores").json()
    assert ind["cantidad_operaciones"] == 14 and ind["categoria_top"] == "Hogar"


def test_archivo_corrupto_500(client):
    logica.RUTA.write_text("{no es json", encoding="utf-8")
    assert client.get("/ventas").status_code == 500
