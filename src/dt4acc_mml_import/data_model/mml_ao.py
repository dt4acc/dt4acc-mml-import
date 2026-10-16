"""
Pydantic models for MML AO (Accelerator Objects) following DT4ACC specifications.

This module contains Pydantic models that represent the data structures from the
MATLAB Middle Layer accelerator objects with proper validation and normalization.

All normalizing validators run in ``mode="before"``: MATLAB's JSON export writes
a one-element array as a bare scalar (``"mm"`` instead of ``["mm"]``), and a
default ("after") validator never sees such a value because pydantic rejects it
against the declared sequence type first.
"""
import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeAlias

from pydantic import BaseModel, field_validator

logger = logging.getLogger("dt4acc-mml-importer")


# Type definitions for nested sequences
StrSequence: TypeAlias = Sequence[str]
FloatSequence: TypeAlias = Sequence[float]
IntSequence2D: TypeAlias = Sequence[Sequence[int]]
FloatSequence2D: TypeAlias = Sequence[Sequence[float]]
DeviceIndex: TypeAlias = tuple[int, int]
#: MATLAB exports NaN / +-Inf limits as JSON null, hence optional bounds.
RangePair: TypeAlias = tuple[float | None, float | None]
Range: TypeAlias = RangePair  # kept for backwards compatibility
#: Conversion parameters, normalized to blocks -> rows -> values.
#: A MATLAB cell array of parameter sets becomes several blocks; a plain
#: numeric array becomes a single block whose rows are usually per device.
#: Rows may differ in length (e.g. tabulated curves of different sizes).
ParamBlocks: TypeAlias = Sequence[FloatSequence2D]


#: a (low, high) range or (sector, index) device pair
_PAIR_LEN = 2
#: depth of a MATLAB cell of parameter blocks (blocks -> rows -> values)
_BLOCKS_DEPTH = 3


def _as_str_sequence(v: Any) -> Any:
    """Bare string -> [string]; nested lists (a MATLAB cell inside a cell,
    e.g. ``["Magnet", ["IVU", "Undulator"]]``) are flattened."""
    if isinstance(v, str):
        return [v]
    if isinstance(v, (list, tuple)) and any(isinstance(e, (list, tuple)) for e in v):
        flat: list[Any] = []
        for e in v:
            flat.extend(_as_str_sequence(e) if isinstance(e, (list, tuple)) else [e])
        return flat
    return v


def _as_sequence(v: Any) -> Any:
    """Wrap a bare scalar into a one-element list; leave None and lists alone."""
    if v is None or isinstance(v, (list, tuple)):
        return v
    return [v]


def _depth(v: Any) -> int:
    if isinstance(v, (list, tuple)):
        return 1 + max((_depth(e) for e in v), default=0)
    return 0


def _as_block(v: Any) -> list[list[Any]]:
    """One numeric array (depth 0..2) -> rows of values."""
    depth = _depth(v)
    if depth == 0:
        return [[v]]
    if depth == 1:
        # a vector: one value per row (typically one per device)
        return [[e] if not isinstance(e, (list, tuple)) else list(e) for e in v]
    return [list(row) if isinstance(row, (list, tuple)) else [row] for row in v]


def normalize_param_blocks(v: Any) -> list[list[list[Any]]] | None:
    """Normalize HW2PhysicsParams / Physics2HWParams to blocks -> rows -> values.

    Observed export shapes: scalar gain; one gain per device; [ndev x 2]
    (BPM gain/offset); a MATLAB cell of blocks, e.g. MLS ``amp2k``
    ``{[ndev x ncoeff], [ndev]}`` or MAX IV ``{[2*ndev x npoints]}``.
    """
    if v is None:
        return None
    if _depth(v) >= _BLOCKS_DEPTH:
        return [_as_block(block) for block in v]
    return [_as_block(v)]


