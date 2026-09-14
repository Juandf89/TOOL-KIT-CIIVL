// verify_prod.mjs — checklist de verificación post-despliegue contra una
// URL YA DESPLEGADA (Hostinger u otra). Análogo Node del verify_prod.py
// del repo Python (que probaba passenger_wsgi.application end-to-end) —
// acá se prueba por HTTP real, porque en producción el proceso corre
// detrás de LiteSpeed/lsnode, no es invocable como función.
//
// Uso:
//   node verify_prod.mjs https://api-latio.datalexlab.com
//   node verify_prod.mjs http://127.0.0.1:3000   (para probar localmente antes de subir)
//
// IMPORTANTE sobre el chequeo de aislamiento por IP (ver ratelimit.mjs):
// contra una URL real, todas las peticiones de este script salen con la
// MISMA IP de origen, así que ese chequeo específico no se puede validar
// acá sin dos redes distintas de verdad — queda documentado como paso
// manual en DEPLOYMENT-NODE.md (dos peticiones desde redes distintas,
// confirmar que bloquear una no bloquea la otra).

const base = process.argv[2];
if (!base) {
  console.error("Uso: node verify_prod.mjs <URL_BASE>");
  process.exit(2);
}

let failures = 0;
function ok(label, cond, extra = "") {
  if (cond) {
    console.log(`OK   ${label}`);
  } else {
    failures++;
    console.log(`FAIL ${label} ${extra}`);
  }
}

async function main() {
  // 1) Salud básica.
  {
    const res = await fetch(`${base}/health`);
    const body = await res.json().catch(() => null);
    ok("GET /health -> 200 {status: ok}", res.status === 200 && body?.status === "ok", `(status=${res.status}, body=${JSON.stringify(body)})`);
  }

  // 2) Caso de oro: contract_end probado para plaintiff (Apéndice B).
  {
    const facts = [
      ...[
        "agreement_of_lease_contract", "agreement_of_sublease_contract",
        "handover_to_lessee", "handover_to_sublessee",
        "using_leased_thing", "manifestation_cancellation",
      ].map((fact) => ({ action: "admission", fact, party: "defendant" })),
    ];
    const res = await fetch(`${base}/v1/reasoning/prove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rulebase_id: "jp-civil-612-sublease-demo", goal: "cancellation_due_to_sublease", party: "plaintiff", facts }),
    });
    const body = await res.json().catch(() => null);
    ok("POST /v1/reasoning/prove: cancellation_due_to_sublease con las 6 condiciones admitidas -> proved=true",
      res.status === 200 && body?.proved === true, `(status=${res.status}, body=${JSON.stringify(body)})`);
  }

  // 3) CORS: origen permitido vs. no permitido.
  {
    const allowed = await fetch(`${base}/health`, { headers: { Origin: "https://datalexlab.com" } });
    ok("CORS: https://datalexlab.com recibe Access-Control-Allow-Origin",
      allowed.headers.get("access-control-allow-origin") === "https://datalexlab.com");

    const denied = await fetch(`${base}/health`, { headers: { Origin: "https://evil.example" } });
    ok("CORS: origen no permitido NO recibe el header", denied.headers.get("access-control-allow-origin") === null);
  }

  // 4) 413 por cuerpo demasiado grande (si LATIO_MAX_BODY_BYTES está en su
  //    default de 262144, mandamos un texto que claramente lo supere).
  {
    const bigText = "x".repeat(300000);
    const res = await fetch(`${base}/v1/statements/propose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text_span: bigText }),
    });
    ok("POST /v1/statements/propose con cuerpo >262KB -> 413 (o 422 si el server ya lo cortó en text_span<=4000)",
      res.status === 413 || res.status === 422, `(status=${res.status})`);
  }

  // 5) 429 tras exceder el límite por defecto (no se manda contra
  //    producción salvo que se pase --hit-rate-limit explícito, para no
  //    dejar la IP del que corre este script bloqueada innecesariamente).
  if (process.argv.includes("--hit-rate-limit")) {
    let saw429 = false;
    for (let i = 0; i < 150; i++) {
      const res = await fetch(`${base}/v1/reasoning/rulebases`);
      if (res.status === 429) {
        saw429 = true;
        ok("Retry-After presente en el 429", Boolean(res.headers.get("retry-after")));
        break;
      }
    }
    ok("Rate limiter: se alcanza un 429 tras suficientes peticiones", saw429);
  } else {
    console.log("SKIP Rate limiter (429) — pasar --hit-rate-limit para probarlo explícitamente.");
  }

  // 6) 404 con detalle útil para corpus inexistente.
  {
    const res = await fetch(`${base}/v1/corpora/ZZ-NOPE`);
    const body = await res.json().catch(() => null);
    ok("GET /v1/corpora/ZZ-NOPE -> 404 con lista de corpus disponibles",
      res.status === 404 && /Corpus disponibles/.test(body?.detail ?? ""));
  }

  console.log("");
  if (failures > 0) {
    console.log(`${failures} chequeo(s) fallaron.`);
    process.exit(1);
  }
  console.log("Todos los chequeos pasaron.");
  console.log("Recordatorio manual (no automatizable desde una sola máquina): verificar aislamiento");
  console.log("por IP del rate limiter con dos peticiones desde redes distintas — ver DEPLOYMENT-NODE.md.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
