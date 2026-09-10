"""
co_civil_256_visitas.py — Ruleset del motor de razonamiento: régimen de
visitas del Art. 256 del Código Civil colombiano.

Primer ruleset del motor derivado de un artículo LATAM real (no del ejemplo
del paper PROLEG). Todos los Rule.source_uid apuntan a un uid con el formato
que exige ArticleRecord (src/models.py, {JUR}-{CODE}-{YEAR}-ART-{NUM}):
CO-CC-1873-ART-256 (CO-CC en config/corpus_registry.yaml: jurisdiction=CO,
code_id=CC, year_tag='1873'). Advertencia honesta: ese uid es una referencia
hacia el futuro, no hacia un dato existente — no hay todavía un
ArticleRecord real para CO-CC-1873-ART-256 en data/processed/ (el pipeline
solo produce N0/N1/N4, ver docs/limitaciones_conocidas.md §5). Este ruleset
se escribió a mano a partir del texto oficial citado abajo, con la misma
metodología que jp_civil_612_sublease.py — no hay todavía un traductor
automático NormativeStatement -> Rule.

Texto verificado (2026-09-10) contra tres fuentes independientes
coincidentes (búsqueda web + leyes.co + vLex Colombia) del Art. 256 del
Código Civil colombiano, modificado por la Ley 2229 de 2022 (arts. 256 y
256A superados en dos incisos + un parágrafo):

    "Al padre o madre de cuyo cuidado personal se sacaren los hijos, no
    por eso se prohibirá visitarlos con la frecuencia y libertad que el
    juez juzgare convenientes.

    Así mismo, teniendo en cuenta las particularidades del caso en
    concreto y atendiendo al interés superior del niño, niña o
    adolescente, el juez ordenará la regulación de visitas respecto de
    los ascendientes en segundo grado de consanguinidad o segundo grado
    de parentesco civil por línea materna o paterna, cuando estos no
    tuvieren el cuidado personal de los nietos y nietas o en los eventos
    en que los progenitores nieguen o sustraigan a sus hijos de la
    relación con estos.

    Parágrafo. El juez podrá negar o regular las visitas de progenitores
    o ascendientes en segundo grado de consanguinidad o segundo grado de
    parentesco civil por línea materna o paterna, cuando estos hayan sido
    condenados mediante sentencia ejecutoriada por la comisión de delitos
    de violencia intrafamiliar o delitos contra la libertad, integridad y
    formación sexuales. En ningún caso el victimario podrá ser titular
    del derecho de visitas a su víctima y los hermanos de esta."

No se verificó contra el texto de la Ley 2229 de 2022 en un repositorio
oficial (funcionpublica.gov.co y suin-juriscol.gov.co devolvieron error de
certificado TLS al momento de escribir esto); si se detecta una divergencia
con el Diario Oficial, corregir aquí y en los tests.

Estructura lógica (dos derechos por defecto que comparten la misma
excepción absoluta):

    derecho_de_visitas_progenitor
      :- no_tiene_cuidado_personal_hijos
      excepción: es_victimario_absoluto

    regimen_visitas_abuelos
      :- es_ascendiente_segundo_grado,
         no_tiene_cuidado_personal_nietos,
         justifica_regulacion
      excepción: es_victimario_absoluto

    justifica_regulacion
      :- progenitores_niegan_relacion
      :- caso_justifica_interes_superior       (regla alternativa, OR)

    es_victimario_absoluto
      :- es_condenado_violencia_o_sexual, es_victima_o_hermano_del_solicitante

    es_condenado_violencia_o_sexual
      :- condena_ejecutoriada_violencia_intrafamiliar
      :- condena_ejecutoriada_delito_sexual    (regla alternativa, OR)

Nota de modelado: el inciso 2 da al ascendiente un régimen de visitas
ordenado por el juez, no una "no prohibición" como el inciso 1 — se modela
igual como un `Rule` por simplicidad (el motor no distingue "derecho" de
"régimen ordenado", ambos son metas que se prueban o no). El parágrafo es
una excepción ABSOLUTA ("en ningún caso") compartida por ambas reglas, fiel
al texto: se declara una sola vez (`es_victimario_absoluto`) y se enlaza a
las dos con dos `ExceptionLink` distintos, en vez de duplicar la lógica.
"""

from __future__ import annotations

from src.reasoning.models import ExceptionLink, Rule, RuleBase

_SOURCE_UID = "CO-CC-1873-ART-256"
_SOURCE_NOTE = (
    "Art. 256 Código Civil colombiano, modificado por la Ley 2229 de 2022 "
    "(régimen de visitas) — verificado 2026-09-10 contra fuentes "
    "independientes coincidentes, no contra el Diario Oficial."
)

RULEBASE = RuleBase(
    id="co-civil-256-visitas",
    description=(
        "Régimen de visitas del Art. 256 del Código Civil colombiano "
        "(modificado por la Ley 2229 de 2022): derecho por defecto del "
        "progenitor sin custodia y régimen judicial para abuelos, ambos "
        "derrotados por la excepción absoluta de victimario condenado."
    ),
    rules=[
        Rule(
            head="derecho_de_visitas_progenitor",
            body=["no_tiene_cuidado_personal_hijos"],
            source_uid=_SOURCE_UID,
            source_note=_SOURCE_NOTE + " — inciso 1.",
        ),
        Rule(
            head="regimen_visitas_abuelos",
            body=[
                "es_ascendiente_segundo_grado",
                "no_tiene_cuidado_personal_nietos",
                "justifica_regulacion",
            ],
            source_uid=_SOURCE_UID,
            source_note=_SOURCE_NOTE + " — inciso 2.",
        ),
        Rule(
            head="justifica_regulacion",
            body=["progenitores_niegan_relacion"],
            source_uid=_SOURCE_UID,
            source_note=_SOURCE_NOTE + " — inciso 2 (rama: negación del vínculo).",
        ),
        Rule(
            head="justifica_regulacion",
            body=["caso_justifica_interes_superior"],
            source_uid=_SOURCE_UID,
            source_note=_SOURCE_NOTE + " — inciso 2 (rama: interés superior del NNA).",
        ),
        Rule(
            head="es_victimario_absoluto",
            body=[
                "es_condenado_violencia_o_sexual",
                "es_victima_o_hermano_del_solicitante",
            ],
            source_uid=_SOURCE_UID,
            source_note=_SOURCE_NOTE + " — parágrafo, segunda frase (\"en ningún caso\").",
        ),
        Rule(
            head="es_condenado_violencia_o_sexual",
            body=["condena_ejecutoriada_violencia_intrafamiliar"],
            source_uid=_SOURCE_UID,
            source_note=_SOURCE_NOTE + " — parágrafo, primera frase (rama: violencia intrafamiliar).",
        ),
        Rule(
            head="es_condenado_violencia_o_sexual",
            body=["condena_ejecutoriada_delito_sexual"],
            source_uid=_SOURCE_UID,
            source_note=_SOURCE_NOTE + " — parágrafo, primera frase (rama: delito sexual).",
        ),
    ],
    exceptions=[
        ExceptionLink(
            rule_head="derecho_de_visitas_progenitor",
            exception_head="es_victimario_absoluto",
        ),
        ExceptionLink(
            rule_head="regimen_visitas_abuelos",
            exception_head="es_victimario_absoluto",
        ),
    ],
)
