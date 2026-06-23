"""Tools for reading and analyzing CESM/MOM6 run logs."""

import re
import subprocess
from pathlib import Path

# Patterns that indicate a fatal model error
ERROR_PATTERNS = [
    (re.compile(r"FATAL ERROR", re.IGNORECASE), "FATAL"),
    (re.compile(r"ERROR:", re.IGNORECASE), "ERROR"),
    (re.compile(r"Abort called", re.IGNORECASE), "ABORT"),
    (re.compile(r"SIGTERM|SIGABRT|SIGSEGV", re.IGNORECASE), "SIGNAL"),
    (re.compile(r"NaN detected", re.IGNORECASE), "NaN"),
    (re.compile(r"CFL violation", re.IGNORECASE), "CFL"),
    (re.compile(r"Inf detected|infinity", re.IGNORECASE), "INF"),
    (re.compile(r"negative thickness|negative depth", re.IGNORECASE), "NEGATIVE_THICKNESS"),
    (re.compile(r"mass balance error|tracer budget error", re.IGNORECASE), "MASS_BALANCE"),
    (re.compile(r"out of memory|OOM", re.IGNORECASE), "OOM"),
    (re.compile(r"segmentation fault", re.IGNORECASE), "SEGFAULT"),
    (re.compile(r"EXITING with error", re.IGNORECASE), "FATAL"),
    (re.compile(r"stopping at", re.IGNORECASE), "STOP"),
]

# Known MOM6/CESM error signatures → probable cause and suggested fix
KNOWN_ERRORS = {
    "CFL": {
        "cause": "CFL (Courant–Friedrichs–Lewy) stability violation. The model timestep is too large for the grid resolution or flow speeds.",
        "fix": "Reduce DT_THERM and/or DT in MOM_input. A safe starting point for 1/4° is DT=1800s, DT_THERM=3600s. For 1/12°, try DT=600s, DT_THERM=1800s.",
    },
    "NaN": {
        "cause": "NaN (Not-a-Number) values detected. Usually caused by a CFL violation, negative layer thickness, or a bad initial condition/forcing file.",
        "fix": "Check for CFL violations first. Also validate forcing files for fill values bleeding into the domain, and check min_depth in bathymetry.",
    },
    "NEGATIVE_THICKNESS": {
        "cause": "A model layer has collapsed to negative thickness, typically caused by steep bathymetry gradients or an aggressive timestep.",
        "fix": "Increase MINIMUM_DEPTH in MOM_input, smooth bathymetry near problem cells, or reduce DT.",
    },
    "MASS_BALANCE": {
        "cause": "Mass/tracer conservation error. Can be caused by OBC inconsistencies or open boundaries with mismatched forcing.",
        "fix": "Check OBC forcing files for time interpolation gaps. Verify SPONGE settings. Check that OBC normal velocity is consistent with tracer OBCs.",
    },
    "OOM": {
        "cause": "Out-of-memory error. The job ran out of RAM on the nodes.",
        "fix": "Increase nodes/ppn, or reduce NTASKS to use more memory per task. On Derecho, check memory per node for the queue.",
    },
    "SEGFAULT": {
        "cause": "Segmentation fault — a memory access error. Often a model bug or a corrupted restart/forcing file.",
        "fix": "Check restart files for corruption. Try a clean build (./case.build --clean-all). If persistent, file a bug report.",
    },
}


def _find_logs(case_dir: str, component: str) -> list[Path]:
    case = Path(case_dir).expanduser()
    candidates = []
    for d in [case, case / "run", case / "logs"]:
        if not d.exists():
            continue
        if component == "all":
            candidates.extend(d.glob("*.log*"))
        else:
            candidates.extend(d.glob(f"{component}.log*"))
            candidates.extend(d.glob(f"*{component}*.log*"))
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)


def read_run_log(case_dir: str, component: str = "cesm", lines: int = 200) -> str:
    """
    Return recent lines from a CESM or MOM6 run log.

    component: 'cesm', 'ocn' (MOM6), 'atm', 'ice', 'rof', or 'all'.
    Searches case_dir and case_dir/run/ for log files. Returns the most recent match.
    """
    logs = _find_logs(case_dir, component)
    if not logs:
        return f"No {component} log files found in {case_dir}"

    log = logs[0]
    result = subprocess.run(["tail", f"-{lines}", str(log)], capture_output=True, text=True)
    return f"=== {log} (last {lines} lines) ===\n{result.stdout}"


def find_errors(case_dir: str) -> str:
    """
    Scan all run logs in a CESM case for error indicators.

    Searches for FATAL, ERROR, NaN, CFL violations, negative thickness, OOM, and similar.
    Returns a structured list of matches with filename, line number, and error type.
    Call classify_error() on the error text for probable cause and fix suggestions.
    """
    case = Path(case_dir).expanduser()
    logs = _find_logs(case_dir, "all")
    if not logs:
        return f"No log files found in {case_dir}"

    findings = []
    for log in logs[:10]:  # cap at 10 most recent logs
        try:
            text = log.read_text(errors="replace")
        except Exception as e:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern, label in ERROR_PATTERNS:
                if pattern.search(line):
                    findings.append(f"[{label}] {log.name}:{lineno}: {line.strip()}")
                    break

    if not findings:
        return "No errors found in run logs. Model may have completed successfully."
    return "\n".join(findings[:100])  # cap output


def classify_error(error_text: str) -> str:
    """
    Classify a MOM6/CESM error message and return probable cause and fix suggestions.

    Pass a snippet of error text (e.g. from find_errors output) and get back
    a structured diagnosis. Matches against a library of known MOM6 failure modes.
    """
    matched = []
    for label, info in KNOWN_ERRORS.items():
        # Check if the label pattern matches the error text
        pattern, _ = next((p, l) for p, l in ERROR_PATTERNS if l == label)
        if pattern.search(error_text):
            matched.append(f"**{label}**\nCause: {info['cause']}\nFix: {info['fix']}")

    if not matched:
        return (
            "No known error pattern matched. Try query_domain_knowledge() with a description "
            "of the error for expert guidance from interview transcripts.\n\n"
            f"Error text received:\n{error_text[:500]}"
        )
    return "\n\n".join(matched)
