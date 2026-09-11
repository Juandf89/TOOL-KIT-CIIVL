# LATIO: Una propuesta para el ecosistema LegalTech latinoamericano

**Versión:** 1.0 · **Fecha:** 2026-09-07

### Taxonomía y Ontología de la Información Jurídica para el Civil Law

Los modelos de lenguaje (LLM) que usamos comúnmente no fueron diseñados para razonar sobre la estructura del derecho continental europeo ni latinoamericano. En el derecho, la escritura sintética produce texto plausible, no necesariamente verificable. La diferencia fundamental radica en que un juez continental no puede cerrar un proceso aduciendo que faltan pruebas: la verdad formal se dirime a través de la **carga de la prueba**.

### ¿Por qué la IA tropieza con el derecho codificado?
En América Latina el derecho se construye sobre códigos: reglas escritas con excepciones organizadas jerárquicamente. El common law opera por casos analógicos. La solución no es entrenar LLMs más grandes, sino adoptar una **arquitectura neurosimbólica**:

1. **LLM**: Traduce hechos caóticos en lenguaje natural hacia hechos estructurados.
2. **Motor de reglas (tipo PROLEG)**: Aplica reglas por defecto, excepciones y desplazamiento de la carga probatoria, garantizando inferencias auditables y explicables.
3. **LATIO**: La taxonomía y ontología abierta que define las primitivas del lenguaje jurídico en la región.

**Estado actual (2026-09-11):** la capa 1 (LLM) descrita arriba es la visión de arquitectura a futuro, no lo que corre hoy — LATIO Kit implementa el etiquetado estructurado con reglas léxicas deterministas locales (`src/labeling/`), sin ningún LLM ni servicio externo, sin costo. La capa 2 (motor PROLEG) sí está implementada y corre en `src/reasoning/`. Ver `docs/limitaciones_conocidas.md` para el detalle completo de qué está construido y qué es todavía aspiracional.
