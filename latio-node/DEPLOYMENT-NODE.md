# Despliegue de LATIO API (Node.js) — Hostinger, plan Business

## Por qué existe este documento (y no se reutiliza DEPLOYMENT.md)

`DEPLOYMENT.md` (en el repo Python, `latio/`) describe el despliegue original
vía **Passenger + `passenger_wsgi.py`**, pensado para **Setup Python App**.
Se confirmó con dos artículos oficiales de soporte de Hostinger que **Python
solo corre en planes VPS** — nunca en Web/Cloud/Business (hosting
compartido). El plan actual es Business, y no se va a migrar a VPS ni sumar
suscripciones nuevas (decisión explícita: mantener la infraestructura de
`datalexlab.com` sin más aplicaciones ni suscripciones).

La alternativa real, ya probada en producción por el proyecto hermano
**datalex-lab** (`api.datalexlab.com`), es un **Node.js Web App** — Hostinger
sí lo soporta en Business vía `Websites → Add website → Node.js Web App`,
corriendo detrás del módulo `lsnode` de LiteSpeed. Este repo (`latio-node/`)
es el puerto completo del motor real (PROLEG + etiquetado léxico + navegación
de corpus) a Node.js/Express para ese camino.

**Decisión de aislamiento:** esta es una app Node.js **nueva y separada** del
proceso ya en producción de datalex-lab — no comparte proceso ni dominio con
`api.datalexlab.com` — con su **propio subdominio**:

```
api-latio.datalexlab.com
```

## 0. Qué se verificó antes de este documento

- **133/133 tests** del repo Python (oráculo) pasan, incluida la suite con el
  rate limiter activo en modo agresivo.
- **54/54 tests Node** (`npm test`, `node --test tests/`) — subconjunto
  representativo de los mismos comportamientos, corriendo directo contra los
  módulos portados (sin HTTP) y contra la app Express completa (con HTTP).
- **`cross_validate.mjs`**: el caso de oro del Apéndice B del paper PROLEG
  (Satoh et al. 2010) — incluida la cadena completa "defensa alegada pero no
  probada" → "defensa probada pero derrotada por su propia excepción" →
  `contract_end` probado — corrido en paralelo por el motor Python real
  (importado directo, sin pasar por HTTP) y por el motor Node vía HTTP.
  Coinciden campo a campo. También corre 2 escenarios de CO-256 y 5 textos
  por el motor de etiquetado léxico. **Correr de nuevo antes de desplegar**
  si se toca cualquier archivo bajo `server/reasoning/` o
  `server/labeling/`:

  ```bash
  cd latio-node
  node cross_validate.mjs
  ```

  (Requiere que `/ruta/a/latio` — el repo Python — exista localmente con sus
  dependencias instaladas; ajustar `PY_REPO` en `cross_validate.mjs` si la
  ruta cambia.)

- **`verify_prod.mjs`**: checklist HTTP contra una URL ya desplegada (local o
  producción) — ver paso 6 más abajo.

## 1. Qué SÍ y qué NO se portó (alcance deliberado)

Portado completo y verificado: el meta-intérprete PROLEG
(`server/reasoning/engine.mjs`), los dos rulebases de ejemplo, el motor de
etiquetado léxico determinista (`server/labeling/`), el rate limiter por IP,
y la parte del esquema ontológico (`server/models.mjs`) que las rutas HTTP
realmente usan.

**Deliberadamente NO portado** (confirmado grepeando los imports reales de
`src/api.py` en el repo Python): `ArticleRecord`, `Institution`,
`Architecture`, `Referral`, `Referrals`, `Validity`, `PathNode` y sus
validadores — pertenecen al pipeline de ingesta (`src/pipeline.py`), que no
se expone por ningún endpoint HTTP. Si en el futuro se expone un endpoint de
ingesta, portar esas piezas en ese momento desde `src/models.py`, no antes.

## 2. Diferencia de arquitectura importante: identificación de IP

