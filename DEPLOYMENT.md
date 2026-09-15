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

### Listo en el repo (re-verificado, no solo leído — última vez 2026-09-14)
- **`passenger_wsgi.py`** (raíz del repo): envuelve `src.api:app` con `a2wsgi.ASGIMiddleware` para
  exponer un callable WSGI válido. **Re-probado hoy** (2026-09-14, después de agregar el motor de
  etiquetado y corregir Hohfeld/Unicode), con una request WSGI sintética (mismo mecanismo que usaría
  Passenger — sin `uvicorn`, sin socket real), contra:
  - `GET /health` → 200 `{"status":"ok"}`
  - `POST /v1/statements/propose` con un texto real ("El juez podrá reducir la pena...") → 200,
    `hohfeldian_position: "potestad"` (confirma que el fix de Hohfeld del 09-11 también funciona bajo
    Passenger, no solo bajo `uvicorn`)
  - `POST /v1/statements/validate` → 200
  - `GET /v1/corpora` → 200, 8 corpus (con `data/processed/` ya versionado en git desde el 09-14, esto
    funciona en un clon limpio sin pasos manuales adicionales)

  Nada roto — no hizo falta tocar el archivo. (Verificación anterior del 09-10 contra
  `/v1/reasoning/*` sigue vigente, no se repitió porque ese código no cambió.)
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
   - **Versión de Python**: la más alta disponible que sea **≥ 3.10**; confirmá cuál ofrece tu plan
     — **a confirmar en tu panel**. El piso lo imponen las dependencias pineadas, no el código
     propio: `fastapi==0.141.1` y su `starlette==1.0.0` declaran `Requires-Python >= 3.10`
     (`pydantic` pide ≥3.9, `a2wsgi` y `pyyaml` ≥3.8). El código de `src/` corre en 3.9 sin
     problema — todos los módulos de `src/reasoning/` y `src/labeling/` empiezan con
     `from __future__ import annotations`, así que las anotaciones ni se evalúan al importar.
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
5. **Bloquear el acceso web directo a los datos.** Passenger no captura los archivos estáticos que
   estén en el directorio de la app: los sigue sirviendo Apache. Si el document root de la Python
   App queda dentro de `public_html` (lo habitual en Hostinger compartido), esto funciona y
   **esquiva la API por completo**:

   ```
   https://api.datalexlab.com/data/processed/CO-CC_articles.json    → 2.9 MB
   https://api.datalexlab.com/config/corpus_registry.yaml
   https://api.datalexlab.com/reports/manifest.json
   ```

   Son los 25 MB de los 8 corpus descargables de una, sin pasar por ningún endpoint, sin quedar
   sujetos al límite de tasa y sin aparecer en ninguna métrica. Subí el archivo
   `deploy/htaccess-para-carpetas-de-datos.txt` **con el nombre `.htaccess`** dentro de `data/`,
   `config/` y `reports/`. La API abre esos archivos por sistema de archivos (`open()`), no por
   HTTP, así que no rompe ningún endpoint.

   ⚠️ **No toques el `.htaccess` que hPanel genera en la RAÍZ de la app** — lleva la configuración
   de Passenger (`PassengerAppRoot`, etc.) y modificarlo puede impedir el arranque. Estas reglas
   van en las subcarpetas, que no tienen `.htaccess` propio.

6. **Reiniciar la app** (botón "Restart" en hPanel) y probar `https://api.datalexlab.com/health` desde
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
2. **Versión de Python incompatible**: si tu plan te dio Python 3.9 o anterior, el problema
   **no** se manifiesta como `SyntaxError` (una versión anterior de este documento decía eso y
   estaba mal: `list[dict]` existe desde 3.9, y además todo `src/reasoning/` y `src/labeling/` usa
   `from __future__ import annotations`, así que las anotaciones no se evalúan al importar).
   Lo que falla es la **instalación**: `fastapi==0.141.1` y `starlette==1.0.0` declaran
   `Requires-Python >= 3.10`, así que en 3.9 `pip` o bien aborta con un error de resolución —
   visible en el log de instalación de hPanel, no en el de la app — o instala una FastAPI vieja
   compatible, y entonces el síntoma es un `ImportError`/`AttributeError` al arrancar, no un
   `ModuleNotFoundError` limpio. Solución: cambiar la versión de Python de la app a ≥ 3.10 en
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
2. Si `LATIO_ALLOWED_ORIGINS` **no está seteada** en hPanel, la API cae al default de `src/api.py`
   (`https://datalexlab.com`, `https://juandf89.github.io`, `localhost:5500`, `localhost:8080` —
   actualizado el 09-14 para incluir GitHub Pages, ya que ahí es donde vive hoy la consola pública
   real).

   ⚠️ **`https://www.datalexlab.com` NO está en ese default, y para el navegador es un origen
   distinto de `https://datalexlab.com`.** Es una trampa concreta: el propio endpoint raíz de la
   API devuelve `'website': 'https://www.datalexlab.com'`, y muchos dominios en Hostinger
   redirigen el dominio desnudo a `www`. Si el explorador termina servido en
   `https://www.datalexlab.com/latio/`, el default lo bloquea y el síntoma es exactamente el
   error de CORS de arriba, con la variable "correctamente" sin setear. Confirmá en
   hPanel → Dominios hacia qué lado redirige.

   Por eso **hay que setear la variable explícitamente** en hPanel en vez de confiar en el
   default — con las tres variantes:
   `https://datalexlab.com,https://www.datalexlab.com,https://juandf89.github.io`
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
```bash
curl -i https://api.datalexlab.com/v1/corpora -H "Origin: https://www.datalexlab.com"
# esperado: MISMO header con el www. Si este falla y el anterior pasa, falta
# https://www.datalexlab.com en LATIO_ALLOWED_ORIGINS — ver troubleshooting.
```

