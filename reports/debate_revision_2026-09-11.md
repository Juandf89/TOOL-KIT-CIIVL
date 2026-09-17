# Revisión final exhaustiva — LATIO Kit (2026-09-11)

> **Documento histórico.** Describe el estado del repositorio en la fecha del título, no el actual. Los problemas que señala se corrigieron en los commits posteriores (el pipeline corre sobre los 8 corpus, hay 138 tests en Python y 57 en Node, y la consola solo muestra resultados reales de la API). Para el estado vigente, ver `README.md` y `docs/limitaciones_conocidas.md`.

Síntesis de un debate estructurado en 2 rondas entre 4 especialistas (ontología legal, arquitectura/pipeline, calidad de datos, producto/despliegue), cada uno con exploración independiente del repo real (`C:\Users\DELL\Desktop\latio-kit`) en la Ronda 1, y réplica cruzada verificando los hallazgos de los otros tres contra el código en la Ronda 2. Todos los hallazgos están respaldados por evidencia de ejecución real (tests corridos, hashes calculados, reproducciones de bugs en Python, no solo lectura estática).

Contexto: esta revisión llega después de una sesión de trabajo que (a) revirtió una integración con Google Gemini/LLM externo por exigencia de costo cero, (b) construyó un motor de reglas léxicas deterministas para etiquetado N3 (Von Wright + Hohfeld + vista previa PROLEG), (c) conectó un selector real de corpus/artículo a la consola pública, y (d) retiró jerga técnica visible (Swagger, Modo Demo, snippets de código). Esta revisión evalúa si ese trabajo está listo para push a `Juandf89/TOOL-KIT-CIIVL`.

**Nota de proceso**: el orquestador de este debate no llegó a completar su propia síntesis final antes de que el usuario pidiera el informe — este documento es una compilación directa de los 8 reportes de especialista (4 + 4 réplicas) ya recibidos, organizados y priorizados, no una síntesis adicional de un noveno agente.

---

## Veredicto general

El proyecto tiene una base doctrinal y de ingeniería notablemente cuidada para su etapa — el propio equipo se autocritica con un rigor infrecuente en LegalTech (`docs/limitaciones_conocidas.md`), los hashes de procedencia de los 8 corpus son reales y verificables, y no queda ningún resto de la integración con Gemini. **Pero no está listo para push tal como está**: hay un error jurídico de fondo (no solo una simplificación declarada) en la derivación de Hohfeld, el repositorio no es reproducible de punta a punta por un tercero que lo clone, y la documentación pública (README) describe una versión de la consola que ya no existe — contradicciones que un revisor externo (o un juez/investigador que use la herramienta) detectaría de inmediato.

---

## 🔴 Crítico — corregir antes de publicar

### C-1: `permiso → potestad` es un error categorial de Hohfeld, no una simplificación declarada
**Archivos**: `src/models.py:76` (vocabulario `HohfeldianPosition`), `src/labeling/rules.py:76-93` (`_derive_hohfeld_from_deontic`), `tests/test_labeling_rules.py:106-111`.

Hohfeld define 4 pares correlativos: *right/duty*, ***privilege(libertad)/no-right***, *power/liability*, *immunity/disability*. El esquema de LATIO **omite por completo el par privilegio/no-derecho** — `HohfeldianPosition` solo tiene 6 valores, no 8. El código mapea `permiso → "potestad"`, confundiendo una **libertad civil** (facultad de actuar sin alterar la posición jurídica de nadie más, p. ej. "podrá dedicarse libremente a un empleo") con una **potestad** (capacidad de alterar unilateralmente relaciones jurídicas ajenas, p. ej. un juez fijando régimen de visitas). Esto no es un límite documentado: `docs/limitaciones_conocidas.md §2` advierte sobre la falta de correlatividad bilateral, un problema distinto, y nunca cuestiona si "potestad" es la etiqueta correcta. Peor: está **congelado como comportamiento correcto en un test** (`test_detecta_permiso_von_wright_y_deriva_potestad_hohfeld`), y el propio ejemplo curado de la consola ("⚡ Potestad y Capacidad — Art. 150 Chile") promueve activamente el caso que expone el error.

