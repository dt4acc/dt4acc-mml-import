"""
Pydantic models for MML AO (Accelerator Objects) following DT4ACC specifications.

This module contains Pydantic models that represent the data structures from the
MATLAB Middle Layer accelerator objects with proper validation and normalization.
"""
import logging
from typing import Union, Sequence, Tuple, Dict, Any, Optional
from typing_extensions import TypeAlias

from pydantic import BaseModel, field_validator

logger = logging.getLogger("dt4acc-mml-importer")


# Type definitions for nested sequences
IntSequence2D: TypeAlias = Sequence[Sequence[int]]
FloatSequence2D: TypeAlias = Sequence[Sequence[float]]
DeviceIndex: TypeAlias = Tuple[int, int]
Range: TypeAlias = Tuple[float, float]
# StrSequence: TypeAlias = Sequence[str]
# FloatSequence: TypeAlias = Sequence[float]


class ATElementsInfo(BaseModel):
    """To which element does the device connect to.
    
    Should be always a sequence of integers after normalization.
    """
    ATType: str
    ATIndex: Sequence[Sequence[int]]

    @field_validator('ATIndex')
    @classmethod
    def normalize_at_index(cls, v: Union[int, Sequence[int], Sequence[Sequence[int]]]) -> IntSequence2D:
        """Normalize ATIndex to 2D sequence of integers."""
        if isinstance(v, int):
            return [[v]]
        elif v and isinstance(v[0], int):
            # 1D sequence, convert to 2D
            return [[item] for item in v]
        else:
            # Already 2D sequence, ensure it's properly typed
            return v

    def get_element_indices(self) -> IntSequence2D:
        """Return the normalized element indices."""
        return self.ATIndex


class ConversionFunctionHandle(BaseModel):
    """Function name and file name that does the conversion."""
    file: str
    function: str
    type: str


class ConversionFunction(BaseModel):
    """Conversion function with function handle."""
    function_handle: ConversionFunctionHandle


