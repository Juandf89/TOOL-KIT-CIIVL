# LATIO Kit · Latin American Taxonomy and Information Ontology

> **Herramientas, modelos de datos y analítica para capturar y computar la lógica del *civil law* latinoamericano.**

LATIO es una iniciativa comunitaria y de código abierto para dotar al ecosistema LegalTech de la región de un estándar ontológico y computable del derecho continental. Este repositorio contiene los modelos de datos, el pipeline de extracción y segmentación de enunciados normativos, las sondas de comportamiento empírico sobre 8 corpus y el explorador visual.

**Probalo en [datalexlab.com/latio](https://datalexlab.com/latio/).** Elegí cualquiera de los 22.110 artículos de 8 códigos civiles —Chile, Colombia, Argentina (1869 y 2015), Brasil, México (federal y CDMX) y Perú— y el analizador determina:

- su **modalidad deóntica** (Von Wright): obligación, prohibición o permiso;
- su **posición jurídica** (Hohfeld): deber, derecho subjetivo, privilegio, potestad…;
- su **esquema PROLEG**: regla general, excepción o prueba en contrario, a quién le toca probar cada una y, si hay excepción, cómo la resuelve el motor de razonamiento derrotable.

El análisis es determinista (reglas léxicas en castellano y portugués), sin modelos de lenguaje ni costo de uso. Sus límites están documentados en [`docs/limitaciones_conocidas.md`](docs/limitaciones_conocidas.md).

---

## 📂 Estructura del Repositorio

```text
TOOL-KIT-CIIVL/
├── README.md
├── LICENSE                    # MIT para el código; los textos legales tienen su propio régimen
├── DEPLOYMENT.md              # Despliegue de la API Python (referencia; producción usa latio-node/)
├── requirements.txt           # Dependencias: fastapi, uvicorn, pydantic, pyyaml
├── requirements-dev.txt       # + pytest
├── requirements-prod.txt      # Versiones fijadas para desplegar la API Python (+ a2wsgi)
├── passenger_wsgi.py          # Adaptador WSGI de src/api.py para Passenger
├── verify_prod.py             # Verificación de la API Python a través de ese adaptador
├── config/
│   └── corpus_registry.yaml   # Fuentes, licencias y reglas de parsing calibradas de los 8 códigos + TEST-FIXTURE
├── data/
│   ├── raw/                   # Los 8 textos legales fuente (.md) + un fixture sintético
│   └── processed/             # Artículos y remisiones extraídos (versionado)
├── src/
│   ├── models.py              # Modelos de datos Pydantic v2 (niveles N1 a N5, esquema n3_v1.1)
│   ├── pipeline.py            # Pipeline determinista N0 -> N1 -> N4 (segmentación y remisiones) + CLI
│   ├── behavior.py            # Regularidades lógicas, lift de figuras y perfiles + CLI
│   ├── labeling/              # Análisis por reglas léxicas: Von Wright, Hohfeld y esquema PROLEG
│   ├── reasoning/             # Motor de razonamiento derrotable (PROLEG): engine.py, models.py, rulesets/
│   ├── ratelimit.py           # Límite de tasa por IP y tope de tamaño de las peticiones
│   └── api.py                 # API FastAPI de referencia: /v1/corpora/*, /v1/statements/propose, /v1/reasoning/*
├── tests/                     # Suite pytest (134 tests): modelos, pipeline, behavior, razonamiento, análisis, API
├── docs/
│   ├── latio_manifiesto.md             # La necesidad de una arquitectura neurosimbólica
│   ├── bitacora_ontologia_civil_law.md # Diseño de la ontología del enunciado
│   ├── datos_logica_juridica_v1.md     # Catálogo de datos y seis propiedades del civil law
│   ├── diseno_experimental_v2.md       # Protocolo experimental
│   ├── informe_hito1.md                # Corrida en seco y compuertas de calidad (histórico)
│   ├── notas_gobernanza.md             # Registro de calibración y decisiones sobre los corpus
│   └── limitaciones_conocidas.md       # Brechas honestas entre lo declarado y lo implementado
├── reports/
│   ├── manifest.json          # Manifiesto de ejecución: hashes de las fuentes y compuertas de calidad
│   ├── *_run_report.json      # Informe de cada corpus
│   └── debate_revision_*.md   # Auditorías de septiembre de 2026 (históricas)
├── toolkit-api/
│   ├── index.html             # LATIO Explorer: la consola publicada en datalexlab.com/latio/
│   └── card-datalex.html      # Tarjeta del proyecto en la portada de datalexlab.com
└── latio-node/                # Puerto Node.js/Express de src/api.py: la API de producción (api-latio.datalexlab.com)
    ├── server/                # app.mjs (Express), data.mjs, models.mjs, ratelimit.mjs, labeling/, reasoning/
    ├── config/, data/, reports/  # Copias de los datos que sirve la API
    ├── tests/                 # 55 tests node:test (módulos + app Express de punta a punta)
    ├── cross_validate.mjs     # Compara Node contra Python campo a campo
    ├── verify_prod.mjs        # Verificación HTTP contra una URL ya desplegada
    └── DEPLOYMENT-NODE.md     # Guía de despliegue en Hostinger (Node.js Web App / lsnode)
```

---

## ⚡ Guía Rápida de Instalación y Uso

### Prerrequisitos
- Python 3.10 o superior
- Dependencias listadas en `requirements.txt` (`pydantic`, `pyyaml`, y `fastapi`/`uvicorn` para `src/api.py`); `requirements-dev.txt` agrega `pytest` para correr la suite de pruebas.

```bash
git clone https://github.com/Juandf89/TOOL-KIT-CIIVL.git
cd TOOL-KIT-CIIVL
pip install -r requirements.txt -r requirements-dev.txt
```

### Ejecutar el Pipeline de Segmentación
El pipeline toma un `corpus_id` de `config/corpus_registry.yaml` como argumento obligatorio. Las 8 fuentes reales ya tienen su `raw_file` en `data/raw/` y su bloque `parsing` calibrado contra el texto real. El recall de las 8 está entre 96 % y 102 %; `AR-CCYC` es la única con las 6 compuertas de calidad en PASS, y el resto tiene advertencias o fallos puntuales documentados en `reports/manifest.json` y `docs/notas_gobernanza.md`:
```bash
python -m src.pipeline CL-CC
python -m src.pipeline CO-CC
# ... o cualquiera de AR-CC, AR-CCYC, BR-CC, MX-CCF, MX-CDMX, PE-CC
# smoke test sintético (no depende de ningún raw_file real):
python -m src.pipeline TEST-FIXTURE
```
Salida: `data/processed/<corpus_id>_{articles,referrals}.json` y `reports/<corpus_id>_run_report.json` (con el resultado de las 6 compuertas de calidad). `reports/manifest.json` consolida el resultado de las 8 fuentes reales de la corrida más reciente.

**Nota:** `data/processed/` **está versionado en git** desde el 14-09-2026, así que un clon nuevo ya trae los 8 corpus procesados y tanto la suite de pruebas como la consola funcionan sin correr el pipeline primero. Volvé a correrlo solo si cambiás `data/raw/` o las reglas de parsing de `config/corpus_registry.yaml`.

### Ejecutar las Sondas de Comportamiento Lógico
```bash
python -m src.behavior
```
Hoy corre sobre un fixture sintético embebido (`_fixture_articles()`), no sobre datos jurídicos reales — el pipeline solo produce N0/N1/N4; N2/N3/N5 (anotación de modalidad deóntica, posición de Hohfeld, etc.) requieren un lote anotado que todavía no existe en `data/processed/`. Ver `docs/limitaciones_conocidas.md`.

### Motor de Razonamiento Derrotable (PROLEG)
`src/reasoning/` implementa el meta-intérprete de la teoría japonesa del hecho último presupuesto (Satoh et al., "PROLEG: An Implementation of the Presupposed Ultimate Fact Theory of Japanese Civil Code by PROLOG Technology", JURISIN 2010): reglas por defecto + excepciones + carga de la prueba (`allege`/`provide_evidence`/`admission`/`plausible`), con traza de argumentación entre demandante y demandado. Dos rulesets cargados hoy, ambos escritos a mano a partir de una fuente citable (no se inventó contenido) — ver `docs/limitaciones_conocidas.md`:

- `jp-civil-612-sublease-demo` — el ejemplo del propio paper (Art. 612 del Código Civil japonés); el Apéndice B del paper sirve de test de oro.
- `co-civil-256-visitas` — **primer artículo LATAM real conectado al motor**: régimen de visitas del Art. 256 del Código Civil colombiano (modificado por la Ley 2229 de 2022), con `Rule.source_uid="CO-CC-1873-ART-256"`.

`Rule.source_uid` queda como el punto de enlace hacia `ArticleRecord.uid` para cuando exista anotación N2/N3 real de los 8 corpus (hoy no existe — estos dos rulesets se codificaron a mano, no salieron del pipeline).

Con la API corriendo (`uvicorn src.api:app --reload`), y sirviendo `toolkit-api/index.html` con un servidor local (sección "Motor de Razonamiento (real)" de la consola — ver `ALLOWED_ORIGINS` en `src/api.py` para los orígenes de desarrollo permitidos):
```bash
curl http://127.0.0.1:8000/v1/reasoning/rulebases
curl -X POST http://127.0.0.1:8000/v1/reasoning/prove -H "Content-Type: application/json" -d '{
  "rulebase_id": "jp-civil-612-sublease-demo",
  "goal": "contract_end",
  "party": "plaintiff",
  "facts": [ ... ver tests/test_api_reasoning.py para el factbase completo del caso de oro ... ]
}'
```

### Correr las Pruebas
```bash
python -m pytest tests/ -q
```

### Abrir el LATIO Explorer
La consola sirve para elegir un código civil y un artículo real —los 22.110 de los 8 códigos están disponibles, con buscador por número o por palabra— y analizarlo. El resultado son exactamente tres cosas: su **modalidad deóntica** (Von Wright), su **posición jurídica** (Hohfeld) y, cuando el artículo tiene una excepción, cómo la resuelve el **motor de razonamiento derrotable PROLEG**. Es un analizador de solo lectura, no una herramienta de anotación: no hay campos que completar a mano.

**La consola hace llamadas reales**; no hay datos simulados. Si la API no responde, muestra un error de conexión explícito en vez de una demo falsa. No hay que configurar la dirección de la API: la consola la deduce de dónde está corriendo.

- **Servida desde cualquier dominio** (por ejemplo `datalexlab.com`), usa la API de producción: `https://api-latio.datalexlab.com`.
- **Servida desde `localhost`**, usa un backend local de desarrollo en `http://127.0.0.1:8000`. Para ese caso: `uvicorn src.api:app --reload --port 8000`, y serví el HTML con `python -m http.server 5500` desde `toolkit-api/` en vez de abrirlo con `file://`, para que CORS lo permita.

`src/api.py` (FastAPI) es la implementación de referencia y no está desplegada en ningún dominio público; la que corre en producción es el puerto Node.js de `latio-node/`, equivalente campo a campo (ver la sección de despliegue más abajo).

---

## 📜 Licencia y Comunidad
Proyecto abierto para facultades de derecho, investigadores, jueces y desarrolladores de LegalTech en América Latina. El código está bajo licencia MIT (ver [`LICENSE`](LICENSE)). Los textos legales de `data/raw/`/`data/processed/` son normas oficiales de dominio público asumido por jurisdicción — no verificado formalmente contra los términos de cada portal fuente (ver el propio [`config/corpus_registry.yaml`](config/corpus_registry.yaml) para el detalle honesto de esa limitación).

---

## 🌐 Despliegue e Integración en DataLex Lab (datalexlab.com)

### Consola estática

La consola es un único archivo (`toolkit-api/index.html`), sin dependencias ni paso de compilación. Está publicada en **[datalexlab.com/latio](https://datalexlab.com/latio/)**.

Ese sitio se publica automáticamente desde el repositorio [`Juandf89/datalex-lab`](https://github.com/Juandf89/datalex-lab), no por el administrador de archivos de Hostinger (un archivo subido a mano queda pisado en la siguiente publicación). Para actualizar la consola: copiar `toolkit-api/index.html` a `latio/index.html` de ese repositorio y hacer push.

El despliegue a GitHub Pages está desactivado: el workflow `.github/workflows/deploy.yml` se eliminó el 15-09-2026 por decisión del autor.

### API real en producción: puerto Node.js (`latio-node/`)
`src/api.py` (FastAPI) es la implementación de referencia, pero **no está desplegada** en ningún dominio público: los planes de hosting compartido de Hostinger (Business, sin VPS) no soportan Python. La API que sí corre en producción es un **puerto completo a Node.js/Express** — mismo motor PROLEG, mismo etiquetado léxico, mismo contrato HTTP (snake_case en el wire, verificado campo a campo contra el oráculo Python) — publicado en:

```
https://api-latio.datalexlab.com
```

como Node.js Web App de Hostinger (`lsnode`/LiteSpeed), aislado del resto de la infraestructura de `datalexlab.com`. Ver [`latio-node/DEPLOYMENT-NODE.md`](latio-node/DEPLOYMENT-NODE.md) para el detalle completo: qué se portó y qué no, la diferencia de identificación de IP bajo `lsnode`, el checklist post-despliegue (`latio-node/verify_prod.mjs`) y el rollback. La fidelidad del puerto está verificada con dos suites independientes dentro de `latio-node/`:

```bash
cd latio-node
npm install
npm test                    # 55 tests node:test — módulos + Express app end-to-end
# compara Node contra Python (el repo Python tiene que estar disponible localmente):
# caso de oro del Apéndice B, CO-256 y análisis en castellano y portugués
LATIO_PY_REPO=.. LATIO_RATE_LIMIT_ENABLED=0 node cross_validate.mjs
```

Los orígenes `datalexlab.com`, `www.datalexlab.com` y `juandf89.github.io` están permitidos por CORS en la API.
