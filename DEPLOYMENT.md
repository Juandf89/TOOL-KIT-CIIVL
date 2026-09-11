# Despliegue a producción — checklist

Objetivo confirmado: **Hostinger, plan de hosting compartido/Business (hPanel, sin acceso root)** —
el mismo dominio donde ya se sirve el explorador estático. Esta versión del documento prioriza esa
ruta. (Nota: una versión anterior de este documento armaba `Dockerfile`/`docker-compose.yml` sin
haber confirmado antes dónde se iba a hostear — esos archivos quedan en el repo por si en algún
momento migran a un VPS con Docker, pero **no se usan** en el despliegue de mañana.)

---

## Ruta elegida: Hostinger compartido, vía Passenger ("Setup Python App")

Hostinger Business expone en hPanel una función para correr apps Python bajo Phusion Passenger.
Passenger clásico espera un archivo `passenger_wsgi.py` con un callable WSGI llamado `application`.
`src/api.py` es una app **ASGI** (FastAPI) — no WSGI — así que:

### Listo en el repo (re-verificado, no solo leído)
- **`passenger_wsgi.py`** (raíz del repo): envuelve `src.api:app` con `a2wsgi.ASGIMiddleware` para
  exponer un callable WSGI válido. **Re-probado de nuevo hoy**, con una request WSGI sintética
  (mismo mecanismo que usaría Passenger — sin `uvicorn`, sin socket real), contra los 4 grupos de
  endpoints:
  - `GET /health` → 200 `{"status":"ok"}`
  - `GET /v1/reasoning/rulebases` → 200, incluye `jp-civil-612-sublease-demo`
  - `POST /v1/reasoning/prove` con el **caso de oro del paper PROLEG** (Apéndice A, Satoh et al.,
    JURISIN 2010 — el mismo factbase de `tests/test_api_reasoning.py`) → 200, `"proved": true`,
    traza no vacía
  - `GET /v1/corpora` → 200, 8 corpus
  - `GET /v1/corpora/CO-CC/articles?limit=5&offset=0` → 200, `total` real (2672 artículos)

  Nada roto — no hizo falta tocar el archivo.
- **`requirements-prod.txt`**: **re-instalado hoy en un venv nuevo y vacío** (no el entorno principal
  del repo, que ya tenía las dependencias sueltas instaladas globalmente y no serviría como prueba).
  `pip install -r requirements-prod.txt` bajó las 5 dependencias pineadas (`fastapi==0.141.1`,
  `uvicorn[standard]==0.35.0`, `pydantic==2.13.5`, `pyyaml==6.0.3`, `a2wsgi==1.10.10`) sin conflictos
  — `pip check` no reportó nada roto — y `from passenger_wsgi import application` funcionó dentro de
  ese venv limpio. `uvicorn` no hace falta para el camino de Passenger (Passenger no lo usa), pero no
  molesta tenerlo listado para cuando se pruebe local con `uvicorn src.api:app --reload`.
- **`GET /health`**: sirve para que vos mismo confirmes desde el navegador que la app está viva antes
  de cablear DNS/dominio.
- **CORS por variable de entorno** (`LATIO_ALLOWED_ORIGINS`, ver `src/api.py` líneas 28-34) — en
  hPanel esto se configura como variable de entorno de la Python App (la sección "Setup Python App"
  tiene un campo para variables de entorno) o, si no está disponible ahí, hPanel suele permitir un
  archivo `.env` que Passenger carga — **confirmalo en tu panel**, no puedo verlo desde acá. Si no
  seteás nada, cae al default hardcodeado en el código: `https://datalexlab.com` +
  `localhost:5500`/`localhost:8080` (para desarrollo) — ver troubleshooting más abajo si el explorador
  no puede llamar a la API por CORS.

### Pasos en hPanel (a ejecutar por vos — no tengo acceso a tu cuenta)

