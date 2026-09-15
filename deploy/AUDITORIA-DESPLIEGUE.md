# Auditoría del despliegue LATIO — hallazgos verificados

**Fecha:** 2026-09-14 · **Alcance:** `DEPLOYMENT.md`, `passenger_wsgi.py`, `src/api.py`,
`src/reasoning/*`, `src/ratelimit.py` (nuevo), `requirements-prod.txt`, `.gitignore`,
`reports/manifest.json`, `config/corpus_registry.yaml`.

Todo lo que dice "verificado" acá se ejecutó, no se leyó. La verificación corre contra
`passenger_wsgi.application` — el callable WSGI real que usará Passenger — no contra la app
ASGI. Script reproducible: `verify_prod.py`.

---

## Resumen

| # | Hallazgo | Severidad | Estado |
|---|---|---|---|
| 1 | Un limitador por IP ingenuo habría sido **global**: `a2wsgi` no puebla `scope["client"]` sin `REMOTE_PORT` | 🔴 | Corregido y verificado |
| 2 | `facts` sin tope + búsquedas **lineales** en `FactBase` = vector de DoS por CPU | 🔴 | Corregido y verificado |
| 3 | `data/`, `config/` y `reports/` quedan descargables por HTTP si el app root está en `public_html` | 🔴 | `.htaccess` provisto — aplicar y verificar |
| 4 | El motivo que da el documento para exigir Python ≥ 3.10 es incorrecto; el troubleshooting manda a buscar un error que nunca va a aparecer | 🟡 | Documento corregido |
| 5 | El origen `https://www.datalexlab.com` **no** está en el default de CORS, pero la propia API se anuncia con ese dominio | 🟡 | Documento corregido — decisión tuya |
| 6 | La suite de tests pasaba por casualidad debajo del tope del limitador | 🟡 | Corregido en `tests/conftest.py` |
| 7 | `data/raw/` **sí** está versionado en git (el `.gitignore` solo excluye `*.pdf`) | 🟡 | Documento corregido |
| 8 | Consumo de memoria por proceso no cuantificado: ~99 MB, ~395 MB con 4 procesos | 🟡 | Medido y documentado |
| 9 | `/docs` (Swagger) público sobre una API sin autenticación | 🟢 | Decisión tuya — documentada |
| 10 | `allow_credentials=True` sin que nada use credenciales | 🟢 | Documentado, sin cambiar |

---

## 🔴 1. El límite por IP habría sido global, no por IP

**Es el hallazgo más importante y no se ve leyendo el código propio: está en `a2wsgi`.**

`a2wsgi/asgi.py: build_scope()` construye el `scope` ASGI a partir del entorno WSGI, y la IP
del cliente solo la puebla si **ambas** variables están presentes:

```python
if environ.get("REMOTE_ADDR") and environ.get("REMOTE_PORT"):
    scope["client"] = (environ.get("REMOTE_ADDR", ""), int(environ.get("REMOTE_PORT", "0")))
```

`REMOTE_PORT` **no forma parte de la especificación WSGI** (PEP 3333). Passenger no la garantiza.
Si falta, `scope["client"]` no existe, `request.client` es `None`, y cualquier limitador que se
apoye solo en eso mete a todos los visitantes en un mismo contador: **un solo abusador devolvería
429 al resto del mundo** — una caída total disfrazada de protección.

**Demostrado, no supuesto.** La primera versión del limitador usaba `scope["client"]`. Con tres IPs
distintas simuladas sobre un entorno WSGI sin `REMOTE_PORT` (el escenario Passenger):

```
FALLA  otra IP NO hereda el bloqueo (el límite es por IP, no global)
FALLA  las rutas de lectura NO quedan bloqueadas por el presupuesto heavy  -> [200,200,200,200,429,429,429,429]
```

**Corrección** (`src/ratelimit.py: _client_ip`): leer `REMOTE_ADDR` del entorno WSGI original, que
a2wsgi sí conserva en `scope["wsgi_environ"]`, antes de caer a `scope["client"]`. Tras el cambio,
las mismas pruebas pasan:

```
OK  otra IP NO hereda el bloqueo (el límite es por IP, no global)
OK  las rutas de lectura NO quedan bloqueadas por el presupuesto heavy
```

`X-Forwarded-For` **no** se usa por default: lo falsifica cualquiera que mande el header, y
confiar en él sin un proxy que lo reescriba vuelve trivial evadir el límite. Si en producción
resulta que `REMOTE_ADDR` trae la IP del proxy y no la del visitante, se activa con
`LATIO_TRUST_FORWARDED_FOR=1` (usa el **último** elemento, el que agrega el proxy de confianza,
no el primero, que controla el cliente).

