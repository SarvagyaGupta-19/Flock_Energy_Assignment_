"""
Portal service layer for meters, consumption readings, and bulk inventory.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from fastapi import HTTPException

from app.cache import meters_cache, readings_cache
from app.models.meter import (
    GeoLocation,
    MeterDetail,
    MeterHierarchy,
    MeterListResponse,
    NamedCode,
    Reading,
    ReadingsResponse,
)
from app.portal.client import portal_client

logger = logging.getLogger(__name__)


def _map_portal_meter(raw: dict) -> MeterDetail:
    """Transform raw meter object (from bulk export) into MeterDetail."""
    raw_geo = raw.get("geo") or {}
    location = GeoLocation(
        latitude=raw_geo.get("lat"),
        longitude=raw_geo.get("lng") or raw_geo.get("lon"),
    )

    raw_hier = raw.get("hierarchy") or {}
    hierarchy = MeterHierarchy()
    for level in ("zone", "circle", "division", "subdivision", "substation", "feeder", "dt"):
        item = raw_hier.get(level)
        if isinstance(item, dict) and "name" in item and "code" in item:
            setattr(hierarchy, level, NamedCode(name=item["name"], code=item["code"]))

    return MeterDetail(
        meter_id=raw.get("meterId", ""),
        serial_no=raw.get("serialNo", ""),
        make=raw.get("make", "Unknown"),
        phase_type=raw.get("phaseType", "single"),
        install_status=raw.get("installStatus", "Installed"),
        install_type=raw.get("installType") or raw.get("installationType"),
        build=raw.get("build"),
        dt_code=raw.get("dtCode", ""),
        location=location,
        hierarchy=hierarchy,
    )


async def fetch_all_meters() -> list[MeterDetail]:
    """
    Fetch the complete meter inventory via the portal's HMAC-signed export endpoint.
    Caches the parsed result in memory.
    """
    cache_key = "meters:all"
    cached = await meters_cache.get(cache_key)
    if cached is not None:
        return cached

    secret = await portal_client.get_signing_secret()
    headers = portal_client.sign_request("GET", "/portal/export", "page=1", secret)

    resp = await portal_client.get("/portal/export?page=1", headers=headers)
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Portal export failed (HTTP {resp.status_code}): {resp.text[:200]}",
        )

    data = resp.json()
    raw_list = data.get("data", []) if isinstance(data, dict) else data
    meters = [_map_portal_meter(m) for m in raw_list]

    await meters_cache.set(cache_key, meters)
    return meters


async def list_and_filter_meters(
    q: str = "",
    make: Optional[str] = None,
    phase_type: Optional[str] = None,
    install_status: Optional[str] = None,
    dt_code: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> MeterListResponse:
    """Filter and paginate the meter inventory."""
    all_meters = await fetch_all_meters()
    filtered = all_meters

    if q:
        query_lower = q.strip().lower()
        filtered = [
            m for m in filtered
            if query_lower in m.meter_id.lower() or query_lower in m.serial_no.lower()
        ]

    if make:
        filtered = [m for m in filtered if m.make.lower() == make.strip().lower()]

    if phase_type:
        filtered = [m for m in filtered if m.phase_type.value.lower() == phase_type.strip().lower()]

    if install_status:
        filtered = [m for m in filtered if m.install_status.value.lower() == install_status.strip().lower()]

    if dt_code:
        filtered = [m for m in filtered if m.dt_code.lower() == dt_code.strip().lower()]

    total = len(filtered)
    total_pages = max(1, math.ceil(total / page_size))
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_data = filtered[start_idx:end_idx]

    return MeterListResponse(
        data=page_data,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def get_meter_by_id(meter_id: str) -> MeterDetail:
    """Fetch single meter detail by ID from cached inventory or direct portal check."""
    all_meters = await fetch_all_meters()
    for m in all_meters:
        if m.meter_id.upper() == meter_id.strip().upper():
            return m

    # Fallback point check to confirm 404
    resp = await portal_client.get(f"/portal/meters/{meter_id}/geo")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")

    raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")


async def get_meter_readings(meter_id: str) -> ReadingsResponse:
    """Fetch 30-minute interval readings for a meter from /portal/meters/{id}/energy."""
    cache_key = f"readings:{meter_id}"
    cached = await readings_cache.get(cache_key)
    if cached is not None:
        return cached

    # Verify meter exists
    await get_meter_by_id(meter_id)

    resp = await portal_client.get(f"/portal/meters/{meter_id}/energy")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Readings for meter '{meter_id}' not found.")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Portal error: HTTP {resp.status_code}")

    data = resp.json()
    raw_rows = data.get("data", []) if isinstance(data, dict) else data

    readings = []
    for row in raw_rows:
        try:
            readings.append(
                Reading(
                    timestamp=row["timestamp"],
                    kwh=row["kwh"],
                    kvah=row["kvah"],
                    voltage_r=row.get("voltR"),
                )
            )
        except Exception as exc:
            logger.debug("Skipping malformed reading: %s (%s)", row, exc)

    result = ReadingsResponse(
        meter_id=meter_id,
        count=len(readings),
        readings=readings,
    )
    await readings_cache.set(cache_key, result)
    return result
