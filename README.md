# LATIO Kit · Latin American Taxonomy and Information Ontology

> **Herramientas, modelos de datos y analítica para capturar y computar la lógica del *civil law* latinoamericano.**

LATIO es una iniciativa comunitaria y de código abierto para dotar al ecosistema LegalTech de la región de un estándar ontológico y computable del derecho continental. Este repositorio contiene los modelos de datos, el pipeline de extracción y segmentación de enunciados normativos, las sondas de comportamiento empírico sobre 8 corpus y el explorador visual.

---

## 📂 Estructura del Repositorio

```text
latio-kit/
├── README.md                  # Descripción del proyecto, arquitectura y guía rápida
├── .gitignore                 # Exclusiones de control de versiones
├── requirements.txt           # Dependencias runtime: fastapi, uvicorn, pydantic, pyyaml
├── requirements-dev.txt       # Dependencias de desarrollo: pytest
├── .github/
│   └── workflows/
│       └── deploy.yml         # CI: despliega toolkit-api/ a GitHub Pages en cada push a main
├── config/
│   └── corpus_registry.yaml   # Registro oficial de fuentes, licencias y reglas de parsing (scaffold) para 8 códigos + TEST-FIXTURE
├── data/
│   └── raw/fixture_test_corpus.md   # Corpus sintético de prueba (las 8 fuentes reales aún no tienen archivo crudo)
├── src/
│   ├── __init__.py            # Módulo raíz de latio
│   ├── models.py              # Modelos de datos Pydantic v2 (N1 a N5, esquema n3_v1.1, StrictModel base)
│   ├── pipeline.py            # Pipeline determinista N0 -> N1 -> N4 (monotonicidad y remisiones) + CLI
│   ├── behavior.py            # Análisis de regularidades lógicas, lift de figuras y perfiles + CLI
│   └── api.py                 # API FastAPI local (src/api.py) — no desplegada en api.datalexlab.com
├── tests/                     # Suite pytest: modelos, pipeline, behavior (57 casos)
├── docs/
│   ├── latio_manifiesto.md    # Manifiesto LATIO: La necesidad de arquitectura neurosimbólica
│   ├── bitacora_ontologia_civil_law.md # Bitácora de diseño de la ontología del enunciado
│   ├── datos_logica_juridica_v1.md     # Catálogo de datos y seis propiedades del civil law
│   ├── diseno_experimental_v2.md       # Protocolo experimental cerrado para ejecución
│   ├── informe_hito1.md       # Reporte de corrida en seco y compuertas de calidad
│   └── limitaciones_conocidas.md # Brechas honestas entre el esquema/pipeline y lo declarado
├── reports/
│   └── manifest.json          # Manifiesto de ejecución con hashes inmutables y compuertas
├── toolkit-api/
│   ├── index.html              # LATIO Explorer / Consola interactiva (datos de demo en cliente)
│   └── card-datalex.html       # Tarjeta de proyecto para incrustar en datalexlab.com
└── TOOL KIT CIIVL/             # Submódulo git → github.com/Juandf89/TOOL-KIT-CIIVL (repo independiente)
```

> **Nota sobre `TOOL KIT CIIVL/`:** es un submódulo git que apunta a [github.com/Juandf89/TOOL-KIT-CIIVL](https://github.com/Juandf89/TOOL-KIT-CIIVL), un repositorio separado con su propio historial. Antes vivía copiado dentro de este repo como una carpeta suelta (con su propio `.git` anidado, sin relación declarada); se reemplazó por un submódulo real para eliminar la duplicación de fuente de verdad. Si cloná `latio-kit` de cero, traé su contenido con `git submodule update --init`.

---

## ⚡ Guía Rápida de Instalación y Uso

### Prerrequisitos
- Python 3.10 o superior
- Dependencias listadas en `requirements.txt` (`pydantic`, `pyyaml`, y `fastapi`/`uvicorn` para `src/api.py`); `requirements-dev.txt` agrega `pytest` para correr la suite de pruebas.

```bash
git clone https://github.com/tu-usuario/latio-kit.git
cd latio-kit
git submodule update --init   # trae TOOL KIT CIIVL/
pip install -r requirements.txt -r requirements-dev.txt
```

### Ejecutar el Pipeline de Segmentación
El pipeline toma un `corpus_id` de `config/corpus_registry.yaml` como argumento obligatorio. Ninguna de las 8 fuentes reales tiene todavía su archivo crudo en `data/raw/` (ver `docs/notas_gobernanza.md`), así que el smoke test end-to-end usa el corpus sintético `TEST-FIXTURE`:
```bash
python -m src.pipeline TEST-FIXTURE
# con una fuente real, una vez que exista su archivo en data/raw/:
python -m src.pipeline CL-CC
```
Salida: `data/processed/<corpus_id>_{articles,referrals}.json` y `reports/<corpus_id>_run_report.json` (con el resultado de las 6 compuertas de calidad).

### Ejecutar las Sondas de Comportamiento Lógico
```bash
python -m src.behavior
```
Hoy corre sobre un fixture sintético embebido (`_fixture_articles()`), no sobre datos jurídicos reales — el pipeline solo produce N0/N1/N4; N2/N3/N5 (anotación de modalidad deóntica, posición de Hohfeld, etc.) requieren un lote anotado que todavía no existe en `data/processed/`. Ver `docs/limitaciones_conocidas.md`.

### Correr las Pruebas
```bash
python -m pytest tests/ -q
```

### Abrir el LATIO Explorer
Abre `toolkit-api/index.html` en cualquier navegador web moderno para explorar de forma interactiva las regularidades de los 8 códigos y la radiografía de artículos. **Nota:** esta consola funciona hoy con datos de ejemplo generados en el cliente (`MOCK_METRICS`/`MOCK_LIFT`); no consulta un backend en vivo. `src/api.py` es una API FastAPI que puedes correr localmente (`uvicorn src.api:app --reload`), pero no está desplegada en `api.datalexlab.com`.

---

## 📜 Licencia y Comunidad
Proyecto abierto para facultades de derecho, investigadores, jueces y desarrolladores de LegalTech en América Latina.

---

## 🌐 Despliegue e Integración en DataLex Lab (datalexlab.com)

Este repositorio está preparado para desplegarse automáticamente de dos formas:

### Opción A: Despliegue Automático con GitHub Pages (Recomendado)
El archivo `.github/workflows/deploy.yml` ya está configurado.
1. En GitHub, ve a **Settings** > **Pages**.
2. En **Build and deployment** > **Source**, selecciona **GitHub Actions**.
3. Cada vez que hagas `git push`, tu consola interactiva se desplegará automáticamente en:
   `https://juandf89.github.io/latio-kit/`

### Opción B: Integración en Hostinger (datalexlab.com/latio)
1. En **hPanel** de Hostinger, entra a `public_html/` y crea la carpeta `latio/`.
2. Sube el archivo `toolkit-api/index.html` dentro de `public_html/latio/`.
3. Copia el componente `toolkit-api/card-datalex.html` y pégalo en la sección de **Proyectos** de `datalexlab.com`.
