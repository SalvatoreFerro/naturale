#!/usr/bin/env python3
"""Installa la skill locale, senza rete, dipendenze aggiuntive o sovrascritture."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import uuid
from urllib.parse import unquote, urlsplit


HOSTS = {"claude": ".claude", "codex": ".agents"}
IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store"}
MAX_SOURCE_BYTES = 20 * 1024 * 1024
REQUIRED = {"SKILL.md", "LICENSE", "INSTALL.md", "requirements.txt", "scripts/images.py"}
RECEIPT = ".naturale-install.json"
RECEIPT_SCHEMA = "1.0"


class InstallError(Exception):
    """Installazione rifiutata senza modificare file preesistenti."""


def _ignored(path: Path) -> bool:
    return path.as_posix() == RECEIPT or any(part in IGNORED for part in path.parts) or path.suffix in {".pyc", ".pyo"}


def _manifest(directory: Path) -> dict[str, bytes]:
    if directory.is_symlink() or not directory.is_dir():
        raise InstallError(f"Directory assente, non valida o collegamento simbolico: {directory}")
    files = {}
    total = 0
    for base, directories, filenames in os.walk(directory, followlinks=False):
        parent = Path(base)
        directories[:] = [name for name in directories if not _ignored((parent / name).relative_to(directory))]
        for name in directories:
            if (parent / name).is_symlink():
                raise InstallError(f"Collegamento simbolico non accettato: {parent / name}")
        for name in filenames:
            path = parent / name
            relative = path.relative_to(directory)
            if _ignored(relative):
                continue
            # Rifiuta anche FIFO/device: aprirli prima del controllo potrebbe bloccare.
            if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
                raise InstallError(f"File non regolare o collegamento simbolico: {path}")
            # O_NONBLOCK copre una sostituzione concorrente con una FIFO;
            # O_NOFOLLOW impedisce di seguire un symlink finale.
            try:
                fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
                with os.fdopen(fd, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode) or path.is_symlink():
                        raise InstallError(f"File non regolare o collegamento simbolico: {path}")
                    content = stream.read(MAX_SOURCE_BYTES + 1)
            except OSError as error:
                raise InstallError(f"File non leggibile: {path}: {error}") from error
            total += len(content)
            if total > MAX_SOURCE_BYTES:
                raise InstallError("Pacchetto oltre il limite di 20 MiB.")
            files[relative.as_posix()] = content
    return files


def _validate_source(directory: Path) -> dict[str, bytes]:
    files = _manifest(directory)
    missing = REQUIRED - files.keys()
    if missing:
        raise InstallError(f"Pacchetto incompleto: mancano {', '.join(sorted(missing))}.")
    try:
        skill = files["SKILL.md"].decode("utf-8")
    except UnicodeError as error:
        raise InstallError("SKILL.md non è UTF-8.") from error
    frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", skill, re.S)
    if not frontmatter or not re.search(r"(?m)^name:\s*['\"]?naturale['\"]?\s*$", frontmatter.group(1)):
        raise InstallError("SKILL.md deve dichiarare name: naturale nel frontmatter.")
    if not re.search(r"(?m)^description:\s*\S", frontmatter.group(1)):
        raise InstallError("SKILL.md deve avere una descrizione.")
    for relative, content in files.items():
        if not relative.endswith(".md"):
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeError as error:
            raise InstallError(f"Documento non UTF-8: {relative}") from error
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = target.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            reference = (directory / relative).parent / unquote(parsed.path)
            try:
                key = reference.resolve().relative_to(directory.resolve()).as_posix()
            except ValueError as error:
                raise InstallError(f"Riferimento fuori dal pacchetto in {relative}: {target}") from error
            if key not in files:
                raise InstallError(f"Riferimento mancante in {relative}: {target}")
    return files


def _check_ancestors(home: Path, destination: Path) -> None:
    current = home
    if not current.is_dir():
        raise InstallError(f"Directory utente non esistente: {home}")
    for part in destination.relative_to(home).parts:
        current = current / part
        if current.is_symlink():
            raise InstallError(f"Collegamento simbolico nella destinazione: {current}")
        if current.exists() and not current.is_dir():
            raise InstallError(f"La destinazione contiene un file al posto di una directory: {current}")


def _identity(path: Path):
    info = path.lstat()
    return info.st_dev, info.st_ino


def _remove_owned(path: Path, identity) -> None:
    try:
        if not path.is_symlink() and path.is_dir() and _identity(path) == identity:
            shutil.rmtree(path)
    except FileNotFoundError:
        pass


def _write_exclusive(destination: Path, files: dict[str, bytes]) -> None:
    """Il chiamante ha appena riservato una directory nuova con mkdir esclusivo."""
    # La skill diventa rilevabile dall'host soltanto dopo le sue dipendenze.
    for relative, content in sorted(files.items(), key=lambda item: (item[0] == "SKILL.md", item[0])):
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        # Non segue symlink finali e non sovrascrive nemmeno durante una collisione.
        mode = 0o600 if relative == RECEIPT else 0o644
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)


def _hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())}


def _version(files: dict[str, bytes]) -> str:
    try:
        value = files.get("VERSION", b"0.1.0").decode("ascii").strip()
    except UnicodeError as error:
        raise InstallError("VERSION non valida.") from error
    if len(value) > 64 or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?", value):
        raise InstallError("VERSION deve contenere una versione come 0.2.0.")
    return value


def _with_receipt(files: dict[str, bytes]) -> dict[str, bytes]:
    receipt = {"schema_version": RECEIPT_SCHEMA, "version": _version(files), "files": _hashes(files)}
    return {**files, RECEIPT: (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")}


def _receipt(directory: Path) -> dict:
    path = directory / RECEIPT
    if not path.exists() or path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
        raise InstallError("Installazione senza ricevuta valida: conserva una copia della skill e installa la nuova versione manualmente.")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise InstallError("Ricevuta di installazione non regolare.")
            content = stream.read(MAX_SOURCE_BYTES + 1)
        if len(content) > MAX_SOURCE_BYTES:
            raise InstallError("Ricevuta di installazione troppo grande.")
        data = json.loads(content.decode("utf-8"))
    except (UnicodeError, ValueError, OSError) as error:
        raise InstallError("Ricevuta di installazione non leggibile.") from error
    if not isinstance(data, dict) or set(data) != {"schema_version", "version", "files"} or data["schema_version"] != RECEIPT_SCHEMA:
        raise InstallError("Schema della ricevuta di installazione non supportato.")
    if not isinstance(data["version"], str) or not isinstance(data["files"], dict) or not data["files"]:
        raise InstallError("Ricevuta di installazione incompleta.")
    for name, digest in data["files"].items():
        if not isinstance(name, str) or name.startswith("/") or "\\" in name or any(part in {"", ".", ".."} for part in name.split("/")) or name == RECEIPT:
            raise InstallError("Percorso non valido nella ricevuta.")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise InstallError("Hash non valido nella ricevuta.")
    try:
        version_bytes = data["version"].encode("ascii")
    except UnicodeError as error:
        raise InstallError("Versione della ricevuta non valida.") from error
    if data["version"] != _version({"VERSION": version_bytes}):
        raise InstallError("Versione della ricevuta non valida.")
    return data


def _managed(directory: Path) -> tuple[dict[str, bytes], dict]:
    # Questi dati non sono cache sacrificabili. Non spostarli o copiarli
    # automaticamente: una venv può contenere percorsi assoluti e molti file.
    if any(os.path.lexists(directory / name) for name in (".venv", ".git")):
        raise InstallError("La skill contiene .venv o .git: usa un ambiente esterno e conserva i dati prima di aggiornare manualmente.")
    files = _manifest(directory)
    receipt = _receipt(directory)
    if _hashes(files) != receipt["files"]:
        raise InstallError("La skill contiene modifiche o file personali: nessuna sovrascrittura. Confronta le modifiche e conserva una copia prima dell'aggiornamento manuale.")
    if _version(files) != receipt["version"]:
        raise InstallError("VERSION e ricevuta non corrispondono.")
    return files, receipt


def _private_parents(home: Path, directory: Path, created: list) -> None:
    _check_ancestors(home, directory)
    current = home
    for part in directory.relative_to(home).parts:
        current = current / part
        try:
            current.mkdir(mode=0o700)
            created.append((current, _identity(current)))
        except FileExistsError:
            if current.is_symlink() or not current.is_dir():
                raise InstallError(f"Directory non sicura: {current}")


def _clean_parents(parents: list) -> None:
    for path, identity in reversed(parents):
        try:
            if not path.is_symlink() and _identity(path) == identity:
                path.rmdir()
        except OSError:
            pass


def _backup_path(home: Path, host: str, version: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return home / ".naturale" / "backups" / host / f"{stamp}-v{version}-{uuid.uuid4().hex[:12]}"


def _created_tree_unchanged(event: dict) -> bool:
    """Controlla anche receipt/cache/file extra prima di eliminare una copia nuova.

    Durante una scrittura fallita è ammesso un sottoinsieme dei file previsti,
    ma ogni file presente deve avere tutti i byte attesi. Una scrittura parziale
    o un contenuto concorrente dubbio vengono conservati per verifica manuale.
    """
    directory = event["destination"]
    expected = event["expected"]
    expected_directories = {"."}
    for name in expected:
        expected_directories.update(parent.as_posix() for parent in Path(name).parents)
    seen = set()
    try:
        if directory.is_symlink() or not directory.is_dir():
            return False
        for base, directories, filenames in os.walk(directory, followlinks=False):
            parent = Path(base)
            for name in directories:
                path = parent / name
                if path.is_symlink() or path.relative_to(directory).as_posix() not in expected_directories:
                    return False
            for name in filenames:
                path = parent / name
                relative = path.relative_to(directory).as_posix()
                if relative not in expected or path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
                    return False
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                fd = os.open(path, flags)
                with os.fdopen(fd, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        return False
                    if stream.read(len(expected[relative]) + 1) != expected[relative]:
                        return False
                seen.add(relative)
    except OSError:
        return False
    return seen == set(expected) if event.get("complete") else True


def _undo(event: dict) -> None:
    destination = event["destination"]
    if event.get("new_identity") is not None:
        if destination.is_dir() and not destination.is_symlink() and _identity(destination) == event["new_identity"]:
            if not _created_tree_unchanged(event):
                backup = event.get("backup")
                suffix = f"; copia originale nel backup {backup}" if backup else ""
                raise InstallError(f"La copia nuova contiene modifiche concorrenti o dati non verificabili: conservata in {destination}{suffix}. Serve una verifica manuale.")
        _remove_owned(destination, event["new_identity"])
    saved = event.get("saved")
    if saved is not None and saved.exists():
        if os.path.lexists(destination):
            raise InstallError(f"Una destinazione concorrente è stata conservata; l'installazione originale è nel backup {saved.parent}.")
        saved.rename(destination)
        event["backup"].rmdir()


def _replace(destination: Path, files: dict[str, bytes], backup: Path, home: Path,
             expected_identity, parents: list) -> dict:
    """Backup completo, prenotazione esclusiva e ripristino in caso di errore."""
    _check_ancestors(home, destination)
    _managed(destination)  # ricontrolla modifiche intervenute dopo il preflight
    if _identity(destination) != expected_identity:
        raise InstallError("L'installazione è cambiata durante l'operazione: riprovare dopo averla verificata.")
    _private_parents(home, backup.parent, parents)
    backup.mkdir(mode=0o700)
    new_files = _with_receipt(files)
    event = {"destination": destination, "saved": backup / "skill", "backup": backup,
             "new_identity": None, "expected": new_files, "complete": False}
    moved = False
    try:
        destination.rename(event["saved"])
        moved = True
        destination.mkdir(mode=0o700)
        event["new_identity"] = _identity(destination)
        _write_exclusive(destination, new_files)
        if _manifest(destination) != files:
            raise InstallError("Verifica dei file aggiornati non riuscita.")
        _managed(destination)
        event["complete"] = True
    except (OSError, InstallError) as error:
        if moved:
            try:
                _undo(event)
            except (OSError, InstallError) as restore_error:
                raise InstallError(f"Operazione interrotta; i dati originali restano in {backup}: {restore_error}") from error
        else:
            backup.rmdir()
        raise
    return event


def install(source: str | Path, hosts, home: str | Path | None = None,
            dry_run: bool = False, update: bool = False) -> list[dict]:
    """Installa o aggiorna da una copia locale; non scarica né esegue codice remoto."""
    source = Path(source).absolute()
    files = _validate_source(source)
    _version(files)
    hosts = tuple(dict.fromkeys(hosts))
    if not hosts or any(host not in HOSTS for host in hosts):
        raise InstallError("Scegliere claude, codex oppure entrambi.")
    home = Path(home if home is not None else Path.home()).expanduser().resolve()
    results = []
    identities = {}
    for host in hosts:
        destination = home / HOSTS[host] / "skills" / "naturale"
        _check_ancestors(home, destination)
        result = {"host": host, "path": str(destination), "version": _version(files)}
        if destination.exists():
            if _manifest(destination) == files:
                result["status"] = "already_installed"
            elif update:
                _, receipt = _managed(destination)
                backup = _backup_path(home, host, receipt["version"])
                _check_ancestors(home, backup.parent)
                identities[host] = _identity(destination)
                result.update(status="would_update" if dry_run else "updated", previous_version=receipt["version"], backup_path=str(backup))
            else:
                raise InstallError(f"Installazione diversa già presente: {destination}. Confrontarla o spostarla prima; nessun file sovrascritto. Per una copia gestita usa --update.")
        else:
            result["status"] = "would_install" if dry_run else "installed"
        results.append(result)
    if dry_run:
        return results
    events = []
    parents = []
    try:
        for result in results:
            if result["status"] == "already_installed":
                continue
            destination = Path(result["path"])
            if result["status"] == "updated":
                events.append(_replace(destination, files, Path(result["backup_path"]), home, identities[result["host"]], parents))
                continue
            _check_ancestors(home, destination)
            _private_parents(home, destination.parent, parents)
            destination.mkdir(mode=0o700)
            new_files = _with_receipt(files)
            event = {"destination": destination, "new_identity": _identity(destination),
                     "expected": new_files, "complete": False}
            events.append(event)
            _write_exclusive(destination, new_files)
            if _manifest(destination) != files:
                raise InstallError(f"Verifica della copia non riuscita: {destination}")
            _managed(destination)
            event["complete"] = True
    except (OSError, InstallError) as error:
        restore_errors = []
        for event in reversed(events):
            try:
                _undo(event)
            except (OSError, InstallError) as restore_error:
                restore_errors.append(str(restore_error))
        _clean_parents(parents)
        if restore_errors:
            raise InstallError(f"Operazione interrotta; controllare i backup conservati: {'; '.join(restore_errors)}") from error
        if isinstance(error, InstallError):
            raise
        raise InstallError(f"Installazione non completata: {error}") from error
    return results


def rollback(backup_path: str | Path, host: str, home: str | Path | None = None,
             dry_run: bool = False) -> dict:
    """Ripristina un backup locale gestito, conservando prima la versione corrente."""
    if host not in HOSTS:
        raise InstallError("Il ripristino richiede un singolo host: claude oppure codex.")
    home = Path(home if home is not None else Path.home()).expanduser().resolve()
    backup = Path(backup_path).expanduser().absolute()
    backup = backup.parent.resolve() / backup.name
    expected_root = home / ".naturale" / "backups" / host
    try:
        relative = backup.relative_to(expected_root)
    except ValueError as error:
        raise InstallError("Il backup deve trovarsi nella directory locale dei backup del relativo host.") from error
    if len(relative.parts) != 1 or relative.name in {"", ".", ".."}:
        raise InstallError("Percorso backup non valido.")
    _check_ancestors(home, backup / "skill")
    source = backup / "skill"
    files = _validate_source(source)
    _managed(source)
    destination = home / HOSTS[host] / "skills" / "naturale"
    _check_ancestors(home, destination)
    current, receipt = _managed(destination)
    result = {"host": host, "path": str(destination), "version": _version(files), "restored_from": str(backup)}
    if current == files:
        result["status"] = "already_installed"
        return result
    result["status"] = "would_rollback" if dry_run else "rolled_back"
    next_backup = _backup_path(home, host, receipt["version"])
    result["backup_path"] = str(next_backup)
    if dry_run:
        return result
    parents = []
    try:
        _replace(destination, files, next_backup, home, _identity(destination), parents)
    except (OSError, InstallError) as error:
        _clean_parents(parents)
        if isinstance(error, InstallError):
            raise
        raise InstallError(f"Ripristino non completato: {error}") from error
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=["claude", "codex", "both"])
    parser.add_argument("--dry-run", action="store_true", help="Controlla senza creare directory o file")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--update", action="store_true", help="Aggiorna da questo checkout verificato, con backup locale")
    action.add_argument("--rollback", metavar="BACKUP", help="Ripristina un backup gestito; richiede un singolo host")
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[1] / "skills" / "naturale"
    try:
        if args.rollback:
            results = [rollback(args.rollback, args.host, dry_run=args.dry_run)]
        else:
            results = install(source, HOSTS if args.host == "both" else [args.host], dry_run=args.dry_run, update=args.update)
    except (InstallError, OSError) as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1
    labels = {"installed": "Installata", "already_installed": "Già installata e identica", "would_install": "Da installare (simulazione)", "updated": "Aggiornata", "would_update": "Da aggiornare (simulazione)", "rolled_back": "Ripristinata", "would_rollback": "Da ripristinare (simulazione)"}
    for result in results:
        print(f"{labels[result['status']]} [{result['host']}, {result['version']}]: {result['path']}")
        if result.get("backup_path"):
            print(f"Backup {'previsto' if args.dry_run else 'conservato'}: {result['backup_path']}")
    print("Per i testi non servono altre dipendenze. Per le immagini: Python 3.11+, Pillow ed ExifTool; consulta INSTALL.md nella skill.")
    print("Nessun file è stato inviato a servizi esterni; nessuna dipendenza è stata installata.")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
