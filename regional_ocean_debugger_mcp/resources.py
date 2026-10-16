"""Resource handlers for ocean:// URIs."""

from regional_ocean_debugger_mcp.tools.knowledge import _load_knowledge
from regional_ocean_debugger_mcp.tools.logs import find_errors
from regional_ocean_debugger_mcp.tools.params import read_mom6_params

try:
    from fastmcp.resources import ResourceSecurity

    # fastmcp>=4 screens template params and rejects absolute paths by default,
    # but case_dir *is* an absolute case path.
    _CASE_DIR_OPTS = {"security": ResourceSecurity(exempt_params={"case_dir"})}
except ImportError:  # older fastmcp: no screening
    _CASE_DIR_OPTS = {}


def register_resources(mcp):

    # {case_dir*} spans "/"-separated segments: ocean://case//abs/case_dir/params
    @mcp.resource("ocean://case/{case_dir*}/params", **_CASE_DIR_OPTS)
    def case_params_resource(case_dir: str) -> str:
        """MOM_input + MOM_override parameters as KEY = VALUE (read_mom6_params)."""
        return read_mom6_params(case_dir)

    @mcp.resource("ocean://case/{case_dir*}/errors", **_CASE_DIR_OPTS)
    def case_errors_resource(case_dir: str) -> str:
        """Error lines from the latest run's logs (find_errors)."""
        return find_errors(case_dir)

    @mcp.resource("ocean://knowledge/index")
    def knowledge_index() -> str:
        """Summary of what's in the expert interview knowledge base."""
        pairs = _load_knowledge()
        if not pairs:
            return (
                "Knowledge base not available — run: "
                "git submodule update --init data/transcripts"
            )
        return (
            f"Knowledge base: {len(pairs)} expert Q&A pairs\n"
            "Source: AidanJanney/RegionalOceanModelingInterviews\n"
            "Topics: MOM6 configuration, OBC, tides, bathymetry, stability, BGC, "
            "grid design, regional dynamics, diagnostics\n\n"
            "Use query_domain_knowledge(question) or get_parameter_advice(param) to search."
        )
