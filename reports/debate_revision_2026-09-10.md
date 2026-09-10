# Revisión LATIO Kit — Debate multi-agente (2026-09-10)

## Resumen ejecutivo

`latio-kit` propone una taxonomía computable del civil law latinoamericano (esquema `n3_v1.1`, 8 corpus, pipeline determinista N0→N1→N4, análisis de "lift" de figuras, y un explorador web público). El panel de 4 especialistas convergió, de forma **independiente** y después confirmada en réplica cruzada, en que **el sistema nunca se ha ejecutado de punta a punta**: falta la clave `parsing` que el pipeline exige, no hay punto de entrada ejecutable, no hay pruebas, y el manifiesto de gobernanza no contiene ni hashes ni resultados de compuertas — es aparato documental sin ejecución verificable detrás. Sobre esa base rota, el explorador público (`datalexlab.com`) muestra cifras de "lift" y métricas con apariencia de respuesta de API real que en realidad están **fabricadas en JavaScript**, sin ningún cálculo Python detrás. El repo no está listo para ser usado, auditado ni citado tal como está.

## Metodología

Panel de 4 especialistas (ontología jurídica del civil law, arquitectura/código, calidad y gobernanza de datos, producto/despliegue) en 2 rondas:
1. **Revisión independiente** — cada especialista auditó el repo (`C:\Users\DELL\Desktop\latio-kit`) desde su ángulo, sin ver el trabajo de los demás.
2. **Réplica cruzada** — se confrontaron los hallazgos con intersección de dominio; el orquestador verificó directamente con `diff --strip-trailing-cr` la única contradicción factual detectada entre especialistas (ver "Desacuerdos" abajo).

---

## Hallazgos consolidados

### Crítico

- **[C-1] El pipeline nunca corre de punta a punta — causa raíz única, confirmada por los 4 especialistas en réplica.**
  Especialistas: arquitectura, calidad de datos, producto — consenso explícito en la réplica.
  Evidencia: `src/pipeline.py:60,82` accede a `cfg["parsing"]` sin default, pero ninguna de las 8 entradas de `config/corpus_registry.yaml` tiene esa clave → `KeyError` inmediato (confirmado línea por línea por el especialista de arquitectura). Ni `pipeline.py` ni `behavior.py` tienen `if __name__ == "__main__"`; `data/` no existe en el repo; `reports/manifest.json` no contiene `source_hash` ni el array de `gates()` con umbral/estado que el propio código produce; cero pruebas automatizadas en todo el repositorio.
  Los 4 especialistas coincidieron explícitamente: no son 4 bugs independientes, es un único síntoma — nada del "pipeline determinista" documentado se ha ejecutado nunca de verdad.
  Recomendación: escribir un `main()`/CLI real en `pipeline.py` y `behavior.py`, completar la sección `parsing` faltante en el registro, poblar `data/raw/` con al menos una fuente de muestra, y correr el pipeline una vez de punta a punta con evidencia versionada del resultado.

- **[C-2] El LATIO Explorer muestra datos completamente fabricados, indistinguibles de una respuesta real de API.**
  Especialistas: ontología, arquitectura, producto — convergencia independiente, reforzada en réplica.
  Evidencia: `toolkit-api/index.html:665-689` define `MOCK_METRICS`/`MOCK_LIFT` y los renderiza con badge `200 OK` y tiempo de respuesta simulado (`34 ms`); `src/behavior.py` no calcula ningún lift real (no hay función de co-ocurrencia/soporte/lift, ni `main()`); `src/api.py` solo expone `GET /` — los 5 endpoints que la consola JS anuncia (`/v1/statements/parse`, `/v1/behavior/lift`, etc.) no existen en el backend.
  El especialista de producto revisó su propio hallazgo en la réplica: "deja de ser 'backend sin desplegar' y pasa a ser una UI que simula una API completa con datos fabricados en JS, sin ninguna implementación backend que los respalde."
  Recomendación: etiquetar explícitamente la consola como demo/datos de ejemplo mientras no exista backend real, o implementar los endpoints anunciados.

