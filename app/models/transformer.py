"""
Pydantic models for Distribution Transformers and the network hierarchy tree.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Transformer(BaseModel):
    code: str = Field(..., description="DT code, e.g. DT-001")
    name: str = Field(..., description="Transformer name, e.g. Malviya Nagar DT 1")
    feeder_code: str = Field(..., description="Parent feeder code, e.g. F-001")
    capacity_kva: Optional[float] = Field(None, description="Transformer rated capacity in kVA")


class TransformerListResponse(BaseModel):
    data: list[Transformer]
    total: int
    page: int
    page_size: int
    total_pages: int


class NetworkNode(BaseModel):
    id: str = Field(..., description="Unique node identifier or code")
    name: str = Field(..., description="Human-readable node label")
    level: str = Field(..., description="Hierarchy level: zone, circle, division, subdivision, substation, feeder, dt, or meter")
    meter_count: Optional[int] = Field(None, description="Total active meters under this subtree")
    children: list["NetworkNode"] = Field(default_factory=list, description="Child nodes in the network")


NetworkNode.model_rebuild()