1. **hPanel → Avanzado → Setup Python App** (o "Configurar aplicación Python", el nombre exacto
   varía). Creá una nueva app:
   - **Dominio/subdominio**: si `api.datalexlab.com` es el subdominio deseado (coherente con lo que
     ya referencia `README.md`/`toolkit-api/index.html`), primero crealo en hPanel → Dominios →
     Subdominios, apuntando su document root a la carpeta donde subas este repo.
   - **Versión de Python**: la más alta disponible que sea ≥ 3.10 (el código usa sintaxis moderna de
     type hints de `src/reasoning/`); confirmá cuál ofrece tu plan — **a confirmar en tu panel**.
   - **Archivo de arranque**: `passenger_wsgi.py`.
   - **Punto de entrada**: `application` (nombre del callable, ya está así en el archivo).
2. **Subir el código**: por Git (si hPanel lo soporta en tu plan) o por el Administrador de Archivos /
   SFTP. Ver la sección **"Qué subir (mínimo vs. opcional)"** más abajo para el detalle exacto de
   archivos y carpetas — resumen rápido: `src/`, `passenger_wsgi.py`, `requirements-prod.txt`,
   `reports/manifest.json`, `config/corpus_registry.yaml`, y `data/processed/*_articles.json` (los 8
   reales, no hace falta `TEST-FIXTURE_articles.json` ni los `*_referrals.json`). **No hace falta
   `data/raw/`** (confirmado leyendo `src/api.py`: en runtime solo abre archivos bajo
   `data/processed/`, `reports/manifest.json` y `config/corpus_registry.yaml` — nunca toca
   `data/raw/` ni `data/interim/`).
3. **Instalar dependencias**: hPanel normalmente da un botón "Instalar requerimientos" apuntando a un
   `requirements.txt` — apuntalo a **`requirements-prod.txt`** (versiones exactas verificadas), no al
   `requirements.txt` de desarrollo (rangos `>=`, sin `a2wsgi`). Si tu plan solo deja elegir
   literalmente `requirements.txt`, la alternativa más simple es copiar `requirements-prod.txt` sobre
   `requirements.txt` en el servidor (no en el repo local) antes de instalar.
4. **Variables de entorno**: seteá `LATIO_ALLOWED_ORIGINS` al origen real del frontend (ver checklist
   abajo) — si hPanel no expone variables de entorno para Python Apps en tu plan, avisame y agrego un
   fallback que lea un archivo de config en vez de `os.environ`.
5. **Reiniciar la app** (botón "Restart" en hPanel) y probar `https://api.datalexlab.com/health` desde
   el navegador — debería devolver `{"status":"ok"}`. Si da error, ver **Troubleshooting** abajo.

### Qué NO puedo verificar por vos
No tengo acceso a tu cuenta de Hostinger ni a hPanel — todo lo de esta sección son instrucciones para
que las ejecutes vos. Si en algún paso el panel se ve distinto a lo descripto (Hostinger cambia la UI
de hPanel con cierta frecuencia), decime qué ves y ajusto las instrucciones.

---

## Troubleshooting

### Passenger da 500 (o la página de error genérica de Passenger) al arrancar
1. **Mirá el log de Passenger en hPanel**: en la misma pantalla de "Setup Python App" donde creaste
   la app, Hostinger suele mostrar un botón o pestaña de **"Log"** / **"Error log"** junto a la app —
   ahí aparece el traceback real de Python (import fallido, excepción en el módulo, etc.), no solo el
   500 genérico que ve el navegador. Si no lo ves ahí, hPanel también centraliza logs en
   **Avanzado → Registros de errores** (nombre exacto puede variar) — **a confirmar en tu panel**.
2. Causas más comunes de un 500 al arrancar (en orden de probabilidad):
   - **Falta un archivo de datos**: `reports/manifest.json`, `config/corpus_registry.yaml`, o algún
     `data/processed/<CORPUS>_articles.json` no se subió. `src/api.py` los lee en el import del
     módulo (líneas 123-124, `_MANIFEST = _load_manifest()` / `_CORPUS_REGISTRY =
     _load_corpus_registry()`), así que si faltan, **toda la app falla al arrancar** (no es un error
     aislado de un endpoint). El traceback del log va a decir `FileNotFoundError` con la ruta exacta
     que falta.
   - **`import a2wsgi` o `import fastapi` falla** — ver la sección siguiente.
   - **Ruta de arranque o punto de entrada mal configurados** en el paso 1 de hPanel (archivo distinto
     de `passenger_wsgi.py`, o callable distinto de `application`).

