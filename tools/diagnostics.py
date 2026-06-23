"""Tools for reading MOM6 diag_table and suggesting useful diagnostics."""

import re
from pathlib import Path

# Curated suggestions: symptom keywords → recommended MOM6 diagnostics
DIAGNOSTIC_SUGGESTIONS = {
    "temperature": [
        "ocean_model/temp — 3D potential temperature",
        "ocean_model/SST — sea surface temperature",
        "ocean_model/MLD_003 — mixed layer depth (0.03 density criterion)",
    ],
    "salinity": [
        "ocean_model/salt — 3D salinity",
        "ocean_model/SSS — sea surface salinity",
        "ocean_model/halocline_depth — halocline depth",
    ],
    "velocity": [
        "ocean_model/u — zonal velocity",
        "ocean_model/v — meridional velocity",
        "ocean_model/speed — horizontal speed",
        "ocean_model/SSH — sea surface height",
    ],
    "energy": [
        "ocean_model/KE — kinetic energy",
        "ocean_model/PE_to_KE — potential to kinetic energy conversion",
        "ocean_model/TKE_itidal_used — internal tide TKE",
    ],
    "mixing": [
        "ocean_model/Kd_interface — diapycnal diffusivity",
        "ocean_model/Kv_shear — vertical viscosity from shear",
        "ocean_model/KHTH — lateral thickness diffusivity",
        "ocean_model/KHTR — lateral tracer diffusivity",
    ],
    "obc": [
        "ocean_model/u_segment_001 — OBC u velocity (adjust segment number)",
        "ocean_model/v_segment_001 — OBC v velocity",
        "ocean_model/temp_segment_001 — OBC temperature",
    ],
    "tides": [
        "ocean_model/tidal_speed — tidal flow speed",
        "ocean_model/eta_tidal — tidal surface elevation",
        "ocean_model/TKE_tidal_used — tidal TKE dissipation",
    ],
    "cfl": [
        "ocean_model/cfl_umax — maximum CFL number",
        "ocean_model/max_CFL_trans — maximum transport CFL",
        "ocean_model/Zanna_Bolton2020_Sxx — submesoscale param (if used)",
    ],
    "bgc": [
        "ocean_model/NO3 — nitrate",
        "ocean_model/O2 — dissolved oxygen",
        "ocean_model/Chl — chlorophyll",
        "ocean_model/DIC — dissolved inorganic carbon",
    ],
    "heat": [
        "ocean_model/net_heat_coupler — net heat flux from coupler",
        "ocean_model/SW — shortwave radiation",
        "ocean_model/LW — longwave radiation",
        "ocean_model/latent — latent heat flux",
        "ocean_model/sensible — sensible heat flux",
    ],
}


def read_diag_table(case_dir: str) -> str:
    """
    Read and parse the MOM6 diag_table from a CESM case.

    Returns enabled diagnostics grouped by module/component.
    diag_table is typically in case_dir/run/ or case_dir/Buildconf/momconf/.
    """
    case = Path(case_dir).expanduser()
    for d in [case / "run", case / "Buildconf" / "momconf", case]:
        f = d / "diag_table"
        if f.exists():
            diag_table_path = f
            break
    else:
        return f"No diag_table found in {case_dir}/run/ or {case_dir}/Buildconf/momconf/"

    text = diag_table_path.read_text()
    lines = text.splitlines()

    # Parse: first 2 lines are title/date, then file definitions, then field definitions
    output_lines = [f"=== {diag_table_path} ===", ""]
    current_section = None
    file_defs = []
    field_defs = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # File definitions look like: "filename" freq freq_units ... (quoted string first)
        if stripped.startswith('"') and stripped.count('"') >= 2:
            file_defs.append(stripped)
        elif "," in stripped and not stripped.startswith('"'):
            field_defs.append(stripped)

    output_lines.append(f"Output files ({len(file_defs)}):")
    for f in file_defs:
        output_lines.append(f"  {f}")
    output_lines.append(f"\nField definitions ({len(field_defs)}):")
    for f in field_defs[:100]:  # cap at 100
        output_lines.append(f"  {f}")
    if len(field_defs) > 100:
        output_lines.append(f"  ... and {len(field_defs) - 100} more")

    return "\n".join(output_lines)


def suggest_diagnostics(symptoms: str) -> str:
    """
    Suggest useful MOM6 diagnostics to add to diag_table based on a description of the problem.

    symptoms: describe what you're investigating (e.g. 'temperature drift', 'OBC instability',
              'CFL violations', 'tidal mixing', 'BGC', 'mixed layer too shallow').

    Returns a list of recommended diagnostic fields grouped by relevance.
    """
    symptoms_lower = symptoms.lower()
    matched = {}
    for keyword, diags in DIAGNOSTIC_SUGGESTIONS.items():
        if keyword in symptoms_lower or any(w in symptoms_lower for w in keyword.split("_")):
            matched[keyword] = diags

    if not matched:
        all_keys = ", ".join(sorted(DIAGNOSTIC_SUGGESTIONS.keys()))
        return (
            f"No specific matches found for '{symptoms}'.\n"
            f"Available categories: {all_keys}\n\n"
            "Try describing the symptom using one of those keywords."
        )

    lines = [f"Suggested diagnostics for: {symptoms}\n"]
    for category, diags in matched.items():
        lines.append(f"[{category.upper()}]")
        for d in diags:
            lines.append(f"  {d}")
        lines.append("")

    lines.append(
        "Add these to diag_table in case_dir/run/diag_table.\n"
        "Use read_diag_table() to see what's currently enabled."
    )
    return "\n".join(lines)
