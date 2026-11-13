#!/usr/bin/env python3
"""Profili di voce e controlli locali delle riscritture, senza chiamate a modelli."""
from __future__ import annotations

import argparse
from collections import Counter
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata

SCHEMA_VERSION = "1.0"
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_STDIN_BYTES = 16 * 1024 * 1024
PROFILE_FIELDS = {
    "schema_version", "name", "register", "conciseness", "preferred_phrases",
    "avoided_phrases", "punctuation", "notes",
}
PROFILE_LIST_FIELDS = ("preferred_phrases", "avoided_phrases", "punctuation", "notes")
RESERVED_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                  *(f"lpt{i}" for i in range(1, 10))}
URL_PATTERN = re.compile(r"https?://[^\s<>\"“”«»]+", re.I)
NUMBER_PATTERN = re.compile(
    r"(?<![\w])(?:(?:[+\-−][^\S\r\n]*)?[€$£][^\S\r\n]*)?(?:[+\-−][^\S\r\n]*)?\d+(?:[.,:/-]\d+)*(?:[^\S\r\n]*(?:%|€|\$|£))?(?!\d)"
)
QUOTE_PATTERN = re.compile(r'«([^«»\n]{1,2000})»|“([^“”\n]{1,2000})”|"([^"\n]{1,2000})"')
TIME_INTRODUCER = r"(?:alle|dalle|ore|(?:entro|verso|dopo|circa|per|tra|fra)\s+le|prima\s+delle)"
TIME_PATTERN = re.compile(r"\b" + TIME_INTRODUCER + r"\s+([01]?\d|2[0-3])[:.]([0-5]\d)\b", re.I)
NUMBER_WORDS = dict(zip(
    ("uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci",
     "undici", "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette",
     "diciotto", "diciannove", "venti", "trenta", "quaranta", "cinquanta", "sessanta",
     "settanta", "ottanta", "novanta", "cento", "mille"),
    (*range(1, 21), 30, 40, 50, 60, 70, 80, 90, 100, 1000),
))
NUMBER_WORD_PATTERN = re.compile(r"\b(?:" + "|".join(NUMBER_WORDS) + r")\b", re.I)
# Indizi lessicali/grammaticali, non frasi da escludere: gli omografi
# irrisolti restano visibili come segnali di revisione.
COUNT_WORDS = {
    "unità", "euro", "auto", "moto", "radio", "città", "film", "file", "re",
    "persone", "cose", "foto", "ore", "settimane", "volte", "pagine", "righe", "copie",
    "scatole", "tonnellate", "buste", "specie", "serie", "dita", "uova",
    "braccia", "paia", "centinaia", "migliaia", "mura", "ossa", "labbra",
}
COUNT_LABELS = {"numero", "numeri", "codice", "pagina", "capitolo", "articolo", "punto", "caso"}
NUMBER_CONTEXT_CHARS = 128
COPULAR_WORDS = {
    stem + ending for stem in ("liber", "sicur", "pront", "stanc", "occupat", "convint", "cert", "content")
    for ending in ("o", "a")
} | {"disponibile", "capace", "felice", "gentile", "presente", "assente"}
COPULAR_LINKS = {"in", "un", "una", "uno"}
ARTICLE_HEAD_PATTERN = re.compile(r"\b(?:lo|il|un|uno|questo|quello)\s+([^\W\d_]+)\b", re.I)
WORD_BEFORE = re.compile(r"([^\W\d_]+)\s*$")
WORD_AFTER = re.compile(r"\s+([^\W\d_]+)")

CALENDAR_PATTERN = re.compile(
    r"\b(?:luned[ìi]|marted[ìi]|mercoled[ìi]|gioved[ìi]|venerd[ìi]|sabato|domenica|"
    r"gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b", re.I
)
# Matches the longest grammatical forms first, including non-conditional
# concessives, so their inner "se" cannot masquerade as a condition.
CONDITION_PATTERN = re.compile(
    r"\b(?:(?P<concessive>anche\s+se|nonostante|sebbene|bench(?:é|e\u0301))|"
    r"(?P<requirement>solo\s+se|purch(?:é|e\u0301)|a\s+condizione\s+che|a\s+patto\s+che)|"
    r"(?P<exception>salvo|a\s+meno\s+che)|(?P<after_only>solo\s+dopo)|"
    r"(?P<conditional>nel\s+caso\s+in\s+cui|in\s+caso\s+di|qualora|se))(?!\w)", re.I)