### `import a2wsgi` o `import fastapi` falla (`ModuleNotFoundError`)
Dos causas posibles, en este orden de probabilidad:
1. **Se instalaron las dependencias contra el `requirements.txt` de desarrollo, no contra
   `requirements-prod.txt`**. El `requirements.txt` de la raíz (rangos `fastapi>=0.100.0`, etc.) **no
   incluye `a2wsgi`** — sin `a2wsgi`, `passenger_wsgi.py` no puede importar
   `from a2wsgi import ASGIMiddleware` y la app no arranca. Volvé al paso 3 de "Pasos en hPanel" y
   confirmá que el botón de instalación apuntó al archivo correcto (o que copiaste
   `requirements-prod.txt` sobre `requirements.txt` en el servidor antes de instalar).
2. **Versión de Python incompatible**: si tu plan te dio Python 3.9 o anterior, `src/reasoning/`
   usa sintaxis de type hints moderna (por ejemplo `list[dict]`) que rompe en < 3.10 con
   `SyntaxError`, no con `ModuleNotFoundError` — si el traceback del log dice `SyntaxError` en vez de
   `ModuleNotFoundError`, es este caso. Solución: cambiar la versión de Python de la app a ≥ 3.10 en
   hPanel (paso 1) y reinstalar dependencias.
   Si el traceback es específicamente `ModuleNotFoundError: No module named 'a2wsgi'` (o `'fastapi'`)
   después de haber instalado correctamente contra `requirements-prod.txt`, puede ser que hPanel haya
   instalado las dependencias en un entorno virtual distinto del que usa Passenger para correr la app
   (algunos paneles tienen un venv por app que hay que seleccionar explícitamente) — **a confirmar en
   tu panel**.

### CORS bloquea el explorador (`toolkit-api/index.html` no puede llamar a la API)
Síntoma típico: la consola del navegador muestra un error tipo
`has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header...` aunque `curl` contra el
mismo endpoint funciona bien (CORS es una restricción del navegador, no del servidor — `curl` nunca
la ve).
1. Confirmá desde dónde se está sirviendo `toolkit-api/index.html` (¿`https://datalexlab.com/latio/`?
   ¿GitHub Pages? ¿local con `python -m http.server`?) — ese origen exacto (esquema + host + puerto,
   sin path) tiene que estar en `LATIO_ALLOWED_ORIGINS`.
2. Si `LATIO_ALLOWED_ORIGINS` **no está seteada** en hPanel, la API cae al default de
   `src/api.py` (`https://datalexlab.com`, `localhost:5500`, `localhost:8080`) — si tu frontend real
   se sirve desde otro origen (por ejemplo `datalexlab.com/latio` sigue siendo el mismo origen
   `https://datalexlab.com`, así que ese caso ya está cubierto; pero GitHub Pages
   `https://juandf89.github.io` **no** lo está a menos que lo agregues).
3. Seteá `LATIO_ALLOWED_ORIGINS` en hPanel con la lista separada por comas de todos los orígenes que
   necesitás (por ejemplo: `https://datalexlab.com,https://juandf89.github.io`) y reiniciá la app.
4. Si seteaste la variable y sigue fallando, verificá que hPanel realmente la esté pasando al proceso
   de Passenger (algunos paneles requieren reiniciar la app, no solo guardar la variable, para que
   tome efecto) — probá `curl -i https://api.datalexlab.com/v1/corpora -H "Origin:
   https://tu-origen-real"` y mirá si la respuesta trae el header `access-control-allow-origin` con tu
   origen (ver checklist de abajo).

---

## Checklist de verificación post-despliegue

Una vez que `https://api.datalexlab.com` (o el subdominio real que hayas usado) esté levantado,
corré estos `curl` desde tu máquina — reemplazá el dominio si es distinto. Todos deberían devolver
`200` salvo que se indique lo contrario.

### 1. Salud básica
```bash
curl -i https://api.datalexlab.com/health
# esperado: HTTP/2 200, body {"status":"ok"}
```

### 2. Razonamiento — `/v1/reasoning/rulebases`
```bash
curl -s https://api.datalexlab.com/v1/reasoning/rulebases | python -m json.tool
# esperado: array con al menos "jp-civil-612-sublease-demo" y "co-civil-256-visitas"
```

