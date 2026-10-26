"""Build the :class:`Facility` model from the raw ``ao`` and ``ad`` objects.

The ``ao`` holds family wide arrays (one entry per device, or a single entry
shared by the family); here they are split into one record per device.
"""

import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..data_model.mml_ao import (
    FamilyInfoCollection,
    MonitorDataModel,
    SetpointDataModel,
)
from .facility import (
    Channel,
    Classification,
    Conversion,
    Device,
    DeviceKind,
    Facility,
    Family,
    LatticeTarget,
    Limits,
    MachineInfo,
    ParameterLayout,
    Plane,
    Provenance,
    Signal,
    Units,
)

logger = logging.getLogger("dt4acc-mml-importer")

#: ``MemberOf`` tag -> (kind, plane). The first tag of this table found in a
#: family's ``MemberOf`` wins, e.g. a "COR" + "HCOR" family is a horizontal
#: steerer, "SKEWQUAD" is checked before "QUAD". Tags are compared ignoring
#: case: labs spell them differently (BESSY II / MLS "SKEWQUAD", ALS "SkewQuad").
MEMBER_OF_KINDS: tuple[tuple[str, DeviceKind, Plane | None], ...] = (
    ("HCOR", DeviceKind.steerer, Plane.horizontal),
    ("HCM", DeviceKind.steerer, Plane.horizontal),
    ("HCMCHICANE", DeviceKind.steerer, Plane.horizontal),  # ALS chicane correctors
    ("VCOR", DeviceKind.steerer, Plane.vertical),
    ("VCM", DeviceKind.steerer, Plane.vertical),
    ("VCMCHICANE", DeviceKind.steerer, Plane.vertical),
    ("SKEWQUAD", DeviceKind.skew_quadrupole, None),
    ("SKEW", DeviceKind.skew_quadrupole, None),
    ("QUAD", DeviceKind.quadrupole, None),
    ("SEXT", DeviceKind.sextupole, None),
    ("OCTU", DeviceKind.octupole, None),
    ("OCTUPOLE", DeviceKind.octupole, None),
    ("BEND", DeviceKind.bend, None),
    ("BPMx", DeviceKind.bpm, Plane.horizontal),
    ("HBPM", DeviceKind.bpm, Plane.horizontal),
    ("BPMy", DeviceKind.bpm, Plane.vertical),
    ("VBPM", DeviceKind.bpm, Plane.vertical),
    # plane not in the tag (ALS IDBPMx / IDBPMy are both "IDBPM")
    ("BPM", DeviceKind.bpm, None),
    ("IDBPM", DeviceKind.bpm, None),
    ("BBPM", DeviceKind.bpm, None),
    ("RF", DeviceKind.rf, None),
    ("CAVITY", DeviceKind.rf, None),
    ("DCCT", DeviceKind.dcct, None),
    ("TUNE", DeviceKind.tune, None),
    ("KICKER", DeviceKind.kicker, None),
    ("ID", DeviceKind.insertion_device, None),
    ("EPU", DeviceKind.insertion_device, None),
    ("INSERTIONDEVICE", DeviceKind.insertion_device, None),
)

#: DeviceName entries that mean "no device"
_NO_DEVICE_NAMES = ("", "Non-existant")


def classify_family(member_of: Sequence[str]) -> Classification:
    """Kind and plane of a family from its ``MemberOf`` tags."""
    by_upper: dict[str, str] = {}
    for tag in member_of:
        by_upper.setdefault(tag.upper(), tag)
    for known, kind, plane in MEMBER_OF_KINDS:
        found = by_upper.get(known.upper())
        if found is None:
            continue
        reason = f"MemberOf tag {found!r}"
        if found != known:
            reason += f" (matched {known!r} ignoring case)"
        return Classification(kind=kind, plane=plane, reason=reason)
    return Classification(kind=DeviceKind.unknown, reason=f"no known MemberOf tag in {list(member_of)}")


class _Picker:
    """The entry of a family wide array that belongs to device ``i``."""

    def __init__(self, family: str, n_devices: int, warnings: list[str]):
        self.family = family
        self.n = n_devices
        self.warnings = warnings

    def __call__(self, values: Sequence[Any] | None, i: int, what: str) -> Any:
        value = self._pick(values, i, what)
        # names from a MATLAB char matrix are padded with blanks (ALS)
        return value.strip() if isinstance(value, str) else value

    def _pick(self, values: Sequence[Any] | None, i: int, what: str) -> Any:
        if values is None:
            return None
        values = list(values)
        if not values:
            # an empty MATLAB array (e.g. ALS units '' loaded from .mat)
            return None
        if len(values) == self.n:
            return values[i]
        if len(values) == 1:
            return values[0]
        if i == 0:
            self.warnings.append(f"{self.family}: {what} has {len(values)} entries for {self.n} devices; not used")
        return None


