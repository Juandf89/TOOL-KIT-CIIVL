# Notas de gobernanza de datos

**Proyecto:** Ontología de la lógica normativa del civil law latinoamericano
**Autor de esta nota:** latio-implementador-datos · **Fecha:** 2026-09-10

Este documento registra desacuerdos o vacíos de procedencia detectados en el corpus y en los
artefactos de gobernanza (`config/corpus_registry.yaml`, `reports/manifest.json`,
`docs/informe_hito1.md`) que **no se resuelven inventando el dato correcto**, sino dejando
constancia explícita de qué se sabe, qué no, y por qué.

---

## 0. Actualización (2026-09-10): corrida real sobre los 8 corpus — la Nota 1 queda cerrada

El autor proveyó los 8 `raw_file` reales (antes `data/raw/` solo tenía el fixture sintético). Se
calibraron los 8 bloques `parsing` de `config/corpus_registry.yaml` contra el texto real (línea por
línea, con evidencia documentada en cada bloque) y se corrió `python -m src.pipeline <corpus_id>` de
punta a punta para las 8 fuentes. `reports/manifest.json` fue reemplazado por uno nuevo
(`manifest_id: 8corpus-real-2026-09-10`) con `corpus_id`, `source_hash` y `gates()` reales por fuente,
reproducible por cualquiera que tenga los mismos `raw_file` en `data/raw/`.

Esto **no reconcilia retroactivamente** qué corrió el 2026-09-08 (sigue sin saberse, ver Nota 1
abajo, que se conserva sin editar como registro histórico) — lo que hace es reemplazar la única cifra
que importaba de ahí en adelante (`total_articles_evaluated`) por una nueva, verificable de punta a
punta hoy. Recall real por fuente (artículos extraídos / `expected_article_count` del registro):

| corpus_id | recall | nota |
|---|---|---|
| CL-CC | 101.7% | supera el esperado por artículos insertados legítimos (numeración con guión, BIS/TER de reformas posteriores) |
| CO-CC | 99.6% | 12 faltantes son huecos de numeración reales de la fuente |
| AR-CC | 98.5% | ~82 huecos reales (páginas perdidas en la conversión PDF→Markdown, no recuperables por regex) |
| BR-CC | 101.0% *(actualizado)* | tras corregir un bug real de conversión de número (separador de miles con punto) y, más tarde, el empaquetado múltiple por línea (ver Nota 4) |
| MX-CCF | 96.2% *(actualizado)* | anomalía real de OCR en 5 saltos de página que borran encabezados de artículo; +1 artículo tras el fix de empaquetado múltiple por línea (ver Nota 4) |
| MX-CDMX | 99.6% *(actualizado)* | recall subió de 97.4% a 99.6% al corregir el empaquetado múltiple por línea (ver Nota 4) — era el mayor salto de los 8 corpus |
| PE-CC | 100.05% | match esencialmente exacto |
| **AR-CCYC** | **100.1%** *(actualizado)* | resuelto — ver adenda abajo. Único corpus con las 6 compuertas en PASS. |

### Adenda (2026-09-10, más tarde el mismo día): AR-CCYC resuelto reemplazando la fuente

El `raw_file` original (PDF/OCR con corrupción distribuida en todo el documento) fue reemplazado por
el texto oficial de **InfoLeg** (Ministerio de Justicia de Argentina) — HTML limpio del "texto
actualizado" de la Ley 26.994, sin capa de OCR de por medio. Descargado, convertido a texto plano con
un script propio (strip de HTML, decodificación de entidades) y recalibrado desde cero. Resultado:
**2674/2671 artículos (100.1%), completitud PASS, 0 huecos de numeración, las 6 compuertas en PASS**
— pasó de ser la peor fuente del proyecto a la única sin ningún `FAIL`. Ver el bloque `AR-CCYC` en
`config/corpus_registry.yaml` (`source.url`, `source.note`) para la URL exacta y el detalle de
calibración contra el nuevo texto.

