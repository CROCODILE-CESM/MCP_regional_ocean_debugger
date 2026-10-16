"""Read a CESM case's XML variables without running ./xmlquery.

./xmlquery refuses to run on any host other than the case's MACH ("Current
machine casper does not match case machine derecho"), so it can't find a
Derecho case's RUNDIR from a Casper login node. The values live in the case's
env_*.xml files: read them and expand the $VAR, ${VAR} and $ENV{VAR}
references CIME uses (e.g. RUNDIR = $CIME_OUTPUT_ROOT/$CASE/run).
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

_REF = re.compile(r"\$ENV\{(\w+)\}|\$\{(\w+)\}|\$(\w+)")


def case_xml_vars(case_dir: str, names: list[str]) -> dict[str, str]:
    """Return {name: expanded value} for each of names set in the case's env_*.xml."""
    entries = {}
    for f in sorted(Path(case_dir).expanduser().glob("env_*.xml")):
        try:
            root = ET.parse(f).getroot()
        except (ET.ParseError, OSError):
            continue
        for e in root.iter("entry"):
            if "value" in e.attrib:
                entries.setdefault(e.get("id"), e.get("value"))

    def expand(value, depth=0):
        def sub(m):
            if m.group(1):
                return os.environ.get(m.group(1), m.group(0))
            name = m.group(2) or m.group(3)
            if name in entries and depth < 10:
                return expand(entries[name], depth + 1)
            return m.group(0)

        return _REF.sub(sub, value)

    return {n: expand(entries[n]) for n in names if n in entries}


def case_dir_var(case_dir: str, name: str) -> Path | None:
    """A directory-valued case variable (RUNDIR, DOUT_S_ROOT), if it exists."""
    value = case_xml_vars(case_dir, [name]).get(name)
    if not value or "$" in value:
        return None
    path = Path(value)
    return path if path.is_dir() else None
