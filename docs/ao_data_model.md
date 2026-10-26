# A concrete data model for the middle layer `ao` / `ad`

Goal: one model that holds everything a client needs from a facility's
Matlab Middle Layer (MML) configuration (digital twin set ups, a python
middle layer, measurement scripts), read from the exported `getao()` /
`getad()` objects and checked against the middle layer itself.

## Two layers

| layer | module | what |
|---|---|---|
| raw | `dt4acc_mml_import.data_model.mml_ao` | the `ao` as exported: MML field names and nesting, family wide arrays, normalized at parse time. Nothing is interpreted. |
| concrete | `dt4acc_mml_import.model` | `Facility` -> `Family` -> `Device`: one record per device, everything resolved for that device. |

```python
from dt4acc_mml_import.model import DeviceKind, load_facility

facility = load_facility("ao_mls.json")
q = facility.device("Q1", (1, 1))
q.device_name                      # 'Q1P2K1RP'  (power supply)
q.setpoint.channel.name            # 'Q1P2K1RP:setCur'
q.setpoint.limits                  # lower=0.0 upper=65.55
q.setpoint.conversion              # function='amp2k' rows=[[0.138213, 0.0]] layout='per_device'
q.lattice                          # [LatticeTarget(at_index=22, at_type='QUAD')]
facility.devices(DeviceKind.bpm)   # all BPMs
```

Command line: `python -m dt4acc_mml_import.model ao.json --ad ad.json -o facility.json`.

## The concrete model

`Facility`
* `machine: MachineInfo` (from `ad`): machine, submachine, type, operational
  mode, AT model, energy, injection energy, harmonic number, circumference, MCF
* `families: {name: Family}`
* `provenance`: source files, families the raw model could not validate (with
  the reason), inconsistencies found (e.g. a `Position` list shorter than the
  `DeviceList`)

`Family`: name, `MemberOf`, `FamilyType`, `classification` (kind:
quadrupole, skew quadrupole, sextupole, octupole, bend, steerer, bpm, rf,
dcct, tune, kicker, insertion device, unknown; plane; and *which* `MemberOf`
tag decided it), `devices`

`Device`

| field | MML source |
|---|---|
| `family`, `device` | family name, `DeviceList(i,:)` |
| `element` | `ElementList(i)` |
| `name`, `name_from_export` | `CommonNames(i)`; else `<family>_<sector>_<index>` (ALS names only correctors) |
| `status` | `Status(i)` |
| `position` | `Position(i)` (s in m) |
| `device_name` | `DeviceName(i)` (Tango facilities: the power supply); else the EPICS channel without `:attribute` |
| `monitor`, `setpoint` | `Monitor` / `Setpoint`: `ChannelNames(i)`, access read / write, `SpecialFunctionGet/Set`, `HWUnits`, `PhysicsUnits`, `Units` (default), `Range(i,:)` (limits), `Tolerance(i)`, conversion |
| `conversion` | `HW2PhysicsFcn` / `Physics2HWFcn` names, this device's rows of `HW2PhysicsParams` (and `Physics2HWParams` where they differ), and their `layout` |
| `lattice` | `AT.ATParameterGroup{i}` (element, field, field index) and `AT.ATIndex(i,:)` with `AT.ATType`; 1-based as in MML |
| `other_signals` | every further sub-object with `ChannelNames` (`Sum`, `Voltage`, `Resistance`, `VoltageCtrl`, ...) |

Conversions are recorded, not interpreted. Without function MML's default
holds, `physics = gain * hardware`, `gain = rows[0][0]` (`Conversion.gain`).
With a function (`amp2k`, `amp2field`, ...) the rows are its parameters for
this device; what they mean is facility specific (MLS: polynomial and scale;
MAX IV: excitation tables) and belongs to a per facility interpretation on
top of this model.