**Gravedad para el usuario**: un juez/investigador que vea "Potestad" en un artículo sobre la libertad laboral de la mujer casada puede concluir que la norma confiere un poder de disposición sobre terceros, invirtiendo el sentido doctrinal de la norma (que retira una restricción, no otorga un poder).

**Fix — confirmado de bajo riesgo, sin migración de datos** (el pipeline N0→N1→N4 nunca persiste `hohfeldian_position`; es puramente in-memory por request):
1. Agregar `"privilegio"` al `Literal HohfeldianPosition` en `src/models.py:76`.
2. En `src/labeling/rules.py:92`, distinguir `permiso` dirigido a partes privadas (→ `"privilegio"`) de `permiso` dirigido a `juez`/`funcionario_o_notario` (→ `"potestad"`, ahí sí correcto porque implica alterar la posición jurídica de otro).
3. Actualizar `tests/test_labeling_rules.py:106-111` y `tests/factories.py:33`.
4. Agregar la opción `privilegio` al `<select id="lbl-hohfeldian_position">` en `toolkit-api/index.html`.
5. Corregir `docs/limitaciones_conocidas.md §2` para nombrar el error real, no solo la falta de correlatividad.

Alcance del cambio: **1 valor de enum + 1 función + 2 tests + 1 `<option>` HTML**. Ningún dato persistido que migrar.

---

### C-2: La URL de GitHub Pages que promete el README no existe (404 garantizado)
**Archivo**: `README.md:120` → `https://juandf89.github.io/latio-kit/`.

El repositorio real se llama `TOOL-KIT-CIIVL` (`git remote -v` → `Juandf89/TOOL-KIT-CIIVL.git`), no `latio-kit` (ese es solo el nombre de la carpeta local). GitHub Pages sirve en `https://<usuario>.github.io/<nombre-exacto-del-repo>/` — la URL del README apunta a un repo que no existe. `toolkit-api/card-datalex.html:20` ya tiene la URL correcta (`https://juandf89.github.io/TOOL-KIT-CIIVL/`), evidenciando que es una inconsistencia interna, no una duda real sobre cuál es la URL correcta.

**Fix**: corregir `README.md:120`.

---

### C-3: `data/processed/*.json` no está versionado — un clon limpio no puede ni correr los tests
**Archivos**: `.gitignore` (excluye `data/processed/`), `tests/test_api_corpora.py:24-29` (hace `open()` a nivel de módulo, en tiempo de import).

Lo que realmente sirve el selector público de corpus+artículo (`GET /v1/corpora/*`) nunca se commiteó — está gitignoreado. Verificado moviendo la carpeta fuera del árbol y corriendo `pytest`: **la suite completa falla en la fase de *collection*** (no "algunos tests fallan", sino que pytest no llega a ejecutar ni un solo test, porque `test_api_corpora.py` abre un archivo a nivel de módulo). Además, lo que esté corriendo en producción (subido a mano por SFTP a Hostinger, según `DEPLOYMENT.md`) puede divergir silenciosamente de lo que hay en el repo público, sin diff ni commit que lo evidencie.

**Fix — dos rutas, elegir una**:
- (a) Versionar `data/processed/*_articles.json` (25 MB, son derivados deterministas y verificables vía `source_hash` — no hay razón fuerte para excluirlos), **o**
- (b) Agregar un script único (`scripts/regenerate_all.py`) que corra el pipeline para los 8 `corpus_id`, con un `output_hash` (sha256 del JSON serializado) agregado a `manifest.json`/`run_report.json` para verificación criptográfica, y como mínimo commitear una muestra fija (5-10 artículos por corpus) como fixture de test para que `test_api_corpora.py` no rompa la recolección en un clon limpio.

---

## 🟠 Alto — fuertemente recomendado antes de publicar

### A-1: El motor de etiquetado no es determinista frente a Unicode NFC vs. NFD
**Archivos**: `src/labeling/rules.py:203` (`propose_from_text`, solo hace `.strip()`), `src/labeling/lexical_markers.py` (patrones con tildes literales sin normalizar).