DEADLINE_PATTERN = re.compile(
    r"\b(?:(?P<by>entro|non\s+oltre)\b|"
    r"(?P<before>prima\s+(?:(?:di|del|dello|della|dei|degli|delle)\b|dell['’]))|"
    r"(?P<until>fino\s+(?:(?:a|al|allo|alla|ai|agli|alle)\b|all['’]))|"
    r"(?P<from>a\s+partire\s+(?:(?:da|dal|dallo|dalla|dai|dagli|dalle)\b|dall['’])))", re.I)

MARKER_PATTERNS = {
    "negation": re.compile(r"\b(?:non|mai|nessun[oa]?|senza|n(?:é|e\u0301)|niente|nulla|neanche|nemmeno|neppure)(?!\w)", re.I),
    "uncertainty": re.compile(
        r"\b(?:forse|potrebbe|potrebbero|potremmo|potrei|possibile|probabile|"
        r"ipotizziamo|indicativamente|circa|previsto|prevista|dovrebbe|dovremmo|probabilmente|eventualmente)\b", re.I
    ),
    "condition": CONDITION_PATTERN,
    "deadline": DEADLINE_PATTERN,
}


# Deliberately supported common public TLDs. This is not DNS validation and
# intentionally avoids classifying arbitrary dotted prose or file.pdf as links.
FACT_TLDS = (
    "it", "com", "org", "net", "edu", "gov", "eu", "io", "info", "biz", "me", "co", "uk",
    "fr", "de", "es", "ch", "at", "be", "nl", "pt", "us", "ca", "au", "ie", "dev", "app",
    "cloud", "online", "site", "tech", "ai", "museum", "travel", "pro", "xyz", "agency",
)
FACT_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
FACT_DOMAIN = r"(?:" + FACT_LABEL + r"\.)+(?:" + "|".join(sorted(FACT_TLDS, key=len, reverse=True)) + r")"
FACT_DOMAIN_PATTERN = re.compile(r"(?<![\w@.-])" + FACT_DOMAIN + r"(?![\w-]|\.[\w-])", re.I)
# Unquoted ASCII mailbox forms. Local-part case is preserved: only the domain
# is case-insensitive. Complex RFC mailbox syntax deliberately remains outside
# this mechanical extractor.
FACT_EMAIL_PATTERN = re.compile(
    r"(?<![\w@.!#$%&'*+/=?^_`{|}~-])(?P<local>[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*)"
    r"@(?P<host>(?:" + FACT_LABEL + r"\.)+[a-z]{2,24})(?![\w-])", re.I)
FACT_CODE_PATTERN = re.compile(r"(?<!\w)[A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)*(?!\w)")
# A named encoding term, not a case-sensitive identifier. All *other* codes
# preserve case; broad case folding would hide changes to actual identifiers.
FACT_CASE_INSENSITIVE_TERMS = {"base64"}
FACT_DAY_PATTERN = re.compile(
    r"\b(?:in\s+data\s+odierna|quest['’]oggi|l['’]altro\s*ieri|avantieri|"
    r"ieri\s+l['’]altro|domani\s+l['’]altro|dopodomani|domani|ieri|oggi)\b", re.I)
FACT_PERIOD_PATTERN = re.compile(
    r"\b(?:(?P<before>questa|questo|corrente|presente|prossima|prossimo|scorsa|scorso)\s+"
    r"(?P<unit_after>settimana|mese|anno)|(?P<unit_before>settimana|mese|anno)\s+"
    r"(?P<after>corrente|presente|prossima|prossimo|scorsa|scorso)|quest['’]anno)\b", re.I)


def _trim_fact_url(value):
    value = value.rstrip(".,;!")
    for closing, opening in ((")", "("), ("]", "["), ("}", "{")):
        while value.endswith(closing) and value.count(closing) > value.count(opening):
            value = value[:-1]
    return value