Ningún `completitud: FAIL` restante fue forzado a pasar — cada uno está documentado con evidencia
(grep contra el `raw_file` real) en el bloque `parsing` correspondiente del registro.

---

## 1. Discrepancia de alcance histórica (2026-09-08): 2 fuentes declaradas vs. 8 fuentes aparentes

**Estado: no reconciliado — se conserva como registro histórico, ver Nota 0 arriba para el estado actual.**

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

## 2. Reglas de `parsing` en `config/corpus_registry.yaml`

**Actualización (2026-09-10): las 8 fuentes ya están calibradas contra su `raw_file` real** (ver Nota
0). Lo que sigue de esta sección es el registro histórico de cuando eran scaffold sin verificar —
se conserva porque explica el punto de partida, no porque siga describiendo el estado actual.

Se agregó una clave `parsing` a las 8 fuentes (ausente hasta esta corrección, causa raíz de C-1 en
`reports/debate_revision_2026-09-10.md`). Estos bloques eran **scaffold**, no reglas verificadas:
se derivaron de los patrones que `src/pipeline.py` ya usa internamente (`NUM_REF`/`ANA_REF` con flag
inline `(?i)`, `roman_to_int()`/`WORD_ORD` para ordinales) y de convenciones tipográficas comunes en
códigos civiles hispano/luso-parlantes (ARTÍCULO/Art., LIBRO, TÍTULO, CAPÍTULO, SECCIÓN...).

**No habían sido verificados línea por línea contra el texto crudo de cada `raw_file`** (esos archivos
no existían en `data/raw/` en ese momento). Cada bloque calibrado ahora documenta inline, con
evidencia de grep/lectura directa, los hallazgos reales de su fuente — ya no llevan el comentario
`# TODO: calibrar...`.

## 4. Dos límites arquitectónicos compartidos, encontrados al calibrar contra texto real

- **Separador de miles con punto (corregido)**: `BR-CC` numera artículos ≥1000 como "Art. 1.992" (punto
  como separador de miles). El código compartido `src/pipeline.py:158` hacía `int(m.group("num"))`
  directo, que habría lanzado `ValueError` o (peor) truncado silenciosamente el número a "1" si el
  `article_pattern` capturaba el punto. Se corrigió a `int(m.group("num").replace(".", ""))` —
  no-op para el resto de los corpus, cuyo grupo `num` nunca captura un punto literal. Verificado sin
  regresión contra los 8 corpus + la suite de tests (71/71) tras el cambio.
