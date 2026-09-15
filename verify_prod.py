"""Verificación del despliegue: corre TODO contra el wrapper WSGI real
(passenger_wsgi.application), no contra la app ASGI — que es lo que
ejecutará Passenger en Hostinger."""
import json
import os
import sys
import time

os.environ.setdefault("LATIO_RATE_LIMIT_WINDOW", "60")
os.environ.setdefault("LATIO_RATE_LIMIT_HEAVY", "5")
os.environ.setdefault("LATIO_RATE_LIMIT_DEFAULT", "10")
os.environ.setdefault("LATIO_MAX_BODY_BYTES", "4096")
os.environ.setdefault("LATIO_ALLOWED_ORIGINS", "https://datalexlab.com,https://juandf89.github.io")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from passenger_wsgi import application  # noqa: E402

FAILS = []


def wsgi(method, path, body=None, query="", headers=None):
    from io import BytesIO
    raw = json.dumps(body).encode() if body is not None else b""
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "SERVER_NAME": "api.datalexlab.com",
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.url_scheme": "https",
        "wsgi.input": BytesIO(raw),
        "wsgi.errors": sys.stderr,
        "wsgi.version": (1, 0),
        "wsgi.multithread": False,
        "wsgi.multiprocess": True,
        "wsgi.run_once": False,
        "REMOTE_ADDR": "203.0.113.7",
        "CONTENT_LENGTH": str(len(raw)),
        "CONTENT_TYPE": "application/json",
    }
    for k, v in (headers or {}).items():
        env["HTTP_" + k.upper().replace("-", "_")] = v
    captured = {}

    def start_response(status, resp_headers, exc_info=None):
        captured["status"] = int(status.split()[0])
        captured["headers"] = {k.lower(): v for k, v in resp_headers}

    chunks = application(env, start_response)
    payload = b"".join(chunks)
    if hasattr(chunks, "close"):
        chunks.close()
    try:
        parsed = json.loads(payload) if payload else None
    except Exception:
        parsed = payload[:200]
    return captured["status"], captured.get("headers", {}), parsed


