#!/usr/bin/env python3
"""Installa la skill locale, senza rete, dipendenze aggiuntive o sovrascritture."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import stat
import sys
from urllib.parse import unquote, urlsplit


HOSTS = {"claude": ".claude", "codex": ".agents"}
IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store"}
MAX_SOURCE_BYTES = 20 * 1024 * 1024
REQUIRED = {"SKILL.md", "LICENSE", "INSTALL.md", "requirements.txt", "scripts/images.py"}


class InstallError(Exception):
    """Installazione rifiutata senza modificare file preesistenti."""


def _ignored(path: Path) -> bool:
    return any(part in IGNORED for part in path.parts) or path.suffix in {".pyc", ".pyo"}


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
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)


def install(source: str | Path, hosts, home: str | Path | None = None, dry_run: bool = False) -> list[dict]:
    """Preflight completo, poi copia; ritorna host/path/status per ogni destinazione."""
    source = Path(source).absolute()
    files = _validate_source(source)
    hosts = tuple(dict.fromkeys(hosts))
    if not hosts or any(host not in HOSTS for host in hosts):
        raise InstallError("Scegliere claude, codex oppure entrambi.")
    home = Path(home if home is not None else Path.home()).expanduser().resolve()
    results = []
    for host in hosts:
        destination = home / HOSTS[host] / "skills" / "naturale"
        _check_ancestors(home, destination)
        if destination.exists():
            if _manifest(destination) != files:
                raise InstallError(f"Installazione diversa già presente: {destination}. Confrontarla o spostarla prima; nessun file sovrascritto.")
            status = "already_installed"
        else:
            status = "would_install" if dry_run else "installed"
        results.append({"host": host, "path": str(destination), "status": status})
    if dry_run:
        return results
    created = []
    parents = []
    try:
        for result in results:
            if result["status"] == "already_installed":
                continue
            destination = Path(result["path"])
            _check_ancestors(home, destination)
            # Registra soltanto directory create da questa esecuzione.
            for parent in (destination.parent.parent, destination.parent):
                try:
                    parent.mkdir(mode=0o700)
                    parents.append((parent, _identity(parent)))
                except FileExistsError:
                    if parent.is_symlink() or not parent.is_dir():
                        raise InstallError(f"Directory di destinazione non sicura: {parent}")
            destination.mkdir(mode=0o700)  # fallisce se un altro processo ha occupato il nome
            created.append((destination, _identity(destination)))
            _write_exclusive(destination, files)
            if _manifest(destination) != files:
                raise InstallError(f"Verifica della copia non riuscita: {destination}")
    except (OSError, InstallError) as error:
        for path, identity in reversed(created):
            _remove_owned(path, identity)
        for path, identity in reversed(parents):
            try:
                if not path.is_symlink() and _identity(path) == identity:
                    path.rmdir()  # non rimuove contenuti preesistenti o concorrenti
            except (FileNotFoundError, OSError):
                pass
        if isinstance(error, InstallError):
            raise
        raise InstallError(f"Installazione non completata: {error}") from error
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=["claude", "codex", "both"])
    parser.add_argument("--dry-run", action="store_true", help="Controlla senza creare directory o file")
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[1] / "skills" / "naturale"
    try:
        results = install(source, HOSTS if args.host == "both" else [args.host], dry_run=args.dry_run)
    except (InstallError, OSError) as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1
    labels = {"installed": "Installata", "already_installed": "Già installata e identica", "would_install": "Da installare (simulazione)"}
    for result in results:
        print(f"{labels[result['status']]} [{result['host']}]: {result['path']}")
    print("Per i testi non servono altre dipendenze. Per le immagini: Python 3.11+, Pillow ed ExifTool; consulta INSTALL.md nella skill.")
    print("Nessun file è stato inviato a servizi esterni; nessuna dipendenza è stata installata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
