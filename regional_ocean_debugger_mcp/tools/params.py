"""Tools for reading and comparing MOM6 parameter files."""

import re
from pathlib import Path


def _find_mom6_params(case_dir: str) -> tuple[Path | None, Path | None]:
    """Return (MOM_input, MOM_override) paths for a case, or None if not found."""
    case = Path(case_dir).expanduser()
    search_dirs = [case / "run", case / "Buildconf" / "momconf", case]
    mom_input = None
    mom_override = None
    for d in search_dirs:
        if not d.exists():
            continue
        if (d / "MOM_input").exists() and mom_input is None:
            mom_input = d / "MOM_input"
        if (d / "MOM_override").exists() and mom_override is None:
            mom_override = d / "MOM_override"
    return mom_input, mom_override


def _parse_mom_params(path: Path) -> dict[str, str]:
    """Parse a MOM_input or MOM_override file into {param: value} dict."""
    params = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("!"):
            continue
        # Remove inline comments
        line = re.sub(r"\s*!.*$", "", line).strip()
        if "=" in line:
            key, _, val = line.partition("=")
            params[key.strip()] = val.strip().rstrip(",")
    return params


def read_mom6_params(case_dir: str, filter: str = "") -> str:
    """
    Read MOM_input and MOM_override parameter files for a CESM/MOM6 case.

    Returns all parameters as KEY = VALUE pairs.
    Pass filter to show only parameters containing that substring (e.g. 'DT', 'OBC', 'SPONGE').
    MOM_override values take precedence and are marked with [override].
    """
    mom_input, mom_override = _find_mom6_params(case_dir)
    if not mom_input:
        return f"No MOM_input found in {case_dir}/run/ or {case_dir}/Buildconf/momconf/"

    base = _parse_mom_params(mom_input)
    overrides = _parse_mom_params(mom_override) if mom_override else {}

    lines = []
    for key in sorted(set(base) | set(overrides)):
        if filter and filter.lower() not in key.lower():
            continue
        if key in overrides:
            lines.append(f"{key} = {overrides[key]}  [override]")
        else:
            lines.append(f"{key} = {base[key]}")

    if not lines:
        return f"No parameters found matching '{filter}'" if filter else "MOM_input appears empty"
    header = f"=== {mom_input} ===" + (f"\n=== {mom_override} ===" if mom_override else "")
    return header + "\n\n" + "\n".join(lines)


def diff_params(case_dir_a: str, case_dir_b: str) -> str:
    """
    Compare MOM_input parameters between two CESM/MOM6 cases.

    Returns parameters that differ, with values from both cases side by side.
    Useful for diagnosing why two configurations behave differently.
    """
    ma, _ = _find_mom6_params(case_dir_a)
    mb, _ = _find_mom6_params(case_dir_b)
    oa_path, _ = _find_mom6_params(case_dir_a)
    ob_path, _ = _find_mom6_params(case_dir_b)

    if not ma:
        return f"No MOM_input found in {case_dir_a}"
    if not mb:
        return f"No MOM_input found in {case_dir_b}"

    a = _parse_mom_params(ma)
    b = _parse_mom_params(mb)

    # Apply overrides
    oa_file = Path(case_dir_a).expanduser() / "run" / "MOM_override"
    ob_file = Path(case_dir_b).expanduser() / "run" / "MOM_override"
    if oa_file.exists():
        a.update(_parse_mom_params(oa_file))
    if ob_file.exists():
        b.update(_parse_mom_params(ob_file))

    all_keys = sorted(set(a) | set(b))
    diffs = []
    for key in all_keys:
        va = a.get(key, "<not set>")
        vb = b.get(key, "<not set>")
        if va != vb:
            diffs.append(f"{key}:\n  A: {va}\n  B: {vb}")

    if not diffs:
        return "No differences found in MOM_input parameters between the two cases."
    name_a = Path(case_dir_a).name
    name_b = Path(case_dir_b).name
    return f"Differences (A={name_a}, B={name_b}):\n\n" + "\n\n".join(diffs)