### 3. Razonamiento — `/v1/reasoning/prove` (caso de oro del paper PROLEG)
Guardá esto como `golden_case.json` (es el mismo factbase que usa
`tests/test_api_reasoning.py::test_prove_contract_end_golden_case_from_proleg_appendix_a`, ya
verificado contra el wrapper WSGI hoy):
```json
{"rulebase_id": "jp-civil-612-sublease-demo", "goal": "contract_end", "party": "plaintiff", "facts": [{"action": "admission", "fact": "agreement_of_lease_contract", "party": "defendant"}, {"action": "admission", "fact": "agreement_of_sublease_contract", "party": "defendant"}, {"action": "admission", "fact": "handover_to_lessee", "party": "defendant"}, {"action": "admission", "fact": "handover_to_sublessee", "party": "defendant"}, {"action": "admission", "fact": "using_leased_thing", "party": "defendant"}, {"action": "admission", "fact": "manifestation_cancellation", "party": "defendant"}, {"action": "allege", "fact": "approval_of_sublease", "party": "defendant"}, {"action": "provide_evidence", "fact": "approval_of_sublease", "party": "defendant"}, {"action": "allege", "fact": "approval_before_cancellation", "party": "defendant"}, {"action": "provide_evidence", "fact": "approval_before_cancellation", "party": "defendant"}, {"action": "allege", "fact": "fact_of_nonabuse_of_confidence", "party": "defendant"}, {"action": "provide_evidence", "fact": "fact_of_nonabuse_of_confidence", "party": "defendant"}, {"action": "plausible", "fact": "fact_of_nonabuse_of_confidence", "party": null}, {"action": "allege", "fact": "fact_of_abuse_of_confidence", "party": "plaintiff"}, {"action": "provide_evidence", "fact": "fact_of_abuse_of_confidence", "party": "plaintiff"}, {"action": "plausible", "fact": "fact_of_abuse_of_confidence", "party": null}]}
```
```bash
curl -s -X POST https://api.datalexlab.com/v1/reasoning/prove \
  -H "Content-Type: application/json" \
  -d @golden_case.json | python -m json.tool
# esperado: "goal": "contract_end", "party": "plaintiff", "proved": true, "trace": [...] (no vacío)
```

### 4. Corpus — `/v1/corpora`
```bash
curl -s https://api.datalexlab.com/v1/corpora | python -m json.tool
# esperado: array de 8 objetos (CL-CC, CO-CC, AR-CC, AR-CCYC, BR-CC, MX-CCF, MX-CDMX, PE-CC)
```

### 5. Corpus — artículos de un corpus real
```bash
curl -s "https://api.datalexlab.com/v1/corpora/CO-CC/articles?limit=5&offset=0" | python -m json.tool
# esperado: "corpus_id": "CO-CC", "total": 2672 (o el conteo real de artículos), 5 artículos en "articles"
```
```bash
curl -s https://api.datalexlab.com/v1/corpora/CO-CC | python -m json.tool
# esperado: metadata + objeto "gates" con las 6 compuertas de calidad
```

### 6. CORS (si el explorador falla, correr esto para diagnosticar)
```bash
curl -i https://api.datalexlab.com/v1/corpora -H "Origin: https://datalexlab.com"
# esperado: header de respuesta "access-control-allow-origin: https://datalexlab.com"
```

Si alguno de estos falla, volvé a la sección **Troubleshooting** de arriba.

---

## Qué subir (mínimo vs. opcional)

Verificado leyendo `src/api.py` de nuevo (no asumido): en runtime, la API **solo** abre archivos bajo
tres rutas — `reports/manifest.json`, `config/corpus_registry.yaml`, y
`data/processed/<corpus_id>_articles.json` (`src/api.py` líneas 101-256). Nunca toca `data/raw/` ni
`data/interim/`, y nunca abre los archivos `*_referrals.json` de `data/processed/` (esos solo los usa
`src/pipeline.py`, que es el script de extracción offline — no se ejecuta en producción).