def _clean_row(row: Sequence[float | None]) -> list[float]:
    """NaN padding (exported as null) removed."""
    return [float(v) for v in row if v is not None]


def _device_rows(blocks: Sequence[Sequence[Sequence[float]]] | None, i: int, n: int) -> tuple[list[list[float]], ParameterLayout]:
    """This device's rows of each parameter block, and how they were found."""
    rows: list[list[float]] = []
    layouts = set()
    for block in blocks or []:
        if len(block) == n:
            rows.append(_clean_row(block[i]))
            layouts.add(ParameterLayout.per_device)
        elif len(block) > n and len(block) % n == 0:
            rows.extend(_clean_row(block[j * n + i]) for j in range(len(block) // n))
            layouts.add(ParameterLayout.strided)
        elif len(block) == 1:
            rows.append(_clean_row(block[0]))
            layouts.add(ParameterLayout.shared)
        else:
            rows.extend(_clean_row(r) for r in block)
            layouts.add(ParameterLayout.unknown)
    layout = layouts.pop() if len(layouts) == 1 else ParameterLayout.unknown
    return rows, layout


def _conversion(signal: MonitorDataModel, i: int, n: int) -> Conversion | None:
    if signal.HW2PhysicsParams is None and signal.HW2PhysicsFcn is None:
        return None
    rows, layout = _device_rows(signal.HW2PhysicsParams, i, n)
    inverse_rows = None
    if signal.Physics2HWParams is not None:
        inv, _ = _device_rows(signal.Physics2HWParams, i, n)
        if inv != rows:
            inverse_rows = inv
    inverse = signal.Physics2HWFcn.function_handle.function if signal.Physics2HWFcn else None
    return Conversion(
        function=signal.conversion_function_name(),
        inverse_function=inverse,
        rows=rows,
        layout=layout,
        inverse_rows=inverse_rows,
    )


def _signal(signal: MonitorDataModel, i: int, pick: _Picker, what: str, access: str) -> Signal:
    limits = None
    if isinstance(signal, SetpointDataModel) and signal.Range is not None:
        rng = pick(signal.Range, i, f"{what}.Range")
        if rng is not None:
            limits = Limits(lower=rng[0], upper=rng[1])
    return Signal(
        channel=Channel(
            name=pick(signal.ChannelNames, i, f"{what}.ChannelNames"),
            access=access,
            special_function_get=signal.SpecialFunctionGet,
            special_function_set=signal.SpecialFunctionSet,
        ),
        units=Units(
            hardware=pick(signal.HWUnits, i, f"{what}.HWUnits"),
            physics=pick(signal.PhysicsUnits, i, f"{what}.PhysicsUnits"),
            default=signal.Units,
        ),
        conversion=_conversion(signal, i, pick.n),
        limits=limits,
        tolerance=pick(signal.Tolerance, i, f"{what}.Tolerance"),
    )


def _device_name(fam: FamilyInfoCollection, channel: str | None, i: int, pick: _Picker) -> str | None:
    """``DeviceName`` where exported (Tango facilities), else the EPICS
    channel without its ``:attribute`` (``Q1P2K1RP:setCur`` -> ``Q1P2K1RP``)."""
    name = pick(fam.DeviceName, i, "DeviceName")
    if name is not None and name not in _NO_DEVICE_NAMES:
        return name
    if channel and ":" in channel:
        return channel.rsplit(":", 1)[0]
    return None


def _lattice(fam: FamilyInfoCollection, i: int, n: int) -> list[LatticeTarget]:
    """The parameter group (element and field) where exported, plus the
    ``ATIndex`` elements it does not cover."""
    at = fam.AT
    if at is None:
        return []
    targets = []
    if at.ATParameterGroup and len(at.ATParameterGroup) == n:
        targets = [
            LatticeTarget(
                at_index=p.ElemIndex,
                at_type=at.ATType,
                field=p.FieldName,
                field_index=list(p.FieldIndex) if p.FieldIndex is not None else None,
            )
            for p in at.ATParameterGroup[i]
        ]
    indices = at.element_indices()
    # one row per device, or one shared by the family (MAX IV R1 CAVITY)
    row = indices[i] if len(indices) == n else indices[0] if len(indices) == 1 else []
    covered = {t.at_index for t in targets}
    targets.extend(LatticeTarget(at_index=x, at_type=at.ATType) for x in row if x not in covered)
    return targets


def build_family(name: str, fam: FamilyInfoCollection, warnings: list[str]) -> Family:
    """One family of the raw ``ao`` as one record per device."""
    n = len(fam.DeviceList)
    pick = _Picker(name, n, warnings)
    monitor_ch = fam.Monitor.ChannelNames if fam.Monitor else None
    setpoint_ch = fam.Setpoint.ChannelNames if fam.Setpoint else None
    others = fam.other_signals()
    devices = []
    for i, dev in enumerate(fam.DeviceList):
        common = pick(fam.CommonNames, i, "CommonNames") if fam.CommonNames and len(fam.CommonNames) == n else None
        status = pick(fam.Status, i, "Status")
        devices.append(
            Device(
                family=name,
                device=tuple(dev),
                element=pick(fam.ElementList, i, "ElementList"),
                name=common or f"{name}_{dev[0]:02d}_{dev[1]}",
                name_from_export=bool(common),
                status=bool(status) if status is not None else True,
                position=pick(fam.Position, i, "Position"),
                device_name=_device_name(fam, pick(setpoint_ch or monitor_ch, i, "ChannelNames"), i, pick),
                monitor=_signal(fam.Monitor, i, pick, "Monitor", "read") if fam.Monitor else None,
                setpoint=_signal(fam.Setpoint, i, pick, "Setpoint", "write") if fam.Setpoint else None,
                lattice=_lattice(fam, i, n),
                other_signals={
                    sname: _signal(sig, i, pick, sname, "write" if sig.SpecialFunctionSet else "unknown")
                    for sname, sig in others.items()
                },
            )
        )
    return Family(
        name=name,
        member_of=list(fam.MemberOf),
        family_type=fam.FamilyType,
        classification=classify_family(fam.MemberOf),
        devices=devices,
    )


def machine_info(ad: Mapping[str, Any]) -> MachineInfo:
    """The ``getad()`` fields the model keeps."""
    return MachineInfo(
        machine=ad["Machine"],
        submachine=ad.get("SubMachine"),
        machine_type=ad.get("MachineType"),
        operational_mode=ad.get("OperationalMode") or None,
        mode_name=ad.get("ModeName"),
        at_model=ad.get("ATModel"),
        energy=ad.get("Energy"),
        injection_energy=ad.get("InjectionEnergy"),
        harmonic_number=ad.get("HarmonicNumber"),
        circumference=ad.get("Circumference"),
        mcf=ad.get("MCF"),
    )


def build_facility(
    ao: Mapping[str, Any],
    ad: Mapping[str, Any] | None = None,
    *,
    ao_source: str | None = None,
    ad_source: str | None = None,
) -> Facility:
    """``ao``: the exported ``getao()`` dict; ``ad``: ``getad()``, optional."""
    if isinstance(ao.get("ao"), dict):
        ao = ao["ao"]
    provenance = Provenance(ao_source=ao_source, ad_source=ad_source)
    families: dict[str, Family] = {}
    for name, item in ao.items():
        if not isinstance(item, dict):
            continue
        try:
            raw = FamilyInfoCollection.model_validate(item)
        except ValidationError as exc:
            first = exc.errors()[0]
            provenance.skipped_families[name] = f"{exc.error_count()} validation errors, first: {first['loc']}: {first['msg']}"
            logger.error("family %s skipped: %s", name, exc)
            continue
        families[name] = build_family(name, raw, provenance.warnings)
    return Facility(machine=machine_info(ad) if ad else None, families=families, provenance=provenance)


def load_facility(ao_path: str | Path, ad_path: str | Path | None = None) -> Facility:
    """Build the model from ``ao`` (and ``ad``) JSON exports on disk."""
    with open(ao_path, encoding="utf-8") as fp:
        ao = json.load(fp)
    ad = None
    if ad_path is not None:
        with open(ad_path, encoding="utf-8") as fp:
            ad = json.load(fp)
    return build_facility(ao, ad, ao_source=Path(ao_path).name, ad_source=Path(ad_path).name if ad_path else None)
