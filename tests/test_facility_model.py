"""Tests for the per device facility model.

The expected values are read off the real ``ao`` / ``ad`` JSON exports in the
private ``mml-exported-data-sets`` repository (``MML_EXPORTS_DIR``); those
tests are skipped when it is not available.
"""

import json
import os
from pathlib import Path

import pytest

from dt4acc_mml_import import load_strict
from dt4acc_mml_import.model import (
    DeviceKind,
    ParameterLayout,
    Plane,
    build_facility,
    load_facility,
)

EXPORTS_DIR = Path(os.environ.get("MML_EXPORTS_DIR", Path.home() / "workspace" / "mml-exported-data-sets"))
EXPORTS = {
    "bessyii": ("hz-b/bessyii/bessyii_ao_cfg.json", "hz-b/bessyii/bessyii_ad_cfg.json"),
    "mls": ("hz-b/mls/ao_mls.json", None),
    "maxiv_3gev": ("maxiv/maxiv3gev_ao_cfg.json", "maxiv/maxiv3gev_ad_cfg.json"),
    "maxiv_r1": ("maxiv/r1/ao_R1.json", "maxiv/r1/ad_R1.json"),
    "maxiv_r1_lattice": ("maxiv/r1/ao_R1_with_lattice_index.json", None),
}


def _paths(name):
    ao, ad = EXPORTS[name]
    ao_path = EXPORTS_DIR / ao
    if not ao_path.exists():
        pytest.skip(f"{ao_path} not available (set MML_EXPORTS_DIR)")
    ad_path = EXPORTS_DIR / ad if ad and (EXPORTS_DIR / ad).exists() else None
    return ao_path, ad_path


@pytest.fixture(scope="module")
def mls():
    return load_facility(*_paths("mls"))


@pytest.fixture(scope="module")
def r1():
    return load_facility(*_paths("maxiv_r1_lattice"))


@pytest.mark.parametrize("name", sorted(EXPORTS))
def test_every_family_validates_and_every_device_is_built(name):
    ao_path, ad_path = _paths(name)
    data = json.loads(ao_path.read_text())
    assert len(load_strict(data)) == sum(isinstance(v, dict) for v in data.values())
    facility = load_facility(ao_path, ad_path)
    assert facility.provenance.skipped_families == {}
    for fam in facility.families.values():
        for dev in fam.devices:
            assert dev.name
            if dev.setpoint is not None:
                ch = dev.setpoint.channel
                assert ch.access == "write"
                assert ch.name or ch.special_function_set or ch.special_function_get


class TestMLS:
    def test_quadrupole(self, mls):
        q = mls.device("Q1", (1, 1))
        assert mls.families["Q1"].classification.kind == DeviceKind.quadrupole
        assert (q.name, q.device_name, q.element, q.position) == ("Q1M2K1RP", "Q1P2K1RP", 1, 4.75)
        assert q.monitor.channel.name == "Q1P2K1RP:rdCur"
        assert q.monitor.channel.access == "read"
        sp = q.setpoint
        assert sp.channel.name == "Q1P2K1RP:setCur"
        assert (sp.limits.lower, sp.limits.upper) == (0, 65.55)
        assert sp.tolerance == 0.1
        assert (sp.units.hardware, sp.units.physics) == ("Ampere", "meter^-2")
        assert (sp.conversion.function, sp.conversion.inverse_function) == ("amp2k", "k2amp")
        assert sp.conversion.rows == [[0.138213, 0.0]]
        assert sp.conversion.layout == ParameterLayout.per_device
        assert sp.conversion.gain is None
        assert [(t.at_index, t.at_type) for t in q.lattice] == [(22, "QUAD")]
        assert len({d.device_name for d in mls.families["Q1"].devices}) == 8

    def test_steerer_two_parameter_blocks(self, mls):
        h = mls.device("HCM", (1, 1))
        assert mls.families["HCM"].classification.plane == Plane.horizontal
        # amp2k parameters {C, scale}: one row of each block
        assert h.setpoint.conversion.rows == [[0.00268011, 0.0], [1.0]]
        assert (h.setpoint.limits.lower, h.setpoint.limits.upper) == (-3.5, 3.5)

    def test_bpm_gain(self, mls):
        b = mls.device("BPMx", (1, 5))
        assert mls.families["BPMx"].classification.kind == DeviceKind.bpm
        assert b.monitor.channel.name == "BPMZ5K1RP:rdX"
        assert b.monitor.channel.special_function_get == "getBPMFromIOC"
        assert b.monitor.conversion.gain == 0.001
        assert b.monitor.conversion.inverse_rows == [[1000.0]]
        assert b.setpoint is None

    def test_single_device_family(self, mls):
        rf = mls.device("RF", (1, 1))
        assert rf.setpoint.channel.name == "MCLKHGP:setFrq"
        assert (rf.setpoint.units.hardware, rf.setpoint.units.physics) == ("kHz", "Hz")
        assert rf.setpoint.conversion.gain == 1000
        assert rf.lattice[0].at_index == 139
        # further signals: access not stated in the ao
        assert rf.other_signals["VoltageCtrl"].channel.name == "PAHRP:setVoltCav"
        assert rf.other_signals["VoltageCtrl"].channel.access == "unknown"

    def test_special_function_only(self, mls):
        t = mls.device("TUNE", (1, 1))
        assert mls.families["TUNE"].classification.kind == DeviceKind.tune
        assert t.monitor.channel.name is None
        assert t.monitor.channel.special_function_get == "gettune_mls"
        assert (t.name, t.name_from_export) == ("TUNE_01_1", False)