### 7. Límite de tasa — que exista Y que sea por IP
```bash
for i in $(seq 1 25); do
  printf "%s " "$(curl -s -o /dev/null -w '%{http_code}' -X POST \
    https://api.datalexlab.com/v1/statements/propose \
    -H "Content-Type: application/json" \
    -d '{"text_span":"El arrendatario deberá pagar el canon."}')"
done; echo
# esperado: ~20 veces 200 y después 429 (el corte exacto depende de cuántos
# procesos Passenger haya levantado; ver "Límite de tasa" arriba).
```
```bash
curl -i -X POST https://api.datalexlab.com/v1/statements/propose \
  -H "Content-Type: application/json" -d '{"text_span":"x"}' | head -5
# inmediatamente después del bucle: esperado HTTP 429 con header "retry-after".
```

**La comprobación que importa de verdad** — que el límite sea por IP y no global. Esperá un minuto
y pedile a alguien en otra red (datos del celular sirve) que abra
`https://api.datalexlab.com/v1/reasoning/rulebases`. Si le da 429 sin haber pedido nada, el
limitador está agrupando a todos bajo una sola clave porque `REMOTE_ADDR` no llega: poné
`LATIO_TRUST_FORWARDED_FOR=1` y reiniciá la app.

### 8. Topes de entrada (413 / 422)
```bash
python -c "import json;print(json.dumps({'rulebase_id':'jp-civil-612-sublease-demo','goal':'contract_end','party':'plaintiff','facts':[{'action':'admission','fact':'x%d'%i,'party':'defendant'} for i in range(3000)]}))" > too_big.json
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://api.datalexlab.com/v1/reasoning/prove \
  -H "Content-Type: application/json" -d @too_big.json
# esperado: 413 (el cuerpo supera LATIO_MAX_BODY_BYTES y se rechaza sin parsear).
```