def _identifier_records(text):
    """Non-overlapping {kind, value, start, end}; URLs own their inner tokens."""
    records = []
    occupied = bytearray(len(text))
    for kind, pattern in (("url", URL_PATTERN), ("email", FACT_EMAIL_PATTERN),
                          ("domain", FACT_DOMAIN_PATTERN), ("identifier", FACT_CODE_PATTERN)):
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(occupied[start:end]):
                continue
            raw = match.group()
            if kind == "identifier":
                if not any(char.isdigit() for char in raw) or not re.search(r"[A-Za-z]", raw):
                    continue
                value = raw.casefold() if raw.casefold() in FACT_CASE_INSENSITIVE_TERMS else raw
            elif kind == "email":
                value = match["local"] + "@" + match["host"].casefold()
            elif kind == "domain":
                value = raw.casefold()
            else:
                value = _trim_fact_url(raw)
                end = start + len(value)
            records.append({"kind": kind, "value": value, "start": start, "end": end})
            occupied[start:end] = b"\x01" * (end - start)
    return sorted(records, key=lambda record: record["start"])


def _mask_identifiers(text):
    masked = list(text)
    for record in _identifier_records(text):
        masked[record["start"]:record["end"]] = " " * (record["end"] - record["start"])
    return "".join(masked)


def _relative_day_records(text):
    # Preserve indices by masking instead of deleting protected identifiers.
    masked = _mask_identifiers(text)
    result = []
    for match in FACT_DAY_PATTERN.finditer(masked):
        word = re.sub(r"\s+", " ", match.group().casefold()).replace("’", "'")
        if word in {"oggi", "quest'oggi", "in data odierna"}:
            value = "oggi"
        elif word in {"avantieri", "ieri l'altro"} or re.fullmatch(r"l'altro\s*ieri", word):
            value = "altroieri"
        elif word in {"dopodomani", "domani l'altro"}:
            value = "dopodomani"
        else:
            value = word
        result.append({"kind": "relative_day", "value": value, "start": match.start(), "end": match.end()})
    return result


def _relative_period_records(text):
    masked = _mask_identifiers(text)
    result = []
    for match in FACT_PERIOD_PATTERN.finditer(masked):
        unit = match["unit_after"] or match["unit_before"] or "anno"
        marker = (match["before"] or match["after"] or "questo").casefold()
        period = "prossimo" if marker.startswith("prossim") else "scorso" if marker.startswith("scors") else "corrente"
        result.append({"kind": "relative_period", "value": unit.casefold() + ":" + period,
                       "start": match.start(), "end": match.end()})
    return result



INFORMAL_PATTERN = re.compile(r"\b(?:tu|ti|te)\b|\b[a-zàèéìòù]+rti\b", re.I)
FORMAL_PATTERN = re.compile(
    r"\bLei\b|\b[Ll]e\s+(?:scrivo|invio|mando|comunico|confermo|chiedo|allego|"
    r"ringrazio|segnalo|ricordo|auguro|rispondo)\b|\b[a-zàèéìòù]+rLe\b")
HISTORY_HEADER_PATTERN = re.compile(
    r"(?im)^[ \t]*(?:Il\s+giorno\s+[^\r\n]+\bha\s+scritto:|"
    r"On\s+[^\r\n]+\bwrote:)[ \t]*\r?$")
SENTENCE_END_PATTERN = re.compile(r"[.!?;]+(?=\s|$)|\n+")


def _history_boundary(text: str) -> int | None:
    """Only explicit dated reply headers followed by quoted lines are anchors."""
    for match in HISTORY_HEADER_PATTERN.finditer(text):
        prefix, tail = text[:match.start()], text[match.end():]
        if (prefix.strip() and re.search(r"\n[ \t]*\r?\n[ \t]*$", prefix)
                and FACT_EMAIL_PATTERN.search(match.group()) and re.search(r"\d", match.group())
                and re.match(r"\s*>", tail)
                and all(line.lstrip().startswith(">") for line in tail.splitlines() if line.strip())):
            return match.start()
    return None


def _comparison_texts(source: str, revision: str) -> tuple[str, str, dict]:
    source_boundary, revision_boundary = _history_boundary(source), _history_boundary(revision)
    source_excluded = source_boundary is not None and revision_boundary is None
    # Newly added quoted content is not known to come from the source.
    revision_excluded = False
    return (source[:source_boundary].rstrip() if source_excluded else source,
            revision,
            {"name": "new_message" if source_excluded or revision_excluded else "full_text",
             "source_history_excluded": source_excluded, "revision_history_excluded": revision_excluded})