---

## 🔴 2. El vector de DoS real es el tamaño de `facts`, amplificado por búsquedas lineales

`DEPLOYMENT.md` decía, correctamente, que `/v1/reasoning/prove` acepta "cualquier factbase sin
límite de tamaño ni de frecuencia". Lo que no identificaba es **por qué eso es caro**, que es lo
que decide cómo mitigarlo.

`FactBase` (`src/reasoning/models.py`) resuelve cada consulta con un **barrido lineal** sobre
`entries`, y `has_allege_and_evidence` hace **dos**:

```python
alleged   = any(e.action == ALLEGE           and e.fact == fact and e.party == party for e in self.entries)
evidenced = any(e.action == PROVIDE_EVIDENCE and e.fact == fact and e.party == party for e in self.entries)
```

El meta-intérprete (`engine.py`) las llama una o dos veces por literal y por regla. Costo total:
**O(reglas × cuerpo × N)**. Sumado al costo de que Pydantic valide N modelos `FactEntry` — que es
el término dominante en CPU y RAM — un solo POST puede monopolizar el CPU del plan compartido.

**Tres topes, en capas, del más barato al más caro:**

| Capa | Qué corta | Dónde | Respuesta |
|---|---|---|---|
| Tamaño del cuerpo | Rechaza por `Content-Length` **antes** de leer y parsear | `RateLimitMiddleware` | `413` |
| Tamaño de la lista | `facts` ≤ 2000 (~100× el caso de oro del paper, que tiene 16) | `ProveRequest` | `422` |
| Frecuencia | 20 peticiones "caras" por minuto y por IP | `RateLimitMiddleware` | `429` + `Retry-After` |

También se acotaron `rulebase_id` y `goal` a 200 caracteres: son nombres de predicados, no texto
libre, y el mensaje del 404 refleja el `rulebase_id` recibido.

**Cero dependencias nuevas.** Se descartó `slowapi`/`limits` a propósito: cada dependencia extra es
un `ModuleNotFoundError` más capaz de tumbar el arranque bajo Passenger — exactamente el modo de
falla que el propio `DEPLOYMENT.md` dedica una sección a diagnosticar. `requirements-prod.txt`
queda idéntico.

**Detalle de orden que importa:** el limitador se registra **antes** que CORS, para que CORS quede
por fuera y los `429`/`413` también lleven los headers `Access-Control-Allow-*`. Al revés, el
navegador mostraría un error de CORS genérico en lugar del 429 real y el explorador no podría
decirle al usuario qué pasó. Verificado: el 413 con `Origin: https://datalexlab.com` devuelve
`access-control-allow-origin: https://datalexlab.com`.

---

## 🔴 3. Los datos quedan descargables por HTTP, esquivando la API

Passenger no captura los archivos estáticos que estén en el directorio de la app: los sigue
sirviendo Apache. Si el document root de la Python App queda dentro de `public_html` — lo habitual
en Hostinger compartido — entonces esto funciona:

```
https://api.datalexlab.com/data/processed/CO-CC_articles.json   → 2.9 MB
https://api.datalexlab.com/config/corpus_registry.yaml
https://api.datalexlab.com/reports/manifest.json
```

Son los **25 MB de los 8 corpus** descargables de una, sin pasar por ningún endpoint, sin quedar
sujetos al límite de tasa y sin aparecer en ninguna métrica de la API. Un crawler se lleva el plan
de ancho de banda por delante.

`DEPLOYMENT.md` no lo mencionaba. Solución en `deploy/htaccess-para-carpetas-de-datos.txt`: un
`.htaccess` con `Require all denied` dentro de `data/`, `config/` y `reports/`. La API abre esos
archivos por sistema de archivos (`open()`), no por HTTP, así que **no rompe ningún endpoint**.

**No tocar el `.htaccess` que hPanel genera en la raíz de la app** — lleva la configuración de
Passenger y modificarlo puede impedir el arranque. Las reglas van en las subcarpetas.

Verificación después de aplicarlo: la URL de arriba debe dar `403`, y `/v1/corpora` seguir en `200`.

---

## 🟡 4. El motivo de Python ≥ 3.10 estaba mal, y el troubleshooting mandaba a buscar un fantasma

El documento decía:

> `src/reasoning/` usa sintaxis de type hints moderna (por ejemplo `list[dict]`) que rompe en
> < 3.10 con `SyntaxError`

Dos errores:

1. `list[dict]` es **PEP 585, disponible desde Python 3.9**, no 3.10.
2. Todos los módulos de `src/reasoning/` y `src/labeling/` empiezan con
   `from __future__ import annotations` (verificado: 9 archivos), así que las anotaciones ni
   siquiera se evalúan al importar. **No hay `SyntaxError` posible por esa vía.**