Confirmado con ejecución real: el mismo texto, en dos formas Unicode canónicamente equivalentes (NFC vs. NFD — común en texto pegado desde macOS o extraído de OCR/PDF), produce **resultados de etiquetado distintos** (`statement_type=definicion` vs. `statement_type=None`). Esto contradice la premisa central del módulo ("100% determinista", declarada en su propio docstring).

**Importante matiz confirmado en Ronda 2**: los 8 corpus ya commiteados **no están afectados** — `src/pipeline.py:59` normaliza a NFC en la ingesta, y los 9 archivos de `data/raw/` ya están en NFC nativo. El bug se limita al texto que un usuario pega directamente vía `/v1/statements/propose` o `/v1/statements/validate`.

**Fix**: `unicodedata.normalize("NFC", text)` como primer paso de `propose_from_text()` (y opcionalmente en `validate_statement()` antes de construir `NormativeStatement`).

---

### A-2: `POST /v1/statements/validate` no limita el tamaño del texto — DoS medido en ejecución real
**Archivo**: `src/api.py:350` (`StatementDraftRequest.text_span`, sin `max_length`) vs. `src/api.py:451` (`ProposeLabelsRequest.text_span`, con `max_length=4000`).

Medido directamente: un payload de 7.4 MB tarda **6.7 segundos** bloqueando un worker en una sola request. Con 4-6 requests concurrentes ya satura un proceso `uvicorn` de un solo worker — exactamente el target de despliegue documentado (Hostinger compartido, `passenger_wsgi.py`). Hoy la severidad práctica es baja (solo hay backend en `127.0.0.1`, sin exposición pública), pero `DEPLOYMENT.md` ya tiene un plan concreto y verificado para desplegar este mismo código en `api.datalexlab.com` sin mencionar este límite en su checklist — es una condición de carrera con el propio roadmap del proyecto.

**Fix**: agregar `max_length=4000` a `StatementDraftRequest.text_span`, igual que ya existe en `ProposeLabelsRequest`. Tratar como bloqueante para el paso "Reiniciar la app y probar" de `DEPLOYMENT.md`, es decir, corregir antes de ejecutar esa guía.

---

### A-3: README describe una consola que ya no existe, y no advierte los pasos previos necesarios
**Archivo**: `README.md:42,102` (describe datos mock/`MOCK_METRICS` — ya no existen en el código, confirmado por grep) y `README.md:60-99` (no conecta "correr el pipeline" con "si no lo hacés, pytest y la consola con backend real van a fallar").

Dos problemas confirmados en Ronda 2: (1) el README sigue describiendo el comportamiento **anterior** al rediseño de esta sesión (mock data en cliente) — la consola real ya hace `fetch()` reales y falla con un mensaje de error explícito si no hay backend, comportamiento distinto al documentado; (2) un usuario que clona, instala dependencias y corre `pytest` directamente (siguiendo el orden literal del README) se topa con el error de C-3 sin que el README lo haya anticipado como paso obligatorio.

**Fix**: reescribir `README.md:42,102` para reflejar el comportamiento real ("la consola hace llamadas reales a una API local; sin backend corriendo, muestra un error de conexión explícito, no datos simulados"), y agregar una línea explícita antes de "Correr las Pruebas" advirtiendo la dependencia del pipeline.

---

### A-4: La posición de Hohfeld se muestra en el resultado sin ninguna advertencia de que es un valor por defecto
**Archivo**: `toolkit-api/index.html` (tag `HOHFELD: ${n.hohfeldian_position}` en el panel de resultado, plano, sin badge).

El matiz "correlato por defecto" solo existe en el formulario de entrada (antes de ejecutar el análisis), en letra pequeña. En el panel de **resultado** —lo único que un usuario mira después de analizar— la etiqueta aparece sin ningún indicador de confianza, reforzada además por el pie de página "✅ Validado contra el esquema Pydantic real... esta aceptación o rechazo no es simulada", que sugiere autoridad en vez de cautela epistémica justo donde más haría falta la cautela (ver C-1).

**Fix**: repetir el badge "por defecto"/"detectado" (componente `fieldBadge()` ya existe) también dentro de la tarjeta de resultado, no solo en el formulario previo.

---

