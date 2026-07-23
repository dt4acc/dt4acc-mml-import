# Targets for dt4acc-mml-import

## Project Structure
- Root: `dt4acc-mml-import/` (directory name with hyphens)
- Package: `dt4acc_mml_import/` (PEP 625 compatible, underscores)
- Layout follows [hatchling PEP 622 conventional layout](https://hatch.pypa.io/1.6/config/#project):
  - Project root: `dt4acc-mml-import/`
  - Source: `src/dt4acc_mml_import/`
  - Tests: `tests/`
  - Scripts: `scripts/`
  - Data: `example_data/`

## Build & Development
- Build tool: **hatchling** via `pyproject.toml`
- Dev commands:
  ```bash
  hatch build           # Build wheels
  hatch run test        # pytest
  hatch run lint        # ruff check .
  hatch run format      # ruff format .
  ```
- Dependencies (default): pydantic, scipy, numpy — no other deps without permission

## Pydantic Model Conventions
- **All models inherit from `pydantic.BaseModel`**
- **Normalize at parse time** using pydantic validators (`@field_validator`) so callers always receive uniform types
- **No union types for sequences** — all sequence fields resolve to `Sequence[T]` internally
- Fields that accept `int | Sequence[int] | Sequence[Sequence[int]]` normalize to `Sequence[Sequence[int]]`
- `str | list[str]` normalizes to `Sequence[str]`
- Numeric types normalizing to `Sequence[float]` / `Sequence[int]` where applicable
- Use Pydantic's `@field_validator` (Pydantic v2) or `@root_validator` for normalization

## Naming Conventions
- Package: `dt4acc_mml_import` (underscores, PEP 625 compatible)
- Data models: camelCase field names preserved from original MATLAB schema
- Model classes: PascalCase (e.g., `ATElementsInfo`, `FamilyInfoCollection`)
- Field names: camelCase to match original schema (e.g., `ATIndex`, `ChannelNames`, `HW2PhysicsParams`)

## Existing MATLAB Example Data
- `ao_as_loaded_from_mml.mat` is reference test data to be used for testing

## Refactoring Source (unchanged original for reference)
- Reference: `orig/bact-mml-importer/bact_mml_json_importer/`
- Core Pydantic models: `orig/bact-mml-importer/bact_mml_json_importer/data_model/mml_ao.py`
- Normalization utilities: `orig/bact-mml-importer/bact_mml_json_importer/data_model/utils.py`
- Tests: `orig/bact-mml-importer/bact_mml_json_importer/tests/test_data_normalizer.py`

## API Design Decisions
- **No API compatibility** with the original `bact_mml_json_importer`
- Internal normalization means all consumers work with uniform types
- Models produce the same JSON structure for serialization
- Error handling: let Pydantic's validation/errors propagate