### Mínimo imprescindible
- `passenger_wsgi.py`
- `requirements-prod.txt`
- `src/` completo (en la práctica solo se importan `src/__init__.py`, `src/api.py` y
  `src/reasoning/*`, pero subir el paquete entero es más simple que separar archivos y no rompe nada
  — `src/pipeline.py`, `src/behavior.py` y `src/models.py` quedan sin usar en runtime si no los
  importás, no fallan por estar presentes)
- `reports/manifest.json` (un solo archivo, no toda la carpeta `reports/`)
- `config/corpus_registry.yaml`
- `data/processed/CL-CC_articles.json`, `CO-CC_articles.json`, `AR-CC_articles.json`,
  `AR-CCYC_articles.json`, `BR-CC_articles.json`, `MX-CCF_articles.json`, `MX-CDMX_articles.json`,
  `PE-CC_articles.json` (los 8 reales — sin ellos, `/v1/corpora/<id>/articles` devuelve 404 para ese
  corpus puntual, pero no rompe el arranque del resto de la app)

### Opcional / no hace falta subir
- **`data/raw/`** (7.7 MB) — no lo lee nada en runtime, es el insumo del pipeline de extracción.
- **`data/interim/`** — vacío en este repo, no hace falta.
- **`data/processed/*_referrals.json`** — no los lee `src/api.py`, solo el pipeline offline.
- **`data/processed/TEST-FIXTURE_articles.json`** (y su `_referrals.json`) — corpus de prueba interno
  del pipeline, no forma parte de los 8 corpus reales que expone `/v1/corpora` (el manifest no lo
  incluye, y hay un test que confirma explícitamente que no debe filtrarse:
  `tests/test_api_corpora.py::test_list_corpora_returns_the_8_real_corpora`).
- **El resto de `reports/`** (`*_run_report.json`, `debate_revision_2026-09-10.md`) — son artefactos
  de auditoría del pipeline, no los lee la API.
- **`tests/`, `docs/`, `Dockerfile`, `docker-compose.yml`, `requirements-dev.txt`,
  `requirements.txt`** — no hacen falta para que la API funcione; subirlos no rompe nada pero no
  aportan.

---

## `toolkit-api/index.html` y `card-datalex.html`: subida separada, en la misma cuenta de Hostinger

Estos dos archivos son el **explorador estático** (LATIO Explorer) — HTML/JS/CSS puro, sin backend
propio, que hoy corre con datos de ejemplo (`MOCK_METRICS`/`MOCK_LIFT`, ver `README.md`) y que puede
consumir la API real una vez desplegada (sección "Motor de Razonamiento (real)" de la consola). **No
van en la misma carpeta que la Python App** — son un sitio estático aparte, y en hPanel se suben como
cualquier archivo estático del hosting compartido, no a través de "Setup Python App".

Siguiendo la **"Opción B: Integración en Hostinger"** que ya describe `README.md` (líneas 122-125):
1. En **hPanel → Archivos → Administrador de archivos** (o por FTP/SFTP), entrá a `public_html/` —
   la raíz del hosting compartido tradicional, **no** la carpeta que configuraste para la Python App
   en el paso anterior.
2. Creá la carpeta `public_html/latio/` (si no existe) y subí `toolkit-api/index.html` ahí. Quedaría
   accesible en `https://datalexlab.com/latio/index.html` (o `https://datalexlab.com/latio/` si el
   servidor sirve `index.html` por default, que es lo habitual).
3. `toolkit-api/card-datalex.html` **no se sube como archivo** — es un fragmento HTML para copiar y
   pegar dentro del editor de la sección "Proyectos" de `datalexlab.com` (el CMS/builder que uses ahí,
   fuera del alcance de este documento — **a confirmar en tu panel/CMS**).
4. Una vez que la API esté online, actualizá en `toolkit-api/index.html` el campo "API base URL"
   (hoy con el placeholder `http://127.0.0.1:8000`) para que apunte a la URL real de la API
   (`https://api.datalexlab.com`), y el link "Swagger Docs" (hoy marcado `pendiente de despliegue`,
   debería apuntar a `https://api.datalexlab.com/docs` una vez confirmado que `docs_url='/docs'`
   sigue accesible en producción — no hay razón para que Passenger lo bloquee, pero no lo pude probar
   contra un dominio real).