Bajo `lsnode`, Hostinger conecta el proceso Node por un **socket Unix**
(`process.env.LSNODE_SOCKET`), no por TCP — `req.socket.remoteAddress` en
Express **no sirve** para identificar al cliente (ni existe un "peer" TCP que
leer). La única fuente de la IP real es el header `X-Forwarded-For` que
LiteSpeed agrega. `server/ratelimit.mjs` ya implementa esto correctamente
(toma el **último** valor de la cadena, no el primero — ver el comentario de
cabecera de ese archivo para el razonamiento completo). **Verificar este
comportamiento en producción real es el paso más importante del checklist
post-despliegue (sección 6)** — es el tipo de bug que no se nota hasta que
dos usuarios reales chocan contra el mismo límite compartido.

## 3. Pasos en hPanel

Estos pasos replican el patrón ya usado (y ya en producción) para
`api.datalexlab.com` (proyecto `datalex-lab`) — mismo hosting, misma cuenta.

1. **hPanel → Websites → Add website → Node.js Web App.**
2. **Dominio/subdominio:** `api-latio.datalexlab.com` (crear el subdominio
   primero en `Domains → Subdomains` si el asistente no lo ofrece crear
   inline).
3. **Versión de Node.js:** la más reciente LTS disponible en el selector de
   hPanel (el proyecto hermano usa Node moderno con sintaxis ESM sin
   problemas — este puerto también usa `"type": "module"` y sintaxis
   ESM/`.mjs` en todo el código, sin necesidad de transpilar).
4. **Directorio de la app / Application startup file:** apuntar a
   `server/app.mjs` (o dejar que hPanel use el campo `"main"` de
   `package.json`, que ya apunta ahí).
5. **Subir el código.** Opciones, en orden de preferencia:
   - Git (si hPanel lo ofrece para Node.js Web Apps, igual que para
     datalex-lab) apuntando a este repo/carpeta.
   - Subida manual de `latio-node/` completo (excluir `node_modules/` — se
     instala en el paso siguiente) vía el administrador de archivos o SFTP.
6. **Instalar dependencias.** hPanel para Node.js Web Apps normalmente ofrece
   un botón "NPM Install" o un terminal embebido — correr `npm install
   --production` desde el directorio de la app (única dependencia de
   producción: `express`).
7. **Variables de entorno** (panel de la app Node.js en hPanel — mismo lugar
   donde datalex-lab tiene las suyas):

   | Variable | Valor recomendado | Motivo |
   |---|---|---|
   | `LATIO_ALLOWED_ORIGINS` | `https://datalexlab.com,https://www.datalexlab.com,https://juandf89.github.io` | Orígenes reales de producción — sin esto usa el default de desarrollo (`localhost`), que un navegador real rechazaría igual, pero es mejor fijarlo explícito. |
   | `LATIO_RATE_LIMIT_ENABLED` | `1` | Explícito, aunque `1` ya es el default. |
   | `LATIO_RATE_LIMIT_WINDOW` | `60` | Ventana en segundos. |
   | `LATIO_RATE_LIMIT_DEFAULT` | `120` | Peticiones/ventana en rutas normales. |
   | `LATIO_RATE_LIMIT_HEAVY` | `20` | Peticiones/ventana en `/v1/reasoning/prove` y `/v1/statements/*`. |
   | `LATIO_MAX_BODY_BYTES` | `262144` | Tope de `Content-Length` (256KB). |

   No hace falta `PORT` ni `LSNODE_SOCKET` — Hostinger los inyecta solo;
   `server/app.mjs` ya los lee en ese orden de prioridad
   (`LSNODE_SOCKET || PORT || 3000`).
8. **Arrancar/reiniciar la app** desde el panel.

## 4. Qué llevar en la subida (checklist de archivos)

```
latio-node/
├── package.json          (con "type":"module", dependencies.express)
├── package-lock.json
├── server/                (todo el código de la app)
├── config/corpus_registry.json
├── reports/manifest.json
└── data/processed/*.json  (los corpus reales disponibles)
```

