"""ratelimit.py — límite de tasa por IP y tope de tamaño del cuerpo de la
petición, para exponer la API en hosting compartido sin autenticación.

Por qué existe
--------------
`/v1/reasoning/prove` acepta un `facts: List[FactEntry]` de tamaño arbitrario.
Dos costos crecen linealmente con ese tamaño y ninguno estaba acotado:

1. La validación Pydantic de N `FactEntry` (el costo dominante en CPU/RAM).
2. Las búsquedas de `FactBase` (`has_allege_and_evidence`, `has_admission`,
   `is_plausible`, en src/reasoning/models.py) son barridos LINEALES sobre
   `entries`, y el meta-intérprete las llama una o dos veces por literal y
   por regla. El costo total es O(reglas x cuerpo x N).

En hosting compartido eso no es solo un problema de esta app: consume el
CPU/RAM del plan y puede afectar a los demás sitios de la misma cuenta.

Este módulo NO reemplaza autenticación. Es el piso mínimo para publicar un
endpoint de cómputo abierto: acotar el tamaño de entrada y la frecuencia.

Decisiones de diseño
--------------------
* **Cero dependencias nuevas.** Solo stdlib + Starlette (que ya viene con
  FastAPI). Se evitó `slowapi`/`limits` a propósito: cada dependencia extra
  es un `ModuleNotFoundError` más que puede tumbar el arranque bajo
  Passenger, que es exactamente el modo de falla que documenta DEPLOYMENT.md.
* **Middleware ASGI puro**, no `BaseHTTPMiddleware`: menos capas y sin
  task groups de anyio, que es lo más predecible corriendo dentro del
  wrapper `a2wsgi.ASGIMiddleware`.
* **Contador en memoria del proceso.** Passenger puede levantar VARIOS
  procesos para la misma app; cada uno lleva su propio contador, así que el
  límite efectivo es `LATIO_RATE_LIMIT_* x nº de procesos`. Para frenar
  abuso es suficiente; para una cuota exacta haría falta almacenamiento
  compartido (Redis), que el hosting compartido no ofrece.
* **La tabla de contadores se poda** (ver `_MAX_TRACKED_CLIENTS`): sin eso,
  un escaneo distribuido convertiría al propio limitador en una fuga de
  memoria.

Configuración (variables de entorno, todas opcionales)
------------------------------------------------------
LATIO_RATE_LIMIT_ENABLED    "1" (default) | "0" para desactivar del todo
LATIO_RATE_LIMIT_WINDOW     ventana en segundos (default 60)
LATIO_RATE_LIMIT_DEFAULT    peticiones por ventana, rutas normales (default 120)
LATIO_RATE_LIMIT_HEAVY      peticiones por ventana, rutas caras (default 20)
LATIO_MAX_BODY_BYTES        tope de cuerpo en bytes (default 262144 = 256 KB)
LATIO_TRUST_FORWARDED_FOR   "1" si Passenger/Apache NO propaga REMOTE_ADDR y
                            hay que leer la IP del header X-Forwarded-For
                            (default "0"; ver nota en `_client_ip`)

Rutas "caras" (límite HEAVY): las que ejecutan el motor de razonamiento o el
etiquetado. `/health` queda SIEMPRE exento para no romper monitores de uptime.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Deque, Dict, Tuple

from starlette.responses import JSONResponse

__all__ = ["RateLimitMiddleware", "HEAVY_PATH_PREFIXES", "EXEMPT_PATHS"]


HEAVY_PATH_PREFIXES: Tuple[str, ...] = (
    "/v1/reasoning/prove",
    "/v1/statements/",
)

EXEMPT_PATHS: Tuple[str, ...] = ("/health",)

# Tope de IPs distintas con contador vivo. Al superarlo se descartan las
# entradas más antiguas: el limitador prefiere olvidar a crecer sin techo.
_MAX_TRACKED_CLIENTS = 5000


def _env_int(name: str, default: int) -> int:
    """Lee un entero de entorno tolerando basura: si el panel guarda un valor
    vacío o no numérico, se usa el default en vez de romper el arranque —
    un fallo acá tumbaría TODA la app al importar el módulo."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on", "si", "sí")