- **[C-3] El pipeline determinista deja fuera N2, N3 y N5 — donde viven las seis propiedades del civil law que el proyecto dice capturar.**
  Especialista: ontología legal (hallazgo confirmado en réplica como ortogonal a C-1, no resuelto por arreglar la ejecución).
  Evidencia: `src/pipeline.py` solo produce N0 (extracción), N1 (segmentación/arquitectura) y N4 (remisiones); no hay función que produzca `Institution` (N2), `NormativeStatement` (N3 — modalidad deóntica, posición de Hohfeld, derogabilidad, presunción, generalidad) ni `Validity` (N5). Esos niveles dependen de anotación humana/LLM externa no versionada en el repo.
  Nota de réplica: aunque se resuelva C-1 (que el pipeline corra), esto seguirá sin calcular lo que el proyecto promete — es un vacío de diseño, no solo de ejecución.
  Recomendación: documentar explícitamente qué porcentaje de N2/N3/N5 está poblado y por qué método, y no presentar el pipeline como cobertura de la ontología completa.

- **[C-4] Discrepancia de alcance no reconciliada: 2 fuentes declaradas vs. 8 fuentes aparentes en los resultados.**
  Especialistas: calidad de datos (hallazgo original), ontología (escalado a crítico en réplica).
  Evidencia: `docs/informe_hito1.md:6` dice "corrida en seco para Chile y Colombia"; `reports/manifest.json:7` reporta `total_articles_evaluated: 21957`, cifra consistente (±1.3%) con la suma de las 8 fuentes del registro (22,246), no con CL+CO solos (5,208).
  Nota de réplica (ontología): combinado con C-3, la afirmación del README de que el proyecto captura "la lógica del civil law latinoamericano" queda sin respaldo empírico trazable en ningún escenario de alcance.
  Recomendación: el manifiesto debe declarar explícitamente qué `corpus_id` entraron en cada `run_id`; reconciliar con el informe de hito.

- **[C-5] `behavior.py` usa un esquema de claves incompatible con `models.py` — desincronización de contrato de datos.**
  Especialista: ontología legal (confirmado en réplica como hallazgo distinto de C-1, no el mismo).
  Evidencia: `behavior.py` opera sobre `P6_deontic`, `P5_addressee` (listas), `is_definitional`, `P2_indeterminate`; ninguna existe en `models.py`, donde los campos equivalentes son singulares o están anidados distinto (`deontic_modality`, `addressee`, `generality.indeterminate_concepts`).
  Recomendación: escribir y testear un adaptador explícito `ArticleRecord → profile dict`, o reescribir `behavior.py` contra los modelos Pydantic reales.

- **[C-6] El README indica `web/index.html`, que no existe; el archivo real es `toolkit-api/index.html`.**
  Especialista: producto/despliegue.
  Evidencia: `README.md:30-31,59` referencian `web/index.html`; la carpeta `web/` no existe en el repo. La sección "Opción B" del mismo README (línea 81) sí referencia correctamente `toolkit-api/index.html`, evidenciando la contradicción interna.
  Recomendación: corregir el árbol de estructura y la guía de uso del README.

### Alto

- **[A-1] `src/api.py` solo expone `GET /`; los 5 endpoints que la consola pública anuncia no existen.** (arquitectura, producto)
- **[A-2] CORS mal configurado: `allow_origins=['*']` junto con `allow_credentials=True`** — combinación inválida/insegura según la especificación CORS. (arquitectura, `src/api.py:7`)
- **[A-3] El "motor de reglas tipo PROLEG" del manifiesto no tiene ninguna correspondencia en el código** — solo existe un campo estático anotado a mano (`burden_shifts_to`), no un motor de derrotabilidad. (ontología, `docs/latio_manifiesto.md:8-11`)
- **[A-4] Manejo de remisiones cubre solo el caso léxico más simple ("artículo N")**; falta remisión tácita, cierre transitivo de cadenas, y enlace verificable de derogación tácita (la etiqueta `"derogado_tacitamente"` es huérfana, sin campo que apunte a la norma derogante). (ontología, `src/pipeline.py:198-239`, `src/models.py:84`)
- **[A-5] `TOOL KIT CIIVL/` es un clon git completo e independiente, con remoto propio (`github.com/Juandf89/TOOL-KIT-CIIVL`), anidado dentro del working tree.** Verificación directa del orquestador (`diff --strip-trailing-cr`): 6 de 7 archivos técnicos comparados son **byte-idénticos** a la raíz (solo difieren en CRLF/LF); únicamente `README.md` diverge de verdad (título distinto, falta la sección de despliegue). El hallazgo de producto que originalmente reportaba "todos los archivos difieren" (Alto) se corrigió en réplica a Medio por ese motivo — pero arquitectura mantiene este ítem en Alto por el riesgo estructural en sí: doble fuente de verdad sin declarar, sin `.gitmodules`, sin mención en el README, con riesgo de que un `git add -A` incorpore un `.git` ajeno como gitlink roto.
- **[A-6] `requirements.txt` exige `fastapi`/`uvicorn` que la guía de instalación del README omite** (`pip install pydantic pyyaml` incompleto). Confirmado en réplica como parte de la misma cadena de procedencia rota que C-1/C-2: si la API tampoco se puede levantar siguiendo el README, ninguna cifra del explorador es inspeccionable por un tercero. (producto, calidad de datos)
- **[A-7] Cero pruebas automatizadas en todo el repositorio.** Integrado a C-1 como parte de la misma causa raíz, listado aquí también por peso propio. (arquitectura)

