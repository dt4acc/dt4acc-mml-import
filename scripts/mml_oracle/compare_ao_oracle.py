"""Compare the facility model with the middle layer's own answers

Input: the files ao_oracle.m wrote in one middle layer session,
<prefix>_ao.json, <prefix>_ad.json, <prefix>_oracle.json. The model is
built from the ao / ad; each device is then compared, field by field, with
what the middle layer's accessors returned for it (family2common,
DeviceName, Status, dev2elem, getspos, family2channel, Range,
HW2PhysicsParams, family2atindex).

    python scripts/mml_oracle/compare_ao_oracle.py DIR/maxiv_r1 DIR/als -o report.md
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from dt4acc_mml_import.model import build_facility

#: differences listed per field in the report
MAX_EXAMPLES = 6
#: a (low, high) range
_PAIR_LEN = 2


def flat(x):
    """all numbers of a nested list, None / NaN left out"""
    if isinstance(x, (list, tuple)):
        return [v for e in x for v in flat(e)]
    if isinstance(x, bool):
        return [float(x)]
    if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x)):
        return [float(x)]
    return []


def text(x):
    if isinstance(x, str):
        return x.strip() or None
    if isinstance(x, list) and len(x) == 1 and isinstance(x[0], str):
        return x[0].strip() or None
    return None


def same_numbers(a, b, rel=1e-12):
    return len(a) == len(b) and all(math.isclose(x, y, rel_tol=rel, abs_tol=1e-15) for x, y in zip(a, b, strict=True))


def compare(prefix: str):  # noqa: C901, PLR0912, PLR0915 -- one flat list of field checks
    ao = json.loads(Path(f"{prefix}_ao.json").read_text())
    ad = json.loads(Path(f"{prefix}_ad.json").read_text())
    oracle = json.loads(Path(f"{prefix}_oracle.json").read_text())
    facility = build_facility(ao, ad, ao_source=f"{Path(prefix).name}_ao.json")
    counts = defaultdict(lambda: {"agree": 0, "differ": 0, "not given by MML": 0, "MML only": 0})
    examples = defaultdict(list)

    def check(field, mml, ours, equal, where):
        if mml is None or mml == []:
            counts[field]["not given by MML"] += 1
            return
        if equal:
            counts[field]["agree"] += 1
        else:
            counts[field]["differ"] += 1
            if len(examples[field]) < MAX_EXAMPLES:
                examples[field].append(f"{where}: MML {str(mml)[:120]} / model {str(ours)[:120]}")

    for rec in oracle["devices"]:
        fam, dev = rec["family"], tuple(int(v) for v in rec["device"])
        where = f"{fam} {list(dev)}"
        try:
            d = facility.device(fam, dev)
        except KeyError:
            counts["device present"]["differ"] += 1
            examples["device present"].append(f"{where}: not in model")
            continue
        counts["device present"]["agree"] += 1
        if d.name_from_export:
            check("common name", text(rec["common_name"]), d.name, text(rec["common_name"]) == d.name, where)
        mml_dn = text(rec["device_name"])
        if mml_dn not in (None, "Non-existant"):
            check("device name", mml_dn, d.device_name, mml_dn == d.device_name, where)
        st = flat(rec["status"])
        check("status", st or None, d.status, bool(st) and bool(st[0]) == d.status, where)
        el = flat(rec["element"])
        check("element", el or None, d.element, bool(el) and int(el[0]) == d.element, where)
        pos = flat(rec["position"])
        if len(pos) > 1:
            # getspos handed back the whole family (MAX IV R1 KICKER)
            counts["position"]["not given by MML"] += 1
        elif pos and d.position is not None:
            check("position", pos[0], d.position, math.isclose(pos[0], d.position, abs_tol=1e-9), where)
        elif pos:
            check("position", pos[0], None, False, where)
        for sig, key in (("monitor", "monitor_channel"), ("setpoint", "setpoint_channel")):
            mml = text(rec[key])
            ours = getattr(d, sig).channel.name if getattr(d, sig) else None
            if mml is not None:
                check(f"{sig} channel", mml, ours, mml == ours, where)
        rng = rec["setpoint_range"]
        if isinstance(rng, list) and len(rng) == _PAIR_LEN and d.setpoint:
            lim = d.setpoint.limits
            ours = [lim.lower, lim.upper] if lim else None
            check("setpoint range", rng, ours, ours is not None and flat(rng) == flat(ours), where)
        for sig, key in (("setpoint", "setpoint_hw2physics_params"), ("monitor", "monitor_hw2physics_params")):
            mml = flat(rec[key])
            s = getattr(d, sig)
            ours = flat(s.conversion.rows) if s and s.conversion else []
            if mml:
                check(f"{sig} HW2PhysicsParams", mml, ours, same_numbers(mml, ours), where)
        mml_at = sorted({int(v) for v in flat(rec["at_index"]) if v})
        if mml_at:
            ours = sorted({t.at_index for t in d.lattice})
            if not ours and "AT" not in ao[fam]:
                # no AT in the ao: family2atindex looked it up in the lattice
                counts["AT index"]["MML only"] += 1
                if len(examples["AT index (MML only)"]) < MAX_EXAMPLES:
                    examples["AT index (MML only)"].append(f"{where}: {mml_at}")
            else:
                check("AT index", mml_at, ours, set(mml_at) <= set(ours), where)
    return facility, oracle, counts, examples


def report(prefixes):
    lines = []
    for prefix in prefixes:
        facility, oracle, counts, examples = compare(prefix)
        m = facility.machine
        lines += [
            f"## {oracle['machine']} {oracle['submachine']}: {oracle.get('operational_mode')}",
            "",
            f"{len(facility.families)} families, {len(facility.devices())} devices in the model, "
            f"{len(oracle['devices'])} devices answered by MML; families skipped by the model: "
            f"{facility.provenance.skipped_families or 'none'}; energy {m.energy if m else None} GeV.",
            "",
            "| field | agree | differ | not given by MML | MML only (not in ao) |",
            "|---|---:|---:|---:|---:|",
        ]
        for field, c in counts.items():
            lines.append(f"| {field} | {c['agree']} | {c['differ']} | {c['not given by MML']} | {c['MML only']} |")
        for field, ex in examples.items():
            lines += ["", f"Differences in **{field}** (first {len(ex)}):", ""] + [f"* {e}" for e in ex]
        if facility.provenance.warnings:
            lines += ["", "Model warnings:", ""] + [f"* {w}" for w in facility.provenance.warnings]
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("prefixes", nargs="+", help="path prefix of the ao_oracle.m output, e.g. out/maxiv_r1")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    txt = report(args.prefixes)
    if args.output:
        Path(args.output).write_text(txt)
    sys.stdout.write(txt + "\n")


if __name__ == "__main__":
    main()
