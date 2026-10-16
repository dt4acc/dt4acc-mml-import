"""Tests for the MML AO pydantic models.

The real-data tests read the ``ao`` JSON exports in the private
``mml-exported-data-sets`` repository. Point ``MML_EXPORTS_DIR`` at a
checkout of it; they are skipped when it is not available.
"""

import os
from pathlib import Path

import pytest

import dt4acc_mml_import
from dt4acc_mml_import import (
    ATElementsInfo,
    FamilyInfoCollection,
    MonitorDataModel,
    SetpointDataModel,
    load,
    load_file,
    load_strict,
    normalize_param_blocks,
)

EXPORTS_DIR = Path(os.environ.get("MML_EXPORTS_DIR", Path.home() / "workspace" / "mml-exported-data-sets"))
AO_EXPORTS = {
    "bessyii": "hz-b/bessyii/bessyii_ao_cfg.json",
    "mls": "hz-b/mls/ao_mls.json",
    "maxiv_3gev": "maxiv/maxiv3gev_ao_cfg.json",
    "maxiv_r1": "maxiv/r1/ao_R1.json",
}


def test_package_exports_resolve():
    for name in dt4acc_mml_import.__all__:
        assert hasattr(dt4acc_mml_import, name), name


def test_scalars_are_normalized_to_sequences():
    # MATLAB's JSON export writes one-element arrays as bare scalars
    monitor = MonitorDataModel(
        ChannelNames="single_channel",
        DataType="Scalar",
        Units="Hardware",
        HWUnits="mm",
        PhysicsUnits="m",
        HW2PhysicsParams=0.001,
    )
    assert monitor.ChannelNames == ["single_channel"]
    assert monitor.HWUnits == ["mm"]
    assert monitor.PhysicsUnits == ["m"]
    assert monitor.HW2PhysicsParams == [[[0.001]]]

    family = FamilyInfoCollection(MemberOf="single_family", DeviceList=[1, 2], ElementList=5, Status=1)
    assert family.MemberOf == ["single_family"]
    assert family.DeviceList == [(1, 2)]
    assert family.ElementList == [5]
    assert family.Status == [1]


def test_nested_member_of_is_flattened():
    family = FamilyInfoCollection(
        MemberOf=["ID", ["IVU", "Undulator"]], DeviceList=[[1, 1]], ElementList=[1], Status=[1]
    )
    assert family.MemberOf == ["ID", "IVU", "Undulator"]


def test_at_index_normalization():
    assert ATElementsInfo(ATType="QUAD", ATIndex=5).ATIndex == [[5]]
    assert ATElementsInfo(ATType="QUAD", ATIndex=[34, 45]).ATIndex == [[34], [45]]
    assert ATElementsInfo(ATType="BEND", ATIndex=[[1, 2], [3, 4]]).ATIndex == [[1, 2], [3, 4]]


def test_at_parameter_group_without_type_and_index():
    at = ATElementsInfo(
        ATParameterGroup=[
            [{"ElemIndex": 120, "FieldName": "PolynomB", "FieldIndex": 2, "SavedValue": 4.03, "Function": "@(x)x"}]
        ]
    )
    assert at.ATType is None and at.ATIndex is None
    (entry,) = at.ATParameterGroup[0]
    assert (entry.FieldName, list(entry.FieldIndex)) == ("PolynomB", [2])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (5e-06, [[[5e-06]]]),  # one gain for the family
        ([0.1, 0.2], [[[0.1], [0.2]]]),  # one gain per device
        ([[0.001, 0], [0.001, 0]], [[[0.001, 0], [0.001, 0]]]),  # [ndev x 2]
        ([[[1, 2], [3, 4]], [1, 1]], [[[1, 2], [3, 4]], [[1], [1]]]),  # MATLAB cell {coeffs, vector}
        (None, None),
    ],
)
def test_param_block_normalization(raw, expected):
    assert normalize_param_blocks(raw) == expected


def test_conversion_function_given_as_bare_name():
    sp = SetpointDataModel(HW2PhysicsFcn="amp2k", Range=[None, None])
    assert sp.conversion_function_name() == "amp2k"
    assert sp.HW2PhysicsFcn.function_handle.file is None
    assert sp.Range == [(None, None)]


def test_empty_matlab_char_array_in_function_handle_is_none():
    sp = SetpointDataModel(HW2PhysicsFcn={"function_handle": {"function": "amp2k", "file": [], "type": "simple"}})
    assert sp.HW2PhysicsFcn.function_handle.file is None


def test_load_returns_families_and_skips_non_family_entries():
    data = {
        "Q1": {"MemberOf": "QUAD", "DeviceList": [[1, 1]], "ElementList": [1], "Status": [1]},
        "Version": "1.0",
    }
    result = load(data)
    assert list(result) == ["Q1"]


def test_load_logs_and_skips_invalid_family_but_strict_raises():
    data = {"BAD": {"MemberOf": "QUAD"}}
    assert load(data) == {}
    with pytest.raises(ValueError):
        load_strict(data)


@pytest.mark.parametrize("facility", sorted(AO_EXPORTS))
def test_real_ao_exports_validate_strictly(facility):
    path = EXPORTS_DIR / AO_EXPORTS[facility]
    if not path.exists():
        pytest.skip(f"{path} not available (set MML_EXPORTS_DIR)")
    families = load_file(path, strict=True)
    assert families
    for family in families.values():
        if family.Setpoint and family.Setpoint.HW2PhysicsParams is not None:
            for block in family.Setpoint.HW2PhysicsParams:
                assert all(isinstance(row, list) for row in block)
