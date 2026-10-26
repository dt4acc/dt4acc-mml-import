"""Write the facility model of an ``ao`` (+ ``ad``) export as JSON.

    python -m dt4acc_mml_import.model ao.json --ad ad.json -o facility.json
"""

import argparse
import sys

from .build import load_facility


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ao", help="JSON of the object returned by getao()")
    parser.add_argument("--ad", help="JSON of the object returned by getad()")
    parser.add_argument("-o", "--output", help="output file (default: stdout)")
    args = parser.parse_args(argv)
    facility = load_facility(args.ao, args.ad)
    txt = facility.model_dump_json(indent=1)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fp:
            fp.write(txt)
    else:
        sys.stdout.write(txt)
    sys.stderr.write(
        f"{len(facility.families)} families, {len(facility.devices())} devices, "
        f"{len(facility.provenance.skipped_families)} families skipped, "
        f"{len(facility.provenance.warnings)} warnings\n"
    )


if __name__ == "__main__":
    main()
