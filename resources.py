"""Resource handlers for ocean:// URIs."""

from pathlib import Path

from fastmcp import FastMCP

from tools.params import _find_mom6_params, _parse_mom_params
from tools.logs import _find_logs, ERROR_PATTERNS
import re

mcp = FastMCP("regional-ocean-debugger-resources")


@mcp.resource("ocean://case/{case_dir}/params")
def case_params_resource(case_dir: str) -> str:
    """Parsed MOM_input + MOM_override parameters as KEY = VALUE pairs."""
    mom_input, mom_override = _find_mom6_params(case_dir)
    if not mom_input:
        return f"No MOM_input found in {case_dir}"
    params = _parse_mom_params(mom_input)
    if mom_override:
        params.update(_parse_mom_params(mom_override))
    return "\n".join(f"{k} = {v}" for k, v in sorted(params.items()))


@mcp.resource("ocean://case/{case_dir}/errors")
def case_errors_resource(case_dir: str) -> str:
    """Error lines extracted from the most recent run logs."""
    logs = _find_logs(case_dir, "all")
    if not logs:
        return f"No log files in {case_dir}"

    findings = []
    for log in logs[:5]:
        try:
            text = log.read_text(errors="replace")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern, label in ERROR_PATTERNS:
                if pattern.search(line):
                    findings.append(f"[{label}] {log.name}:{lineno}: {line.strip()}")
                    break

    return "\n".join(findings[:200]) if findings else "No errors detected in recent logs."


@mcp.resource("ocean://knowledge/index")
def knowledge_index() -> str:
    """Summary of what's in the expert interview knowledge base."""
    jsonl = Path(__file__).parent / "data" / "transcripts" / "merged_for_finetuning.jsonl"
    if not jsonl.exists():
        return "Knowledge base not available — run: git submodule update --init data/transcripts"
    count = sum(1 for l in jsonl.read_text().splitlines() if l.strip())
    return (
        f"Knowledge base: {count} expert Q&A pairs\n"
        "Source: RegionalMOM6_InterviewTranscripts (private)\n"
        "Topics: MOM6 configuration, OBC, tides, bathymetry, stability, BGC, "
        "grid design, regional dynamics, diagnostics\n\n"
        "Use query_domain_knowledge(question) or get_parameter_advice(param) to search."
    )