def _review_events(text: str) -> dict[str, list[tuple[str, int, int]]]:
    """Canonical classes with original offsets; no inference about their scope."""
    masked = _mask_identifiers(text)
    events = {category: [] for category in ("negation", "uncertainty", "condition", "deadline", "register", "relative_period")}
    for match in CONDITION_PATTERN.finditer(masked):
        if match.lastgroup != "concessive":
            events["condition"].append((match.lastgroup, *match.span()))
    for match in DEADLINE_PATTERN.finditer(masked):
        events["deadline"].append((match.lastgroup, *match.span()))
    for match in MARKER_PATTERNS["uncertainty"].finditer(masked):
        events["uncertainty"].append((match.group().casefold(), *match.span()))
    # One negative-presence event per sentence, including coordinating né.
    # "non oltre" belongs to the deadline class rather than negation.
    negated = list(masked)
    for match in re.finditer(r"\bnon\s+oltre\b", masked, re.I):
        negated[match.start():match.end()] = " " * len(match.group())
    negated = "".join(negated)
    begin = 0
    for end in [match.end() for match in SENTENCE_END_PATTERN.finditer(masked)] + [len(masked)]:
        match = MARKER_PATTERNS["negation"].search(negated, begin, end)
        if match:
            events["negation"].append(("negative", *match.span()))
        begin = end
    for match in INFORMAL_PATTERN.finditer(masked):
        events["register"].append(("informal", *match.span()))
    for match in FORMAL_PATTERN.finditer(masked):
        events["register"].append(("formal", *match.span()))
    for record in _relative_period_records(text):
        events["relative_period"].append((record["value"], record["start"], record["end"]))
    return events


