# Notas de gobernanza de datos

**Proyecto:** Ontología de la lógica normativa del civil law latinoamericano
**Autor de esta nota:** latio-implementador-datos · **Fecha:** 2026-09-10

Este documento registra desacuerdos o vacíos de procedencia detectados en el corpus y en los
artefactos de gobernanza (`config/corpus_registry.yaml`, `reports/manifest.json`,
`docs/informe_hito1.md`) que **no se resuelven inventando el dato correcto**, sino dejando
constancia explícita de qué se sabe, qué no, y por qué.

---

## 1. Discrepancia de alcance: 2 fuentes declaradas vs. 8 fuentes aparentes

**Estado: no reconciliado.**

- `docs/informe_hito1.md` (encabezado y cuerpo) declara que la corrida en seco (`run_type: dry_run`,
  `pipeline_version: pipeline_v0.2`) cubrió **únicamente Chile y Colombia**.
- `reports/manifest.json`, con el mismo `pipeline_version` y `run_type`, reporta
  `total_articles_evaluated: 21957`.
- `config/corpus_registry.yaml` declara `expected_article_count` para las 8 fuentes:

  | corpus_id | expected_article_count |
  |---|---|
  | CL-CC | 2524 |
  | CO-CC | 2684 |
  | AR-CC | 4051 |
  | AR-CCYC | 2671 |
  | BR-CC | 2046 |
  | MX-CCF | 3074 |
  | MX-CDMX | 3074 |
  | PE-CC | 2122 |
  | **Suma (8 fuentes)** | **22246** |
  | **Suma (solo CL-CC + CO-CC)** | **5208** |

  `21957` está a ~1,3% de la suma de las 8 fuentes (22246) y muy lejos de la suma de solo
  Chile+Colombia (5208).

### Por qué no se resuelve aquí

No es posible determinar desde el repositorio cuál de los dos documentos refleja lo que realmente
ocurrió, porque:

1. `reports/manifest.json` no registra qué `corpus_id` participaron en la corrida (no hay campo de
   alcance, ni lista de fuentes, ni `source_hash`/`gates()` por corpus que permitan reconstruirlo).
2. Al momento de esta revisión, `config/corpus_registry.yaml` **no tenía la clave `parsing`** que
   `src/pipeline.py` exige de forma obligatoria (`cfg["parsing"]` sin default, usado en `extract()` y
   `segment()`), lo que habría causado un `KeyError` inmediato al intentar correr el pipeline contra
   *cualquier* fuente, incluidas Chile y Colombia. Es decir: con el código tal como estaba, ni
   siquiera la corrida de 2 fuentes que declara `informe_hito1.md` era ejecutable de punta a punta.
3. `data/raw/` no existe en este working tree, por lo que tampoco puede volver a correrse el pipeline
   ahora mismo contra ninguna fuente para verificar empíricamente cuál cifra es la real.
4. No hay logs de ejecución, ni timestamps de git en la raíz de este repositorio (ver `B-4` del panel
   de revisión) que permitan atribuir `generated_at: 2026-09-08T20:08:53+00:00` a una corrida
   concreta y auditable.

**Conclusión: el manifiesto actual (`manifest_id: ef5830aeeff0d456`) no es reproducible por el código
actual, y su origen exacto (¿corrida real contra las 8 fuentes con una versión distinta del pipeline?
¿valor de prueba/placeholder? ¿copiado de otro entorno?) no pudo verificarse desde este repositorio.**

### Qué se necesita para cerrar esta nota

- Que el autor confirme, de memoria o desde logs externos, contra qué `corpus_id` corrió realmente el
  pipeline el 2026-09-08.
- Alternativamente: volver a poblar `data/raw/` con las 8 fuentes (o solo CL-CC/CO-CC), correr
  `python -m src.pipeline` de punta a punta con el código actual (que ya tiene `parsing` scaffold
  tras esta corrección) y versionar un manifiesto nuevo con `corpus_id` explícitos, `source_hash` y
  `gates()` reales por corpus.
- Hasta entonces, **ninguna cifra de `informe_hito1.md` ni de `manifest.json` debe citarse como
  resultado validado**, tal como advierte `reports/debate_revision_2026-09-10.md` (hallazgo C-4) en
  su veredicto final.

---

## 2. Reglas de `parsing` agregadas a `config/corpus_registry.yaml`

Se agregó una clave `parsing` a las 8 fuentes (ausente hasta esta corrección, causa raíz de C-1 en
`reports/debate_revision_2026-09-10.md`). Estos bloques son **scaffold**, no reglas verificadas:
se derivaron de los patrones que `src/pipeline.py` ya usa internamente (`NUM_REF`/`ANA_REF` con flag
inline `(?i)`, `roman_to_int()`/`WORD_ORD` para ordinales) y de convenciones tipográficas comunes en
códigos civiles hispano/luso-parlantes (ARTÍCULO/Art., LIBRO, TÍTULO, CAPÍTULO, SECCIÓN...).

**No fueron verificados línea por línea contra el texto crudo de cada `raw_file`** (esos archivos no
existen en `data/raw/` en este working tree, por lo que no pudieron calibrarse empíricamente). Antes
de tratar cualquier salida de `segment()`/`gates()` como válida para una fuente dada, su bloque
`parsing` debe revisarse manualmente contra el texto real de esa fuente. Cada bloque lleva un
comentario `# TODO: calibrar...` en el propio YAML.

Limitaciones conocidas del scaffold, documentadas pero no corregidas en esta tarea (fuera de alcance:
`src/pipeline.py` está a cargo de otro agente en esta ronda de correcciones):

- `roman_to_int()`/`WORD_ORD` en `pipeline.py` solo resuelve ordinales masculinos en español
  (PRIMERO, SEGUNDO...); los ordinales femeninos (PRIMERA, SEGUNDA...) capturados por los patrones de
  `PARTE`/`SECCIÓN` quedarán con `ordinal_int=None`.
- El adapter `generic_pt` (BR-CC) usa `level_type: livro`, que no está en el `Literal[LevelType]` de
  `src/models.py` (que solo define `libro`, en español) — incompatibilidad de esquema conocida entre
  el scaffold de parsing y el modelo Pydantic downstream.
- El adapter `co_eva` (CO-CC) es una variante manual, no un adapter real distinto en el código (no
  existe branching por `adapter` en `pipeline.py`); el nombre solo documenta la intención de que este
  corpus decimonónico necesita reglas distintas al resto.

## 3. `license` y `retrieved_at`

- `license`: se agregó `"dominio público — texto oficial, sin restricción de uso conocida"` a las 8
  fuentes. Es un default defendible —textos legales oficiales publicados por un Estado, sin marca de
  copyright restrictivo en la fuente— pero no una verificación jurídica formal por jurisdicción.
- `retrieved_at`: se agregó como `null` explícito con `# TODO: requiere que el autor confirme la
  fecha real de captura` en las 8 fuentes. No existe forma de derivar la fecha real de descarga desde
  este repositorio (sin metadata de descarga ni historial git útil en la raíz). Se optó
  deliberadamente por dejarlo vacío en vez de usar la fecha de hoy, que habría fabricado procedencia.
  Nótese que `src/models.py:338` (`ArticleRecord.source_retrieved_at: date`, campo obligatorio) no
  podrá poblarse para ningún artículo hasta que este campo tenga un valor real — otra corrección
  pendiente fuera del alcance de esta tarea.