class MonitorDataModel(BaseModel):
    """Base model for monitor data with normalization."""
    ChannelNames: Sequence[str]
    MemberOf: Optional[Sequence[str]] = None
    DataType: str
    Units: str
    HWUnits: Sequence[str]
    PhysicsUnits: Sequence[str]
    Mode: Optional[str] = None
    MetaGain: Optional[Sequence[float]] = None
    PhysicalUnits: Optional[str] = None
    HW2PhysicsParams: Optional[Sequence[float]] = None
    Physics2HWParams: Optional[Sequence[float]] = None
    HW2PhysicsFcn: Optional[ConversionFunction] = None
    Physics2HWFcn: Optional[ConversionFunction] = None

    @field_validator('ChannelNames')
    @classmethod
    def normalize_channel_names(cls, v: Union[Sequence[str], str]) -> Sequence[str]:
        """Normalize ChannelNames to sequence of strings."""
        if isinstance(v, str):
            return [v]
        return v

    @field_validator('MemberOf')
    @classmethod
    def normalize_member_of(cls, v: Optional[Union[Sequence[str], str]]) -> Optional[Sequence[str]]:
        """Normalize MemberOf to sequence of strings."""
        if v is None:
            return None
        if isinstance(v, str):
            return [v]
        return v

    @field_validator('HWUnits')
    @classmethod
    def normalize_hw_units(cls, v: Union[Sequence[str], str]) -> Sequence[str]:
        """Normalize HWUnits to sequence of strings."""
        if isinstance(v, str):
            return [v]
        return v

    @field_validator('PhysicsUnits')
    @classmethod
    def normalize_physics_units(cls, v: Union[Sequence[str], str]) -> Sequence[str]:
        """Normalize PhysicsUnits to sequence of strings."""
        if isinstance(v, str):
            return [v]
        return v

    @field_validator('MetaGain')
    @classmethod
    def normalize_meta_gain(cls, v: Optional[Union[Sequence[float], float]]) -> Optional[Sequence[float]]:
        """Normalize MetaGain to sequence of floats."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return [float(v)]
        return v

    @field_validator('HW2PhysicsParams')
    @classmethod
    def normalize_hw2physics_params(cls, v: Optional[Union[Sequence[float], float]]) -> Optional[Sequence[float]]:
        """Normalize HW2PhysicsParams to sequence of floats."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return [float(v)]
        return v

    @field_validator('Physics2HWParams')
    @classmethod
    def normalize_physics2hw_params(cls, v: Optional[Union[Sequence[float], float]]) -> Optional[Sequence[float]]:
        """Normalize Physics2HWParams to sequence of floats."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return [float(v)]
        return v


class SetpointDataModel(MonitorDataModel):
    """Setpoint data model extending monitor data."""
    Range: Union[Sequence[Range], Range]

    @field_validator('Range')
    @classmethod
    def normalize_range(cls, v: Union[Sequence[Range], Range]) -> Sequence[Range]:
        """Normalize Range to sequence of float pairs."""
        if isinstance(v, tuple) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
            return [v]
        return v


class FamilyInfoCollection(BaseModel):
    """Collected info entries following Matlab Middle Layer ao object."""
    MemberOf: Union[Sequence[str], str]
    CommonNames: Optional[Union[Sequence[str], str]] = None
    DeviceList: Union[Sequence[DeviceIndex], DeviceIndex]
    ElementList: Union[Sequence[int], int]
    Status: Union[Sequence[int], int]
    Position: Optional[Union[Sequence[float], float]] = None
    Monitor: Optional[MonitorDataModel] = None
    Offset: Optional[Union[Sequence[float], float]] = None
    Setpoint: Optional[SetpointDataModel] = None
    AT: Optional[ATElementsInfo] = None

    @field_validator('MemberOf')
    @classmethod
    def normalize_member_of(cls, v: Union[Sequence[str], str]) -> Sequence[str]:
        """Normalize MemberOf to sequence of strings."""
        if isinstance(v, str):
            return [v]
        return v

    @field_validator('CommonNames')
    @classmethod
    def normalize_common_names(cls, v: Optional[Union[Sequence[str], str]]) -> Optional[Sequence[str]]:
        """Normalize CommonNames to sequence of strings."""
        if v is None:
            return None
        if isinstance(v, str):
            return [v]
        return v

    @field_validator('DeviceList')
    @classmethod
    def normalize_device_list(cls, v: Union[Sequence[DeviceIndex], DeviceIndex]) -> Sequence[DeviceIndex]:
        """Normalize DeviceList to sequence of device indices."""
        if isinstance(v, tuple) and len(v) == 2 and all(isinstance(x, int) for x in v):
            return [v]
        return v

    @field_validator('ElementList')
    @classmethod
    def normalize_element_list(cls, v: Union[Sequence[int], int]) -> Sequence[int]:
        """Normalize ElementList to sequence of integers."""
        if isinstance(v, int):
            return [v]
        return v

    @field_validator('Status')
    @classmethod
    def normalize_status(cls, v: Union[Sequence[int], int]) -> Sequence[int]:
        """Normalize Status to sequence of integers."""
        if isinstance(v, int):
            return [v]
        return v

    @field_validator('Position')
    @classmethod
    def normalize_position(cls, v: Optional[Union[Sequence[float], float]]) -> Optional[Sequence[float]]:
        """Normalize Position to sequence of floats."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return [float(v)]
        return v

    @field_validator('Offset')
    @classmethod
    def normalize_offset(cls, v: Optional[Union[Sequence[float], float]]) -> Optional[Sequence[float]]:
        """Normalize Offset to sequence of floats."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return [float(v)]
        return v

    def get_device_list(self) -> Sequence[DeviceIndex]:
        """Return the normalized device list."""
        return self.DeviceList

    def member_of(self) -> Sequence[str]:
        """Return the normalized member of sequence."""
        return self.MemberOf

    def get_device_index(self, sector: int, child: int) -> int:
        """Get the index of a device in the device list."""
        return self.DeviceList.index((sector, child))


def load(data: Dict[str, Union[str, Dict[str, Any]]]) -> Dict[str, FamilyInfoCollection]:
    """Load data into FamilyInfoCollection models."""
    result = {}
    for family_name, item in data.items():
        try:
            model = FamilyInfoCollection(**item)
            result[family_name] = model
        except Exception as e:
            logger.error(f"Conversion failed for family {family_name}: {e}")
            continue
    return result