class TestMaxIVR1:
    def test_excitation_table(self, r1):
        s = r1.device("SQFI", (1, 1))
        assert s.device_name == "R1-D100101CAB16/MAG/PSDH-01"
        assert s.setpoint.channel.name == "R1-D100101CAB16/MAG/PSDH-01/Current"
        assert s.setpoint.channel.special_function_set == "setTangoSetpoint_asynch"
        conv = s.setpoint.conversion
        assert conv.layout == ParameterLayout.strided
        assert conv.rows[0][0] == 513.696725
        assert conv.rows[1][0] == pytest.approx(-27.6308699135)
        assert len(conv.rows[0]) == len(conv.rows[1]) == 6
        # Range [NaN, NaN] exported as null
        assert (s.setpoint.limits.lower, s.setpoint.limits.upper) == (None, None)

    def test_parameter_group(self, r1):
        s = r1.device("SQFI", (1, 1))
        assert len(s.lattice) == 144
        assert {t.field for t in s.lattice} == {"PolynomB"}
        assert s.lattice[0].at_index == 73
        assert s.other_signals["Resistance"].channel.name == "R1-D100101CAB16/MAG/PSDH-01/Resistance"

    def test_steerers(self, r1):
        assert len(r1.families["HCM"].devices) == 36
        h = r1.device("HCM", (1, 1))
        assert h.device_name == "R1-D110210CAB01/MAG/PSIB-01"
        assert (h.setpoint.limits.lower, h.setpoint.limits.upper) == (-10.5, 10.5)
        assert h.setpoint.tolerance == 0.0005
        assert h.setpoint.conversion.layout == ParameterLayout.strided
        assert h.setpoint.conversion.rows[0][0] == 11.57333
        assert h.setpoint.units.default == "Physics"

    def test_parameter_group_without_field_name(self, r1):
        shunt = r1.families["SHUNT"]
        assert shunt.classification.kind == DeviceKind.unknown
        assert all(t.field is None for d in shunt.devices for t in d.lattice)


def test_machine_info():
    f = load_facility(*_paths("bessyii"))
    m = f.machine
    assert (m.machine, m.energy, m.harmonic_number) == ("BESSY2", 1.7, 400)
    for q in f.devices(DeviceKind.quadrupole):
        assert q.device_name
        assert q.setpoint.channel.name.startswith(q.device_name)


def test_inconsistent_lengths_reported():
    f = load_facility(*_paths("maxiv_3gev"))
    assert "OYY: Position has 20 entries for 1 devices; not used" in f.provenance.warnings
    assert f.device("OYY", (1, 1)).position is None


def test_rows_strided_by_device():
    """k rows per device: device i gets rows i, n + i, 2 n + i, ... as the
    middle layer's getfamilydata does (checked against MAX IV's MML)."""
    ao = {
        "BEND": {
            "MemberOf": ["BEND"],
            "DeviceList": [[1, 1], [1, 2]],
            "ElementList": [1, 2],
            "Status": [1, 1],
            "Setpoint": {
                "ChannelNames": ["a", "b"],
                "HW2PhysicsFcn": "amp2field",
                "HW2PhysicsParams": [[[10, 20], [11, 21], [1, 2], [3, 4], [5, 6], [7, 8]]],
            },
        }
    }
    f = build_facility(ao)
    assert f.device("BEND", (1, 1)).setpoint.conversion.rows == [[10, 20], [1, 2], [5, 6]]
    assert f.device("BEND", (1, 2)).setpoint.conversion.rows == [[11, 21], [3, 4], [7, 8]]


def test_shapes_of_other_exports():
    """Scalars for single entries, cell in cell MemberOf, a function handle
    struct, empty arrays and blank padded names from a .mat file (ALS)."""
    ao = {
        "ID": {
            "FamilyName": "ID",
            "MemberOf": ["ID", ["IVU", "Undulator"]],
            "DeviceList": [4, 1],
            "ElementList": 1,
            "Status": 0,
            "AT": {"ATType": "ID", "ATIndex": 7},
            "Setpoint": {
                "ChannelNames": "SR04U:Gap   ",
                "Units": "Hardware",
                "HWUnits": [],
                "PhysicsUnits": "mm",
                "HW2PhysicsParams": 1,
                "Range": [None, 30],
                "SpecialFunctionGet": {"function_handle": {"function": "getid_als", "type": "simple"}},
                "SpecialFunctionSet": [],
            },
        },
        "IonGauge": {"MemberOf": "Pressure", "DeviceList": [[1, 1], [1, 2]], "ElementList": [1, 2], "Status": [1, 1]},
        "GeV": 1.9,
    }
    f = build_facility(ao)
    assert f.provenance.skipped_families == {}
    fam = f.families["ID"]
    assert fam.member_of == ["ID", "IVU", "Undulator"]
    assert fam.classification.kind == DeviceKind.insertion_device
    d = fam.devices[0]
    assert (d.device, d.status, d.device_name) == ((4, 1), False, "SR04U")
    assert d.lattice[0].at_index == 7
    sp = d.setpoint
    assert sp.channel.name == "SR04U:Gap"
    assert sp.channel.special_function_get == "getid_als"
    assert sp.channel.special_function_set is None
    assert (sp.units.hardware, sp.units.physics) == (None, "mm")
    assert (sp.limits.lower, sp.limits.upper) == (None, 30)
    assert sp.conversion.gain == 1
    unknown = f.families["IonGauge"].classification
    assert unknown.kind == DeviceKind.unknown
    assert "Pressure" in unknown.reason