- **Empaquetado de varios artículos en una sola línea (corregido 2026-09-10, más tarde el mismo día)**:
  tanto `BR-CC` como `MX-CDMX` tienen tramos donde varios artículos derogados consecutivos aparecen en
  una única línea del `raw_file` (ej. "Art. 789. (Revogado...) Art. 790. (Revogado...) Art. 791.
  ..."). `segment()` en `src/pipeline.py` reconocía como máximo un artículo por línea (`re.match`, no
  múltiples matches); el resto de cada grupo empaquetado se perdía. Esto explicaba una porción real
  (no toda) del `completitud: FAIL` de ambos corpus.

  **Fix**: `segment()` ahora, tras el primer match de `article_pattern` en una línea, reintenta el
  mismo patrón contra el resto de la línea (`_find_next_article_boundary()`, `src/pipeline.py`),
  cerrando el artículo anterior y abriendo uno nuevo por cada match adicional encontrado, hasta agotar
  la línea. Dos guardas evitan romper el caso normal (un artículo por línea, la inmensa mayoría):
  1. Un candidato solo se acepta si el carácter no blanco inmediatamente anterior es un cierre de
     cláusula (`.)>;:]`, típico de `</u>` o `(DEROGADO...)` justo antes del siguiente artículo) —
     así no se confunde una remisión inline (ej. "...según lo dispuesto en el art. 29...") con un
     artículo nuevo.
  2. Se exige que `article_pattern` matchee exactamente en la posición posterior al cierre de
     cláusula (sin usar `finditer` directo), porque varios `article_pattern` del registro (MX-CDMX)
     admiten un grupo opcional de paréntesis ANTES de la palabra clave — sin esta guarda, el
     "(DEROGADO...)" que cierra un artículo se colaría como si fuera el prefijo opcional del
     siguiente, perdiendo la anotación.

  Tests sintéticos en `tests/test_pipeline.py` (`test_packed_line_*`) ejercitan ambas guardas contra
  líneas de 2-3 artículos empaquetados. Recorrida de los 8 corpus tras el fix: **BR-CC +9 artículos
  (2058→2067)**, **MX-CDMX +69 artículos (2993→3062, recall 97.4%→99.6%, el mayor salto)**, **MX-CCF
  +1 artículo (2955→2956)** — los otros 5 corpus (CL-CC, CO-CC, AR-CC, AR-CCYC, PE-CC) no cambiaron,
  confirmando que no hay regresión. `source_hash` no cambió para ningún corpus. Detalle completo en
  `reports/manifest.json` (campo `note` de cada corpus_id afectado).

  **Residual que sigue sin corregirse** (documentado, no bloqueante): cuando la línea empaquetada
  empieza con un encabezado de nivel a mitad de línea antes del primer "Art." (ej. "Seção III Do
  Seguro de Pessoa Art. 789. ..." en BR-CC, línea 2832 de `L10406compilada.md`), el primer match de
  `article_pattern` sigue sin reconocerse porque no matchea en la posición 0 de la línea — ese grupo
  completo (Art. 789-802 en BR-CC) se pierde igual que antes. Corregir esto requeriría reconocer
  encabezados de nivel a mitad de línea, un cambio de alcance mayor (afecta también el árbol `path`),
  deliberadamente fuera de esta corrección.

Limitaciones conocidas del scaffold, documentadas pero no corregidas en esta tarea:

- `roman_to_int()`/`WORD_ORD` en `pipeline.py` solo resuelve ordinales masculinos en español
  (PRIMERO, SEGUNDO...); los ordinales femeninos (PRIMERA, SEGUNDA...) capturados por los patrones de
  `PARTE`/`SECCIÓN` quedarán con `ordinal_int=None`. Tampoco resuelve ordinales en portugués
  (PRIMEIRO, SEGUNDO...) usados por `BR-CC`.
- **`level_type: livro` (corregido 2026-09-10)**: el adapter `generic_pt` (BR-CC) usaba
  `level_type: livro`, que no está en el `Literal[LevelType]` de `src/models.py` (que solo define
  `libro`, en español) — incompatibilidad de esquema conocida entre el scaffold de parsing y el
  modelo Pydantic downstream (no rompía el pipeline liviano actual, que no instancia `ArticleRecord`,
  pero habría roto la construcción de un `ArticleRecord` real el día que exista anotación N2/N3 para
  BR-CC). Se normalizó `type: livro` → `type: libro` en `config/corpus_registry.yaml` (bloque
  `BR-CC`) en vez de agregar "livro" al `Literal` de `models.py`: los otros 3 niveles del mismo bloque
  (`titulo`/`capitulo`/`seccion`) ya usaban el nombre canónico en español pese a matchear texto en
  portugués (TÍTULO/CAPÍTULO/SEÇÃO), así que "livro" era la única excepción inconsistente dentro de su
  propio bloque; y `LevelType` es una taxonomía estructural pensada para comparar los 8 corpus entre
  sí (el objetivo del proyecto), no para bifurcarse por idioma — el texto real en portugués se
  conserva íntegro en `label` (la línea cruda "LIVRO I", etc.), así que no se pierde información al
  normalizar `level_type`. Ver el comentario extendido en el bloque `BR-CC` de
  `config/corpus_registry.yaml` para el detalle completo de esta decisión.
- El adapter `co_eva` (CO-CC) es una variante manual, no un adapter real distinto en el código (no
  existe branching por `adapter` en `pipeline.py`); el nombre solo documenta la intención de que este
  corpus decimonónico necesita reglas distintas al resto.

## 5. Validación cruzada del Art. 256 (CO-CC) contra el ruleset del motor de razonamiento — discrepancia real, no corregida aquí

`src/reasoning/rulesets/co_civil_256_visitas.py` cita `Rule.source_uid="CO-CC-1873-ART-256"` con un
texto "verificado (2026-09-10) contra tres fuentes independientes" que corresponde al Art. 256 del
Código Civil colombiano **modificado por la Ley 2229 de 2022** (régimen de visitas ampliado a
ascendientes en segundo grado, con una excepción por victimario condenado).

Ahora que `data/processed/CO-CC_articles.json` existe (extraído del `raw_file` real,
`data/raw/ley_57_de_1887.md`), se comparó el `uid` `CO-CC-1873-ART-256` contra ese archivo:

```
CO-CC-1873-ART-256 → text_raw: "VISITAS . Al padre o madre de cuyo cuidado personal se sacaren
los hijos, no por eso se prohibirá visitarlos con la frecuencia y libertad que el juez juzgare
convenientes."
```

**Resultado: coincide EXACTAMENTE, palabra por palabra, con el inciso 1 citado en el ruleset** — la
regla `derecho_de_visitas_progenitor` (source_note "— inciso 1") queda verificada contra el N0 real
del pipeline.

**Pero el resto del ruleset NO tiene contraparte en el artículo extraído.** `CO-CC-1873-ART-256` en
`data/processed/` termina ahí — no existe un `CO-CC-1873-ART-2560` con el inciso 2 (régimen de
visitas de los ascendientes en segundo grado) ni un artículo separado para el parágrafo (excepción del
victimario condenado); el siguiente uid en el archivo es `CO-CC-1873-ART-2561` (artículo distinto,
sobre notarios), y no existe ningún `CO-CC-1873-ART-256A` (a pesar de que el propio docstring del
ruleset menciona "arts. 256 y 256A" como los superados por la reforma de 2022). Es decir: **4 de las 7
reglas del ruleset** (`regimen_visitas_abuelos`, las dos ramas de `justifica_regulacion`,
`es_victimario_absoluto` y las dos ramas de `es_condenado_violencia_o_sexual`) citan contenido que
**no existe en el N0 extraído del `raw_file` real de CO-CC**.

La explicación más probable, y la más simple, es que `data/raw/ley_57_de_1887.md` es el texto de la
codificación **original de 1887** del Código Civil colombiano (tal como sugiere el propio nombre del
archivo), sin las reformas legislativas posteriores incorporadas — mientras que el ruleset cita
deliberadamente el texto **vigente hoy** (post-reforma de 2022). Esto no es un error del pipeline
(extrajo fielmente lo que hay en el `raw_file`), ni necesariamente un error del ruleset (su cita puede
ser correcta contra el Diario Oficial actual, algo que el propio módulo ya advierte no haber podido
verificar — ver su docstring), pero sí es una discrepancia real entre "lo que dice el N0 oficial de
este proyecto" y "lo que el motor de razonamiento asume como fuente verificada para 4 de sus 7
reglas".

**No se edita `co_civil_256_visitas.py` en esta tarea** (fuera de alcance según las instrucciones de
esta ronda) — se deja como hallazgo explícito. Si se quiere cerrar esta discrepancia, las opciones son:
(a) confirmar que `data/raw/ley_57_de_1887.md` en efecto no incorpora la Ley 2229 de 2022 y conseguir
una fuente actualizada (como se hizo con AR-CCYC/InfoLeg en la Nota 0), o (b) marcar explícitamente en
el ruleset que las reglas derivadas del inciso 2 y el parágrafo citan una versión del artículo
posterior a la que hoy existe en `data/processed/CO-CC_articles.json`, hasta que (a) se resuelva.

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
