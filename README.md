# dt4acc-mml-import

Read a facility's Matlab Middle Layer (MML) configuration into python: the
AO (`getao`), the AD (`getad`) and the AT lattice, exported from the MML as
JSON, as validated pydantic models.

* `dt4acc_mml_import.data_model`: the AO as exported, field names and
  nesting as in MML (family wide arrays), normalized at parse time
* `dt4acc_mml_import.model`: one record per device (`Facility` -> `Family` ->
  `Device`): names, status, position, power supply, monitor / setpoint
  channels, units, limits, conversion parameters, lattice targets, machine
  data. Design and field by field MML sources: [docs/ao_data_model.md](docs/ao_data_model.md)

## From your MML to the model

1. **Export** (MATLAB, in your MML): [scripts/mml_oracle/README.md](scripts/mml_oracle/README.md)
   ```bash
   export MML_ROOT=/path/to/mml MML_MACHINE=ALS MML_SUBMACHINE=StorageRing MML_MODE=1 OUT_PREFIX=als
   matlab -batch ao_oracle   # als_ao.json, als_ad.json, als_oracle.json
   matlab -batch dump_ring   # als_ring.json
   ```
2. **Model** (python):
   ```bash
   pip install -e .
   python -m dt4acc_mml_import.model als_ao.json --ad als_ad.json -o als_facility.json
   ```
   ```python
   from dt4acc_mml_import.model import DeviceKind, load_facility

   facility = load_facility("als_ao.json", "als_ad.json")
   for q in facility.devices(DeviceKind.quadrupole):
       print(q.name, q.device_name, q.setpoint.channel.name, q.setpoint.limits)
   ```
3. **Check** the model against your middle layer:
   ```bash
   python scripts/mml_oracle/compare_ao_oracle.py als -o report.md
   ```

Exports made otherwise (MATLAB's `jsonencode` of `getao`) load the same way:
`load_facility("ao.json")`.

## Development

```bash
hatch run test      # pytest; real exports via MML_EXPORTS_DIR
hatch run lint      # ruff
```

The tests on real data read the exports in the `mml-exported-data-sets`
repository (`MML_EXPORTS_DIR=/path/to/it`) and are skipped without it.

## Layout

| path | what |
|---|---|
| `src/dt4acc_mml_import/data_model/` | AO as exported (`load`, `load_strict`, `load_file`) |
| `src/dt4acc_mml_import/model/` | per device model (`load_facility`, `build_facility`) |
| `scripts/mml_oracle/` | MATLAB export scripts, comparison with the middle layer |
| `docs/` | design, results of the comparison with MML |
| `tests/` | pytest |