**No subir**: `node_modules/` (se instala en el servidor), `tests/`,
`cross_validate.mjs`, `verify_prod.mjs`, este mismo documento — no son
necesarios para que la app corra, aunque tampoco rompen nada si quedan (no
se exponen por ningún endpoint HTTP; a diferencia de la ruta Python, acá no
hay archivos estáticos servidos automáticamente desde el directorio del
proyecto — Express solo responde a las rutas que `server/app.mjs` registra
explícitamente, así que ni `data/`, ni `config/`, ni `reports/` son
descargables por HTTP sin necesidad de un `.htaccess` adicional, a
diferencia del hallazgo de la auditoría Python original).

**Corpus disponibles:** los 8 (`AR-CC`, `AR-CCYC`, `BR-CC`, `CL-CC`, `CO-CC`,
`MX-CCF`, `MX-CDMX`, `PE-CC`) — copiados desde `latio-kit/data/processed/` y
verificados con `/v1/corpora/{id}/articles` (HTTP 200 real en los 8) antes de
esta entrega. Si algún corpus se vuelve a copiar a mano en el futuro, cada
`*_articles.json` debe ser JSON válido — un archivo corrupto o truncado
responde 500 con detalle (`server/data.mjs`, `CorruptDataError`) en vez de
tumbar el proceso; uno ausente responde 404 explícito
(`No se encontró el archivo de artículos de '<id>'`).

## 5. Memoria del proceso

Un solo proceso Node por app en plan Business (igual que Passenger con
`min_instances`/`max_pool_size` bajos en el plan anterior). El costo de
memoria acá es más liviano que la ruta Python: no hay múltiples procesos
worker, y los artículos de cada corpus se cargan perezosamente y se cachean
solo tras el primer acceso (`server/data.mjs`) — el peor caso son los 8
archivos de artículos cacheados a la vez (hasta ~4.4MB cada uno según la
medición original en Python), del orden de unas pocas decenas de MB por
encima del baseline de Node/Express, muy por debajo de lo medido para el
proceso Python (~99MB baseline, hasta ~395MB×4 procesos).

## 6. Checklist post-despliegue

Con la app ya corriendo en `https://api-latio.datalexlab.com`:

```bash
node verify_prod.mjs https://api-latio.datalexlab.com
```

Esto corre automáticamente: `/health`, el caso de oro del Apéndice B vía
`/v1/reasoning/prove`, CORS (origen permitido vs. no permitido), el 413 por
cuerpo grande, y el 404 con detalle de `/v1/corpora`.

**Paso manual que el script NO puede automatizar** (todas sus peticiones
salen con la misma IP): confirmar el aislamiento por IP del rate limiter
haciendo varias peticiones seguidas desde dos redes distintas (por ejemplo,
tu conexión normal y los datos móviles del celular, o dos personas distintas
del equipo) contra una ruta "heavy" (`/v1/reasoning/prove` o
`/v1/statements/propose`) — confirmar que agotar el límite desde una red
**no** bloquea a la otra. Es exactamente el bug que existía en la ruta
Python original (`a2wsgi` compartía `scope["client"]` entre todos los
clientes) y el motivo de todo el comentario de cabecera en
`server/ratelimit.mjs` — si este chequeo falla, es casi seguro un problema
de configuración de `X-Forwarded-For` en LiteSpeed/hPanel, no un bug en el
código (revisar primero si hay un proxy adicional agregando su propia IP a
la cadena antes que LiteSpeed).

Para probar el 429 explícitamente (bloquea tu propia IP durante la ventana
configurada — usar con cuidado en producción):

```bash
node verify_prod.mjs https://api-latio.datalexlab.com --hit-rate-limit
```

## 7. Rollback

Si algo falla en producción y hace falta volver atrás rápido: el Node.js Web
App de `api-latio.datalexlab.com` es un sitio/subdominio completamente
aparte de `api.datalexlab.com` (datalex-lab) — apagarlo o borrarlo desde
hPanel no afecta al proyecto hermano en absoluto. El explorador
(`toolkit-api/index.html`, banner "Modo demostración") puede seguir
sirviendo el modo mock mientras se resuelve, sin URL de LATIO real apuntando
a nada roto.