### A-5: `build_proleg_preview()` no distingue presunción rebatible de excepción sustantiva
**Archivo**: `src/labeling/rules.py:138-199`.

Se dispara correctamente solo cuando `exception_present=True` (acotado). Pero cuando se genera, siempre modela la estructura como "regla derrotada por excepción absoluta", sin distinguir si el `statement_type` real es una `presuncion` (donde la "excepción" es en realidad la prueba en contrario, que opera por desplazamiento de carga probatoria — figura procesal distinta) versus una `regla` con excepción sustantiva ordinaria (hecho impeditivo). El propio `note` visible no comunica esta distinción, aunque el proyecto ya la modela internamente (`PresumptionInfo.burden_shifts_to`).

**Fix**: condicionar el lenguaje de la vista previa (o el propio disparo) según `statement_type`, con una nota distinta para el caso de presunción.

---

### A-6: `docs/informe_hito1.md` desactualizado, contradice `docs/notas_gobernanza.md`
**Archivo**: `docs/informe_hito1.md:7,13` (describe alcance de 2 países y cita el manifiesto viejo `ef5830aeeff0d456`) vs. `reports/manifest.json` (`manifest_id: 8corpus-real-2026-09-10`) y `docs/notas_gobernanza.md` (que ya documenta la reconciliación).

Un lector que abra solo `informe_hito1.md` (el documento que el propio registro nombra como destino de "resultados reales") recibe información obsoleta y contradictoria con el estado real del repo.

**Fix**: actualizar `informe_hito1.md` con los resultados reales del manifiesto vigente.

---

## 🟡 Medio

| # | Hallazgo | Archivo(s) | Fix sugerido |
|---|---|---|---|
| M-1 | Sin `output_hash` en `manifest.json`/`run_report.json` — no se puede verificar criptográficamente que un output regenerado es idéntico al original | `src/pipeline.py:56-57` (solo hashea el input) | Agregar sha256 del JSON de salida antes de escribirlo |
| M-2 | `retrieved_at: null` en las 8 fuentes reales; `version_date` falta en 4 de 8 | `config/corpus_registry.yaml` | Completar con la fecha real de esta ronda de trabajo |
| M-3 | Sin archivo `LICENSE` pese a "proyecto abierto" | raíz del repo | Agregar MIT/Apache-2.0 para el código; aclarar por separado la licencia (asumida, no verificada) de los textos legales |
| M-4 | `.claude/agents/` (prompts internos) y `reports/debate_revision_2026-09-10.md` (autocrítica cruda, ya resuelta en parte) quedarán públicos sin contexto | `.claude/`, `reports/` | Confirmar con el dueño si se publican; si sí, agregar nota de estado ("resuelto en commit X") al informe viejo |
| M-5 | Jerga técnica residual fuera de la pestaña de análisis: comando `uvicorn` repetido 8 veces en distintos lugares de la UI, "CORS", "esquema Pydantic", ruta `src/models.py` expuesta en el resultado, `alert()` nativo con texto técnico en la pestaña de Razonamiento | `toolkit-api/index.html` (pestaña "Razonamiento jurídico", mensajes de error) | Mover detrás de un `<details>` colapsable (patrón ya usado correctamente en la pestaña de análisis), reemplazar `alert()` por el mismo patrón de caja de error en línea |
| M-6 | Botón principal todavía dice "Ejecutar Petición (Send Request)" — mezcla inglés, jerga | `toolkit-api/index.html` | Renombrar a algo comprensible ("Confirmar" / "Validar resultado") |
| M-7 | Licencia de redistribución de los 8 textos asumida como "dominio público" sin verificación real por jurisdicción (ya declarado como no-verificado en el propio registro) | `config/corpus_registry.yaml` | Verificación mínima de términos de los 6 portales fuente, o redacción explícita de "no verificado" |
| M-8 | Cobertura concentrada en 6 países (sin Centroamérica/Caribe) pese a que el README promete "la región" | `README.md:5` vs `config/corpus_registry.yaml` | Acotar la promesa o ampliar cobertura |
| M-9 | Sin comando único para regenerar los 8 corpus | `src/pipeline.py` (solo acepta 1 `corpus_id` a la vez) | Script batch |
| M-10 | Manifiesto (`latio_manifiesto.md`) menciona "LLM" como parte de la arquitectura sin aclarar que hoy no está implementado | `docs/latio_manifiesto.md:10-14` | Nota al pie remitiendo a `docs/limitaciones_conocidas.md` |
| M-11 | Huecos de test: texto vacío/whitespace en `propose`, límite de 4000 chars, `build_proleg_preview` invocado de forma aislada, tamaño anómalo en `/validate` una vez corregido A-2 | `tests/test_labeling_rules.py` | Agregar los 4 tests |
| M-12 | Acoplamiento rígido `presunción de derecho → derogability=inderogable` como excepción dura de Pydantic en vez de advertencia | `src/models.py:275-279` | Relajar a `qa_flags` o documentar que es un valor derivado, no observado |