### Medio

- **[M-1]** Sin `validate_assignment=True`, los invariantes de Pydantic (p. ej. presunción de derecho ⇒ inderogable) solo se garantizan en construcción, no tras mutación; `extra="forbid"` solo está en `ArticleRecord`, los 11 modelos anidados aceptan claves desconocidas en silencio. (arquitectura)
- **[M-2]** Detección de remisiones circulares limitada a auto-referencia directa (A→A); sin detección de ciclos multi-salto (A→B→A). (arquitectura)
- **[M-3]** Umbral heurístico `INTERPOLATION_JUMP=50` en `pipeline.py:23` reclasifica/descarta texto sin dejar rastro por artículo, solo en estadísticas agregadas. (arquitectura)
- **[M-4]** `Ley 153 de 1887` (fuente colombiana sobre derogación e interpretación) excluida del corpus CO-CC, que sí usa esas etiquetas de derogación. (ontología)
- **[M-5]** Corpus históricos y de linaje compartido mezclados sin ponderar en las comparaciones agregadas: `AR-CC` (derogado desde 1869) junto a codificaciones vigentes; `MX-CCF`/`MX-CDMX` no son observaciones independientes (comparten redacción heredada) — riesgo de pseudo-réplica estadística en cualquier cifra de "consenso"/"lift" regional. (ontología)
- **[M-6]** El modelo de Hohfeld anota una sola posición por enunciado, perdiendo la correlatividad por pares que le da su valor analítico. (ontología)
- **[M-7]** Ninguna de las 8 fuentes en `corpus_registry.yaml` declara licencia/derechos de uso. (calidad de datos)
- **[M-8]** Fecha de captura (`retrieved_at`) ausente y confundida con fecha de vigencia de la norma (`version_date`, faltante en 4 de 8 fuentes). (calidad de datos)
- **[M-9]** Sesgo de cobertura: 6 países representados (con Argentina y México aportando 2 corpus cada uno), Centroamérica y el Caribe hispanohablante completamente ausentes, pese a que el proyecto se presenta como representativo de "el civil law latinoamericano". (calidad de datos)
- **[M-10]** Enlace `href="/docs"` (Swagger) en el explorador es una ruta raíz-relativa que no resuelve en ningún despliegue estático documentado (GitHub Pages ni Hostinger). (producto)
- **[M-11]** `card-datalex.html` usa clases de Tailwind sin cargar la librería ni documentar la dependencia del sitio destino. (producto)
- **[M-12]** El árbol "Estructura del Repositorio" del README omite `toolkit-api/`, `.github/`, `src/api.py` y `requirements.txt`. (producto)
- **[M-13]** *(corregido en réplica, ver A-5)* Duplicación `TOOL KIT CIIVL/` — severidad revisada de Alto a Medio por el propio especialista de producto tras la verificación del orquestador.

### Bajo

- **[B-1]** `sali_lmss_mapping` (taxonomía SALI/LMSS, de origen common-law/EE.UU.) usado como mapeo institucional sin capa de traducción documentada. (ontología)
- **[B-2]** `PresumptionInfo` no valida coherencia entre `rebuttable` y `burden_shifts_to`, a diferencia de otros submodelos similares. (arquitectura)
- **[B-3]** Sin CI: `fastapi` no está instalado en el entorno de verificación real; nada detecta desalineaciones de dependencias tempranamente. (arquitectura)
- **[B-4]** El repositorio raíz `latio-kit` no tiene historial git propio (a diferencia de la copia anidada en `TOOL KIT CIIVL/`, que sí lo tiene) — ningún archivo de gobernanza es auditable vía `git blame`. (calidad de datos)
- **[B-5]** Metadatos de versión/fecha inconsistentes entre los 5 documentos de `docs/` (3 de 5 no tienen encabezado de versión/fecha). (producto)
- **Nota positiva:** `.github/workflows/deploy.yml` está bien formado y apunta correctamente a `toolkit-api/` — el problema es que el README no está alineado con lo que el workflow ya hace bien. (producto)