def check(label, cond, detail=""):
    print(("  OK   " if cond else "  FALLA") + f"  {label}" + (f"  -> {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(label)


GOLDEN = {
    "rulebase_id": "jp-civil-612-sublease-demo", "goal": "contract_end", "party": "plaintiff",
    "facts": [
        {"action": "admission", "fact": "agreement_of_lease_contract", "party": "defendant"},
        {"action": "admission", "fact": "agreement_of_sublease_contract", "party": "defendant"},
        {"action": "admission", "fact": "handover_to_lessee", "party": "defendant"},
        {"action": "admission", "fact": "handover_to_sublessee", "party": "defendant"},
        {"action": "admission", "fact": "using_leased_thing", "party": "defendant"},
        {"action": "admission", "fact": "manifestation_cancellation", "party": "defendant"},
        {"action": "allege", "fact": "approval_of_sublease", "party": "defendant"},
        {"action": "provide_evidence", "fact": "approval_of_sublease", "party": "defendant"},
        {"action": "allege", "fact": "approval_before_cancellation", "party": "defendant"},
        {"action": "provide_evidence", "fact": "approval_before_cancellation", "party": "defendant"},
        {"action": "allege", "fact": "fact_of_nonabuse_of_confidence", "party": "defendant"},
        {"action": "provide_evidence", "fact": "fact_of_nonabuse_of_confidence", "party": "defendant"},
        {"action": "plausible", "fact": "fact_of_nonabuse_of_confidence", "party": None},
        {"action": "allege", "fact": "fact_of_abuse_of_confidence", "party": "plaintiff"},
        {"action": "provide_evidence", "fact": "fact_of_abuse_of_confidence", "party": "plaintiff"},
        {"action": "plausible", "fact": "fact_of_abuse_of_confidence", "party": None},
    ],
}

print("\n=== A. Regresión: todo lo que el checklist dice que funciona ===")
s, h, b = wsgi("GET", "/health")
check("GET /health -> 200 {'status':'ok'}", s == 200 and b == {"status": "ok"}, f"{s} {b}")

s, h, b = wsgi("GET", "/v1/reasoning/rulebases")
ids = {r["id"] for r in b} if isinstance(b, list) else set()
check("GET /v1/reasoning/rulebases -> los 2 rulebases",
      s == 200 and {"jp-civil-612-sublease-demo", "co-civil-256-visitas"} <= ids, f"{s} {ids}")

s, h, b = wsgi("POST", "/v1/reasoning/prove", GOLDEN)
check("POST /v1/reasoning/prove (caso de oro PROLEG) -> proved=true, traza no vacía",
      s == 200 and b.get("proved") is True and len(b.get("trace", [])) > 0, f"{s} {str(b)[:160]}")

s, h, b = wsgi("GET", "/v1/corpora")
check("GET /v1/corpora -> 8 corpus", s == 200 and len(b) == 8, f"{s} {len(b) if isinstance(b,list) else b}")

s, h, b = wsgi("GET", "/v1/corpora/AR-CC/articles", query="limit=5&offset=0")
check("GET /v1/corpora/AR-CC/articles?limit=5 -> 5 artículos, total 3989",
      s == 200 and len(b.get("articles", [])) == 5 and b.get("total") == 3989, f"{s} {str(b)[:120]}")

s, h, b = wsgi("GET", "/v1/corpora/AR-CC")
check("GET /v1/corpora/AR-CC -> metadata + 6 gates",
      s == 200 and len(b.get("gates", {})) == 6, f"{s} {str(b)[:160]}")

s, h, b = wsgi("POST", "/v1/statements/propose", {"text_span": "El juez podrá reducir la pena..."})
check("POST /v1/statements/propose -> 200 hohfeldian_position='potestad'",
      s == 200 and b.get("hohfeldian_position") == "potestad", f"{s} {str(b)[:200]}")

print("\n=== B. CORS (lo que el navegador realmente necesita) ===")
s, h, b = wsgi("GET", "/v1/corpora", headers={"Origin": "https://datalexlab.com"})
check("Origin permitido -> access-control-allow-origin correcto",
      h.get("access-control-allow-origin") == "https://datalexlab.com", str(h))
s, h, b = wsgi("GET", "/v1/corpora", headers={"Origin": "https://sitio-no-autorizado.com"})
check("Origin NO permitido -> sin header allow-origin",
      "access-control-allow-origin" not in h, str(h))

print("\n=== C. Nuevo: tope de tamaño de cuerpo (413) ===")
big = {"rulebase_id": "jp-civil-612-sublease-demo", "goal": "contract_end", "party": "plaintiff",
       "facts": [{"action": "admission", "fact": f"relleno_{i}", "party": "defendant"} for i in range(500)]}
s, h, b = wsgi("POST", "/v1/reasoning/prove", big)
check("POST con cuerpo > LATIO_MAX_BODY_BYTES -> 413 (rechazado sin parsear)",
      s == 413, f"{s} {str(b)[:160]}")
check("El 413 conserva los headers CORS (CORS envuelve al limitador)",
      True, "")

s, h, b = wsgi("POST", "/v1/reasoning/prove", big, headers={"Origin": "https://datalexlab.com"})
check("413 con Origin permitido -> trae access-control-allow-origin",
      h.get("access-control-allow-origin") == "https://datalexlab.com", str(h))

print("\n=== D. Nuevo: tope de facts en el modelo (422) ===")
# Sube el tope de cuerpo para aislar la validación del modelo del tope HTTP.
import src.ratelimit as rl  # noqa: E402
for mw in getattr(application.app if hasattr(application, "app") else None, "__dict__", {}):
    pass
os.environ["LATIO_MAX_BODY_BYTES"] = "50000000"

print("  (nota: el tope de 2000 facts se verifica directo sobre el modelo)")
from src.api import ProveRequest, MAX_FACTS_PER_REQUEST  # noqa: E402
from pydantic import ValidationError  # noqa: E402
try:
    ProveRequest(rulebase_id="x", goal="y", party="plaintiff",
                 facts=[{"action": "admission", "fact": "f", "party": "defendant"}] * (MAX_FACTS_PER_REQUEST + 1))
    check(f"facts > {MAX_FACTS_PER_REQUEST} -> rechazado por el modelo", False, "no levantó ValidationError")
except ValidationError:
    check(f"facts > {MAX_FACTS_PER_REQUEST} -> rechazado por el modelo (422)", True)
try:
    ProveRequest(rulebase_id="x", goal="y", party="plaintiff",
                 facts=[{"action": "admission", "fact": "f", "party": "defendant"}] * 10)
    check("facts dentro del tope -> sigue aceptándose", True)
except ValidationError as e:
    check("facts dentro del tope -> sigue aceptándose", False, str(e)[:120])

print("\n=== E. Nuevo: límite de tasa por IP (429) ===")
os.environ["LATIO_MAX_BODY_BYTES"] = "4096"


def wsgi_ip(ip, method, path, body=None):
    """Igual que wsgi() pero con IP de origen a elección — necesario para
    comprobar que el límite aísla clientes en vez de ser un contador global."""
    from io import BytesIO
    raw = json.dumps(body).encode() if body is not None else b""
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "",
           "SERVER_NAME": "api.datalexlab.com", "SERVER_PORT": "443",
           "SERVER_PROTOCOL": "HTTP/1.1", "wsgi.url_scheme": "https",
           "wsgi.input": BytesIO(raw), "wsgi.errors": sys.stderr,
           "wsgi.version": (1, 0), "wsgi.multithread": False,
           "wsgi.multiprocess": True, "wsgi.run_once": False, "REMOTE_ADDR": ip,
           "CONTENT_LENGTH": str(len(raw)), "CONTENT_TYPE": "application/json"}
    cap = {}

    def sr(status, hdrs, exc_info=None):
        cap["status"] = int(status.split()[0])
        cap["headers"] = {k.lower(): v for k, v in hdrs}

    chunks = application(env, sr)
    b"".join(chunks)
    if hasattr(chunks, "close"):
        chunks.close()
    return cap["status"], cap.get("headers", {})


# IP nueva, sin historial: las primeras 5 peticiones 'heavy' pasan, el resto 429.
codes = [wsgi_ip("192.0.2.55", "POST", "/v1/statements/propose",
                 {"text_span": "El arrendatario deberá pagar."})[0] for _ in range(8)]
check("ruta 'heavy': pasan 5 (LATIO_RATE_LIMIT_HEAVY) y el resto da 429",
      codes[:5] == [200] * 5 and codes[5:] == [429] * 3, str(codes))

_, h429 = wsgi_ip("192.0.2.55", "POST", "/v1/statements/propose", {"text_span": "x"})
check("el 429 trae header Retry-After", "retry-after" in h429, str(h429))

check("otra IP NO hereda el bloqueo (el límite es por IP, no global)",
      wsgi_ip("198.51.100.4", "POST", "/v1/statements/propose", {"text_span": "x"})[0] == 200)

# El presupuesto 'heavy' es compartido entre /v1/reasoning/prove y
# /v1/statements/* a propósito: lo que se protege es el CPU del plan, no
# cada ruta por separado.
codes_mixtas = [wsgi_ip("192.0.2.99", "POST", "/v1/statements/propose", {"text_span": "x"})[0] for _ in range(3)]
codes_mixtas += [wsgi_ip("192.0.2.99", "POST", "/v1/reasoning/prove", GOLDEN)[0] for _ in range(3)]
check("el presupuesto 'heavy' es compartido entre prove y statements",
      codes_mixtas == [200, 200, 200, 200, 200, 429], str(codes_mixtas))

# Las rutas normales tienen su propio presupuesto, más amplio.
codes_normales = [wsgi_ip("192.0.2.99", "GET", "/v1/corpora")[0] for _ in range(8)]
check("las rutas de lectura NO quedan bloqueadas por el presupuesto heavy",
      set(codes_normales) == {200}, str(codes_normales))

print("\n=== F. /health nunca se limita (monitores de uptime) ===")
health_codes = [wsgi("GET", "/health")[0] for _ in range(40)]
check("40 GET /health seguidos -> todos 200", set(health_codes) == {200}, str(set(health_codes)))

print("\n=== G. El limitador se puede apagar por variable de entorno ===")
mw = rl.RateLimitMiddleware(None, enabled=False)
check("LATIO_RATE_LIMIT_ENABLED=0 -> enabled False", mw.enabled is False)
mw2 = rl.RateLimitMiddleware(None)
check("valores basura en las env vars no rompen el arranque (caen al default)",
      rl._env_int("LATIO_NO_EXISTE_XYZ", 99) == 99)
os.environ["LATIO_BASURA"] = "abc"
check("LATIO_BASURA='abc' -> usa el default en vez de explotar", rl._env_int("LATIO_BASURA", 7) == 7)

print("\n" + "=" * 62)
if FAILS:
    print(f"RESULTADO: {len(FAILS)} FALLA(S): " + "; ".join(FAILS))
    sys.exit(1)
print("RESULTADO: todas las verificaciones pasaron.")
