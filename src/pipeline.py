"""
pipeline.py — N0 -> N1 -> N4 para el proyecto de ontología del enunciado normativo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
PIPELINE_VERSION = "pipeline_v0.2"
INTERPOLATION_JUMP = 50

ROMAN = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
WORD_ORD = {"PRIMERO":1,"SEGUNDO":2,"TERCERO":3,"CUARTO":4,"QUINTO":5}

def roman_to_int(s: str) -> int | None:
    s = s.upper()
    if s in WORD_ORD:
        return WORD_ORD[s]
    if s.isdigit():
        return int(s)
    if not s or any(ch not in ROMAN for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total

@dataclass
class Corpus:
    corpus_id: str
    cfg: dict
    lines: list[str] = field(default_factory=list)
    source_hash: str = ""
    removed_furniture: int = 0

def extract(corpus_id: str, registry: dict) -> Corpus:
    cfg = registry[corpus_id]
    path = RAW / cfg["raw_file"]
    raw_bytes = path.read_bytes()
    source_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()

    text = unicodedata.normalize("NFC", raw_bytes.decode("utf-8"))
    text = text.replace("\u00a0", " ").replace("\r\n", "\n")

    furniture = [re.compile(p) for p in cfg["parsing"].get("page_furniture", [])]
    kept, removed = [], 0
    for line in text.split("\n"):
        if any(f.search(line) for f in furniture):
            removed += 1
            continue
        kept.append(re.sub(r"[ \t]+", " ", line).rstrip())

    return Corpus(corpus_id, cfg, kept, source_hash, removed)

@dataclass
class Article:
    uid: str
    number: int
    suffix: str | None
    path: list[dict]
    position_index: int
    text_raw: str
    editorial_notes: list[str] = field(default_factory=list)
    qa_flags: list[str] = field(default_factory=list)

def segment(c: Corpus) -> tuple[list[Article], dict]:
    p = c.cfg["parsing"]
    art_re = re.compile(p["article_pattern"])
    final_re = re.compile(p["final_article_pattern"]) if p.get("final_article_pattern") else None
    levels = [(l["type"], re.compile(l["pattern"])) for l in p["levels"]]
    superseded = [re.compile(x) for x in p.get("superseded_block_markers", [])]
    editorial = [re.compile(x) for x in p.get("editorial_markers", [])]

    articles: list[Article] = []
    path: list[dict] = []
    last_num = 0
    seen_suffix: set[tuple[int, str]] = set()
    cur: Article | None = None
    buf: list[str] = []
    in_superseded = False
    rejected_non_monotonic = 0
    level_rank = {t: i for i, (t, _) in enumerate(levels)}

    def close():
        nonlocal cur, buf
        if cur is None:
            return
        body = " ".join(x.strip() for x in buf if x.strip())
        notes = []
        for rx in editorial:
            for m in rx.finditer(body):
                notes.append(m.group(0).strip())
            body = rx.sub(" ", body)
        cur.text_raw = re.sub(r"\s+", " ", body).strip()
        cur.editorial_notes = notes
        if not cur.text_raw:
            cur.qa_flags.append("empty_body")
        articles.append(cur)
        cur, buf = None, []

    for i, line in enumerate(c.lines):
        s = line.strip()
        if not s:
            if not in_superseded:
                buf.append("")
            continue

        if any(rx.match(s) for rx in superseded):
            in_superseded = True
            continue

        matched_level = False
        for ltype, rx in levels:
            m = rx.match(s)
            if m:
                close()
                in_superseded = False
                rk = level_rank[ltype]
                path = [n for n in path if n["rank"] < rk]
                path.append({
                    "level_type": ltype,
                    "rank": rk,
                    "ordinal": m.groupdict().get("ord"),
                    "ordinal_int": roman_to_int(m.groupdict().get("ord") or ""),
                    "label": s,
                    "depth": len(path),
                })
                for k, n in enumerate(path):
                    n["depth"] = k
                matched_level = True
                break
        if matched_level:
            continue

        m = art_re.match(s)
        is_final = bool(final_re and final_re.match(s))
        if m or is_final:
            if is_final:
                num, suffix = last_num + 1, "FINAL"
            else:
                num = int(m.group("num"))
                suffix = (m.groupdict().get("suffix") or "").strip(".oº° ").upper() or None
                key = (num, suffix or "")
                backward = num < last_num or (num == last_num and (key in seen_suffix or suffix is None))
                if backward:
                    rejected_non_monotonic += 1
                    if last_num - num > INTERPOLATION_JUMP:
                        in_superseded = True
                    elif cur is not None:
                        buf.append(s)
                    continue
                seen_suffix.add(key)
            close()
            in_superseded = False
            uid = f"{c.cfg['jurisdiction']}-{c.cfg['code_id']}-{c.cfg['year_tag']}-ART-{num}"
            if suffix:
                uid += f"-{suffix}"
            cur = Article(uid, num, suffix, [dict(n) for n in path], len(articles), "")
            rest = s[m.end():].strip() if m else ""
            if rest:
                buf.append(rest)
            last_num = max(last_num, num)
            continue

        if not in_superseded and cur is not None:
            buf.append(s)

    close()

    stats = {
        "articles_parsed": len(articles),
        "max_article_number": last_num,
        "rejected_non_monotonic": rejected_non_monotonic,
        "furniture_lines_removed": c.removed_furniture,
        "with_suffix": sum(1 for a in articles if a.suffix),
        "with_editorial_notes": sum(1 for a in articles if a.editorial_notes),
        "empty_body": sum(1 for a in articles if "empty_body" in a.qa_flags),
        "max_depth": max((len(a.path) for a in articles), default=0),
        "level_types": sorted({n["level_type"] for a in articles for n in a.path}),
    }
    return articles, stats

NUM_REF = re.compile(r"(?i)art[íi]culos?\s+(\d+)")
ANA_REF = re.compile(r"(?i)art[íi]culo\s+(anterior|precedente|siguiente)")

def referrals(articles: list[Article], jur: str, code: str, year: str) -> tuple[list[dict], dict]:
    by_num = {a.number: a.uid for a in articles}
    order = [a.uid for a in articles]
    idx = {u: i for i, u in enumerate(order)}
    edges, unresolved, ana = [], 0, 0

    for a in articles:
        for m in NUM_REF.finditer(a.text_raw):
            n = int(m.group(1))
            tgt = by_num.get(n)
            edges.append({
                "source": a.uid, "target": tgt, "raw_reference": m.group(0),
                "resolution": "numeric" if tgt else "unresolved",
                "function": "indeterminada", "in_function_sample": False, "verified": False,
            })
            if not tgt:
                unresolved += 1
        for m in ANA_REF.finditer(a.text_raw):
            i = idx[a.uid]
            j = i - 1 if m.group(1).lower() in ("anterior", "precedente") else i + 1
            tgt = order[j] if 0 <= j < len(order) else None
            edges.append({
                "source": a.uid, "target": tgt, "raw_reference": m.group(0),
                "resolution": "anaphoric" if tgt else "unresolved",
                "function": "indeterminada", "in_function_sample": False, "verified": False,
            })
            ana += 1
            if not tgt:
                unresolved += 1

    total = len(edges)
    stats = {
        "edges_total": total,
        "edges_anaphoric": ana,
        "edges_unresolved": unresolved,
        "resolution_rate": round((total - unresolved) / total, 4) if total else None,
        "reflexive": sum(1 for e in edges if e["target"] == e["source"]),
    }
    return edges, stats

def gates(c: Corpus, articles: list[Article], seg: dict, ref: dict) -> list[dict]:
    expected = c.cfg["expected_article_count"]
    base_numbers = {a.number for a in articles if not a.suffix}
    missing = sorted(set(range(1, expected + 1)) - base_numbers)
    uids = [a.uid for a in articles]
    src = c.cfg["source"]

    return [
        {"gate": "completitud", "metric": "artículos base / declarados en fuente",
         "value": f"{len(base_numbers)}/{expected}", "threshold": "100%",
         "status": "PASS" if not missing else "FAIL",
         "detail": f"ausentes: {len(missing)} → {missing[:12]}"},
        {"gate": "unicidad", "metric": "uid duplicados", "value": len(uids) - len(set(uids)),
         "threshold": "0", "status": "PASS" if len(uids) == len(set(uids)) else "FAIL", "detail": ""},
        {"gate": "consistencia_N4", "metric": "remisiones con destino existente",
         "value": ref["resolution_rate"], "threshold": "≥ 0.98",
         "status": "PASS" if (ref["resolution_rate"] or 0) >= 0.98 else "FAIL",
         "detail": f"sin resolver: {ref['edges_unresolved']}"},
        {"gate": "integridad_grafo", "metric": "aristas reflexivas", "value": ref["reflexive"],
         "threshold": "0", "status": "PASS" if ref["reflexive"] == 0 else "WARN", "detail": ""},
        {"gate": "cuerpo_no_vacio", "metric": "artículos sin texto", "value": seg["empty_body"],
         "threshold": "0", "status": "PASS" if seg["empty_body"] == 0 else "WARN", "detail": ""},
        {"gate": "trazabilidad", "metric": "url + fecha de consulta + versión",
         "value": "ausente" if not src.get("official") else "presente", "threshold": "100%",
         "status": "PASS" if src.get("official") else "FAIL",
         "detail": "fuente no oficial: solo válido para run_type=dry_run"},
    ]

# ---------------------------------------------------------------------------
# CLI — encadena extract -> segment -> referrals -> gates y persiste evidencia
# ---------------------------------------------------------------------------

def load_registry(path: Path | None = None) -> dict:
    registry_path = path or (ROOT / "config" / "corpus_registry.yaml")
    with open(registry_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_corpus(corpus_id: str, registry: dict) -> dict:
    """Corre N0 -> N1 -> N4 -> gates para un corpus y persiste evidencia
    versionada (data/processed/ + reports/), en vez de solo devolver valores
    en memoria — ver C-1 en reports/debate_revision_2026-09-10.md."""
    c = extract(corpus_id, registry)
    articles, seg_stats = segment(c)
    edges, ref_stats = referrals(articles, c.cfg["jurisdiction"], c.cfg["code_id"], c.cfg["year_tag"])
    gate_results = gates(c, articles, seg_stats, ref_stats)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    (PROCESSED / f"{corpus_id}_articles.json").write_text(
        json.dumps([asdict(a) for a in articles], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (PROCESSED / f"{corpus_id}_referrals.json").write_text(
        json.dumps(edges, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    report = {
        "corpus_id": corpus_id,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hash": c.source_hash,
        "segment_stats": seg_stats,
        "referral_stats": ref_stats,
        "gates": gate_results,
    }
    (REPORTS / f"{corpus_id}_run_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return report

def main(argv: list[str] | None = None) -> int:
    # Windows CMD/PowerShell por defecto usa cp1252, que no puede imprimir
    # caracteres como '→' usados en el detalle de gates(); forzar UTF-8 en
    # stdout/stderr evita un UnicodeEncodeError al correr el CLI ahí.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Pipeline N0 -> N1 -> N4 de latio-kit (extract -> segment -> referrals -> gates)."
    )
    parser.add_argument(
        "corpus_id",
        help="corpus_id declarado en config/corpus_registry.yaml. "
             "Usa TEST-FIXTURE para un smoke test end-to-end con datos sintéticos "
             "(no requiere ninguna fuente real en data/raw/).",
    )
    parser.add_argument("--registry", default=None, help="ruta alternativa al registro YAML.")
    args = parser.parse_args(argv)

    registry = load_registry(Path(args.registry) if args.registry else None)
    if args.corpus_id not in registry:
        print(f"corpus_id desconocido: {args.corpus_id!r}. Disponibles: {sorted(registry)}", file=sys.stderr)
        return 1

    report = run_corpus(args.corpus_id, registry)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    failed = [g for g in report["gates"] if g["status"] == "FAIL"]
    if failed:
        print(f"\n{len(failed)} compuerta(s) en FAIL — ver detalle arriba.", file=sys.stderr)
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
