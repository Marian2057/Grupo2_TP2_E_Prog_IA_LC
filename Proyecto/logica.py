"""logica.py — persistencia JSON, validaciones y análisis con pandas.

No importa nada de FastAPI ni de main.py: trabaja con diccionarios comunes.
"""
import json
import os
import tempfile
import threading
from pathlib import Path

import pandas as pd

RUTA = Path(os.getenv("VENTAS_PATH", Path(__file__).resolve().parent / "data" / "ventas.json"))
LOCK = threading.Lock()


# ---------------------------------------------------------------------
# Persistencia (JSON)
# ---------------------------------------------------------------------

class ErrorPersistencia(Exception):
    """No se pudo leer o escribir el archivo de datos."""


def cargar() -> list[dict]:
    if not RUTA.exists():
        return []
    try:
        datos = json.loads(RUTA.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        raise ErrorPersistencia(f"No se pudo leer '{RUTA.name}': {e}") from e
    if not isinstance(datos, list):
        raise ErrorPersistencia(f"'{RUTA.name}' no contiene una lista de ventas.")
    return datos


def guardar(ventas: list[dict]) -> None:
    """Escribe en un temporal y reemplaza, para no corromper el archivo."""
    try:
        RUTA.parent.mkdir(parents=True, exist_ok=True)
        contenido = json.dumps(ventas, indent=4, ensure_ascii=False, allow_nan=False)
        fd, tmp = tempfile.mkstemp(dir=RUTA.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(contenido)
        os.replace(tmp, RUTA)
    except (OSError, TypeError, ValueError) as e:
        raise ErrorPersistencia(f"No se pudo guardar '{RUTA.name}': {e}") from e


def siguiente_id(ventas: list[dict]) -> int:
    return max((v.get("id", 0) for v in ventas), default=0) + 1


# ---------------------------------------------------------------------
# Reglas de negocio
# ---------------------------------------------------------------------

def construir_venta(datos: dict, id_: int) -> dict:
    """Arma el registro persistido a partir de datos ya validados."""
    return {**{"id": id_}, **datos, "total_venta": round(datos["precio"] * datos["cantidad"], 2)}


def buscar_indice(ventas: list[dict], id_: int) -> int | None:
    for i, v in enumerate(ventas):
        if v.get("id") == id_:
            return i
    return None


def filtrar(ventas: list[dict], producto: str | None, categoria: str | None) -> list[dict]:
    if producto:
        ventas = [v for v in ventas if producto.strip().lower() in v["producto"].lower()]
    if categoria:
        ventas = [v for v in ventas if v["categoria"].lower() == categoria.strip().lower()]
    return ventas


# ---------------------------------------------------------------------
# Análisis con pandas
# ---------------------------------------------------------------------

def calcular_indicadores(ventas: list[dict]) -> dict:
    if not ventas:
        return {
            "cantidad_operaciones": 0, "ingresos_totales": 0.0, "promedio_venta": 0.0,
            "producto_top": None, "categoria_top": None, "ingresos_por_categoria": {},
        }
    df = pd.DataFrame(ventas)
    por_producto = df.groupby("producto")["cantidad"].sum()
    por_categoria = df.groupby("categoria")["total_venta"].sum()
    return {
        "cantidad_operaciones": int(len(df)),
        "ingresos_totales": round(float(df["total_venta"].sum()), 2),
        "promedio_venta": round(float(df["total_venta"].mean()), 2),
        "producto_top": ", ".join(por_producto[por_producto == por_producto.max()].index),
        "categoria_top": ", ".join(por_categoria[por_categoria == por_categoria.max()].index),
        "ingresos_por_categoria": {k: round(float(v), 2) for k, v in por_categoria.items()},
    }


def detectar_anomalias(ventas: list[dict], factor_iqr: float = 3.0) -> list[dict]:
    """Detecta (1) ventas duplicadas y (2) totales atípicos (regla IQR)."""
    anomalias: list[dict] = []

    vistos: dict[tuple, int] = {}
    for v in ventas:
        clave = (v["producto"], v["categoria"], v["precio"], v["cantidad"])
        if clave in vistos:
            anomalias.append({
                "id": v["id"], "tipo": "duplicado",
                "detalle": f"Idéntica a la venta id={vistos[clave]} ({v['producto']}).",
            })
        else:
            vistos[clave] = v["id"]

    if len(ventas) >= 4:
        totales = pd.Series([v["total_venta"] for v in ventas])
        q1, q3 = totales.quantile(0.25), totales.quantile(0.75)
        limite = q3 + factor_iqr * (q3 - q1)
        for v in ventas:
            if v["total_venta"] > limite:
                anomalias.append({
                    "id": v["id"], "tipo": "valor_atipico",
                    "detalle": f"Total ${v['total_venta']:,.2f} supera el límite ${limite:,.2f} ({v['producto']}).",
                })
    return anomalias
