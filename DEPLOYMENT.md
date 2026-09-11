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

### Listo en el repo
- **`passenger_wsgi.py`** (raíz del repo): envuelve `src.api:app` con `a2wsgi.ASGIMiddleware` para
  exponer un callable WSGI válido. **Probado de verdad** con una request WSGI sintética contra
  `/health` y `/v1/corpora` — ambos responden 200 con datos reales, no es solo código sin ejercitar.
- **`requirements-prod.txt`**: agregó `a2wsgi==1.10.10` (versión instalada y verificada acá) además
  de `fastapi`/`uvicorn`/`pydantic`/`pyyaml` pineados. `uvicorn` no hace falta para este camino
  (Passenger no lo usa), pero no molesta tenerlo listado para cuando se pruebe local.
- **`GET /health`**: sirve para que vos mismo confirmes desde el navegador que la app está viva antes
  de cablear DNS/dominio.
- **CORS por variable de entorno** (`LATIO_ALLOWED_ORIGINS`, ver `src/api.py`) — en hPanel esto se
  configura como variable de entorno de la Python App (la sección "Setup Python App" tiene un campo
  para variables de entorno) o, si no está disponible ahí, hPanel suele permitir un archivo `.env`
  que Passenger carga — confirmalo en tu panel, no puedo verlo desde acá.

### Pasos en hPanel (a ejecutar por vos — no tengo acceso a tu cuenta)

1. **hPanel → Avanzado → Setup Python App** (o "Configurar aplicación Python", el nombre exacto
   varía). Creá una nueva app:
   - **Dominio/subdominio**: si `api.datalexlab.com` es el subdominio deseado (coherente con lo que
     ya referencia `README.md`/`toolkit-api/index.html`), primero crealo en hPanel → Dominios →
     Subdominios, apuntando su document root a la carpeta donde subas este repo.
   - **Versión de Python**: la más alta disponible que sea ≥ 3.10 (el código usa sintaxis moderna de
     type hints de `src/reasoning/`); confirmá cuál ofrece tu plan.
   - **Archivo de arranque**: `passenger_wsgi.py`.
   - **Punto de entrada**: `application` (nombre del callable, ya está así en el archivo).
2. **Subir el código**: por Git (si hPanel lo soporta en tu plan) o por el Administrador de Archivos /
   SFTP. Necesitás como mínimo: `src/`, `passenger_wsgi.py`, `requirements-prod.txt`,
   `reports/manifest.json`, `config/corpus_registry.yaml`, y `data/processed/*.json` (los artículos
   reales que sirven `/v1/corpora/*` — sin esa carpeta esos endpoints devuelven 404, no rompen el
   arranque, pero pierden su contenido real).
3. **Instalar dependencias**: hPanel normalmente da un botón "Instalar requerimientos" apuntando a un
   `requirements.txt` — apuntalo a **`requirements-prod.txt`** (versiones exactas verificadas), no al
   `requirements.txt` de desarrollo (rangos `>=`, sin `a2wsgi`). Si tu plan solo deja elegir
   literalmente `requirements.txt`, la alternativa más simple es copiar `requirements-prod.txt` sobre
   `requirements.txt` en el servidor (no en el repo local) antes de instalar.
4. **Variables de entorno**: seteá `LATIO_ALLOWED_ORIGINS` al origen real del frontend (ver checklist
   abajo) — si hPanel no expone variables de entorno para Python Apps en tu plan, avisame y agrego un
   fallback que lea un archivo de config en vez de `os.environ`.
5. **Reiniciar la app** (botón "Restart" en hPanel) y probar `https://api.datalexlab.com/health` desde
   el navegador — debería devolver `{"status":"ok"}`. Si da error, lo primero a revisar es el log de
   Passenger que hPanel expone en la misma pantalla (errores de import, versión de Python incompatible,
   dependencias faltantes son las causas más comunes).

### Qué NO puedo verificar por vos
No tengo acceso a tu cuenta de Hostinger ni a hPanel — todo lo de esta sección son instrucciones para
que las ejecutes vos. Si en algún paso el panel se ve distinto a lo descripto (Hostinger cambia la UI
de hPanel con cierta frecuencia), decime qué ves y ajusto las instrucciones.

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
pip install -r requirements-prod.txt
python -c "
from passenger_wsgi import application
# smoke test WSGI mínimo — ver el que corrí yo mismo para /health y /v1/corpora
"
```

---

## Alternativa descartada por ahora: Docker/VPS

`Dockerfile`, `docker-compose.yml` y `requirements-prod.txt` (compartido con la ruta de Hostinger)
quedan preparados por si en el futuro migran a un VPS con Docker (Hostinger también vende VPS KVM, o
cualquier otro proveedor). **No construí ni probé la imagen** (el daemon de Docker no estaba
disponible en este entorno) — si retoman esta ruta más adelante, correr `docker compose up --build`
y validar antes de confiar en ella.
