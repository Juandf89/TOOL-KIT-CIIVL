# LATIO Kit · Latin American Taxonomy and Information Ontology

> **Herramientas, modelos de datos y analítica para capturar y computar la lógica del *civil law* latinoamericano.**

LATIO es una iniciativa comunitaria y de código abierto para dotar al ecosistema LegalTech de la región de un estándar ontológico y computable del derecho continental. Este repositorio contiene los modelos de datos, el pipeline de extracción y segmentación de enunciados normativos, las sondas de comportamiento empírico sobre 8 corpus y el explorador visual.

---

## 📂 Estructura del Repositorio

```text
TOOL-KIT-CIIVL/
├── README.md                  # Descripción del proyecto, arquitectura y guía rápida
├── .gitignore                 # Exclusiones de control de versiones
├── requirements.txt           # Dependencias runtime: fastapi, uvicorn, pydantic, pyyaml
├── requirements-dev.txt       # Dependencias de desarrollo: pytest
├── .github/
│   └── workflows/
│       └── deploy.yml         # CI: despliega toolkit-api/ a GitHub Pages en cada push a main
├── config/
│   └── corpus_registry.yaml   # Registro de fuentes, licencias y reglas de parsing calibradas para los 8 códigos reales + TEST-FIXTURE
├── data/
│   └── raw/                   # Los 8 textos legales fuente (.md) + fixture_test_corpus.md (sintético, no real)
├── src/
│   ├── __init__.py            # Módulo raíz de latio
│   ├── models.py              # Modelos de datos Pydantic v2 (N1 a N5, esquema n3_v1.1, StrictModel base)
│   ├── pipeline.py            # Pipeline determinista N0 -> N1 -> N4 (segmentación y remisiones) + CLI
│   ├── behavior.py            # Análisis de regularidades lógicas, lift de figuras y perfiles + CLI
│   ├── labeling/               # Motor de etiquetado N3 por reglas léxicas deterministas (Von Wright, Hohfeld, PROLEG preview) — sin LLM, sin costo
│   ├── reasoning/              # Motor de razonamiento derrotable (PROLEG): models.py, engine.py, rulesets/
│   └── api.py                 # API FastAPI local (src/api.py) — no desplegada en api.datalexlab.com; expone /v1/reasoning/*, /v1/corpora/*, /v1/statements/*
├── tests/                     # Suite pytest: modelos, pipeline, behavior, motor de razonamiento, etiquetado, API
├── docs/
│   ├── latio_manifiesto.md    # Manifiesto LATIO: La necesidad de arquitectura neurosimbólica
│   ├── bitacora_ontologia_civil_law.md # Bitácora de diseño de la ontología del enunciado
│   ├── datos_logica_juridica_v1.md     # Catálogo de datos y seis propiedades del civil law
│   ├── diseno_experimental_v2.md       # Protocolo experimental cerrado para ejecución
│   ├── informe_hito1.md       # Reporte de corrida en seco y compuertas de calidad
│   └── limitaciones_conocidas.md # Brechas honestas entre el esquema/pipeline y lo declarado
├── reports/
│   └── manifest.json          # Manifiesto de ejecución con hashes inmutables y compuertas
└── toolkit-api/
    ├── index.html              # LATIO Explorer — consola de análisis, hace llamadas reales a una API local (sin backend corriendo, muestra un error de conexión explícito)
    └── card-datalex.html       # Tarjeta de proyecto para incrustar en datalexlab.com
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
El pipeline toma un `corpus_id` de `config/corpus_registry.yaml` como argumento obligatorio. Las 8 fuentes reales ya tienen su `raw_file` en `data/raw/` y su bloque `parsing` calibrado contra el texto real (ver `docs/notas_gobernanza.md` §0 para el recall exacto de cada una — entre 96% y 102%, salvo `AR-CCYC` al 33% por corrupción de OCR de la fuente, no por calibración):
```bash
python -m src.pipeline CL-CC
python -m src.pipeline CO-CC
# ... o cualquiera de AR-CC, AR-CCYC, BR-CC, MX-CCF, MX-CDMX, PE-CC
# smoke test sintético (no depende de ningún raw_file real):
python -m src.pipeline TEST-FIXTURE
```
Salida: `data/processed/<corpus_id>_{articles,referrals}.json` y `reports/<corpus_id>_run_report.json` (con el resultado de las 6 compuertas de calidad). `reports/manifest.json` consolida el resultado de las 8 fuentes reales de la corrida más reciente.

**Importante:** `data/processed/` está excluido de git (son artefactos derivados, regenerables desde `data/raw/`) — en un clon nuevo del repo, esa carpeta no existe todavía. **Correr el pipeline para los 8 `corpus_id` es un paso obligatorio, no opcional**, antes de: (a) `python -m pytest tests/ -q` (`tests/test_api_corpora.py` abre esos archivos y sin ellos la recolección de la suite completa falla), y (b) usar la sección "Buscar en los códigos civiles" / "Analizar un artículo" de la consola contra un backend local.

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
Abre `toolkit-api/index.html` en cualquier navegador web moderno (o entrá a la versión publicada en GitHub Pages, ver más abajo) para elegir un código civil y un artículo real, analizarlo (tipo de norma, modalidad deóntica de Von Wright, posición jurídica de Hohfeld) y ver el motor de razonamiento PROLEG en acción cuando hay una excepción. **La consola hace llamadas reales** a `src/api.py` corriendo localmente (`uvicorn src.api:app --reload --port 8000`, sirviendo el HTML con `python -m http.server 5500` en vez de abrirlo con `file://`, para que CORS lo permita) — no hay datos simulados: sin ese backend corriendo, vas a ver un mensaje de error de conexión explícito, no una demo falsa. `src/api.py` todavía no está desplegado en ningún dominio público (`api.datalexlab.com` u otro) — la versión en GitHub Pages es solo el HTML/JS estático, y por eso muestra ese mismo error de conexión hasta que alguien corra la API localmente.

---

## 📜 Licencia y Comunidad
Proyecto abierto para facultades de derecho, investigadores, jueces y desarrolladores de LegalTech en América Latina. El código está bajo licencia MIT (ver [`LICENSE`](LICENSE)). Los textos legales de `data/raw/`/`data/processed/` son normas oficiales de dominio público asumido por jurisdicción — no verificado formalmente contra los términos de cada portal fuente (ver el propio [`config/corpus_registry.yaml`](config/corpus_registry.yaml) para el detalle honesto de esa limitación).

---

## 🌐 Despliegue e Integración en DataLex Lab (datalexlab.com)

Este repositorio está preparado para desplegarse automáticamente de dos formas:

### Opción A: Despliegue Automático con GitHub Pages (Recomendado)
El archivo `.github/workflows/deploy.yml` ya está configurado.
1. En GitHub, ve a **Settings** > **Pages**.
2. En **Build and deployment** > **Source**, selecciona **GitHub Actions**.
3. Cada vez que hagas `git push`, tu consola interactiva se desplegará automáticamente en:
   `https://juandf89.github.io/TOOL-KIT-CIIVL/`

### Opción B: Integración en Hostinger (datalexlab.com/latio)
1. En **hPanel** de Hostinger, entra a `public_html/` y crea la carpeta `latio/`.
2. Sube el archivo `toolkit-api/index.html` dentro de `public_html/latio/`.
3. Copia el componente `toolkit-api/card-datalex.html` y pégalo en la sección de **Proyectos** de `datalexlab.com`.