El piso real de 3.10 viene de otro lado — de los metadatos de las dependencias pineadas:

| Paquete | Versión | `Requires-Python` |
|---|---|---|
| fastapi | 0.141.1 | **>= 3.10** |
| starlette | 1.0.0 | **>= 3.10** |
| pydantic | 2.13.5 | >= 3.9 |
| a2wsgi | 1.10.10 | >= 3.8 |
| pyyaml | 6.0.3 | >= 3.8 |

**Por qué importa en la práctica:** con Python 3.9, `pip install -r requirements-prod.txt` no
llega a producir un `SyntaxError` — falla antes, al resolver, o instala una FastAPI vieja que sí
entra. El síntoma real es un error de pip en el log de instalación, o un `ImportError`/
`AttributeError` por versión incompatible. Si buscás un `SyntaxError` como decía el documento, no
lo vas a encontrar nunca y vas a diagnosticar mal.

---

## 🟡 5. `www.datalexlab.com` no está en el default de CORS — y la API se anuncia con ese dominio

El default de `src/api.py` (líneas 41-46) incluye `https://datalexlab.com` pero **no**
`https://www.datalexlab.com`. Para el navegador son **orígenes distintos**: `datalexlab.com` y
`www.datalexlab.com` no comparten política CORS.

Y el propio endpoint raíz devuelve:

```python
return {'lab': 'DataLex Lab', 'website': 'https://www.datalexlab.com', ...}
```

Si el explorador termina servido en `https://www.datalexlab.com/latio/` — o si Hostinger redirige
el dominio desnudo a `www`, que es una configuración muy común — el default bloquea al frontend y
el síntoma va a ser exactamente el error de CORS que el documento describe en troubleshooting, con
la variable "correctamente" sin setear.

**Recomendación:** setear `LATIO_ALLOWED_ORIGINS` explícitamente con las tres variantes, en vez de
confiar en el default:

```
https://datalexlab.com,https://www.datalexlab.com,https://juandf89.github.io
```

Confirmá antes, en hPanel → Dominios, si `datalexlab.com` redirige a `www` o al revés.

---

## 🟡 6. La suite de tests pasaba por casualidad

Con el limitador activo, los 92 tests pasaban — pero solo porque el total de peticiones a rutas
"caras" quedaba por debajo del tope de 20/minuto. `TestClient` manda todo desde una única IP
ficticia, así que **toda la suite comparte un presupuesto**.

Demostración: bajando el tope a 5, fallan 8 tests, y los mensajes no dicen nada útil —
`test_propose_rechaza_texto_vacio` falla con un 429, no con lo que está probando. Agregar unos
pocos tests de `/v1/reasoning/prove` o `/v1/statements/*` habría roto tests ajenos con un error
desconcertante.

**Corrección** en `tests/conftest.py`: `os.environ.setdefault("LATIO_RATE_LIMIT_ENABLED", "0")`.
Lo que la suite prueba es la lógica de la API; el limitador tiene su propia verificación con
límites explícitos en `verify_prod.py`.

Verificado: con `LATIO_RATE_LIMIT_HEAVY=1 LATIO_RATE_LIMIT_DEFAULT=1`, los 92 tests siguen pasando.

---

## 🟡 7. `data/raw/` sí está versionado

El documento dice que `data/raw/` (7.7 MB) "no hace falta subirlo". Es cierto que la API no lo lee
—verificado— pero el `.gitignore` solo excluye `data/raw/*.pdf`, y los archivos reales son `.md`:

```
data/raw/ar_ccyc_2015.md, codido_civil_argentino.md, Código_Civil_Chileno.MD,
codigo_civil_federal_de_mexico.md, Codigo_Civil_Mexico_DF.md, CODIGO_CIVIL_peruano.md,
L10406compilada.md, ley_57_de_1887.md, fixture_test_corpus.md   →  ~8.0 MB
```

O sea: **si desplegás por Git, `data/raw/` viene igual**. No rompe nada, pero el clon son ~33 MB,
no 25, y esos 8 MB quedan expuestos por HTTP igual que el resto (ver hallazgo 3 — el `.htaccess` en
`data/` los cubre). Si querés excluirlos del despliegue por Git hay que cambiar el `.gitignore` a
`data/raw/` y sacarlos del índice, que es una decisión de repositorio, no de despliegue.

---

## 🟡 8. Memoria por proceso: medida, no estimada

`_ARTICLES_CACHE` (`src/api.py`) cachea cada corpus en memoria para toda la vida del proceso. Es la
decisión correcta para la latencia, pero en hosting compartido conviene tener el número.

