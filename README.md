# regional-ocean-debugger-mcp

MCP server for debugging regional ocean (MOM6 + CESM) model runs.

Combines practical log analysis tools with a searchable knowledge base of expert interview transcripts, giving an LLM agent both the ability to inspect model output files and access to domain-expert guidance.

## Tools

| Tool | Purpose |
|------|---------|
| `read_run_log(case_dir, component, lines)` | Read recent CESM/MOM6 run log lines |
| `find_errors(case_dir)` | Scan all logs for FATAL/NaN/CFL/etc. |
| `classify_error(error_text)` | Match error against known MOM6 failure modes |
| `check_obc_forcing_status(inputdir)` | Check CrocoDash forcing outputs: OBC raw data + `ocn/` segment files, IC, WW3 spectra in `wav/`, CICE forcing in `ice/` |
| `read_mom6_params(case_dir, filter)` | Read MOM_input + MOM_override |
| `diff_params(case_dir_a, case_dir_b)` | Compare MOM_input between two cases |
| `check_cfl(case_dir)` | Evaluate CFL stability from MOM_input timestep settings |
| `suggest_timestep(resolution_deg)` | Recommend DT and DT_THERM for a given resolution |
| `read_diag_table(case_dir)` | Parse enabled MOM6 diagnostics |
| `suggest_diagnostics(symptoms)` | Suggest useful diagnostics for a given problem |
| `query_domain_knowledge(question)` | Search expert interview knowledge base |
| `get_parameter_advice(param_name)` | Look up guidance for a specific MOM6 parameter |
| `read_cesm_timing(case_dir)` | Summarise CIME's `timing/cesm_timing.*` throughput/cost file |

## Resources

| URI | Content |
|-----|---------|
| `ocean://case/{case_dir*}/params` | MOM_input + MOM_override as KEY = VALUE (same as `read_mom6_params`) |
| `ocean://case/{case_dir*}/errors` | Error lines from the latest run's logs (same as `find_errors`) |
| `ocean://knowledge/index` | Summary of knowledge base contents |

`{case_dir*}` takes the case path as-is, slashes included, e.g.
`ocean://case//glade/u/home/<user>/croc_cases/my_case/errors`.

## Knowledge Base

Domain knowledge comes from expert interviews on regional MOM6 modelling (private repo:
`AidanJanney/RegionalOceanModelingInterviews`). Topics include:
OBC setup, tidal forcing, bathymetry, stability, BGC, grid design, and regional ocean dynamics.

The transcripts are a git submodule in `data/transcripts/`. After cloning this repo:

```bash
git submodule update --init data/transcripts
```

## Setup

```bash
pip install -e .
# with the transcripts submodule:
git submodule update --init data/transcripts
```

## Running

```bash
regional-ocean-debugger-mcp
# or
python server.py
```

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "ocean-debugger": {
      "command": "python",
      "args": ["/path/to/MCP_regional_ocean_debugger/server.py"]
    }
  }
}
```

## Design

- **Stateless**: reads from the filesystem per call
- **No ML dependencies**: knowledge search is keyword-based (fast, transparent, works without GPU)
- **Composable**: use `find_errors` → `classify_error` → `query_domain_knowledge` in sequence for triage
- **Private data**: transcripts submodule is private; do not make public without authorisation

## CESM / MOM6 paths on Derecho

Cases: `~/croc_cases/`  
Run dir: the case's `RUNDIR` (default `$CIME_OUTPUT_ROOT/$CASE/run`, read from `env_run.xml`)  
MOM_input: `RUNDIR/MOM_input` or `<case_dir>/Buildconf/momconf/MOM_input`  
diag_table: `RUNDIR/diag_table` or `<case_dir>/Buildconf/momconf/diag_table`