class ATParameter(BaseModel):
    """One entry of an ``ATParameterGroup``: which field of which AT element
    a device's setpoint writes to, e.g. ``PolynomB`` with MATLAB (1-based)
    ``FieldIndex`` ``[2]`` for a quadrupole gradient.
    """

    ElemIndex: int
    FieldName: str
    FieldIndex: Sequence[int]
    SavedValue: Any = None
    #: an anonymous-function string ("@(x)x") or an exported inline object
    Function: Any = None
    Args: Any = None
    DeviceList: DeviceIndex | None = None

    @field_validator("FieldIndex", mode="before")
    @classmethod
    def normalize_field_index(cls, v: Any) -> Any:
        """Normalize a bare index to a one-element sequence."""
        return _as_sequence(v)


class ATElementsInfo(BaseModel):
    """To which element does the device connect to.

    ``ATIndex`` is always a 2D sequence of integers after normalization (one
    row per device). Some exports (e.g. MAX IV 3 GeV) omit ``ATType`` /
    ``ATIndex`` and only carry ``ATParameterGroup``.
    """

    ATType: str | None = None
    ATIndex: IntSequence2D | None = None
    #: one group per device, each a sequence of AT fields the setpoint drives
    ATParameterGroup: Sequence[Sequence[ATParameter]] | None = None

    @field_validator("ATParameterGroup", mode="before")
    @classmethod
    def normalize_parameter_group(cls, v: Any) -> Any:
        """One entry per device -> a one-entry group per device."""
        if isinstance(v, dict):
            return [[v]]
        if isinstance(v, (list, tuple)):
            return [[g] if isinstance(g, dict) else g for g in v]
        return v

    @field_validator("ATIndex", mode="before")
    @classmethod
    def normalize_at_index(cls, v: Any) -> Any:
        """Normalize ATIndex to 2D sequence of integers (one row per device)."""
        if isinstance(v, int):
            return [[v]]
        if isinstance(v, (list, tuple)) and v and isinstance(v[0], int):
            return [[item] for item in v]
        return v

    def get_element_indices(self) -> IntSequence2D | None:
        """Return the normalized element indices."""
        return self.ATIndex


class ConversionFunctionHandle(BaseModel):
    """Function name and file name that does the conversion.

    Exports often carry only the function name; ``file`` and ``type`` are
    then unknown rather than guessed.
    """

    function: str
    file: str | None = None
    type: str | None = None

    @field_validator("file", "type", mode="before")
    @classmethod
    def normalize_empty(cls, v: Any) -> Any:
        """An empty MATLAB char array loads from .mat as ``[]``: treat as unknown."""
        if isinstance(v, (list, tuple)) and not v:
            return None
        return v


class ConversionFunction(BaseModel):
    """Conversion function with function handle."""

    function_handle: ConversionFunctionHandle


def _as_conversion_function(v: Any) -> Any:
    if isinstance(v, str):
        return {"function_handle": {"function": v}}
    return v


class MonitorDataModel(BaseModel):
    """Base model for monitor data with normalization."""

    #: absent for e.g. TUNE / PFS families
    ChannelNames: StrSequence | None = None
    MemberOf: StrSequence | None = None
    DataType: str | None = None
    Units: str | None = None
    HWUnits: StrSequence | None = None
    PhysicsUnits: StrSequence | None = None
    Mode: str | None = None
    MetaGain: FloatSequence | None = None
    PhysicalUnits: str | None = None
    HW2PhysicsParams: ParamBlocks | None = None
    Physics2HWParams: ParamBlocks | None = None
    HW2PhysicsFcn: ConversionFunction | None = None
    Physics2HWFcn: ConversionFunction | None = None

    @field_validator("ChannelNames", "MemberOf", "HWUnits", "PhysicsUnits", mode="before")
    @classmethod
    def normalize_str_sequences(cls, v: Any) -> Any:
        """Normalize a bare string to a one-element sequence of strings."""
        return _as_str_sequence(v)

    @field_validator("MetaGain", mode="before")
    @classmethod
    def normalize_meta_gain(cls, v: Any) -> Any:
        """Normalize MetaGain to sequence of floats."""
        return _as_sequence(v)

    @field_validator("HW2PhysicsParams", "Physics2HWParams", mode="before")
    @classmethod
    def normalize_params(cls, v: Any) -> Any:
        """Normalize conversion parameters to blocks -> rows -> values."""
        return normalize_param_blocks(v)

    @field_validator("HW2PhysicsFcn", "Physics2HWFcn", mode="before")
    @classmethod
    def normalize_conversion_function(cls, v: Any) -> Any:
        """Accept a bare function name as exported (e.g. ``"amp2k"``)."""
        return _as_conversion_function(v)

    def conversion_function_name(self) -> str | None:
        """Name of the HW -> physics conversion function, if any."""
        return self.HW2PhysicsFcn.function_handle.function if self.HW2PhysicsFcn else None


