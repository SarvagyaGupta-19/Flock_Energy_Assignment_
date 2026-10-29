"""
Meter routes.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.meter import MeterDetail, MeterListResponse, ReadingsResponse
from app.portal.meters import (
    fetch_all_meters,
    get_meter_by_id,
    get_meter_readings,
    list_and_filter_meters,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meters", tags=["Meters"])


@router.get("", response_model=MeterListResponse, summary="List, search, and filter meters")
async def get_meters(
    q: str = Query("", description="Search query matching Meter ID or Serial Number"),
    make: Optional[str] = Query(None, description="Filter by manufacturer (e.g. Genus, HPL, L&T, Secure, Allied)"),
    phase_type: Optional[str] = Query(None, description="Filter by phase: 'single' or 'three'"),
    install_status: Optional[str] = Query(None, description="Filter by status: 'Installed', 'Faulty', 'Decommissioned'"),
    dt_code: Optional[str] = Query(None, description="Filter by DT code (e.g. DT-001)"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Returns a paginated list of smart meters with optional filtering."""
    return await list_and_filter_meters(
        q=q,
        make=make,
        phase_type=phase_type,
        install_status=install_status,
        dt_code=dt_code,
        page=page,
        page_size=page_size,
    )


@router.get("/export", response_model=list[MeterDetail], summary="Bulk dataset export")
async def export_meters():
    """Returns the complete, unpaginated dataset of all 403 meters."""
    return await fetch_all_meters()


@router.get("/{meter_id}", response_model=MeterDetail, summary="Get single meter details")
async def get_meter(meter_id: str):
    """Retrieve full details for a specific meter by ID (e.g. J100000)."""
    return await get_meter_by_id(meter_id)


@router.get("/{meter_id}/readings", response_model=ReadingsResponse, summary="Get consumption readings")
async def get_readings(meter_id: str):
    """Retrieve 30-minute interval smart-meter consumption readings for a meter."""
    return await get_meter_readings(meter_id)
