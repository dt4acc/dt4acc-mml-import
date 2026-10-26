"""Concrete data model of a facility as described by its Matlab Middle Layer.

One record per device, with everything a client (digital twin, a python
middle layer, measurement scripts) needs from the ``ao`` and ``ad`` objects:

* identity: family, (sector, index), element number, common name, status
* control system: device name (power supply for magnets), monitor / setpoint
  channel names with access mode and special functions, further signals
* lattice: which AT element(s) and, where exported, which field(s)
* conversion: hardware <-> physics as exported (function name and this
  device's parameter rows), units, limits

Nothing is guessed: a conversion function is recorded by name with its
parameters; interpreting e.g. ``amp2k`` is facility specific and left to the
consumer. Values are as in the middle layer (indices 1-based).
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class DeviceKind(StrEnum):
    """What a family is."""

    quadrupole = "quadrupole"
    skew_quadrupole = "skew_quadrupole"
    sextupole = "sextupole"
    octupole = "octupole"
    bend = "bend"
    steerer = "steerer"
    bpm = "bpm"
    rf = "rf"
    dcct = "dcct"
    tune = "tune"
    kicker = "kicker"
    insertion_device = "insertion_device"
    unknown = "unknown"


class Plane(StrEnum):
    horizontal = "horizontal"
    vertical = "vertical"


class Classification(BaseModel):
    """What a family is, and from which ``MemberOf`` tag that was read."""

    kind: DeviceKind
    plane: Plane | None = None
    reason: str


class Channel(BaseModel):
    """A control system signal: EPICS PV or Tango attribute.

    ``name`` is None for signals only accessed by a special function (e.g.
    MLS TUNE: ``gettune_mls``). ``access``: Monitor is read, Setpoint write;
    for further signals (e.g. ``VoltageCtrl``) the ``ao`` does not say,
    unless they have a ``SpecialFunctionSet``.
    """

    name: str | None = None
    access: Literal["read", "write", "unknown"]
    special_function_get: str | None = None
    special_function_set: str | None = None


class Units(BaseModel):
    hardware: str | None = None
    physics: str | None = None
    #: which units the middle layer uses by default ("Hardware" / "Physics")
    default: str | None = None


class Limits(BaseModel):
    """Setpoint range in hardware units; None where exported as NaN."""

    lower: float | None = None
    upper: float | None = None


class ParameterLayout(StrEnum):
    """How a device's rows were found in a family's parameter block."""

    #: one value / row for the whole family
    shared = "shared"
    #: one row per device
    per_device = "per_device"
    #: k rows per device, row j of device i at j * n_devices + i: all
    #: devices' first rows, then all second rows, ... (MAX IV excitation
    #: tables: currents, fields; R1 BEND: currents, B L, B' L). The rows
    #: the middle layer's getfamilydata hands to each device.
    strided = "strided"
    #: rows that match none of the above; all kept
    unknown = "unknown"


class Conversion(BaseModel):
    """Hardware -> physics conversion as exported.

    Without ``function`` the middle layer default applies,
    ``physics = gain * hardware`` with ``gain = rows[0][0]`` (see
    :attr:`gain`). With a function (e.g. ``amp2k``) the rows are its
    parameters for this device, block after block.
    """

    function: str | None = None
    inverse_function: str | None = None
    rows: list[list[float]] = Field(default_factory=list)
    layout: ParameterLayout
    #: rows of Physics2HWParams, where they differ from HW2PhysicsParams
    inverse_rows: list[list[float]] | None = None

    @property
    def gain(self) -> float | None:
        """The linear gain, for conversions without function."""
        if self.function is not None or not self.rows or not self.rows[0]:
            return None
        return self.rows[0][0]


class Signal(BaseModel):
    """One signal (monitor, setpoint, ...) of one device."""

    channel: Channel
    units: Units
    conversion: Conversion | None = None
    #: setpoints only
    limits: Limits | None = None
    tolerance: float | None = None


class LatticeTarget(BaseModel):
    """An AT element the device acts on or is located at.

    ``field`` / ``field_index`` are known where the export has an
    ``ATParameterGroup``; ``at_index`` and ``field_index`` are 1-based.
    """

    at_index: int
    at_type: str | None = None
    field: str | None = None
    field_index: list[int] | None = None


class Device(BaseModel):
    family: str
    device: tuple[int, int]
    element: int
    #: CommonNames entry, else ``<family>_<sector>_<index>``
    name: str
    name_from_export: bool
    status: bool
    #: longitudinal position s [m]
    position: float | None = None
    #: control system device: the power supply for magnets
    device_name: str | None = None
    monitor: Signal | None = None
    setpoint: Signal | None = None
    lattice: list[LatticeTarget] = Field(default_factory=list)
    #: further signals of the family, e.g. ``Sum``, ``Voltage``, ``Resistance``
    other_signals: dict[str, Signal] = Field(default_factory=dict)


class Family(BaseModel):
    name: str
    member_of: list[str]
    family_type: str | None = None
    classification: Classification
    devices: list[Device]


class MachineInfo(BaseModel):
    """From the ``ad`` object; energies in GeV, lengths in m."""

    machine: str
    submachine: str | None = None
    machine_type: str | None = None
    operational_mode: str | None = None
    mode_name: str | None = None
    at_model: str | None = None
    energy: float | None = None
    injection_energy: float | None = None
    harmonic_number: int | None = None
    circumference: float | None = None
    mcf: float | None = None


class Provenance(BaseModel):
    ao_source: str | None = None
    ad_source: str | None = None
    #: families the raw model could not validate, with the reason
    skipped_families: dict[str, str] = Field(default_factory=dict)
    #: inconsistencies found while building, e.g. list lengths that differ
    warnings: list[str] = Field(default_factory=list)


class Facility(BaseModel):
    machine: MachineInfo | None = None
    families: dict[str, Family]
    provenance: Provenance

    def devices(self, kind: DeviceKind | None = None) -> list[Device]:
        """All devices, or those of the families of one kind."""
        return [
            dev
            for fam in self.families.values()
            if kind is None or fam.classification.kind == kind
            for dev in fam.devices
        ]

    def device(self, family: str, device: tuple[int, int]) -> Device:
        """One device by family name and (sector, index)."""
        for dev in self.families[family].devices:
            if dev.device == tuple(device):
                return dev
        msg = f"no device {device} in family {family}"
        raise KeyError(msg)