class SetpointDataModel(MonitorDataModel):
    """Setpoint data model extending monitor data."""

    Range: Sequence[RangePair] | None = None

    @field_validator("Range", mode="before")
    @classmethod
    def normalize_range(cls, v: Any) -> Any:
        """Normalize a single (low, high) pair to a sequence of pairs."""
        if isinstance(v, (list, tuple)) and len(v) == _PAIR_LEN and _depth(v) == 1:
            return [v]
        return v


class FamilyInfoCollection(BaseModel):
    """Collected info entries following Matlab Middle Layer ao object."""

    FamilyName: str | None = None
    FamilyType: str | None = None
    MemberOf: StrSequence
    CommonNames: StrSequence | None = None
    #: power-supply / device names where the lab exports them (e.g. MAX IV)
    DeviceName: StrSequence | None = None
    DeviceList: Sequence[DeviceIndex]
    ElementList: Sequence[int]
    Status: Sequence[int]
    Position: FloatSequence | None = None
    Monitor: MonitorDataModel | None = None
    Offset: FloatSequence | None = None
    Setpoint: SetpointDataModel | None = None
    AT: ATElementsInfo | None = None

    @field_validator("MemberOf", "CommonNames", "DeviceName", mode="before")
    @classmethod
    def normalize_str_sequences(cls, v: Any) -> Any:
        """Normalize a bare string to a one-element sequence of strings."""
        return _as_str_sequence(v)

    @field_validator("DeviceList", mode="before")
    @classmethod
    def normalize_device_list(cls, v: Any) -> Any:
        """Normalize a single (sector, index) pair to a sequence of pairs."""
        if isinstance(v, (list, tuple)) and len(v) == _PAIR_LEN and _depth(v) == 1:
            return [v]
        return v

    @field_validator("ElementList", "Status", "Position", "Offset", mode="before")
    @classmethod
    def normalize_scalar_sequences(cls, v: Any) -> Any:
        """Normalize a bare number to a one-element sequence."""
        return _as_sequence(v)

    def get_device_list(self) -> Sequence[DeviceIndex]:
        """Return the normalized device list."""
        return self.DeviceList

    def member_of(self) -> StrSequence:
        """Return the normalized member of sequence."""
        return self.MemberOf

    def get_device_index(self, sector: int, child: int) -> int:
        """Get the index of a device in the device list."""
        return list(self.DeviceList).index((sector, child))


def load(data: dict[str, Any]) -> dict[str, FamilyInfoCollection]:
    """Load an exported ``ao`` dict into FamilyInfoCollection models.

    Non-family entries (scalars / strings at the top level) are skipped.
    Families that fail validation are logged and skipped; use ``load_strict``
    to have validation errors propagate instead.
    """
    result = {}
    for family_name, item in data.items():
        if not isinstance(item, dict):
            continue
        try:
            result[family_name] = FamilyInfoCollection.model_validate(item)
        except ValueError as exc:
            logger.error("Conversion failed for family %s: %s", family_name, exc)
    return result


def load_strict(data: dict[str, Any]) -> dict[str, FamilyInfoCollection]:
    """Like ``load``, but any family failing validation raises."""
    return {
        family_name: FamilyInfoCollection.model_validate(item)
        for family_name, item in data.items()
        if isinstance(item, dict)
    }


def load_file(path: str | Path, *, strict: bool = False) -> dict[str, FamilyInfoCollection]:
    """Load an ``ao`` JSON export from disk."""
    with open(path, encoding="utf-8") as fp:
        data = json.load(fp)
    return load_strict(data) if strict else load(data)
