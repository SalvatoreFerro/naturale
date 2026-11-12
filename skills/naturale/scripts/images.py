#!/usr/bin/env python3
"""Ispezione e pulizia mirata locale JPEG/PNG. Nessun detector AI o upload."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import warnings

_runtime_spec = importlib.util.spec_from_file_location(
    "naturale_image_runtime", Path(__file__).resolve().with_name("exiftool_runtime.py"))
_exiftool_runtime = importlib.util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(_exiftool_runtime)

SCHEMA_VERSION = "1.0"
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_PIXELS = 40_000_000
TIMEOUT_SECONDS = 60
SUFFIXES = {"JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}}
PROFILES = {"provenance", "privacy"}
MAX_BATCH_FILES = 1000
EXIF_PRIVATE_IDS = {0xA430, 0xA431, 0xA435, 0xC62F}
PRIVATE_NAMES = {"OwnerName", "SerialNumber", "LensSerialNumber", "CameraSerialNumber"}
EXIF_GROUPS = {"IFD0", "IFD1", "ExifIFD", "InteropIFD"}
PRIVACY_REMOVE_ARGS = (
    "-GPS:all=", "-EXIF:OwnerName=", "-EXIF:SerialNumber=",
    "-EXIF:LensSerialNumber=", "-EXIF:CameraSerialNumber=",
    "-XMP:GPS*=", "-XMP:OwnerName=", "-XMP:SerialNumber=",
    "-XMP:LensSerialNumber=", "-XMP:CameraSerialNumber=",
)


class ImageError(Exception):
    """Errore operativo leggibile, senza interpretazioni sull'origine AI."""

    def __init__(self, message, code="operation_failed"):
        super().__init__(message)
        self.code = code