---

## Desacuerdos y su resolución

**Contradicción factual (resuelta por verificación directa):** el especialista de producto reportó que `TOOL KIT CIIVL/` divergía en el contenido de todos los archivos comparados (severidad Alto); arquitectura y calidad de datos reportaron que el contenido era idéntico salvo terminadores de línea. El orquestador ejecutó `diff --strip-trailing-cr` sobre los 7 archivos en disputa: **6 son byte-idénticos, solo `README.md` difiere de verdad**. En la réplica, el especialista de producto revisó su comparación (no había normalizado CRLF/LF) y corrigió su severidad de Alto a Medio, manteniendo arquitectura el ítem en Alto por el riesgo estructural del clon anidado en sí (ver A-5).

**Matiz no resuelto (legítimo, no requiere más evidencia):** los cuatro especialistas coinciden en que C-1 (falta de ejecución end-to-end) es una única causa raíz para los síntomas de gobernanza/pruebas/manifest. El especialista de ontología sostiene, y el resto no lo contradice, que C-3 (N2/N3/N5 nunca implementados) y C-5 (desincronización de esquema en `behavior.py`) son capas **distintas y ortogonales** — no se resuelven arreglando el entry point del pipeline. Esta distinción importa para la priorización: arreglar C-1 hace el pipeline *ejecutable*, no hace que calcule lo que el proyecto promete.

---

## Plan de acción priorizado

1. **Hacer el pipeline ejecutable de verdad**: `main()`/CLI en `pipeline.py` y `behavior.py`, completar la clave `parsing` en `corpus_registry.yaml`, poblar `data/raw/` con al menos una fuente de muestra, y correr el pipeline de punta a punta una vez con evidencia versionada.
2. **Sincronizar `behavior.py` con el esquema real de `models.py`** (adaptador `ArticleRecord → profile dict`) para que el cálculo de las seis propiedades sea real.
3. **Eliminar o etiquetar como demo** los datos fabricados del LATIO Explorer (`MOCK_METRICS`/`MOCK_LIFT`) hasta que exista un backend real que los sirva; implementar o retirar los 5 endpoints que la consola anuncia.
4. **Corregir el README**: `web/index.html` → `toolkit-api/index.html`, comando de instalación unificado con `requirements.txt` (incluir `fastapi`/`uvicorn`), árbol de estructura regenerado.
5. **Reconciliar el alcance real** entre `informe_hito1.md` y `manifest.json` (2 vs. 8 fuentes) con `corpus_id` explícitos por `run_id`.
6. **Resolver `TOOL KIT CIIVL/`**: eliminarla del working tree o convertirla en submódulo explícito documentado.
7. **Persistir hashes y resultados de `gates()` reales en `manifest.json`**; añadir suite de tests (Pydantic + casos sintéticos de `pipeline.py`, incluyendo el umbral de 50 y remisiones circulares multi-salto).
8. **Documentar como limitación explícita**: ausencia de remisión tácita/en cadena, derogación tácita sin enlace verificable, simplificación unilateral del modelo de Hohfeld, exclusión de la Ley 153/1887, y el sesgo de cobertura geográfica (6 países, sin Centroamérica/Caribe).
9. **Higiene menor**: fijar CORS explícito, `validate_assignment=True` + `extra="forbid"` uniforme vía clase base, licencias y fecha de captura por fuente en el registro, CI mínimo.

## Veredicto final

`latio-kit` tiene un modelo de datos (`src/models.py`) razonablemente sofisticado y jurídicamente informado, y una intención de arquitectura neurosimbólica genuinamente interesante — pero en su estado actual es, en la práctica, **documentación y taxonomía sin sistema funcionando detrás**: el pipeline que se declara "determinista" nunca se ha ejecutado de punta a punta (falla en el primer acceso a una clave de configuración inexistente), el análisis de comportamiento no puede correr contra el esquema real, y el producto público que representa el proyecto ante la comunidad LegalTech (`datalexlab.com`) muestra cifras fabricadas con apariencia de resultado empírico verificado. Nada de esto es irreparable — el plan de acción de arriba es concreto y acotado — pero el repositorio no debe presentarse hoy como un sistema operativo ni sus cifras deben citarse como resultados válidos hasta resolver, como mínimo, los 6 hallazgos críticos.
