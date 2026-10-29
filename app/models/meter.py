"""
Pydantic models for meters, readings, and hierarchy.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class InstallStatus(str, Enum):
    installed = "Installed"
    faulty = "Faulty"
    decommissioned = "Decommissioned"


class PhaseType(str, Enum):
    single = "single"
    three = "three"


class GeoLocation(BaseModel):
    latitude: Optional[float] = Field(None, description="GPS Latitude")
    longitude: Optional[float] = Field(None, description="GPS Longitude")


class NamedCode(BaseModel):
    name: str = Field(..., description="Human-readable entity name")
    code: str = Field(..., description="Entity code or identifier")


class MeterHierarchy(BaseModel):
    zone: Optional[NamedCode] = None
    circle: Optional[NamedCode] = None
    division: Optional[NamedCode] = None
    subdivision: Optional[NamedCode] = None
    substation: Optional[NamedCode] = None
    feeder: Optional[NamedCode] = None
    dt: Optional[NamedCode] = None


class MeterSummary(BaseModel):
    meter_id: str = Field(..., description="Unique meter identifier, e.g. J100000")
    serial_no: str = Field(..., description="Manufacturer serial number")
    make: str = Field(..., description="Meter manufacturer brand (e.g. Genus, HPL, L&T, Secure, Allied)")
    phase_type: PhaseType = Field(..., description="Phase configuration (single or three)")
    install_status: InstallStatus = Field(..., description="Operational status")
    dt_code: str = Field(..., description="Associated Distribution Transformer code, e.g. DT-001")


class MeterDetail(MeterSummary):
    install_type: Optional[str] = Field(None, description="Installation type (e.g. Whole Current)")
    build: Optional[str] = Field(None, description="Hardware build category (e.g. legacy, modern)")
    location: GeoLocation = Field(default_factory=GeoLocation, description="Geographic coordinates")
    hierarchy: MeterHierarchy = Field(default_factory=MeterHierarchy, description="7-level network ancestry")


class MeterListResponse(BaseModel):
    data: list[MeterDetail]
    total: int
    page: int
    page_size: int
    total_pages: int


class Reading(BaseModel):
    timestamp: datetime = Field(..., description="Reading interval timestamp (UTC/ISO-8601)")
    kwh: float = Field(..., description="Active energy (kWh) cumulative register")
    kvah: float = Field(..., description="Apparent energy (kVAh) cumulative register")
    voltage_r: Optional[float] = Field(None, description="R-phase voltage (V)")

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
        return v

    @field_validator("kwh", "kvah", "voltage_r", mode="before")
    @classmethod
    def parse_numeric(cls, v):
        if v is None or v == "":
            return None
        return float(v)


class ReadingsResponse(BaseModel):
    meter_id: str
    count: int
    readings: list[Reading]
