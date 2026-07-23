#!/usr/bin/env python3
"""
Simple test script to verify the Pydantic models work correctly.
"""

import sys
from pathlib import Path

# Add src to path so we can import our package
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that we can import all models."""
    try:
        from dt4acc_mml_import import (
            ATElementsInfo,
            ConversionFunctionHandle,
            ConversionFunction,
            MonitorDataModel,
            SetpointDataModel,
            FamilyInfoCollection,
            load,
            DeviceIndex,
            Range,
            StrSequence,
            FloatSequence,
            IntSequence2D,
            FloatSequence2D
        )
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_basic_models():
    """Test basic model instantiation."""
    try:
        from dt4acc_mml_import.data_model.mml_ao import (
            MonitorDataModel,
            FamilyInfoCollection,
            ATElementsInfo
        )
        
        # Test MonitorDataModel
        monitor = MonitorDataModel(
            ChannelNames=["test_channel"],
            DataType="float",
            Units="mm",
            HWUnits=["mm"],
            PhysicsUnits=["mm"]
        )
        
        # Test FamilyInfoCollection
        family = FamilyInfoCollection(
            MemberOf=["test_family"],
            DeviceList=[(1, 2)],
            ElementList=[1],
            Status=[1]
        )
        
        # Test ATElementsInfo
        at_info = ATElementsInfo(
            ATType="test",
            ATIndex=[1, 2, 3]
        )
        
        print("✓ Basic models test passed")
        return True
    except Exception as e:
        print(f"✗ Basic models test failed: {e}")
        return False

def test_normalization():
    """Test that normalization works correctly."""
    try:
        from dt4acc_mml_import.data_model.mml_ao import (
            MonitorDataModel,
            FamilyInfoCollection,
            ATElementsInfo
        )
        
        # Test ATElementsInfo normalization
        at_info = ATElementsInfo(ATType="test", ATIndex=5)
        assert at_info.ATIndex == [[5]]
        
        # Test string normalization
        monitor = MonitorDataModel(
            ChannelNames="single_channel",  # Scalar should be normalized
            DataType="float",
            Units="mm",
            HWUnits="single_hw_unit",  # Scalar should be normalized
            PhysicsUnits="single_physics_unit"  # Scalar should be normalized
        )
        assert monitor.ChannelNames == ["single_channel"]
        assert monitor.HWUnits == ["single_hw_unit"]
        assert monitor.PhysicsUnits == ["single_physics_unit"]
        
        # Test FamilyInfoCollection normalization
        family = FamilyInfoCollection(
            MemberOf="single_family",  # Scalar should be normalized
            DeviceList=(1, 2),  # Tuple should be normalized to list
            ElementList=5,  # Scalar should be normalized
            Status=1  # Scalar should be normalized
        )
        assert family.MemberOf == ["single_family"]
        assert family.DeviceList == [(1, 2)]
        assert family.ElementList == [5]
        assert family.Status == [1]
        
        print("✓ Normalization test passed")
        return True
    except Exception as e:
        print(f"✗ Normalization test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing DT4ACC MML Import models...")
    print()
    
    tests = [
        test_imports,
        test_basic_models,
        test_normalization
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print()
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)