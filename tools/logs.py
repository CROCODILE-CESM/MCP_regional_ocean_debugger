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
    # OBC forcing preprocessing errors (CrocoDash process_forcings)
    (re.compile(r"KeyError.*bathymetry_path", re.IGNORECASE), "OBC_PREPROCESS"),
    (re.compile(r"OBC file.*corrupt", re.IGNORECASE), "OBC_PREPROCESS"),
    (re.compile(r"No files found.*obc|forcing_obc_segment.*not found", re.IGNORECASE), "OBC_PREPROCESS"),
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
    "OBC_PREPROCESS": {
        "cause": (
            "OBC forcing preprocessing failure in CrocoDash process_forcings. "
            "Common causes: (1) KeyError: 'bathymetry_path' — config is missing the bathymetry path, "
            "which means configure_forcings was not called through a CrocoDash Case object; "
            "(2) get_glorys_data.sh is missing some boundary entries — a race condition in threaded "
            "dask.compute() causes concurrent writes to the script file to drop entries; "
            "(3) OBC file is corrupt or empty — the GLORYS script was generated but not run."
        ),
        "fix": (
            "For KeyError 'bathymetry_path': ensure you used Case.configure_forcings() (not a hand-crafted config). "
            "For missing script entries: check how many copernicusmarine commands are in "
            "extract_forcings/raw_data/get_glorys_data.sh — there should be one per boundary per time chunk. "
            "If entries are missing, re-run process_forcings (it regenerates the script). "
            "For script-based GLORYS: run the generated get_glorys_data.sh, then call process_forcings "
            "again with skip_get=True to proceed to regridding."
        ),
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


def check_obc_forcing_status(inputdir: str) -> str:
    """
    Check the status of OBC forcing preprocessing for a CrocoDash case.

    Inspects the extract_forcings/ directory inside the case inputdir and reports:
    - Whether config.json exists (configure_forcings was called)
    - Which boundaries are expected (from boundary_number_conversion in config)
    - Whether the GLORYS download script exists and how many boundary entries it has
    - Which raw OBC files exist vs expected
    - Which regridded OBC segment files exist in ocnice/

    Pass the case inputdir path (e.g. ~/scratch/croc_input/my_case).
    """
    import json

    inputdir_path = Path(inputdir).expanduser()
    extract_dir = inputdir_path / "extract_forcings"
    config_path = extract_dir / "config.json"

    lines = [f"=== OBC Forcing Status: {inputdir_path.name} ===\n"]

    if not config_path.exists():
        lines.append("MISSING: config.json — configure_forcings() has not been called yet.")
        return "\n".join(lines)

    with open(config_path) as f:
        config = json.load(f)

    basic = config.get("basic", {})
    boundaries = list(basic.get("general", {}).get("boundary_number_conversion", {}).keys())
    lines.append(f"Boundaries: {boundaries}")

    # GLORYS download script
    script_path = extract_dir / "raw_data" / "get_glorys_data.sh"
    if script_path.exists():
        script_text = script_path.read_text()
        script_entries = [l for l in script_text.splitlines() if "copernicusmarine" in l]
        lines.append(f"\nGLORYS script: {script_path}")
        lines.append(f"  Entries in script: {len(script_entries)} (expected {len(boundaries)} per time chunk)")
        if len(script_entries) < len(boundaries):
            lines.append(
                "  WARNING: fewer script entries than boundaries — likely a race condition "
                "in threaded dask.compute(). Re-run process_forcings to regenerate."
            )
        for entry in script_entries:
            # Extract just the output filename
            m = re.search(r"-f (\S+\.nc)", entry)
            if m:
                lines.append(f"  - {m.group(1)}")
    else:
        lines.append("\nGLORYS script: NOT FOUND (process_forcings not yet run, or uses RDA method)")

    # Raw OBC files
    raw_dir = extract_dir / "raw_data"
    raw_files = sorted(raw_dir.glob("*_unprocessed*.nc")) if raw_dir.exists() else []
    lines.append(f"\nRaw OBC files ({len(raw_files)} found):")
    for f in raw_files:
        size = f.stat().st_size
        lines.append(f"  {'OK' if size > 1000 else 'EMPTY/CORRUPT'}: {f.name} ({size} bytes)")

    # Regridded OBC segment files
    ocnice_dir = inputdir_path / "ocnice"
    seg_files = sorted(ocnice_dir.glob("forcing_obc_segment_*.nc")) if ocnice_dir.exists() else []
    lines.append(f"\nFinal OBC segment files in ocnice/ ({len(seg_files)} found):")
    for f in seg_files:
        lines.append(f"  {f.name}")

    if not seg_files:
        lines.append("  NONE — regridding and merging not yet complete.")

    return "\n".join(lines)
