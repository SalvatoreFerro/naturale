#!/usr/bin/env python3
"""Ispezione e pulizia mirata locale JPEG/PNG. Nessun detector AI o upload."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import warnings

SCHEMA_VERSION = "1.0"
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_PIXELS = 40_000_000
TIMEOUT_SECONDS = 60
SUFFIXES = {"JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}}


class ImageError(Exception):
    """Errore operativo leggibile, senza interpretazioni sull'origine AI."""


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _exiftool(*args: str) -> str:
    executable = shutil.which("exiftool")
    if not executable:
        raise ImageError("ExifTool non trovato nel PATH. Installarlo prima di elaborare immagini.")
    try:
        # Un file .ExifTool_config dell'utente può contenere codice Perl: non caricarlo.
        result = subprocess.run(
            [executable, "-config", "", *args], capture_output=True,
            encoding="utf-8", errors="replace", timeout=TIMEOUT_SECONDS,
            check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ImageError(f"ExifTool non eseguibile o scaduto: {exc}") from exc
    if result.returncode != 0:
        raise ImageError(f"ExifTool: {result.stderr.strip() or result.stdout.strip() or 'errore'}")
    return result.stdout


def _metadata(path: Path) -> dict:
    try:
        data = json.loads(_exiftool("-json", "-G1", "-s", "-n", "-struct", str(path)))
    except (ValueError, TypeError) as exc:
        raise ImageError("Rapporto ExifTool non leggibile.") from exc
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise ImageError("Rapporto ExifTool inatteso.")
    metadata = data[0]
    for key, value in metadata.items():
        if key.split(":")[-1] == "Error":
            raise ImageError(f"ExifTool non riesce a leggere il file: {value}")
    # Date/permessi di filesystem del temporaneo non descrivono l'output finale.
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
                    "_exif": dict(im.getexif()),
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
                validate_c2pa: bool = False) -> dict:
    """Rimuove XMP/JUMBF su copia, verifica e pubblica immagine e rapporto."""
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
    with tempfile.TemporaryDirectory(prefix=".naturale-", dir=destination.parent) as tempdir:
        temp = Path(tempdir) / ("image" + destination.suffix.lower())
        shutil.copyfile(source, temp)
        _exiftool("-overwrite_original", "-XMP:all=", "-JUMBF:all=", str(temp))
        after = _snapshot(temp)
        metadata_after = _metadata(temp)
        leftovers = _groups(metadata_after)
        if leftovers:
            raise ImageError(f"Pulizia incompleta: gruppi ancora presenti: {', '.join(sorted(leftovers))}.")
        if any(key.split(":")[-1] == "Warning" for key in metadata_after):
            raise ImageError("ExifTool segnala dati non leggibili nell'output: pulizia non verificabile.")
        invariants = ("format", "width", "height", "_pixels", "_mode", "_icc", "_exif",
                      "_transparency", "_palette", "_color")
        if any(before[key] != after[key] for key in invariants):
            raise ImageError("La verifica ha rilevato variazioni dei pixel, EXIF o della resa: output non pubblicato.")
        if _sha256(source) != before["sha256"]:
            raise ImageError("L'originale è cambiato durante l'elaborazione: output non pubblicato.")
        report["output"] = {**_public(after), "path": str(destination)}
        metadata_after["SourceFile"] = str(destination)
        report["metadata"]["after"] = metadata_after
        report["metadata"]["removed_groups"] = sorted(_groups(metadata_before))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="operation", required=True)
    for name in ("inspect", "clean"):
        sub = subcommands.add_parser(name)
        sub.add_argument("input", help="JPEG o PNG statico locale")
        sub.add_argument("--validate-c2pa", action="store_true", help="Validazione SDK facoltativa, offline")
        if name == "clean":
            sub.add_argument("--output", required=True, help="Nuovo file: mai sovrascritto")
    args = parser.parse_args(argv)
    try:
        report = (inspect_image(args.input, args.validate_c2pa) if args.operation == "inspect"
                  else clean_image(args.input, args.output, args.validate_c2pa))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (ImageError, OSError, ValueError) as exc:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