class RateLimitMiddleware:
    """Middleware ASGI: rechaza con 413 los cuerpos demasiado grandes y con
    429 las IPs que exceden la frecuencia permitida."""

    def __init__(
        self,
        app,
        *,
        window_seconds: int | None = None,
        default_limit: int | None = None,
        heavy_limit: int | None = None,
        max_body_bytes: int | None = None,
        enabled: bool | None = None,
        trust_forwarded_for: bool | None = None,
    ) -> None:
        self.app = app
        self.enabled = _env_flag("LATIO_RATE_LIMIT_ENABLED", True) if enabled is None else enabled
        self.window = _env_int("LATIO_RATE_LIMIT_WINDOW", 60) if window_seconds is None else window_seconds
        self.default_limit = _env_int("LATIO_RATE_LIMIT_DEFAULT", 120) if default_limit is None else default_limit
        self.heavy_limit = _env_int("LATIO_RATE_LIMIT_HEAVY", 20) if heavy_limit is None else heavy_limit
        self.max_body_bytes = _env_int("LATIO_MAX_BODY_BYTES", 262144) if max_body_bytes is None else max_body_bytes
        self.trust_forwarded_for = (
            _env_flag("LATIO_TRUST_FORWARDED_FOR", False)
            if trust_forwarded_for is None
            else trust_forwarded_for
        )

        # (ip, bucket) -> timestamps de las peticiones dentro de la ventana.
        self._hits: Dict[Tuple[str, str], Deque[float]] = {}
        # a2wsgi corre el loop ASGI en un hilo dedicado; el lock es barato y
        # evita cualquier sorpresa si el despliegue cambia a un servidor
        # multihilo (uvicorn con workers, gunicorn, etc.).
        self._lock = threading.Lock()

    # -- identificación del cliente ---------------------------------------

    def _client_ip(self, scope) -> str:
        """IP del cliente.

        OJO — acá hay una trampa específica de este despliegue, comprobada
        leyendo el código de a2wsgi (`a2wsgi/asgi.py: build_scope`):

            if environ.get("REMOTE_ADDR") and environ.get("REMOTE_PORT"):
                scope["client"] = (...)

        a2wsgi solo puebla `scope["client"]` si el entorno WSGI trae AMBAS
        variables. Pero `REMOTE_PORT` **no es parte de la especificación
        WSGI** (PEP 3333) y varios servidores, Passenger entre ellos, no la
        setean. Si falta, `scope["client"]` queda ausente, `request.client`
        es None, y un limitador que dependa solo de eso mete a TODO el
        mundo en un mismo contador: un único abusador devolvería 429 a
        todos los visitantes. Por eso se lee primero `REMOTE_ADDR` del
        entorno WSGI original, que a2wsgi sí conserva en
        `scope["wsgi_environ"]`.

        `X-Forwarded-For` no se usa por default: lo puede falsificar
        cualquiera que mande el header, así que confiar en él sin un proxy
        que lo reescriba vuelve trivial evadir el límite. Si al probar en
        producción resulta que `REMOTE_ADDR` trae la IP del proxy y no la
        del visitante, poner LATIO_TRUST_FORWARDED_FOR=1: se usa entonces el
        ÚLTIMO elemento de X-Forwarded-For (el que agrega el proxy de
        confianza), no el primero, que es el que controla el cliente.
        """
        if self.trust_forwarded_for:
            for raw_name, raw_value in scope.get("headers", ()):
                if raw_name == b"x-forwarded-for":
                    parts = [p.strip() for p in raw_value.decode("latin-1").split(",") if p.strip()]
                    if parts:
                        return parts[-1]
                    break

        environ = scope.get("wsgi_environ")
        if isinstance(environ, dict):
            remote_addr = environ.get("REMOTE_ADDR")
            if remote_addr:
                return str(remote_addr)

        client = scope.get("client")
        if client and client[0]:
            return str(client[0])

        # Sin forma de identificar al cliente. Se agrupa todo bajo una sola
        # clave, que es conservador (puede limitar de más) pero nunca deja
        # el endpoint caro sin ningún tope.
        return "unknown"

    # -- contabilidad de la ventana deslizante ----------------------------

    def _allow(self, ip: str, bucket: str, limit: int) -> Tuple[bool, int]:
        """Registra una petición y dice si se permite. Devuelve
        `(permitida, segundos_hasta_reintentar)`."""
        now = time.monotonic()
        cutoff = now - self.window
        key = (ip, bucket)

        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                if len(self._hits) >= _MAX_TRACKED_CLIENTS:
                    self._prune_locked(cutoff)
                hits = self._hits.setdefault(key, deque())

            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= limit:
                retry_after = max(1, int(self.window - (now - hits[0])) + 1)
                return False, retry_after

            hits.append(now)
            return True, 0

    def _prune_locked(self, cutoff: float) -> None:
        """Descarta contadores sin actividad dentro de la ventana. Se llama
        con `self._lock` tomado."""
        stale = [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]
        for k in stale:
            self._hits.pop(k, None)
        if len(self._hits) >= _MAX_TRACKED_CLIENTS:
            # Todavía lleno de contadores activos: se sacrifican los más
            # antiguos. Es una degradación consciente, no un error.
            oldest = sorted(self._hits.items(), key=lambda kv: kv[1][-1])
            for k, _ in oldest[: len(self._hits) // 4 or 1]:
                self._hits.pop(k, None)

    # -- ASGI --------------------------------------------------------------

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        if path in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        # 1) Tope de tamaño. Se mira Content-Length ANTES de que FastAPI lea
        #    y valide el cuerpo: es el único punto donde el rechazo es
        #    realmente barato.
        if scope.get("method") in ("POST", "PUT", "PATCH"):
            declared = self._declared_length(scope)
            if declared is not None and declared > self.max_body_bytes:
                await JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Cuerpo de {declared} bytes; el máximo admitido es "
                            f"{self.max_body_bytes} bytes."
                        )
                    },
                )(scope, receive, send)
                return

        # 2) Frecuencia por IP.
        bucket = "heavy" if path.startswith(HEAVY_PATH_PREFIXES) else "default"
        limit = self.heavy_limit if bucket == "heavy" else self.default_limit
        ip = self._client_ip(scope)

        allowed, retry_after = self._allow(ip, bucket, limit)
        if not allowed:
            await JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Límite de {limit} peticiones cada {self.window} s excedido "
                        f"para esta ruta. Reintentar en {retry_after} s."
                    )
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Window": str(self.window),
                },
            )(scope, receive, send)
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _declared_length(scope) -> int | None:
        for raw_name, raw_value in scope.get("headers", ()):
            if raw_name == b"content-length":
                try:
                    return int(raw_value)
                except ValueError:
                    return None
        return None