def _require_exiftool():
    report = _exiftool_runtime.exiftool_report()
    if report["problem"] == "exiftool_too_old":
        raise ImageError(f"ExifTool troppo vecchio: serve almeno {report['minimum_version']}.",
                         code="exiftool_too_old")
    if not report["available"]:
        raise ImageError("ExifTool non trovato o non verificabile nel PATH.")


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _exiftool(*args: str, cwd: str | Path | None = None, stdin=None) -> str:
    executable = shutil.which("exiftool")
    if not executable:
        raise ImageError("ExifTool non trovato nel PATH. Installarlo prima di elaborare immagini.")
    try:
        # Un file .ExifTool_config dell'utente può contenere codice Perl: non caricarlo.
        result = subprocess.run(
            [executable, "-config", "", *args], capture_output=True,
            encoding="utf-8", errors="replace", timeout=TIMEOUT_SECONDS,
            check=False, shell=False, cwd=cwd, stdin=stdin,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ImageError(f"ExifTool non eseguibile o scaduto: {exc}") from exc
    if result.returncode != 0:
        raise ImageError(f"ExifTool: {result.stderr.strip() or result.stdout.strip() or 'errore'}")
    return result.stdout


def _metadata(path: Path) -> dict:
    try:
        # Python apre il nome Unicode; ExifTool legge il descriptor già aperto.
        # Anche i surrogate-pair Windows non vengono interpretati da Perl/argv.
        with path.open("rb") as source:
            data = json.loads(_exiftool("-json", "-G1", "-s", "-n", "-struct", "-", stdin=source))
    except (ValueError, TypeError) as exc:
        raise ImageError("Rapporto ExifTool non leggibile.") from exc
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise ImageError("Rapporto ExifTool inatteso.")
    metadata = data[0]
    for key, value in metadata.items():
        if key.split(":")[-1] == "Error":
            raise ImageError(f"ExifTool non riesce a leggere il file: {value}")
    # Date/permessi di filesystem del temporaneo non descrivono l'output finale.
    metadata["SourceFile"] = str(path)
    return {key: value for key, value in metadata.items() if not key.startswith("System:")}


def _target_group(key: str) -> str | None:
    group = key.split(":", 1)[0].lower()
    if group == "xmp" or group.startswith("xmp-"):
        return "XMP"
    if group in {"jumbf", "c2pa"} or group.startswith("c2pa-"):
        return "JUMBF"
    return None


def _groups(metadata: dict) -> set[str]:
    return {group for key in metadata if (group := _target_group(key))}


def _privacy_targets(metadata: dict) -> set[str]:
    targets = set()
    for key in metadata:
        group, _, name = key.partition(":")
        if group == "GPS" or (group in EXIF_GROUPS and name in PRIVATE_NAMES):
            targets.add(key)
        elif group.startswith("XMP-") and (name.startswith("GPS") or name in PRIVATE_NAMES):
            targets.add(key)
    return targets


def _exif_snapshot(image) -> dict:
    """Confronta valori EXIF, non gli offset che cambiano eliminando un IFD."""
    exif = image.getexif()
    pointers = {34665, 34853, 40965}
    result = {"ifd0": {key: value for key, value in exif.items() if key not in pointers}}
    for name, tag in (("exif", 34665), ("gps", 34853), ("interop", 40965)):
        try:
            values = exif.get_ifd(tag)
        except KeyError:  # Pillow raises for an absent Interop pointer.
            values = {}
        result[name] = {key: value for key, value in values.items() if key not in pointers}
    return result


def _exif_without_private(snapshot: dict) -> dict:
    return {
        name: {} if name == "gps" else {
            key: value for key, value in values.items() if key not in EXIF_PRIVATE_IDS
        }
        for name, values in snapshot.items()
    }


def _jumbf_digest(path: Path, required: bool = False) -> str:
    """Hash dei byte estratti del contenitore, senza decodificarli come testo."""
    executable = shutil.which("exiftool")
    if not executable:
        raise ImageError("ExifTool non trovato nel PATH.")
    try:
        with path.open("rb") as source:
            result = subprocess.run(
                [executable, "-config", "", "-b", "-JUMBF", "-"],
                stdin=source, capture_output=True, timeout=TIMEOUT_SECONDS, check=False, shell=False,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ImageError("Estrazione locale JUMBF non completata.") from exc
    if result.returncode or (required and not result.stdout):
        raise ImageError("Contenitore JUMBF non verificabile.")
    return hashlib.sha256(result.stdout).hexdigest()


def _snapshot(path: Path) -> dict:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise ImageError("Pillow non installato. Installare le dipendenze del modulo immagini.") from exc
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ImageError("File oltre il limite di 100 MiB.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as im:
                fmt = im.format
                if fmt not in SUFFIXES:
                    raise ImageError("Formato non supportato: usare JPEG o PNG statici.")
                if path.suffix.lower() not in SUFFIXES[fmt]:
                    raise ImageError("Estensione e formato reale non corrispondono.")
                if im.width * im.height > MAX_PIXELS:
                    raise ImageError("Immagine oltre il limite di 40 milioni di pixel.")
                if getattr(im, "n_frames", 1) != 1 or "mp" in im.info:
                    raise ImageError("Immagini animate o multiple non supportate.")
                im.verify()
            with Image.open(path) as im:
                im.load()
                return {
                    "path": str(path), "sha256": _sha256(path), "format": fmt,
                    "width": im.width, "height": im.height,
                    "_pixels": hashlib.sha256(im.tobytes()).hexdigest(),
                    "_mode": im.mode, "_icc": im.info.get("icc_profile"),
                    "_exif": _exif_snapshot(im),
                    "_transparency": im.info.get("transparency"),
                    "_palette": (im.palette.mode, im.palette.tobytes()) if im.palette else None,
                    "_color": tuple(im.info.get(k) for k in ("gamma", "chromaticity", "srgb")),
                }
    except ImageError:
        raise
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageError(f"Immagine non leggibile o non sicura da decodificare: {exc}") from exc


def _public(snapshot: dict) -> dict:
    return {key: value for key, value in snapshot.items() if not key.startswith("_")}


def _input_path(path: str | Path) -> Path:
    result = Path(path).expanduser().resolve()
    if not result.is_file():
        raise ImageError(f"File di input non trovato: {result}")
    return result


def _c2pa(path: Path, metadata: dict, validate: bool, notices: list[str]) -> dict:
    parsing_warning = any(key.split(":")[-1] == "Warning" for key in metadata)
    embedded = "present" if "JUMBF" in _groups(metadata) else (
        "unreadable" if parsing_warning else "not_found"
    )
    result = {"embedded": embedded, "validation": "not_checked", "remote_manifest": "not_fetched"}
    if not validate:
        return result
    try:
        sdk = importlib.import_module("c2pa")
    except ImportError:
        result["validation"] = "unavailable"
        notices.append("SDK C2PA non disponibile: validazione crittografica non eseguita.")
        return result
    # Le impostazioni sono per questo contesto: non modificano default globali.
    # Una versione SDK senza Context/Settings viene rifiutata prima di leggere il file.
    if not hasattr(sdk, "Context") or not hasattr(sdk, "Settings"):
        result["validation"] = "unavailable"
        notices.append("SDK C2PA incompatibile con la validazione offline: operazione saltata.")
        return result
    try:
        settings = sdk.Settings()
        settings.update({"verify": {"remote_manifest_fetch": False, "ocsp_fetch": False}})
        context = sdk.Context(settings=settings)
        with sdk.Reader(str(path), context=context) as reader:
            data = json.loads(reader.json())
        # Il SDK combina firma, hash, validità e ingredienti nel suo stato.
        # L'assenza di errori in una lista vuota NON è una prova di validità.
        state = data.get("validation_state")
        active = data.get("active_manifest")
        has_manifest = bool(active and active in data.get("manifests", {}))
        if state in {"Valid", "Trusted"} and has_manifest:
            result["validation"] = "valid"
        elif state == "Invalid" and has_manifest:
            result["validation"] = "invalid"
        else:
            result["validation"] = "not_checked"
            notices.append("Il SDK non ha restituito uno stato C2PA conclusivo con manifest attivo.")
        result["signer_trust"] = "not_established"
        result["validation_state"] = state
        result["validation_details"] = data.get("validation_results", data.get("validation_status", []))
    except Exception as exc:
        # Anche con manifest assente non dichiarare la firma valida.
        result["validation"] = "not_checked"
        notices.append(f"Validazione C2PA offline non completata: {type(exc).__name__}: {exc}")
    return result


def _report(operation: str, before: dict, metadata: dict, validate: bool, path: Path) -> dict:
    notices = [
        "La pulizia riguarda solo XMP e JUMBF/C2PA incorporati. EXIF, IPTC, commenti e altri dati possono restare.",
        "Assenza di metadati non equivale ad assenza di watermark invisibili o origine AI.",
    ]
    notices.extend(str(v) for k, v in metadata.items() if k.split(":")[-1] == "Warning")
    return {
        "schema_version": SCHEMA_VERSION, "operation": operation,
        "input": _public(before), "output": None,
        "metadata": {"before": metadata, "after": None, "removed_groups": []},
        "c2pa": {"before": _c2pa(path, metadata, validate, notices), "after": None},
        "pixel_data_unchanged": None,
        "invisible_watermark": "not_checked", "instagram_label": "unknown",
        "warnings": notices,
    }


def inspect_image(path: str | Path, validate_c2pa: bool = False) -> dict:
    """Rapporto locale: non scrive file né prova a identificare l'origine dai pixel."""
    _require_exiftool()
    source = _input_path(path)
    before = _snapshot(source)
    metadata = _metadata(source)
    report = _report("inspect", before, metadata, validate_c2pa, source)
    if _sha256(source) != before["sha256"]:
        raise ImageError("L'input è cambiato durante l'ispezione. Riprovare con un file stabile.")
    return report


def _publish_exclusive(temp: Path, destination: Path) -> None:
    """Riserva esclusivamente il nome: non sovrascrive nemmeno in una race."""
    created = False
    try:
        with temp.open("rb") as source:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created = True
            with os.fdopen(fd, "wb") as out:
                shutil.copyfileobj(source, out)
                out.flush()
                os.fsync(out.fileno())
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def clean_image(input_path: str | Path, output_path: str | Path,
                validate_c2pa: bool = False, profile: str = "provenance") -> dict:
    """Applica un profilo su copia, verifica e pubblica immagine e rapporto locale."""
    if profile not in PROFILES:
        raise ImageError("Profilo non supportato: usare provenance o privacy.")
    _require_exiftool()
    source = _input_path(input_path)
    destination = Path(output_path).expanduser().absolute()
    # Canonicalizza alias del parent (/var su macOS, nomi corti su Windows),
    # senza seguire un eventuale symlink finale che va rifiutato da lexists.
    destination = destination.parent.resolve() / destination.name
    # lexists intercetta anche link simbolici pendenti.
    sidecar = Path(str(destination) + ".report.json")
    if destination.resolve() == source or os.path.lexists(destination) or os.path.lexists(sidecar):
        raise ImageError("L'output o il rapporto esistono già, oppure coincidono con l'originale.")
    if not destination.parent.is_dir():
        raise ImageError("La directory di destinazione non esiste.")
    before = _snapshot(source)
    if destination.suffix.lower() not in SUFFIXES[before["format"]]:
        raise ImageError("L'output deve mantenere il formato e un'estensione coerente con l'input.")
    metadata_before = _metadata(source)
    report = _report("clean", before, metadata_before, validate_c2pa, source)
    report["profile"] = profile
    report["metadata"]["removed_tags"] = []
    if profile == "privacy":
        report["warnings"] = [
            "Il profilo privacy rimuove soltanto GPS EXIF/XMP e i tag OwnerName, SerialNumber, LensSerialNumber, CameraSerialNumber EXIF/XMP.",
            "Altri campi XMP/IPTC, descrizioni, pixel, credenziali e riferimenti possono ancora contenere dati personali: non è anonimizzazione.",
            "Le credenziali C2PA vengono conservate byte per byte, ma modificare i metadati può invalidarne la firma o il legame con il file.",
            "Assenza di metadati non equivale ad assenza di watermark invisibili o origine AI.",
        ] + report["warnings"][2:]
        if "JUMBF" in _groups(metadata_before):
            report["warnings"].append("Le credenziali conservate possono contenere copie o asserzioni di dati personali e riferimenti.")
    has_jumbf = "JUMBF" in _groups(metadata_before)
    jumbf_before = _jumbf_digest(source, required=has_jumbf) if profile == "privacy" else None
    with tempfile.TemporaryDirectory(prefix=".naturale-", dir=destination.parent) as tempdir:
        temp = Path(tempdir) / ("image" + destination.suffix.lower())
        shutil.copyfile(source, temp)
        remove_args = ("-XMP:all=", "-JUMBF:all=") if profile == "provenance" else PRIVACY_REMOVE_ARGS
        if profile == "privacy":
            # Togliendo gli ultimi tag privati ExifTool può eliminare anche
            # IFD0/ExifIFD rimasti con soli campi tecnici. Ricopia soltanto i
            # valori già presenti: mai creare default o reintrodurre dati privati.
            technical = {36864: "ExifVersion", 37121: "ComponentsConfiguration", 40960: "FlashpixVersion", 40961: "ColorSpace"}
            retain = [f"-EXIF:{name}" for key, name in technical.items() if key in before["_exif"]["exif"]]
            ifd0_technical = {282: "XResolution", 283: "YResolution", 296: "ResolutionUnit", 531: "YCbCrPositioning"}
            retain.extend(f"-IFD0:{name}" for key, name in ifd0_technical.items() if key in before["_exif"]["ifd0"])
            if retain:
                original = Path(tempdir) / ("original" + destination.suffix.lower())
                shutil.copyfile(source, original)
                remove_args = (*remove_args, "-TagsFromFile", original.name, *retain)
        # Tutti i nomi passati a ExifTool sono relativi e ASCII. Il cwd Unicode
        # è impostato da Python tramite le API native del sistema operativo.
        _exiftool("-overwrite_original", *remove_args, temp.name, cwd=Path(tempdir))
        after = _snapshot(temp)
        metadata_after = _metadata(temp)
        leftovers = _groups(metadata_after) if profile == "provenance" else _privacy_targets(metadata_after)
        if leftovers:
            raise ImageError(f"Pulizia incompleta: gruppi ancora presenti: {', '.join(sorted(leftovers))}.")
        unreadable_warnings = [str(value) for key, value in metadata_after.items() if key.split(":")[-1] == "Warning"]
        if any(profile != "privacy" or not any(term in message.lower() for term in ("c2pa", "jumbf")) for message in unreadable_warnings):
            raise ImageError("ExifTool segnala dati non leggibili nell'output: pulizia non verificabile.")
        invariants = ("format", "width", "height", "_pixels", "_mode", "_icc",
                      "_transparency", "_palette", "_color")
        if any(before[key] != after[key] for key in invariants):
            raise ImageError("La verifica ha rilevato variazioni dei pixel, EXIF o della resa: output non pubblicato.")
        expected_exif = before["_exif"] if profile == "provenance" else _exif_without_private(before["_exif"])
        if after["_exif"] != expected_exif:
            raise ImageError("La verifica ha rilevato modifiche EXIF diverse dalle rimozioni consentite: output non pubblicato.")
        if profile == "privacy" and _jumbf_digest(temp, required=has_jumbf) != jumbf_before:
            raise ImageError("Il contenitore JUMBF/C2PA è cambiato: output non pubblicato.")
        if _sha256(source) != before["sha256"]:
            raise ImageError("L'originale è cambiato durante l'elaborazione: output non pubblicato.")
        report["output"] = {**_public(after), "path": str(destination)}
        metadata_after["SourceFile"] = str(destination)
        report["metadata"]["after"] = metadata_after
        if profile == "provenance":
            report["metadata"]["removed_groups"] = sorted(_groups(metadata_before))
        else:
            report["metadata"]["removed_groups"] = ["GPS"] if any(key.startswith("GPS:") for key in metadata_before) else []
            report["metadata"]["removed_tags"] = sorted(_privacy_targets(metadata_before))
            report["c2pa_container_unchanged"] = True if "JUMBF" in _groups(metadata_before) else None
        report["pixel_data_unchanged"] = True
        report["c2pa"]["after"] = _c2pa(temp, metadata_after, validate_c2pa, report["warnings"])
        temp_report = Path(tempdir) / "report.json"
        temp_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        image_published = False
        try:
            _publish_exclusive(temp, destination)
            image_published = True
            _publish_exclusive(temp_report, sidecar)
        except Exception:
            if image_published:
                destination.unlink(missing_ok=True)
            raise
    return report


def summarize_report(report: dict) -> dict:
    """Vista per l'agente: niente metadati grezzi, hash o percorsi assoluti."""
    def file_summary(record):
        if record is None:
            return None
        return {"name": Path(record["path"]).name, **{
            key: record[key] for key in ("format", "width", "height")
        }}

    def c2pa_summary(record):
        if record is None:
            return None
        return {key: record[key] for key in ("embedded", "validation", "remote_manifest")}

    groups = sorted({key.split(":", 1)[0] for key in report["metadata"]["before"] if ":" in key})
    result = {
        "schema_version": SCHEMA_VERSION, "detail": "summary", "operation": report["operation"],
        "input": file_summary(report["input"]), "output": file_summary(report["output"]),
        "metadata": {"groups_before": groups, "removed_groups": report["metadata"]["removed_groups"],
                     "removed_tag_count": len(report["metadata"].get("removed_tags", []))},
        "c2pa": {stage: c2pa_summary(record) for stage, record in report["c2pa"].items()},
        "pixel_data_unchanged": report["pixel_data_unchanged"],
        "invisible_watermark": "not_checked", "instagram_label": "unknown",
        "warnings": ["invisible_watermark_not_checked", "instagram_label_unknown"],
        "local_warning_count": len(report["warnings"]),
    }
    if "profile" in report:
        result["profile"] = report["profile"]
    if report.get("profile") == "privacy":
        result["warnings"].append("targeted_privacy_cleanup_not_anonymization")
        if report["c2pa"]["before"]["embedded"] == "present":
            result["warnings"].extend([
                "retained_credentials_may_contain_personal_data", "c2pa_may_be_invalidated",
            ])
        result["c2pa_container_unchanged"] = report.get("c2pa_container_unchanged")
    if report["output"]:
        result["report_file"] = Path(report["output"]["path"]).name + ".report.json"
        result["warnings"].append("local_report_contains_original_metadata")
    return result


def _save_report(report: dict, destination: str | Path) -> Path:
    path = Path(destination).expanduser().absolute()
    path = path.parent.resolve() / path.name
    if not path.parent.is_dir() or os.path.lexists(path):
        raise ImageError("La directory del rapporto manca o il rapporto esiste già.")
    with tempfile.TemporaryDirectory(prefix=".naturale-report-", dir=path.parent) as directory:
        temporary = Path(directory) / "report.json"
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _publish_exclusive(temporary, path)
    return path


def _safe_error(error: Exception) -> dict:
    """Non copiare messaggi parser/filepath o metadati nello stdout dell'agente."""
    if getattr(error, "code", None) == "exiftool_too_old":
        minimum = ".".join(map(str, _exiftool_runtime.MIN_EXIFTOOL_VERSION))
        return {"code": "exiftool_too_old", "message": f"ExifTool non supportato: serve almeno {minimum}."}
    detail = str(error).lower()
    if "exiftool non trovato" in detail:
        return {"code": "exiftool_missing", "message": "ExifTool non disponibile nel PATH."}
    if "pillow non installato" in detail:
        return {"code": "pillow_missing", "message": "Pillow non disponibile nell'interprete Python."}
    return {"code": "operation_failed", "message": "Operazione non completata; controllare file, formato, dipendenze e collisioni. Nessun dettaglio privato mostrato."}


def batch_images(input_directory: str | Path, output_directory: str | Path,
                 profile: str = "provenance", dry_run: bool = False,
                 validate_c2pa: bool = False, full_report: bool = False) -> dict:
    """Elabora file indipendenti, senza ricorsione, mantenendo i rapporti su disco."""
    if profile not in PROFILES:
        raise ImageError("Profilo non supportato.")
    _require_exiftool()
    raw_source = Path(input_directory).expanduser().absolute()
    if raw_source.is_symlink() or not raw_source.is_dir():
        raise ImageError("La directory di input manca o è un collegamento simbolico.")
    source = raw_source.resolve()
    raw_destination = Path(output_directory).expanduser().absolute()
    if raw_destination.is_symlink():
        raise ImageError("La directory di output non può essere un collegamento simbolico.")
    destination = raw_destination.parent.resolve() / raw_destination.name
    if source == destination.resolve():
        raise ImageError("Scegliere una directory di output distinta da quella di input.")
    if destination.exists() and not destination.is_dir():
        raise ImageError("La destinazione non è una directory.")
    if not destination.parent.is_dir():
        raise ImageError("La directory padre dell'output non esiste.")
    entries = sorted(source.iterdir(), key=lambda path: (path.name.casefold(), path.name))
    candidates = [path for path in entries if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
                  and (path.is_symlink() or path.is_file())]
    if len(candidates) > MAX_BATCH_FILES:
        raise ImageError("Batch oltre il limite di 1000 immagini: dividere la cartella.")
    if not dry_run:
        try:
            destination.mkdir(mode=0o700)
        except FileExistsError:
            if destination.is_symlink() or not destination.is_dir():
                raise ImageError("Directory di output non sicura.")
    results = []
    for path in candidates:
        suffix = "-clean" if profile == "provenance" else "-privacy"
        output = destination / (path.stem + suffix + path.suffix)
        result = {"input_name": path.name, "output_name": output.name}
        try:
            if path.is_symlink():
                raise ImageError("I collegamenti simbolici non sono accettati nel batch.")
            if os.path.lexists(output) or os.path.lexists(Path(str(output) + ".report.json")):
                raise ImageError("L'output o il rapporto esistono già.")
            if dry_run:
                report = inspect_image(path, validate_c2pa)
                metadata = report["metadata"]["before"]
                groups = sorted(_groups(metadata)) if profile == "provenance" else (
                    ["GPS"] if any(key.startswith("GPS:") for key in metadata) else []
                )
                target_count = sum(_target_group(key) is not None for key in metadata) if profile == "provenance" else len(_privacy_targets(metadata))
                result.update({
                    "status": "planned", "report": report if full_report else summarize_report(report),
                    "plan": {"profile": profile, "groups_to_remove": groups,
                             "targeted_tag_count": target_count,
                             "retains_c2pa_container": profile == "privacy"},
                })
            else:
                report = clean_image(path, output, validate_c2pa, profile)
                result.update({"status": "success", "report": report if full_report else summarize_report(report)})
        except (ImageError, OSError, ValueError) as error:
            result.update({"status": "failed", "error": _safe_error(error)})
            if full_report:
                result["error_detail"] = str(error)
        results.append(result)
    return {
        "schema_version": SCHEMA_VERSION, "operation": "batch", "detail": "full" if full_report else "summary",
        "profile": profile, "dry_run": dry_run,
        "input_directory": source.name, "output_directory": destination.name,
        "total": len(candidates), "success": sum(r["status"] == "success" for r in results),
        "planned": sum(r["status"] == "planned" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "ignored": len(entries) - len(candidates), "results": results,
        "invisible_watermark": "not_checked", "instagram_label": "unknown",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="operation", required=True)
    for name in ("inspect", "clean"):
        sub = subcommands.add_parser(name)
        sub.add_argument("input", help="JPEG o PNG statico locale")
        sub.add_argument("--validate-c2pa", action="store_true", help="Validazione SDK facoltativa, offline")
        sub.add_argument("--full-report", action="store_true", help="Mostra metadati completi e percorsi: può esporre dati personali")
        if name == "clean":
            sub.add_argument("--output", required=True, help="Nuovo file: mai sovrascritto")
            sub.add_argument("--profile", choices=sorted(PROFILES), default="provenance")
        else:
            sub.add_argument("--report", help="Salva un rapporto completo locale, senza sovrascrivere")
    batch = subcommands.add_parser("batch")
    batch.add_argument("input", help="Cartella locale; solo file JPEG/PNG al primo livello")
    batch.add_argument("--output-dir", required=True)
    batch.add_argument("--profile", choices=sorted(PROFILES), default="provenance")
    batch.add_argument("--dry-run", action="store_true")
    batch.add_argument("--validate-c2pa", action="store_true")
    batch.add_argument("--full-report", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.operation == "batch":
            report = batch_images(args.input, args.output_dir, args.profile, args.dry_run,
                                  args.validate_c2pa, args.full_report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1 if report["failed"] else 0
        report = (inspect_image(args.input, args.validate_c2pa) if args.operation == "inspect"
                  else clean_image(args.input, args.output, args.validate_c2pa, args.profile))
        saved_report = _save_report(report, args.report) if args.operation == "inspect" and args.report else None
        shown = report if args.full_report else summarize_report(report)
        if saved_report is not None and not args.full_report:
            shown["report_file"] = saved_report.name
        print(json.dumps(shown, ensure_ascii=False, indent=2))
        return 0
    except (ImageError, OSError, ValueError) as exc:
        error = str(exc) if args.full_report else _safe_error(exc)
        print(json.dumps({"schema_version": SCHEMA_VERSION, "error": error}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
