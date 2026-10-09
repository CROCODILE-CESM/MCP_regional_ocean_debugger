"""Tools for reading CIME's native model-throughput/scaling timing output."""

import re
from pathlib import Path


def _find_timing_file(case_dir: str) -> Path | None:
    case = Path(case_dir).expanduser()
    candidates = sorted(
        case.glob("timing/cesm_timing.*"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return candidates[0] if candidates else None


def read_cesm_timing(case_dir: str) -> str:
    """
    Read CIME's native cesm_timing.$CASE.$jobid file for a CESM case.

    This is the file CIME writes to case_dir/timing/ after a completed run —
    it's the authoritative source for model scaling/throughput numbers
    (Model Throughput, Model Cost, per-component Run Time), useful for
    comparing wallclock/throughput across different NTASKS/PE-layout runs
    of the same case. Returns "not found" if the case hasn't finished a
    run yet (case.submit writes this file at the end of a successful run).

    Pass the CASEROOT (case_dir), e.g. ~/croc_cases/my_case.
    """
    timing_file = _find_timing_file(case_dir)
    if timing_file is None:
        return (
            f"No cesm_timing.* file found in {case_dir}/timing/. "
            "The case may not have finished a run yet — this file is written "
            "at the end of case.submit."
        )

    text = timing_file.read_text(errors="replace")

    lines = [f"=== {timing_file} ==="]

    m = re.search(r"Model Cost:\s*([\d.]+)\s*pe-hrs/simulated_year", text)
    if m:
        lines.append(f"Model Cost:       {m.group(1)} pe-hrs/simulated_year")

    m = re.search(r"Model Throughput:\s*([\d.]+)\s*simulated_years/day", text)
    if m:
        lines.append(f"Model Throughput: {m.group(1)} simulated_years/day")

    for label, pattern in [
        ("Init Time", r"Init Time\s*:\s*([\d.]+)\s*seconds"),
        ("Run Time", r"^\s*Run Time\s*:\s*([\d.]+)\s*seconds"),
        ("Final Time", r"Final Time\s*:\s*([\d.]+)\s*seconds"),
    ]:
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            lines.append(f"{label}:         {m.group(1)} seconds")

    lines.append("\nPer-component run time:")
    component_pattern = re.compile(
        r"^\s*(\w+) Run Time:\s*([\d.]+) seconds\s*([\d.]+) seconds/mday\s*([\d.]+) myears/wday",
        re.MULTILINE,
    )
    found_component = False
    for comp, run_s, s_per_mday, myears_per_wday in component_pattern.findall(text):
        found_component = True
        lines.append(
            f"  {comp}: {run_s}s total, {s_per_mday}s/model-day, {myears_per_wday} myears/wall-day"
        )
    if not found_component:
        lines.append("  (none parsed — file format may differ from expected)")

    pe_pattern = re.search(r"total pes active\s*:\s*(\d+)", text)
    if pe_pattern:
        lines.append(f"\nTotal PEs active: {pe_pattern.group(1)}")

    ntasks_ocn = re.search(r"ocn\s*=\s*\S+\s+\d+\s+\d+\s+(\d+)\s*x", text)
    if ntasks_ocn:
        lines.append(f"NTASKS_OCN (from PE layout): {ntasks_ocn.group(1)}")

    return "\n".join(lines)
