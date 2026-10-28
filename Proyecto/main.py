"""main.py — API REST (FastAPI + Pydantic + Uvicorn).

Ejecutar:  uvicorn main:app --reload --port 8000
Docs:      http://localhost:8000/docs
"""
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

import logica

app = FastAPI(title="Analizador de Ventas - TP2", version="1.0.0")


# ---------------------------------------------------------------------
# Esquemas Pydantic
# ---------------------------------------------------------------------

class VentaIn(BaseModel):
    """Datos que envía el cliente para crear o modificar una venta."""
    model_config = ConfigDict(str_strip_whitespace=True)

    producto: str = Field(min_length=1, examples=["Remera Lisa"])
    categoria: str = Field(min_length=1, examples=["Indumentaria"])
    precio: float = Field(gt=0, allow_inf_nan=False, examples=[8500.0])
    cantidad: int = Field(gt=0, examples=[3])

    @field_validator("producto", "categoria")
    @classmethod
    def _formato_titulo(cls, v: str) -> str:
        return v.title()

    @field_validator("precio")
    @classmethod
    def _redondear(cls, v: float) -> float:
        v = round(v, 2)
        if v <= 0:
            raise ValueError("el precio debe ser de al menos 0.01")
        return v


class VentaOut(VentaIn):
    """Venta persistida: agrega id y total calculado."""
    id: int
    total_venta: float


class ImportarIn(BaseModel):
    """Filas crudas (ej. leídas de un CSV). Se validan una por una."""
    filas: list[dict[str, Any]] = Field(min_length=1)


# ---------------------------------------------------------------------
# Manejo de errores
# ---------------------------------------------------------------------

@app.exception_handler(logica.ErrorPersistencia)
async def _error_persistencia(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


def _indice_o_404(ventas: list[dict], id_: int) -> int:
    i = logica.buscar_indice(ventas, id_)
    if i is None:
        raise HTTPException(status_code=404, detail=f"No existe la venta con id={id_}.")
    return i


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------

@app.get("/health", tags=["sistema"])
def health():
    return {"estado": "ok"}


@app.post("/ventas", response_model=VentaOut, status_code=201, tags=["ventas"])
def crear_venta(datos: VentaIn):
    with logica.LOCK:
        ventas = logica.cargar()
        nueva = logica.construir_venta(datos.model_dump(), logica.siguiente_id(ventas))
        ventas.append(nueva)
        logica.guardar(ventas)
    return nueva


@app.get("/ventas", response_model=list[VentaOut], tags=["ventas"])
def listar_ventas(
    producto: str | None = Query(None, description="Texto contenido en el producto"),
    categoria: str | None = Query(None, description="Categoría exacta"),
):
    return logica.filtrar(logica.cargar(), producto, categoria)


@app.get("/ventas/{id_venta}", response_model=VentaOut, tags=["ventas"])
def obtener_venta(id_venta: int):
    ventas = logica.cargar()
    return ventas[_indice_o_404(ventas, id_venta)]


@app.put("/ventas/{id_venta}", response_model=VentaOut, tags=["ventas"])
def modificar_venta(id_venta: int, datos: VentaIn):
    with logica.LOCK:
        ventas = logica.cargar()
        i = _indice_o_404(ventas, id_venta)
        ventas[i] = logica.construir_venta(datos.model_dump(), id_venta)
        logica.guardar(ventas)
    return ventas[i]


@app.delete("/ventas/{id_venta}", tags=["ventas"])
def eliminar_venta(id_venta: int):
    with logica.LOCK:
        ventas = logica.cargar()
        eliminada = ventas.pop(_indice_o_404(ventas, id_venta))
        logica.guardar(ventas)
    return {"mensaje": "Venta eliminada.", "venta": eliminada}


@app.post("/ventas/importar", tags=["ventas"])
def importar_ventas(datos: ImportarIn):
    """Valida fila por fila: acepta las válidas y devuelve las rechazadas con el motivo."""
    rechazadas: list[dict] = []
    validas: list[VentaIn] = []
    for n, fila in enumerate(datos.filas, start=1):
        try:
            validas.append(VentaIn(**{k: fila.get(k) for k in ("producto", "categoria", "precio", "cantidad")}))
        except ValidationError as e:
            motivo = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
            rechazadas.append({"fila": n, "datos": fila, "motivo": motivo})

    aceptadas: list[dict] = []
    if validas:
        with logica.LOCK:
            ventas = logica.cargar()
            sig = logica.siguiente_id(ventas)
            aceptadas = [logica.construir_venta(v.model_dump(), sig + k) for k, v in enumerate(validas)]
            logica.guardar(ventas + aceptadas)

    return {
        "total_recibidas": len(datos.filas),
        "aceptadas": len(aceptadas),
        "rechazadas": len(rechazadas),
        "detalle_rechazadas": rechazadas,
    }


@app.get("/indicadores", tags=["analisis"])
def indicadores():
    return logica.calcular_indicadores(logica.cargar())


@app.get("/anomalias", tags=["analisis"])
def anomalias():
    encontradas = logica.detectar_anomalias(logica.cargar())
    return {"cantidad": len(encontradas), "anomalias": encontradas}
