# Analizador de Ventas — TP2

Sistema integrado con **Python (FastAPI + Streamlit)**, **n8n (Low-Code)** e **IA (agente en n8n)**,
construido a partir del TP1 (Analizador de Ventas por consola).

> **Estado:** API, interfaz, persistencia, tests y Docker de n8n listos.
> Pendiente: workflows n8n (`n8n/workflows/`) y agente de IA.

## Componentes

| Componente | Tecnología | Puerto | Dónde corre |
|---|---|---|---|
| API REST | FastAPI + Pydantic + Uvicorn | 8000 | Local |
| Interfaz | Streamlit | 8501 | Local |
| Automatización + IA | n8n (nodo AI Agent, Gemini u Ollama) | 5678 | Docker |
| Persistencia | `data/ventas.json` (leído/escrito solo por la API) | — | Archivo |

Comunicación: `Streamlit → FastAPI (HTTP/JSON)` y `n8n → FastAPI (nodo HTTP Request)`.
Desde el contenedor de n8n, la API local se alcanza en `http://host.docker.internal:8000`.
Ver `docs/arquitectura.md`.

## Requisitos
Python 3.10+, Docker Desktop (o Docker Engine + Compose), Git.

## Instalación
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución
```bash
# 1) API  (docs interactivas: http://localhost:8000/docs)
uvicorn main:app --reload --port 8000

# 2) Interfaz (otra terminal)
streamlit run app_streamlit.py

# 3) n8n en Docker
docker compose up -d       # iniciar  -> http://localhost:5678
docker compose down        # detener
docker compose restart n8n # reiniciar
docker compose logs -f n8n # ver logs
```

## Endpoints
| Método | Ruta | Descripción | Errores |
|---|---|---|---|
| POST | `/ventas` | Registrar venta | 422 |
| GET | `/ventas?producto=&categoria=` | Listar / filtrar | 500 |
| GET | `/ventas/{id}` | Obtener una venta | 404 |
| PUT | `/ventas/{id}` | Modificar | 404, 422 |
| DELETE | `/ventas/{id}` | Eliminar | 404 |
| POST | `/ventas/importar` | Importar filas (CSV); informa aceptadas y rechazadas | 422 |
| GET | `/indicadores` | Ingresos, promedio, producto/categoría líder | — |
| GET | `/anomalias` | Duplicados y totales atípicos (IQR) | — |
| GET | `/health` | Estado del servicio | — |

## Tests
```bash
pytest -q
```

## Datos de ejemplo
`data/ventas.json` incluye un Televisor duplicado a propósito para demostrar la detección de anomalías.
`data/ventas_nuevas.csv` incluye filas inválidas para demostrar el manejo de errores en la importación.

## Seguridad
No se suben claves. Copiá `.env.example` a `.env` (ignorado por git); la API key de Gemini se carga como credencial dentro de n8n.

## Estructura
```
main.py            FastAPI: esquemas Pydantic + endpoints HTTP
logica.py          persistencia JSON, validaciones y pandas (sin FastAPI)
app_streamlit.py   interfaz
n8n/workflows/     JSON exportados de los workflows
data/              ventas.json, ventas_nuevas.csv
docs/              arquitectura.md, bitacora_ia.md, responsabilidades.md
tests/             test_api.py
compose.yaml, requirements.txt, .gitignore, .env.example
