"""Tools for checking MOM6 numerical stability and suggesting safe timesteps."""

import re
from pathlib import Path

from .params import _find_mom6_params, _parse_mom_params


# Resolution → recommended (DT, DT_THERM) in seconds based on common MOM6 experience
# These are conservative starting points; actual limits depend on bathymetry and forcing.
RESOLUTION_TIMESTEP_GUIDE = [
    (0.083, 300, 900),    # 1/12°
    (0.125, 450, 1350),   # 1/8°
    (0.25, 900, 1800),    # 1/4°
    (0.5, 1800, 3600),    # 1/2°
    (1.0, 3600, 7200),    # 1°
]


def _get_resolution_from_params(params: dict) -> float | None:
    """Try to extract approximate resolution in degrees from MOM_input."""
    for key in ["NIGLOBAL", "NJGLOBAL", "NX", "NY"]:
        if key in params:
            try:
                return float(params[key])
            except ValueError:
                pass
    return None


def check_cfl(case_dir: str) -> str:
    """
    Evaluate CFL stability condition for a MOM6 case.

    Reads DT, DT_THERM, and resolution-related parameters from MOM_input.
    Compares against recommended safe values for the apparent resolution.
    Returns a stability assessment and flags potential violations.

    Note: A full CFL check requires the actual grid file (dx, dy values).
    This tool uses MOM_input parameters as a proxy for a quick sanity check.
    """
    mom_input, mom_override = _find_mom6_params(case_dir)
    if not mom_input:
        return f"No MOM_input found in {case_dir}"

    params = _parse_mom_params(mom_input)
    if mom_override:
        params.update(_parse_mom_params(mom_override))

    dt = params.get("DT", "NOT SET")
    dt_therm = params.get("DT_THERM", "NOT SET")

    lines = [f"DT (baroclinic timestep): {dt} s"]
    lines.append(f"DT_THERM (thermodynamic timestep): {dt_therm} s")

    if dt != "NOT SET" and dt_therm != "NOT SET":
        try:
            dt_val = float(dt)
            dt_therm_val = float(dt_therm)
            ratio = dt_therm_val / dt_val
            lines.append(f"DT_THERM / DT ratio: {ratio:.1f}")
            if ratio < 1:
                lines.append("WARNING: DT_THERM < DT — thermodynamic step shorter than dynamic step is unusual.")
            elif ratio > 48:
                lines.append("WARNING: DT_THERM / DT ratio > 48 — may cause tracer instability in some configurations.")
        except ValueError:
            pass

    # Resolution guidance
    lines.append("\n--- Resolution-based timestep guidance ---")
    lines.append("Resolution | Rec. DT | Rec. DT_THERM")
    for res, rec_dt, rec_therm in RESOLUTION_TIMESTEP_GUIDE:
        lines.append(f"  ~{res}°     | {rec_dt:5d} s | {rec_therm:6d} s")

    lines.append(
        "\nNote: actual safe DT depends on bathymetry steepness, tidal forcing, and OBC "
        "settings. Start conservative and increase gradually while monitoring for CFL violations in logs."
    )

    return "\n".join(lines)


def suggest_timestep(resolution_deg: float) -> str:
    """
    Suggest safe MOM6 timestep values (DT and DT_THERM) for a given grid resolution.

    resolution_deg: approximate horizontal resolution in degrees (e.g. 0.1 for 1/10°).
    Returns recommended values with caveats about bathymetry and tidal forcing.
    """
    # Find the closest resolution bracket
    best = None
    for res, rec_dt, rec_therm in RESOLUTION_TIMESTEP_GUIDE:
        if best is None or abs(res - resolution_deg) < abs(best[0] - resolution_deg):
            best = (res, rec_dt, rec_therm)

    if best is None:
        return "Could not determine a recommendation for the given resolution."

    res, rec_dt, rec_therm = best
    lines = [
        f"For ~{resolution_deg}° resolution (closest reference: {res}°):",
        f"  DT       = {rec_dt} s   (baroclinic/momentum timestep)",
        f"  DT_THERM = {rec_therm} s   (thermodynamic/tracer timestep)",
        "",
        "These are conservative starting values. You may be able to increase DT after",
        "confirming stability in a short test run.",
        "",
        "Reduce further if:",
        "  - The domain has steep or complex bathymetry (e.g. shelf breaks, narrow straits)",
        "  - Tidal forcing is enabled (tides can require 2-4x shorter DT)",
        "  - You see CFL violations or NaN values in the first few model days",
        "",
        "To set in MOM_override (case_dir/run/MOM_override):",
        f"  DT = {rec_dt}",
        f"  DT_THERM = {rec_therm}",
    ]
    return "\n".join(lines)