---

## ⚪ Bajo / informativo (no bloqueante)

- Uso del término "monotonicidad" en README es ambiguo — colisiona con el sentido de "derrotabilidad" (no-monotonicidad lógica) que el propio proyecto usa en otra parte. Renombrar a "orden secuencial de artículos".
- Motor PROLEG (`_prove`) sin guarda contra recursión/ciclos — no explotable hoy (rulebases estáticas y acíclicas), defensa en profundidad barata de agregar.
- `generated_at` (timestamp) no determinista en `run_report.json` — solo metadata de auditoría, no afecta los datos del corpus en sí.
- Título de la pestaña del navegador (`<title>`) todavía dice "API Console & Explorer".
- `DEPLOYMENT.md` referencia un archivo (`_preview_comparacion_proyectos.html`) que no existe en el repo.
- El punto de estado de conexión no cambia de color cuando falla (queda verde con texto de error) — inconsistencia visual menor.
- `.gitignore` no excluye explícitamente `.env` — preventivo, no hay evidencia de que haya ocurrido.

---

## Confirmaciones positivas (verificadas, no solo asumidas)

- **Cero residuos de la integración con Gemini/LLM** en todo el repo (código, comentarios, docs, `Dockerfile`, `DEPLOYMENT.md`) — búsqueda exhaustiva sin coincidencias.
- Los 8 `source_hash` de `reports/manifest.json` coinciden exactamente (verificado con sha256 real) con los archivos de `data/raw/`.
- `articles_parsed` en `manifest.json` coincide exactamente con cada `run_report.json` individual y con el total (22.110).
- No existe ya la carpeta duplicada `TOOL KIT CIIVL/` señalada en la revisión del 2026-09-10 — resuelto.
- CORS bien configurado (nunca `allow_origins=['*']` combinado con `allow_credentials=True`).
- `validate_statement()` construye un `NormativeStatement` real y deja que Pydantic decida — no reimplementa reglas de compatibilidad.
- Los mensajes de error de conexión de la consola son específicos y accionables (no un error crudo de red), y la dirección del analizador es configurable por el usuario, no una URL fija.
- El fixture sintético (`TEST-FIXTURE`) está claramente rotulado como no-real y excluido de `/v1/corpora` — sin riesgo de confusión.
- `docs/limitaciones_conocidas.md` es un documento de autocrítica inusualmente honesto para un proyecto en esta etapa.

---

## Orden recomendado para corregir antes del push

1. **C-1** (Hohfeld) — cambio acotado, sin deuda de datos, pero es el error de mayor gravedad doctrinal.
2. **C-2** (URL README) — una línea.
3. **A-1** (Unicode NFC) — una línea (`normalize`) en el punto de entrada del motor de reglas.
4. **A-2** (max_length validate) — una línea.
5. **C-3** (data/processed) — decisión de arquitectura de datos, la más laboriosa; puede diferirse un día más si hace falta, pero debe resolverse antes de invitar a terceros a clonar el repo.
6. **A-3, A-6** (README/informe_hito1 desactualizados) — edición de documentación.
7. **A-4, A-5** (comunicación de incertidumbre en la UI) — mejoras de confianza del usuario, no bloqueantes técnicamente pero centrales al objetivo de "herramienta seria, no juguete".
8. Resto de **M-** y **⚪** — pueden abordarse después del push inicial, o en un segundo commit el mismo día.
