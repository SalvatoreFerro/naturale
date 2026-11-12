"""Shared, offline ExifTool compatibility contract for images and diagnostics."""
import re
import shutil
import subprocess

# First adjacent release fixing PNG embedded-directory bookkeeping (ExifTool #453).
# 13.59 fails both signed-PNG privacy regressions; 13.60 passes the full baseline.
MIN_EXIFTOOL_VERSION = (13, 60)


def exiftool_report(timeout=10):
    minimum = ".".join(map(str, MIN_EXIFTOOL_VERSION))
    result = {"available": False, "compatible": False, "version": None,
              "minimum_version": minimum, "problem": None}
    executable = shutil.which("exiftool")
    if not executable:
        result["problem"] = "not_found"
        return result
    try:
        completed = subprocess.run([executable, "-config", "", "-ver"], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=timeout,
                                   check=False, shell=False)
    except (OSError, subprocess.TimeoutExpired):
        result["problem"] = "not_executable_or_timeout"
        return result
    value = completed.stdout.strip()
    if completed.returncode or not re.fullmatch(r"\d+(?:\.\d+){1,2}", value):
        result["problem"] = "version_check_failed"
        return result
    compatible = tuple(map(int, value.split("."))) >= MIN_EXIFTOOL_VERSION
    result.update(available=True, compatible=compatible, version=value,
                  problem=None if compatible else "exiftool_too_old")
    return result