Nota: `toolkit-api/_preview_comparacion_proyectos.html` (presente en el repo) no se menciona en el
README como parte del flujo de despliegue — parece un archivo de trabajo/preview interno; no lo subas
salvo que sepas específicamente para qué se usa.

---

## Falta decidir/confirmar

1. **Subdominio exacto para la API** (`api.datalexlab.com` asumido, por ser lo que ya referencian
   `README.md` y `toolkit-api/index.html` — confirmalo o corregilo).
2. **`LATIO_ALLOWED_ORIGINS` real**: el origen exacto del frontend que va a llamar a la API — si el
   explorador (`toolkit-api/index.html`) también se sirve desde este mismo Hostinger en
   `datalexlab.com/latio/` (Opción B del README), el origen es `https://datalexlab.com`; si sigue en
   GitHub Pages, es `https://juandf89.github.io`. Pueden ser varios, separados por coma.
3. **TLS/HTTPS**: Hostinger normalmente emite un certificado Let's Encrypt automático por dominio/
   subdominio desde hPanel (SSL) — confirmá que está activado para el subdominio de la API antes de
   anunciarlo, para no servir la API en HTTP plano.
4. **Actualizar el placeholder de la consola** (`toolkit-api/index.html`, campo "API base URL", hoy
   `http://127.0.0.1:8000` por default) para que apunte a la URL real una vez esté online, y el link
   "Swagger Docs" (hoy marcado `pendiente de despliegue`).
5. **Versión de Python disponible en tu plan de Hostinger** y **si tu plan expone variables de
   entorno para Python Apps** — ambos marcados como "a confirmar en tu panel" arriba porque no tengo
   forma de verlos desde acá.

## Riesgo a evaluar antes de ir a producción (no bloqueante, pero real)

- **La API no tiene autenticación ni rate limiting.** `/v1/reasoning/prove` acepta cualquier rulebase
  registrado y cualquier factbase sin límite de tamaño ni de frecuencia. En hosting compartido esto
  importa el doble: un uso abusivo puede consumir los recursos compartidos del plan (CPU/memoria) y
  afectar a otras apps en la misma cuenta. Para un lanzamiento de alcance controlado puede ser
  aceptable por ahora; si esperás tráfico público sin restricción, avisame y agrego un límite básico
  (por IP) antes de anunciarlo ampliamente — no lo agregué solo porque cambia comportamiento visible
  de la API y es una decisión de producto.
- **Ningún corpus tiene `retrieved_at` poblado** (sigue en `null` con TODO, ver
  `docs/notas_gobernanza.md`) — no bloquea el despliegue técnico, pero si el lanzamiento incluye
  afirmaciones de procedencia/trazabilidad de los datos, falta ese dato.

## Cómo probar `passenger_wsgi.py` localmente antes de subir a Hostinger

```bash
python -m venv .venv-prod-test        # venv nuevo y vacío, NO el entorno principal del repo
.venv-prod-test/Scripts/activate      # Windows; en Linux/Mac: source .venv-prod-test/bin/activate
pip install -r requirements-prod.txt  # sin conflictos de versiones (verificado en este entorno)
python -c "
from passenger_wsgi import application
# smoke test WSGI mínimo — reemplazá con requests reales contra /health,
# /v1/reasoning/rulebases, /v1/reasoning/prove (caso de oro PROLEG) y
# /v1/corpora; los 5 se re-verificaron hoy con una request WSGI sintética
# antes de escribir este documento.
"
```
Después de probar, borrá el venv de prueba (`.venv-prod-test/`) — no hace falta subirlo a Hostinger,
Passenger instala las dependencias del lado del servidor.

---

## Alternativa descartada por ahora: Docker/VPS

`Dockerfile`, `docker-compose.yml` y `requirements-prod.txt` (compartido con la ruta de Hostinger)
quedan preparados por si en el futuro migran a un VPS con Docker (Hostinger también vende VPS KVM, o
cualquier otro proveedor). **No construí ni probé la imagen** (el daemon de Docker no estaba
disponible en este entorno) — si retoman esta ruta más adelante, correr `docker compose up --build`
y validar antes de confiar en ella.