### 9. Los datos NO se descargan esquivando la API
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.datalexlab.com/data/processed/CO-CC_articles.json
curl -s -o /dev/null -w "%{http_code}\n" https://api.datalexlab.com/config/corpus_registry.yaml
curl -s -o /dev/null -w "%{http_code}\n" https://api.datalexlab.com/reports/manifest.json
# esperado: 403 (o 404) en los tres, con el .htaccess del paso 5 aplicado.
# Si devuelven 200, el .htaccess no está puesto o no está donde corresponde.
```
```bash
curl -s https://api.datalexlab.com/v1/corpora | python -m json.tool | head -5
# esperado: sigue devolviendo los 8 corpus — el bloqueo es solo para HTTP,
# la API lee esos archivos por sistema de archivos.
```

Si alguno de estos falla, volvé a la sección **Troubleshooting** de arriba.

---

## Qué subir (mínimo vs. opcional)

Verificado leyendo `src/api.py` de nuevo (no asumido): en runtime, la API abre archivos bajo tres
rutas — `reports/manifest.json`, `config/corpus_registry.yaml`, y
`data/processed/<corpus_id>_articles.json` — y además importa código de `src/labeling/` (motor de
etiquetado N3, agregado el 09-11) además de `src/reasoning/*`. Nunca toca `data/raw/` ni
`data/interim/`, y nunca abre los archivos `*_referrals.json` de `data/processed/` (esos solo los usa
`src/pipeline.py`, que es el script de extracción offline — no se ejecuta en producción).

**Cambio importante desde el 09-14: `data/processed/` ya está commiteado en git** (antes estaba en
`.gitignore` y había que subirlo aparte a mano). Si desplegás por Git (ver paso 2 más abajo), los 8
archivos de artículos vienen automáticamente con el clon/pull — ya no hace falta subirlos por
separado. Si desplegás por SFTP/Administrador de Archivos igual podés subir la carpeta entera tal
cual sale del repo, sin filtrar nada a mano.

**Corrección (09-14): `data/raw/` TAMBIÉN está versionado.** El `.gitignore` solo excluye
`data/raw/*.pdf`, y los archivos reales son `.md` (~8.0 MB). Sigue siendo cierto que la API nunca
los lee, pero la frase "no hace falta subirlo" solo aplica a SFTP: **si desplegás por Git, vienen
igual** y el clon son ~33 MB, no 25. No rompe nada; hay que tenerlo en cuenta para el
`.htaccess` de la sección siguiente, que los cubre.

### Mínimo imprescindible
- `passenger_wsgi.py`
- `requirements-prod.txt`
- `deploy/htaccess-para-carpetas-de-datos.txt` → copiar como `.htaccess` dentro de `data/`,
  `config/` y `reports/` (paso 5 de hPanel)
- `src/` completo (en la práctica se importan `src/__init__.py`, `src/api.py`, `src/models.py`,
  `src/ratelimit.py`, `src/labeling/*` y `src/reasoning/*`; subir el paquete entero es más simple
  que separar archivos y no rompe nada — `src/pipeline.py` y `src/behavior.py` quedan sin usar en
  runtime, no fallan por estar presentes)
- `reports/manifest.json` (un solo archivo, no toda la carpeta `reports/`)
- `config/corpus_registry.yaml`
- `data/processed/CL-CC_articles.json`, `CO-CC_articles.json`, `AR-CC_articles.json`,
  `AR-CCYC_articles.json`, `BR-CC_articles.json`, `MX-CCF_articles.json`, `MX-CDMX_articles.json`,
  `PE-CC_articles.json` (los 8 reales — sin ellos, `/v1/corpora/<id>/articles` devuelve 404 para ese
  corpus puntual, pero no rompe el arranque del resto de la app). **Ya vienen con el repo si
  desplegás por Git.**

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

### Cerrado — decidido el 09-14

1. **Subdominio de la API: `api.datalexlab.com`.** Es lo que ya referencian `README.md` y
   `toolkit-api/index.html`; cambiarlo obliga a tocar los dos. Queda así salvo que digas lo
   contrario.
2. **`LATIO_ALLOWED_ORIGINS`: setearla explícitamente con las tres variantes** —
   `https://datalexlab.com,https://www.datalexlab.com,https://juandf89.github.io`. No basta con el
   default: hoy la consola pública vive en GitHub Pages (`README.md` Opción A) y el explorador
   puede terminar además en `datalexlab.com/latio/` (Opción B), y `www` es un origen distinto que
   el default **no** cubre. Setear las tres cierra los tres escenarios de una y no cuesta nada.

### Sigue abierto — necesita tu panel o tu decisión

3. **TLS/HTTPS**: Hostinger normalmente emite un certificado Let's Encrypt automático por dominio/
   subdominio desde hPanel (SSL) — confirmá que está activado para el subdominio de la API antes de
   anunciarlo, para no servir la API en HTTP plano.
4. **Actualizar el placeholder de la consola** (`toolkit-api/index.html`, campo "API base URL", hoy
   `http://127.0.0.1:8000` por default) para que apunte a la URL real una vez esté online, y el link
   "Swagger Docs" (hoy marcado `pendiente de despliegue`).
5. **Versión de Python disponible en tu plan** (necesitás ≥ 3.10 — ver el motivo real en el paso 1
   de hPanel) y **si tu plan expone variables de entorno para Python Apps**. Si no las expone,
   avisame: el fallback es leer un archivo de config en vez de `os.environ`, y ahora hay **siete**
   variables en juego, no una (`LATIO_ALLOWED_ORIGINS` + las seis del limitador).
6. **¿El document root de la Python App queda dentro de `public_html`?** De eso depende que haga
   falta el `.htaccess` del paso 5. Si queda fuera, no hace falta — pero aplicarlo igual no rompe
   nada y es más barato que averiguarlo mal.
7. **¿Dejamos `/docs` (Swagger) público?** Está abierto hoy. No es una vulnerabilidad —los
   endpoints ya son públicos— pero es un catálogo navegable que invita a probar el endpoint caro.
   Con el límite de tasa puesto, dejarlo abierto es defendible para un lanzamiento académico, que
   es el caso. Se apaga con `docs_url=None` si preferís. **Mi recomendación: dejarlo.**

## Límite de tasa y topes de entrada (implementado el 09-14)

`src/ratelimit.py` — **cero dependencias nuevas**, `requirements-prod.txt` queda idéntico. Se
descartó `slowapi`/`limits` a propósito: cada dependencia extra es un `ModuleNotFoundError` más
capaz de tumbar el arranque bajo Passenger, que es el modo de falla que documenta la sección de
Troubleshooting de arriba.

**Por qué el tamaño del `factbase` era el problema real, no solo la frecuencia:** `FactBase`
(`src/reasoning/models.py`) resuelve cada consulta con un barrido **lineal** sobre `entries`, y
`has_allege_and_evidence` hace dos. El meta-intérprete las llama una o dos veces por literal y por
regla: costo **O(reglas × cuerpo × N)**. Sumado al costo de que Pydantic valide N modelos
`FactEntry` — el término dominante —, un solo POST podía monopolizar el CPU del plan compartido.
Por eso hay tres topes en capas, del más barato al más caro:

| Capa | Qué corta | Respuesta |
|---|---|---|
| Tamaño del cuerpo (`Content-Length`) | Rechaza **antes** de leer y parsear | `413` |
| Tamaño de la lista (`facts` ≤ 2000, ~100× el caso de oro del paper) | Validación del modelo | `422` |
| Frecuencia por IP | Ventana deslizante en memoria | `429` + `Retry-After` |

### Variables de entorno (todas opcionales — el default ya es razonable)

| Variable | Default | Qué hace |
|---|---|---|
| `LATIO_RATE_LIMIT_ENABLED` | `1` | `0` desactiva el limitador por completo |
| `LATIO_RATE_LIMIT_WINDOW` | `60` | Ventana en segundos |
| `LATIO_RATE_LIMIT_DEFAULT` | `120` | Peticiones/ventana en rutas de lectura |
| `LATIO_RATE_LIMIT_HEAVY` | `20` | Peticiones/ventana en `/v1/reasoning/prove` y `/v1/statements/*` |
| `LATIO_MAX_BODY_BYTES` | `262144` | Tope de cuerpo (256 KB) |
| `LATIO_TRUST_FORWARDED_FOR` | `0` | Ver abajo — solo si `REMOTE_ADDR` no trae la IP real |

Un valor basura en cualquiera de estas (vacío, no numérico) cae al default en vez de tumbar el
arranque: un error acá rompería **toda** la app al importar el módulo.

`/health` está **siempre exento**, para no romper monitores de uptime.

### Dos detalles que no son obvios

1. **`X-Forwarded-For` no se usa por default.** Bajo Passenger, Apache normalmente entrega la IP
   real en `REMOTE_ADDR`. `X-Forwarded-For` lo puede falsificar cualquiera que mande el header, así
   que confiar en él sin un proxy que lo reescriba vuelve trivial evadir el límite. **Cómo
   comprobarlo en producción:** pegale desde tu casa 21 veces seguidas a
   `/v1/statements/propose` (ver checklist §7); si el 21° da 429, `REMOTE_ADDR` funciona. Si en
   cambio ves que un solo visitante bloquea a todos, poné `LATIO_TRUST_FORWARDED_FOR=1` — usa el
   **último** elemento de `X-Forwarded-For` (el que agrega el proxy de confianza), no el primero,
   que controla el cliente.

2. **El contador vive en la memoria del proceso.** Passenger puede levantar varios procesos para
   la misma app; cada uno lleva su propio contador, así que el límite efectivo es
   `LATIO_RATE_LIMIT_* × nº de procesos`. Para frenar abuso alcanza; para una cuota exacta haría
   falta almacenamiento compartido (Redis), que el hosting compartido no ofrece.

## Memoria por proceso (medido, no estimado)

`_ARTICLES_CACHE` cachea cada corpus para toda la vida del proceso — la decisión correcta para la
latencia, pero conviene tener el número antes de que aparezca en el panel:

| Concepto | Medido |
|---|---|
| RSS tras importar la app (baseline) | 45 MB |
| `AR-CC`: 4.40 MB en disco → en RAM | 9.9 MB (2.25×) |
| `CO-CC`: 2.88 MB en disco → en RAM | 5.9 MB (2.04×) |
| Los 8 corpus cacheados (proyección) | ~54 MB |
| **Total por proceso Passenger** | **~99 MB** |
| Con 4 procesos Passenger | ~395 MB |

Manejable en un plan Business, pero se paga **por proceso**. Si el panel reporta presión de
memoria: limitar el número de procesos de la app en hPanel, o servir menos corpus. No bloquea el
lanzamiento.

## Riesgo que queda abierto

- **La API sigue sin autenticación.** El límite de tasa frena el abuso accidental y el escaneo
  casual; no frena a alguien decidido con IPs rotativas. Para un lanzamiento académico de alcance
  controlado es la postura correcta. Si en algún momento hay que cerrarla, el paso siguiente es una
  API key por header, no más límites.
- **Ningún corpus tiene `retrieved_at` poblado** (sigue en `null` con TODO en
  `config/corpus_registry.yaml`, 9 ocurrencias; ver `docs/notas_gobernanza.md`) — no bloquea el
  despliegue técnico, pero si el lanzamiento incluye afirmaciones de procedencia/trazabilidad de
  los datos, falta ese dato.

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