Per device rows (`layout`), as the middle layer hands them out:
`per_device` (one row per device), `shared` (one row for all), `strided`
(k rows per device: device i gets rows i, n+i, 2n+i, ...; MAX IV tables:
currents, fields; R1 BEND: currents, B L, B' L), `unknown` (all rows kept).

## Raw layer additions

Found with the exports and the MML oracle below: `ATParameter.FieldName` /
`FieldIndex` optional (MAX IV R1 SHUNT has only `ElemIndex`);
`SpecialFunctionGet/Set` (also on `AT`), given as name or, from a `.mat`
(ALS), as function handle struct; `Tolerance`; a numeric `HW2PhysicsFcn`
(MAX IV `1`) means no function; further signals kept as extra fields
(`FamilyInfoCollection.other_signals()`); `load_file` unwraps a top level
`ao`.

Compared with `bact-mml-importer` (the original importer, from ALS): its
pydantic `mml_ao.py` validated 2 of 16 MLS, 10 of 32 MAX IV R1 and 10 of 39
R3 families of the exports (strict types for gain + offset rows, bare
function names, `[NaN NaN]` ranges, nested `MemberOf`); its dataclass model
(`family.py`, `app/families.py`) had the right shape (machine info, device
info with conversion and limits) but no validation, no `MemberOf`, no
`DeviceName`, no `ATParameterGroup`, and silent padding where list lengths
differ.

## Tests

`tests/test_facility_model.py`, on the real exports in
`mml-exported-data-sets` (`MML_EXPORTS_DIR`): BESSY II, MLS, MAX IV 3 GeV,
MAX IV R1 (both files)

* every family validates, every device is built;
* device values checked against the export: MLS Q1 / HCM / BPMx / RF / TUNE,
  R1 SQFI / HCM / SHUNT, BESSY II machine data and quadrupole supplies, the
  3 GeV inconsistency report;
* synthetic: strided rows, ALS shapes from a `.mat` (function handle structs,
  empty arrays, blank padded names).

All tests pass (`hatch run test`), `ruff check` is clean.

## Checked against the middle layer itself

`scripts/mml_oracle/ao_oracle.m` runs in the facility's MML (MATLAB, simulator
mode) and writes, from one session, the `ao`, the `ad` and what MML's own
accessors return for every device: `family2common`, `DeviceName`, `Status`,
`dev2elem`, `getspos`, `family2channel`, `Range`, `HW2PhysicsParams` (via
`getfamilydata(..., DeviceList)`), `family2atindex`.
`scripts/mml_oracle/compare_ao_oracle.py` builds the model from that `ao` /
`ad` and compares each device field by field:

```
MML_ROOT=<mml> MML_MACHINE=MAXIV MML_SUBMACHINE=R1 MML_MODE=20 OUT_PREFIX=maxiv_r1 matlab -batch ao_oracle
python scripts/mml_oracle/compare_ao_oracle.py maxiv_r1 als -o report.md
```

Run 2026-10-26 with MATLAB R2023b: MAX IV's MML, R1, operational mode 20
(1.5 GeV, production optics 2024) and ALS's public MML, TopOff (1.9 GeV).
Result: [mml_oracle_results.md](mml_oracle_results.md)

| | devices | checks (device x field) | agree | differ |
|---|---:|---:|---:|---:|
| MAX IV R1 | 397 | 3 975 | 3 975 | 0 |
| ALS | 1270 | 9 108 | 9 108 | 0 |

What the comparison found and fixed on the way:

* MAX IV R1 BEND: 3 table rows per device (75 rows for 25 devices); MML hands
  device i the rows i, 25+i, 50+i: `strided`, not only 2 rows per device.
* ALS: channel names padded with blanks (MATLAB char matrix); stripped.
* MAX IV R1 CAVITY / LANDAU: one `ATIndex` for two devices; shared.

Not differences of the model, reported separately:

* R1 BPM and three insertion devices (39 devices): no `AT` in the `ao`;
  MML's `family2atindex` looks them up in the lattice. The model does not
  hold the lattice.
* R1 KICKER: `getspos` returns both positions for each device; the model takes
  `Position(i)`.

## Not covered

* Interpreting conversion functions: per facility, on top of this model.
* The AT lattice itself (`THERING`): no element lengths / classes, no split of
  one parameter group into physical magnets (MAX IV R1 SQFI: one supply,
  12 magnets x 4 slices); a lattice model would sit beside this one.
* Families whose MML behaviour is computed, not configured (MAX IV PFS, BEND
  energy coupling `bend2gev`).
* BESSY II / MLS: checked against their exports, not yet against their MML.
