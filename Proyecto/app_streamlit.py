"""Interfaz Streamlit. Solo habla con la API (no toca el JSON directamente).

Ejecutar:  streamlit run app_streamlit.py
"""
import csv
import io
import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Analizador de Ventas", page_icon="📊", layout="wide")


def llamar_api(metodo: str, ruta: str, **kwargs):
    """Devuelve (datos, error). Traduce los fallos a mensajes comprensibles."""
    try:
        r = requests.request(metodo, f"{API_URL}{ruta}", timeout=10, **kwargs)
    except requests.exceptions.ConnectionError:
        return None, f"No se pudo conectar con la API en {API_URL}. ¿Está corriendo uvicorn?"
    except requests.exceptions.Timeout:
        return None, "La API tardó demasiado en responder."
    if r.status_code >= 400:
        try:
            detalle = r.json().get("detail", r.text)
        except ValueError:
            detalle = r.text
        if isinstance(detalle, list):  # errores 422 de Pydantic
            detalle = "; ".join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in detalle)
        return None, f"Error {r.status_code}: {detalle}"
    return r.json(), None


def mostrar_error(error: str | None) -> bool:
    if error:
        st.error(error)
        return True
    return False


st.title("📊 Analizador de Ventas")
seccion = st.sidebar.radio(
    "Sección",
    ["Registrar venta", "Ventas", "Importar CSV", "Indicadores", "Anomalías"],
)
st.sidebar.caption(f"API: {API_URL}")

# ------------------------------------------------------------------ Registrar
if seccion == "Registrar venta":
    st.subheader("Registrar nueva venta")
    with st.form("alta", clear_on_submit=True):
        producto = st.text_input("Producto")
        categoria = st.text_input("Categoría")
        precio = st.number_input("Precio unitario", min_value=0.0, step=100.0, format="%.2f")
        cantidad = st.number_input("Cantidad", min_value=0, step=1)
        if st.form_submit_button("Guardar"):
            datos, error = llamar_api("POST", "/ventas", json={
                "producto": producto, "categoria": categoria,
                "precio": precio, "cantidad": int(cantidad),
            })
            if not mostrar_error(error):
                st.success(f"Venta registrada con id {datos['id']} (total ${datos['total_venta']:,.2f}).")

# --------------------------------------------------------------------- Ventas
elif seccion == "Ventas":
    st.subheader("Consultar, modificar y eliminar")
    c1, c2 = st.columns(2)
    f_producto = c1.text_input("Buscar por producto")
    f_categoria = c2.text_input("Filtrar por categoría")
    params = {k: v for k, v in {"producto": f_producto, "categoria": f_categoria}.items() if v}
    ventas, error = llamar_api("GET", "/ventas", params=params)

    if not mostrar_error(error):
        if not ventas:
            st.info("No hay ventas con ese criterio.")
        else:
            st.dataframe(pd.DataFrame(ventas), use_container_width=True, hide_index=True)

            st.markdown("#### Editar o eliminar")
            por_id = {v["id"]: v for v in ventas}
            id_sel = st.selectbox(
                "Venta", list(por_id), format_func=lambda i: f"{i} - {por_id[i]['producto']}"
            )
            v = por_id[id_sel]
            with st.form("edicion"):
                e_producto = st.text_input("Producto", v["producto"])
                e_categoria = st.text_input("Categoría", v["categoria"])
                e_precio = st.number_input("Precio unitario", value=float(v["precio"]), min_value=0.0, format="%.2f")
                e_cantidad = st.number_input("Cantidad", value=int(v["cantidad"]), min_value=0, step=1)
                b1, b2 = st.columns(2)
                guardar = b1.form_submit_button("Guardar cambios")
                borrar = b2.form_submit_button("Eliminar venta")
            if guardar:
                _, error = llamar_api("PUT", f"/ventas/{id_sel}", json={
                    "producto": e_producto, "categoria": e_categoria,
                    "precio": e_precio, "cantidad": int(e_cantidad),
                })
                if not mostrar_error(error):
                    st.success("Venta actualizada.")
                    st.rerun()
            if borrar:
                _, error = llamar_api("DELETE", f"/ventas/{id_sel}")
                if not mostrar_error(error):
                    st.success("Venta eliminada.")
                    st.rerun()

# -------------------------------------------------------------------- Importar
elif seccion == "Importar CSV":
    st.subheader("Importar ventas desde CSV")
    st.caption("Columnas: producto, categoria, precio, cantidad. Separador coma, decimales con punto.")
    archivo = st.file_uploader("Archivo CSV", type="csv")
    if archivo is not None:
        try:
            texto = archivo.getvalue().decode("utf-8")
            filas = list(csv.DictReader(io.StringIO(texto)))
        except (UnicodeDecodeError, csv.Error) as e:
            st.error(f"No se pudo leer el CSV: {e}")
            filas = []
        if filas:
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
            if st.button("Importar"):
                res, error = llamar_api("POST", "/ventas/importar", json={"filas": filas})
                if not mostrar_error(error):
                    st.success(f"Aceptadas: {res['aceptadas']} de {res['total_recibidas']}.")
                    if res["rechazadas"]:
                        st.warning(f"Rechazadas: {res['rechazadas']}")
                        st.dataframe(pd.DataFrame(res["detalle_rechazadas"]), use_container_width=True)
        elif archivo is not None:
            st.warning("El archivo no tiene filas.")

# ----------------------------------------------------------------- Indicadores
elif seccion == "Indicadores":
    st.subheader("Indicadores del negocio")
    ind, error = llamar_api("GET", "/indicadores")
    if not mostrar_error(error):
        if ind["cantidad_operaciones"] == 0:
            st.info("Todavía no hay datos para analizar.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Operaciones", ind["cantidad_operaciones"])
            c2.metric("Ingresos totales", f"${ind['ingresos_totales']:,.2f}")
            c3.metric("Promedio por venta", f"${ind['promedio_venta']:,.2f}")
            st.write(f"**Producto más vendido:** {ind['producto_top']}")
            st.write(f"**Categoría líder ($):** {ind['categoria_top']}")
            st.bar_chart(pd.Series(ind["ingresos_por_categoria"], name="Ingresos"))

# ------------------------------------------------------------------- Anomalías
elif seccion == "Anomalías":
    st.subheader("Anomalías detectadas")
    res, error = llamar_api("GET", "/anomalias")
    if not mostrar_error(error):
        if res["cantidad"] == 0:
            st.success("No se detectaron anomalías.")
        else:
            st.warning(f"Se detectaron {res['cantidad']} anomalías. Revisalas antes de confiar en los indicadores.")
            st.dataframe(pd.DataFrame(res["anomalias"]), use_container_width=True, hide_index=True)
