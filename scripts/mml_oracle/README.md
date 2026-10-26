# Exporting a facility's Matlab Middle Layer (MML) data

MATLAB scripts that run **inside your facility's MML** and write its
configuration as JSON: the AO (`getao`), the AD (`getad`), the AT lattice
(`THERING`) and, per device, what the middle layer's own functions return.
The python package of this repository builds its data model from these
files, and checks itself against the middle layer's answers.

## What you need

* MATLAB R2019a or later (`jsonencode`, `matlab -batch`); tested with R2023b.
  GNU Octave is untested.
* Your facility's MML tree, i.e. the directory that contains `mml/` and
  `machine/<YOUR MACHINE>/`, with the AT version your lattice files need.
* For the python part: python >= 3.11 and this package (see the top level
  [README](../../README.md)).

The scripts run the middle layer in **simulator mode** on the model
(`setoperationalmode` / `getsp(..., 'Model')`); they do not connect to your
control system.

## Files

| file | what |
|---|---|
| `ao_oracle.m` | writes `<prefix>_ao.json`, `<prefix>_ad.json`, `<prefix>_oracle.json` |
| `dump_ring.m` | writes `<prefix>_ring.json` (the lattice) |
| `mml_session.m` | starts the MML for one machine and mode; used by both |
| `mml_sanitize.m`, `mml_write_json.m` | make MML values JSON encodable, write them |
| `compare_ao_oracle.py` | python: the data model against `<prefix>_oracle.json` |

## 1. Find your machine's names and mode

The scripts call `setpathmml(MACHINE, SUBMACHINE, 'StorageRing', MML_ROOT)`
and then `setoperationalmode(MODE)`, exactly as you start your MML by hand.
Take the values from how you do that, or from your machine's
`setoperationalmode.m` (the mode numbers and their names are listed there).
Examples:

| facility | MML_MACHINE | MML_SUBMACHINE | MML_MODE |
|---|---|---|---|
| ALS (public MML) | `ALS` | `StorageRing` | `1` (TopOff) |
| MAX IV 1.5 GeV ring | `MAXIV` | `R1` | `20` (production optics 2024) |

`MML_MODE` may be left out: the mode MML starts in is used then.

## 2. Run the export

Copy the `.m` files of this directory to a working directory (outputs are
written there). From a shell:

```bash
cd my_export
export MML_ROOT=/path/to/mml MML_MACHINE=ALS MML_SUBMACHINE=StorageRing MML_MODE=1 OUT_PREFIX=als
matlab -batch ao_oracle      # als_ao.json, als_ad.json, als_oracle.json
matlab -batch dump_ring      # als_ring.json
```

or inside a MATLAB session (Windows, or no shell at hand):

```matlab
cd my_export
setenv('MML_ROOT', 'C:\mml'); setenv('MML_MACHINE', 'ALS');
setenv('MML_SUBMACHINE', 'StorageRing'); setenv('MML_MODE', '1'); setenv('OUT_PREFIX', 'als');
ao_oracle
dump_ring
```

Each script takes a few minutes, mostly for starting the MML and loading the mode.

### Outputs

* `<prefix>_ao.json`: the full AO as `getao` returns it. Function handles are
  written as their text (`@amp2k` -> `"amp2k"`), MATLAB objects (e.g.
  `inline` functions in an `ATParameterGroup`) as `"<inline>"`, NaN as `null`.
* `<prefix>_ad.json`: `getad`, without the `Directory` field (local paths).
* `<prefix>_ring.json`: one object per `THERING` element, in order, with every
  field the element has, its 1-based `Index` and `Class`: the element's own
  where the lattice sets it, else AT's `atguessclass` where that function is
  on the path (older AT versions lack it; `Class` is then missing). The AO's
  `ATIndex` and `ATParameterGroup.ElemIndex` are indices into this list.
* `<prefix>_oracle.json`: for every device of every family (`family2dev(fam,
  0)`, so also devices marked bad), what the middle layer returns:
  `family2common`, `DeviceName`, `Status`, `dev2elem`, `getspos`,
  `family2channel` (Monitor, Setpoint), `Range`, `HWUnits`, `PhysicsUnits`,
  `HW2PhysicsFcn`, `HW2PhysicsParams` (via `getfamilydata(..., DeviceList)`),
  `family2atindex`. Values a family does not have are `[]`.

Check the files before you share them: they contain your facility's channel
names, and the AD may hold other site specific fields.

## 3. Build the data model (python)

```bash
pip install -e /path/to/dt4acc-mml-import
python -m dt4acc_mml_import.model als_ao.json --ad als_ad.json -o als_facility.json
```

or

```python
from dt4acc_mml_import.model import load_facility
facility = load_facility("als_ao.json", "als_ad.json")
facility.device("QF", (1, 1)).setpoint.channel.name
```

See [docs/ao_data_model.md](../../docs/ao_data_model.md) for the model.

## 4. Check the model against your middle layer

```bash
python scripts/mml_oracle/compare_ao_oracle.py my_export/als -o report.md
```

builds the model from `als_ao.json` / `als_ad.json` and compares each device
with `als_oracle.json`, field by field: names, device names, status, element
numbers, positions, channels, ranges, conversion parameter rows, AT
indices. The report lists counts per field (agree / differ / not given by
MML / only in MML) and the first differences. A difference means the model
reads the AO differently from how your middle layer does: please report it
with the report and your `_ao.json`.

Results so far: [docs/mml_oracle_results.md](../../docs/mml_oracle_results.md)
(MAX IV R1, ALS: no differences).

## Facility specific notes

* **Financial Toolbox**: its `@drift` class shadows AT's `drift()`;
  `mml_session.m` removes it from the path when present.
* **Files your lattice needs but your MML tree lacks**: put them in the
  working directory, it is first on the path. MAX IV R1 needs `PC.mat`
  (physical constants; build it from MAX IV's `fundamental_physical_constants.m`:
  `PC.c` speed of light, `PC.me_eV` electron mass in eV) and AT 2.0's
  `PhysConstant.m`, and a newer AT (2.5) than the bundled one next to the MML root.
* **AT version**: the lattice files of a mode may need a newer AT than the one
  in the MML tree (`atSetRingProperties` missing is the typical error).
* A family whose functions fail in simulator mode (e.g. MAX IV `SHUNT`
  setpoints) still appears in the AO; the oracle records `[]` for what failed.

## Troubleshooting

* `set MML_ROOT, MML_MACHINE and MML_SUBMACHINE`: the environment variables
  are not visible to MATLAB; use `setenv` in the session.
* `setpathmml` errors: the machine / submachine names do not match a
  directory under `machine/`.
* `jsonencode` errors: a value type `mml_sanitize.m` does not handle;
  please report the family and field.
