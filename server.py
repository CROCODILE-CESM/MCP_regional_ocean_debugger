"""
Regional Ocean Debugger MCP — post-run diagnostics and scientific guidance
for MOM6/CESM regional ocean model runs.

Domain knowledge is sourced from expert interview transcripts in data/transcripts/.
"""

from fastmcp import FastMCP

from tools.logs import read_run_log, find_errors, classify_error
from tools.params import read_mom6_params, diff_params
from tools.stability import check_cfl, suggest_timestep
from tools.diagnostics import read_diag_table, suggest_diagnostics
from tools.knowledge import query_domain_knowledge, get_parameter_advice

mcp = FastMCP("regional-ocean-debugger")

mcp.add_tool(read_run_log)
mcp.add_tool(find_errors)
mcp.add_tool(classify_error)
mcp.add_tool(read_mom6_params)
mcp.add_tool(diff_params)
mcp.add_tool(check_cfl)
mcp.add_tool(suggest_timestep)
mcp.add_tool(read_diag_table)
mcp.add_tool(suggest_diagnostics)
mcp.add_tool(query_domain_knowledge)
mcp.add_tool(get_parameter_advice)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