Medido en este entorno (Python 3.11, `tracemalloc` + RSS):

| Concepto | Medido |
|---|---|
| RSS tras importar la app (baseline Passenger) | **45 MB** |
| `AR-CC`: 4.40 MB en disco → en RAM | 9.9 MB (2.25×) |
| `CO-CC`: 2.88 MB en disco → en RAM | 5.9 MB (2.04×) |
| Los 8 corpus en disco | 25.3 MB |
| Proyección: los 8 cacheados | **~54 MB** |
| **Total por proceso Passenger** | **~99 MB** |
| Con 4 procesos Passenger | **~395 MB** |

Es manejable en un plan Business, pero no es despreciable y se paga por proceso. Dos palancas si el
panel reporta presión de memoria: limitar el número de procesos de la app en hPanel, o servir menos
corpus. No hace falta tocarlo antes de lanzar — hace falta saberlo antes de que aparezca.

---

## 🟢 9. `/docs` público sobre una API sin autenticación

`docs_url='/docs'` deja el Swagger UI abierto. No es una vulnerabilidad —los endpoints ya son
públicos— pero es un catálogo navegable que invita a probar el endpoint caro. El documento lo trata
como algo a confirmar que sigue accesible; vale tratarlo como decisión: dejarlo (bueno para un
lanzamiento académico, que es el caso) o apagarlo con `docs_url=None`. Con el límite de tasa puesto,
dejarlo abierto es defendible.

## 🟢 10. `allow_credentials=True` sin credenciales

Nada en la API usa cookies ni `Authorization`. `allow_credentials=True` no aporta y es lo que obliga
a enumerar orígenes en vez de usar `*`. Se puede poner en `False` sin efecto visible para el
explorador. No lo cambié: es cosmético y cambiar middleware de CORS la noche antes de un despliegue
no se paga.

---

## Verificaciones ejecutadas

```
=== A. Regresión: todo lo que el checklist dice que funciona ===
  OK   GET  /health -> 200 {'status':'ok'}
  OK   GET  /v1/reasoning/rulebases -> los 2 rulebases
  OK   POST /v1/reasoning/prove (caso de oro PROLEG) -> proved=true, traza no vacía
  OK   GET  /v1/corpora -> 8 corpus
  OK   GET  /v1/corpora/AR-CC/articles?limit=5 -> 5 artículos, total 3989
  OK   GET  /v1/corpora/AR-CC -> metadata + 6 gates
  OK   POST /v1/statements/propose -> 200 hohfeldian_position='potestad'
=== B. CORS ===
  OK   Origin permitido -> access-control-allow-origin correcto
  OK   Origin NO permitido -> sin header allow-origin
=== C. Tope de tamaño de cuerpo (413) ===
  OK   POST con cuerpo > LATIO_MAX_BODY_BYTES -> 413 (rechazado sin parsear)
  OK   413 con Origin permitido -> trae access-control-allow-origin
=== D. Tope de facts en el modelo (422) ===
  OK   facts > 2000 -> rechazado por el modelo
  OK   facts dentro del tope -> sigue aceptándose
=== E. Límite de tasa por IP (429) ===
  OK   ruta 'heavy': pasan 5 (LATIO_RATE_LIMIT_HEAVY) y el resto da 429
  OK   el 429 trae header Retry-After
  OK   otra IP NO hereda el bloqueo (el límite es por IP, no global)
  OK   el presupuesto 'heavy' es compartido entre prove y statements
  OK   las rutas de lectura NO quedan bloqueadas por el presupuesto heavy
=== F. /health nunca se limita (monitores de uptime) ===
  OK   40 GET /health seguidos -> todos 200
=== G. Configuración por variables de entorno ===
  OK   LATIO_RATE_LIMIT_ENABLED=0 -> desactiva el limitador
  OK   valores basura en las env vars caen al default en vez de tumbar el arranque

RESULTADO: todas las verificaciones pasaron.
pytest: 92 passed
pytest con LATIO_RATE_LIMIT_HEAVY=1 LATIO_RATE_LIMIT_DEFAULT=1: 92 passed
```

## Lo que no pude verificar

- Nada que requiera hPanel o el dominio real: versión de Python del plan, si expone variables de
  entorno para Python Apps, si el app root queda dentro de `public_html`, el certificado TLS, si
  `REMOTE_ADDR` bajo Passenger trae la IP real o la del proxy, y si `datalexlab.com` redirige a
  `www`.
- `Dockerfile`/`docker-compose.yml`: sin cambios y sin construir, igual que antes.
- La medición de memoria es de Python 3.11 en este entorno; en el servidor el orden de magnitud
  será el mismo, el número exacto no.
