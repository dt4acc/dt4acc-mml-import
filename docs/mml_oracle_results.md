# MML oracle comparison, 2026-10-26

Produced by scripts/mml_oracle/ao_oracle.m (MATLAB R2023b) and compare_ao_oracle.py; see ao_data_model.md.

## MAXIV R1: R1 1.500 GeV, production optics 2024, run period 2

32 families, 397 devices in the model, 397 devices answered by MML; families skipped by the model: none; energy 1.5 GeV.

| field | agree | differ | not given by MML | MML only (not in ao) |
|---|---:|---:|---:|---:|
| device present | 397 | 0 | 0 | 0 |
| common name | 397 | 0 | 0 | 0 |
| device name | 370 | 0 | 0 | 0 |
| status | 397 | 0 | 0 | 0 |
| element | 397 | 0 | 0 | 0 |
| position | 291 | 0 | 2 | 0 |
| monitor channel | 336 | 0 | 0 | 0 |
| monitor HW2PhysicsParams | 324 | 0 | 0 | 0 |
| AT index | 295 | 0 | 0 | 39 |
| setpoint channel | 256 | 0 | 0 | 0 |
| setpoint range | 271 | 0 | 0 | 0 |
| setpoint HW2PhysicsParams | 244 | 0 | 0 | 0 |

Differences in **AT index (MML only)** (first 6):

* BPM [1, 1]: [10]
* BPM [1, 2]: [15]
* BPM [1, 3]: [85]
* BPM [2, 1]: [10]
* BPM [2, 2]: [15]
* BPM [2, 3]: [85]

## ALS StorageRing: 1.9 GeV, TopOff

45 families, 1270 devices in the model, 1270 devices answered by MML; families skipped by the model: none; energy 1.89086196873342 GeV.

| field | agree | differ | not given by MML | MML only (not in ao) |
|---|---:|---:|---:|---:|
| device present | 1270 | 0 | 0 | 0 |
| status | 1270 | 0 | 0 | 0 |
| element | 1270 | 0 | 0 | 0 |
| position | 1156 | 0 | 0 | 0 |
| monitor channel | 1152 | 0 | 0 | 0 |
| monitor HW2PhysicsParams | 712 | 0 | 0 | 0 |
| AT index | 877 | 0 | 0 | 0 |
| common name | 301 | 0 | 0 | 0 |
| setpoint channel | 523 | 0 | 0 | 0 |
| setpoint range | 523 | 0 | 0 | 0 |
| setpoint HW2PhysicsParams | 54 | 0 | 0 | 0 |

Model warnings:

* SQEPU: Position has 6 entries for 7 devices; not used
* BBPMx: Position has 22 entries for 24 devices; not used
* BBPMy: Position has 22 entries for 24 devices; not used
