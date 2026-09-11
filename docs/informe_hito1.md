# Informe de corrida en seco — Hito 1

**Proyecto:** Ontología de la lógica normativa del civil law latinoamericano
**Versión:** 1.0 · **Fecha:** 2026-09-08
**Pipeline:** pipeline_v0.2 · **Run type:** dry_run

Resultados de la corrida en seco para Chile y Colombia, monotonicidad en los encabezados y compuertas de calidad.

---

## ✅ Estado: histórico, reconciliado (actualización 2026-09-11)

Este informe describe una corrida en seco (`dry_run`) sobre datos de alcance incierto (ver nota de
2026-09-10 abajo, que documenta la discrepancia). Esa discrepancia **ya está resuelta**: existe una
corrida real (`run_type: real_run`) sobre los 8 corpus completos, con `manifest_id:
8corpus-real-2026-09-10`, `source_hash` y compuertas de calidad verificables por fuente en
`reports/manifest.json` — ver `docs/notas_gobernanza.md` **Nota 0** para el detalle completo de la
reconciliación (22.110 artículos reales, no los 21.957 de este informe ni del manifiesto viejo).

**Ninguna cifra de este documento debe citarse como el estado actual del proyecto.** Se conserva como
registro histórico de cómo se detectó y diagnosticó el problema, no como fuente de resultados vigentes
— para eso, usar `reports/manifest.json` directamente.

---

## ⚠️ Nota de gobernanza — discrepancia de alcance, diagnosticada aquí y reconciliada después (2026-09-10)

Este informe declara que la corrida en seco cubrió **únicamente Chile y Colombia**. Sin embargo,
`reports/manifest.json` (mismo `pipeline_version: pipeline_v0.2`, `run_type: dry_run`) reporta
`total_articles_evaluated: 21957` — una cifra muy por encima de lo que arrojarían solo esas dos
fuentes (CL-CC + CO-CC ≈ 5.208 artículos declarados en `config/corpus_registry.yaml`) y, en cambio,
cercana a la suma de las 8 fuentes del registro (≈ 22.246 artículos declarados).

**No se resuelve aquí cuál de los dos documentos es correcto.** No es posible determinarlo desde el
repositorio: no hay logs de ejecución, no hay `source_hash`/`gates()` poblados en el manifiesto, y
`config/corpus_registry.yaml` no tenía la clave `parsing` que el pipeline exige (`src/pipeline.py`
la lee vía `cfg["parsing"]` sin default), por lo que el pipeline no podía correr de punta a punta con
el código tal como estaba. En consecuencia, el manifiesto actual (`manifest_id: ef5830aeeff0d456`,
`generated_at: 2026-09-08T20:08:53+00:00`) **no es reproducible por el código actual** y su origen
exacto no pudo verificarse desde este repositorio.

Ver detalle completo en `docs/notas_gobernanza.md` y en el hallazgo C-4 de
`reports/debate_revision_2026-09-10.md`. Hasta que se reconcilie explícitamente (declarando qué
`corpus_id` entraron en cada `run_id`, con una corrida real versionada), ninguna cifra de este informe
ni del manifiesto debe citarse como resultado validado.