def _review_contexts(text: str, events: list[tuple[str, int, int]], changed: set[str]) -> list[str]:
    snippets = []
    for value, start, end in events:
        if value not in changed:
            continue
        left = max(0, start - max(0, (60 - (end - start)) // 2))
        snippet = text[left:min(len(text), left + 60)]
        if snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) == 2:
            break
    return snippets


def _review_flags(source: str, revision: str) -> list[dict]:
    before_events, after_events = _review_events(source), _review_events(revision)
    flags = []
    for category in before_events:
        before = Counter(event[0] for event in before_events[category])
        after = Counter(event[0] for event in after_events[category])
        if category == "register":
            # Omitted pronouns alone do not establish a switch of address.
            before, after = Counter(set(before)), Counter(set(after))
            if len(before) != 1 or len(after) != 1:
                continue
        if before == after:
            continue
        changed = {value for value in before.keys() | after.keys() if before[value] != after[value]}
        flags.append({"category": category, "source_markers": dict(before), "revision_markers": dict(after),
                      "message": "Indicatori linguistici cambiati: rileggere nel contesto; non è una prova di errore.",
                      "contexts": {"source": _review_contexts(source, before_events[category], changed),
                                   "revision": _review_contexts(revision, after_events[category], changed)}})
    return flags


class TextError(ValueError):
    """Input o operazione locale non validi."""


def _read_text(path: str | Path) -> str:
    """Legge soltanto un file regolare UTF-8, senza seguire symlink finali/FIFO."""
    path = Path(path).expanduser().absolute()
    try:
        if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
            raise TextError(f"File non regolare o collegamento simbolico: {path}")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise TextError(f"File non regolare: {path}")
            content = stream.read(MAX_INPUT_BYTES + 1)
        if len(content) > MAX_INPUT_BYTES:
            raise TextError("Input oltre il limite di 2 MiB.")
        return content.decode("utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise TextError(f"File UTF-8 non leggibile: {path}: {error}") from error


def _read_json(path: str | Path):
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as error:
        raise TextError(f"JSON non valido alla riga {error.lineno}.") from error


def _profile_name(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise TextError("Il nome del profilo deve usare minuscole, numeri e trattini, senza percorsi.")
    if len(name) > 64 or name in RESERVED_NAMES:
        raise TextError("Nome del profilo troppo lungo o riservato dal sistema operativo.")
    return name


def _short_text(value, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise TextError(f"{field}: serve un testo non vuoto di massimo {limit} caratteri.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise TextError(f"{field}: testo Unicode non codificabile in UTF-8.") from error
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise TextError(f"{field}: caratteri di controllo non ammessi.")
    return value.strip()


def validate_profile(data, name: str | None = None) -> dict:
    """Whitelist di caratteristiche stilistiche; non accetta campioni o biografie."""
    if not isinstance(data, dict) or set(data) - PROFILE_FIELDS:
        raise TextError("Profilo non valido: usare soltanto i campi stilistici documentati.")
    chosen = _profile_name(name if name is not None else data.get("name"))
    if "name" in data and data["name"] != chosen:
        raise TextError("Il nome nel JSON deve coincidere con il nome richiesto.")
    if data.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise TextError("Versione dello schema profilo non supportata.")
    result = {
        "schema_version": SCHEMA_VERSION, "name": chosen,
        "register": _short_text(data.get("register"), "register", 160),
        "conciseness": _short_text(data.get("conciseness"), "conciseness", 160),
    }
    for field in PROFILE_LIST_FIELDS:
        values = data.get(field, [])
        if not isinstance(values, list) or len(values) > 20:
            raise TextError(f"{field}: usare una lista di massimo 20 elementi.")
        result[field] = [_short_text(value, field, 240) for value in values]
    return result


def _profile_directory(directory: str | Path | None = None, create: bool = False) -> Path:
    if directory is None:
        target = Path.home().expanduser().resolve() / ".naturale" / "profiles"
    else:
        target = Path(directory).expanduser().absolute()
        # Risolve gli alias della base, non il deposito finale: un link a
        # profiles deve restare visibile ai controlli qui sotto.
        target = target.parent.resolve() / target.name
    current = Path(target.anchor)
    for part in target.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise TextError(f"Collegamento simbolico nella directory dei profili: {current}")
        if current.exists():
            if not current.is_dir():
                raise TextError(f"La directory dei profili contiene un file: {current}")
        elif create:
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                if current.is_symlink() or not current.is_dir():
                    raise TextError(f"Directory profili non sicura: {current}")
    return target


def create_profile(name: str, data, directory: str | Path | None = None) -> dict:
    """Salvataggio esplicito, privato e senza sovrascritture; restituisce il profilo."""
    name = _profile_name(name)
    profile = validate_profile(data, name)
    # Serializza prima di creare directory o file: un errore di codifica non
    # deve lasciare un profilo parziale che impedisca un tentativo successivo.
    content = (json.dumps(profile, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = _profile_directory(directory, create=True) / f"{name}.json"
    fd = None
    created = False
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        created = True
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise TextError(f"Il profilo esiste già e non viene sovrascritto: {name}") from error
    except (OSError, UnicodeError) as error:
        if created:
            target.unlink(missing_ok=True)
        raise TextError(f"Profilo non salvato: {error}") from error
    finally:
        if fd is not None:
            os.close(fd)
    return profile


def show_profile(name: str, directory: str | Path | None = None) -> dict:
    name = _profile_name(name)
    path = _profile_directory(directory) / f"{name}.json"
    return validate_profile(_read_json(path), name)


def list_profiles(directory: str | Path | None = None) -> list[dict]:
    target = _profile_directory(directory)
    if not target.exists():
        return []
    result = []
    for path in sorted(target.glob("*.json")):
        profile = show_profile(path.stem, target)
        result.append({key: profile[key] for key in ("name", "register", "conciseness")})
    return result


def delete_profile(name: str, directory: str | Path | None = None) -> dict:
    name = _profile_name(name)
    target = _profile_directory(directory) / f"{name}.json"
    try:
        if target.is_symlink() or not stat.S_ISREG(target.lstat().st_mode):
            raise TextError("Il profilo non è un file regolare: cancellazione rifiutata.")
        target.unlink()
    except OSError as error:
        raise TextError(f"Profilo non cancellato: {error}") from error
    return {"deleted": name}


def _urls(text: str) -> list[str]:
    result = []
    for match in URL_PATTERN.finditer(text):
        url = match.group().rstrip(".,;!")
        for closing, opening in ((")", "("), ("]", "["), ("}", "{")):
            while url.endswith(closing) and url.count(closing) > url.count(opening):
                url = url[:-1]
        result.append(url)
    return result


def _word_numbers(text: str, article_heads: set[str]) -> tuple[list[str], list[str]]:
    """Separa quantità certe e omografi incerti, senza interpretazione semantica."""
    numbers, ambiguous = [], []
    for match in NUMBER_WORD_PATTERN.finditer(text):
        word = match.group().casefold()
        if word not in {"uno", "sei", "mille"}:
            numbers.append(str(NUMBER_WORDS[word]))
            continue
        # Finestre limitate evitano scansioni ripetute dell'intero testo.
        left = text[max(0, match.start() - NUMBER_CONTEXT_CHARS):match.start()]
        right = text[match.end():match.end() + NUMBER_CONTEXT_CHARS]
        before, after = WORD_BEFORE.search(left), WORD_AFTER.match(right)
        previous = before[1].casefold() if before else ""
        following = after[1].casefold() if after else ""
        if word == "mille" and "grazie" in (previous, following):
            continue
        temporal = re.search(r"\b" + TIME_INTRODUCER + r"\s+$", left, re.I)
        partitive = (re.search(r"\bne\s+[^\W\d_]+\s+$", left, re.I)
                     or previous.endswith(("ane", "ine", "ene")))
        quantitative = (temporal or partitive or previous in COUNT_LABELS
                        or following in COUNT_WORDS or re.match(r"\s*[€$£%]", right))
        if word == "uno" and not quantitative:
            # La fonetica da sola non distingue articolo+nome e pronome+
            # aggettivo: risolvi l'articolo solo se l'altro testo conserva
            # la stessa testa nominale con un articolo/determinante.
            if re.match(r"(?:s[bcdfghjklmnpqrstvwxyz]|z|gn|ps|pn|x|y)", following):
                if following not in article_heads:
                    ambiguous.append("1")
                continue
        if word == "sei":
            quantitative = (quantitative or previous in {"in", "sono", "siamo", "erano", "eravamo", "saremo", "saranno"}
                            or re.match(r"\s+in\s+(?:tutto|totale)\b", right, re.I))
            if not quantitative:
                verbal_position = ((match.start() <= NUMBER_CONTEXT_CHARS and not left.strip())
                                   or re.search(r"[.!?;:,]\s*$", left)
                                   or previous in {"tu", "non", "se", "che", "quando", "come", "quanto", "dove", "perché", "perche"})
                if verbal_position and following in COPULAR_WORDS | COPULAR_LINKS:
                    continue
                if following in COPULAR_WORDS | COPULAR_LINKS or not following.endswith("i"):
                    ambiguous.append("6")
                    continue
        numbers.append(str(NUMBER_WORDS[word]))
    return numbers, ambiguous


def _article_heads(text: str) -> set[str]:
    return {match[1].casefold() for match in ARTICLE_HEAD_PATTERN.finditer(URL_PATTERN.sub(" ", text))}


def _ambiguous_numbers(text: str, article_heads: set[str]) -> list[str]:
    return _word_numbers(URL_PATTERN.sub(" ", text), article_heads)[1]


def _numbers(text: str, article_heads: set[str] | None = None) -> list[str]:
    # Il contenuto degli URL è controllato separatamente, non come numeri nel testo.
    masked = URL_PATTERN.sub(" ", text)
    times = []
    def take_time(match):
        times.append(f"{int(match[1]):02d}:{match[2]}")
        return " " * len(match.group())
    masked = TIME_PATTERN.sub(take_time, masked)
    numbers = []
    for match in NUMBER_PATTERN.finditer(masked):
        value = re.sub(r"\s+", "", match.group()).replace("−", "-")
        if "€" in value:
            amount = value.replace("€", "")
            # La posizione del simbolo è sempre una variazione di forma,
            # anche quando i separatori numerici restano letterali.
            value = f"€{amount}"
            integer, separator, fraction = amount.partition(",")
            # Solo la notazione italiana non ambigua: gruppi di migliaia,
            # virgola decimale. Non reinterpretare identificativi generici.
            if re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)", integer) and (
                    not separator or fraction.isdigit()):
                integer = integer.replace(".", "")
                sign = "-" if integer.startswith("-") else ""
                integer = integer.lstrip("+-").lstrip("0") or "0"
                fraction = fraction.rstrip("0").ljust(2, "0")
                value = f"€{sign}{integer},{fraction}"
        numbers.append(value)
    numbers.extend(_word_numbers(masked, article_heads or set())[0])
    return numbers + times


def _calendar(text: str) -> list[str]:
    text = URL_PATTERN.sub(" ", unicodedata.normalize("NFC", text))
    return [m.group().casefold().replace("ì", "i") for m in CALENDAR_PATTERN.finditer(text)]


def _quotes(text: str) -> list[str]:
    return [next(group for group in match.groups() if group is not None) for match in QUOTE_PATTERN.finditer(text)]


def _value_detail(kind: str, value: str) -> dict:
    if kind == "quoted_text" or len(value) > 256:
        return {"preview": value[:80], "characters": len(value),
                "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()}
    return {"value": value}


def validate_constraints(data) -> dict:
    if data is None:
        return {"preserve_exact": [], "forbid": []}
    if not isinstance(data, dict) or set(data) - {"preserve_exact", "forbid"}:
        raise TextError("Vincoli non validi: usare preserve_exact e/o forbid.")
    result = {}
    for field in ("preserve_exact", "forbid"):
        values = data.get(field, [])
        if not isinstance(values, list) or len(values) > 100:
            raise TextError(f"{field}: usare una lista di massimo 100 testi.")
        result[field] = [_short_text(value, field, 2000) for value in values]
        if len(set(result[field])) != len(result[field]):
            raise TextError(f"{field}: vincoli duplicati.")
    if set(result["preserve_exact"]) & set(result["forbid"]):
        raise TextError("Una stessa espressione non può essere richiesta e vietata.")
    return result


def _unified_diff(source: str, revision: str) -> str:
    lines = difflib.unified_diff(source.splitlines(keepends=True), revision.splitlines(keepends=True),
                                 fromfile="source", tofile="revision")
    return "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines)


def audit_text(source: str, revision: str, constraints=None, include_diff: bool = False,
               operation: str = "rewrite") -> dict:
    """Confronto meccanico + indicatori da rileggere, senza giudizi di verità."""
    if operation not in {"rewrite", "summarize"}:
        raise TextError("Operazione audit non supportata.")
    if not isinstance(source, str) or not isinstance(revision, str):
        raise TextError("Fonte e revisione devono essere testi.")
    if not source.strip():
        raise TextError("La fonte non può essere vuota.")
    if max(len(source.encode("utf-8")), len(revision.encode("utf-8"))) > MAX_INPUT_BYTES:
        raise TextError("Testo oltre il limite di 2 MiB.")
    constraints = validate_constraints(constraints)
    for value in constraints["preserve_exact"]:
        if value not in source:
            raise TextError("Un vincolo preserve_exact non compare nella fonte.")
    original_source, original_revision = source, revision
    source, revision, comparison_scope = _comparison_texts(source, revision)
    masked_source, masked_revision = _mask_identifiers(source), _mask_identifiers(revision)
    source_heads, revision_heads = _article_heads(masked_source), _article_heads(masked_revision)
    number_source = Counter(_numbers(masked_source, revision_heads))
    number_revision = Counter(_numbers(masked_revision, source_heads))
    # Uncertain homographs are not evidence alone; they can only account for
    # the same numeric value explicitly present in the other version.
    for value, count in Counter(_ambiguous_numbers(masked_source, revision_heads)).items():
        number_source[value] += min(count, max(0, number_revision[value] - number_source[value]))
    for value, count in Counter(_ambiguous_numbers(masked_revision, source_heads)).items():
        number_revision[value] += min(count, max(0, number_source[value] - number_revision[value]))
    identifiers_source, identifiers_revision = _identifier_records(source), _identifier_records(revision)
    comparisons = [("number", number_source, number_revision)]
    for kind in ("url", "identifier", "domain", "email"):
        comparisons.append((kind, Counter(record["value"] for record in identifiers_source if record["kind"] == kind),
                            Counter(record["value"] for record in identifiers_revision if record["kind"] == kind)))
    for kind, extractor in (("calendar", _calendar), ("relative_day", lambda text: [record["value"] for record in _relative_day_records(text)]),
                            ("quoted_text", _quotes)):
        before_text, after_text = (masked_source, masked_revision) if kind == "calendar" else (source, revision)
        comparisons.append((kind, Counter(extractor(before_text)), Counter(extractor(after_text))))
    findings = []
    for kind, before, after in comparisons:
        for value in sorted(before.keys() | after.keys()):
            if before[value] == after[value]:
                continue
            change = "added" if after[value] > before[value] else "missing"
            if operation == "summarize" and change == "missing":
                continue
            findings.append({"kind": kind, "change": change, **_value_detail(kind, value),
                             "source_count": before[value], "revision_count": after[value]})
    if not revision.strip():
        findings.append({"kind": "empty_revision", "change": "missing"})
    for value in constraints["preserve_exact"]:
        if value not in original_revision:
            findings.append({"kind": "required_text", "change": "missing", "value": value})
    for value in constraints["forbid"]:
        if value in original_revision:
            findings.append({"kind": "forbidden_text", "change": "added", "value": value})
    review_flags = _review_flags(source, revision)
    result = {
        "schema_version": SCHEMA_VERSION, "operation": operation,
        "unchanged": original_source == original_revision,
        "comparison_scope": comparison_scope,
        "deterministic_status": "issues_found" if findings else "passed",
        "review_status": "required" if findings or review_flags else "not_required",
        "semantic_equivalence": "not_verified", "human_review_required": True,
        "findings": findings, "review_flags": review_flags,
        "counts": {"source_characters": len(original_source), "revision_characters": len(original_revision)},
        "limitations": [
            "I controlli meccanici possono segnalare variazioni lecite di forma o ripetizione.",
            "Nomi, unità, responsabilità, causalità, fatti aggiunti e significato richiedono una verifica separata.",
            "L'assenza di segnalazioni non dimostra equivalenza semantica o verità del testo.",
        ],
    }
    if include_diff:
        result["diff"] = _unified_diff(original_source, original_revision)
    return result


def audit_files(source: str | Path, revision: str | Path, constraints: str | Path | None = None,
                include_diff: bool = False, operation: str = "rewrite") -> dict:
    return audit_text(_read_text(source), _read_text(revision),
                      _read_json(constraints) if constraints is not None else None, include_diff, operation)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    profiles = commands.add_parser("profiles", help="Profili stilistici espliciti, salvati localmente")
    actions = profiles.add_subparsers(dest="profile_action", required=True)
    for action in ("create", "show", "list", "delete"):
        command = actions.add_parser(action)
        if action != "list":
            command.add_argument("name")
        command.add_argument("--directory", help="Directory profili; default ~/.naturale/profiles")
        if action == "create":
            command.add_argument("--from-json", required=True)
    audit = commands.add_parser("audit", help="Controlli locali: non certifica il significato")
    inputs = audit.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--source")
    inputs.add_argument("--stdin-json", action="store_true", help="JSON UTF-8 da stdin, senza file temporanei")
    audit.add_argument("--revision")
    audit.add_argument("--constraints")
    audit.add_argument("--operation", choices=["rewrite", "summarize"], default="rewrite")
    audit.add_argument("--diff", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "audit":
        if args.stdin_json and (args.revision is not None or args.constraints is not None):
            parser.error("--stdin-json non accetta --revision o --constraints su file")
        if not args.stdin_json and args.revision is None:
            parser.error("--source richiede --revision")
    try:
        if args.command == "audit":
            if args.stdin_json:
                stream = getattr(sys.stdin, "buffer", sys.stdin)
                raw = stream.read(MAX_STDIN_BYTES + 1)
                if isinstance(raw, str):
                    raw = raw.encode("utf-8")
                if len(raw) > MAX_STDIN_BYTES:
                    raise TextError("JSON stdin oltre il limite di 16 MiB.")
                try:
                    data = json.loads(raw.decode("utf-8-sig"))
                except (ValueError, UnicodeError) as error:
                    raise TextError("JSON UTF-8 da stdin non valido.") from error
                if not isinstance(data, dict) or not {"source", "revision"} <= data.keys() or data.keys() - {"source", "revision", "constraints"}:
                    raise TextError("JSON stdin richiede source e revision, con constraints facoltativo.")
                result = audit_text(data["source"], data["revision"], data.get("constraints"), args.diff, args.operation)
            else:
                result = audit_files(args.source, args.revision, args.constraints, args.diff, args.operation)
            status = 1 if result["findings"] else 3 if result["review_flags"] else 0
        else:
            directory = args.directory
            if args.profile_action == "create":
                result = create_profile(args.name, _read_json(args.from_json), directory)
            elif args.profile_action == "show":
                result = show_profile(args.name, directory)
            elif args.profile_action == "list":
                result = {"profiles": list_profiles(directory)}
            else:
                result = delete_profile(args.name, directory)
            status = 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return status
    except (TextError, OSError, UnicodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
