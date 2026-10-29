"""
End-to-end test suite for Urja Meter Ops API.
Tests all endpoints using httpx AsyncClient and ASGITransport.
"""

import asyncio
import httpx
from app.main import app

async def run_tests():
    print("=" * 60)
    print("RUNNING END-TO-END API TEST SUITE")
    print("=" * 60)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health
        print("\n[1] Testing GET /health...")
        r = await client.get("/health")
        assert r.status_code == 200, f"Health check failed: {r.status_code}"
        print("    -> OK:", r.json())

        # 2. Meters list
        print("\n[2] Testing GET /meters?page=1&page_size=5...")
        r = await client.get("/meters?page=1&page_size=5")
        assert r.status_code == 200, f"Meters list failed: {r.status_code}"
        data = r.json()
        assert data["total"] == 403, f"Expected 403 total meters, got {data['total']}"
        assert len(data["data"]) == 5, f"Expected 5 items, got {len(data['data'])}"
        print(f"    -> OK: Total meters = {data['total']}, Page size = {len(data['data'])}")

        # 3. Filtered meters (Make = Genus)
        print("\n[3] Testing GET /meters?make=Genus...")
        r = await client.get("/meters?make=Genus")
        assert r.status_code == 200
        data = r.json()
        for m in data["data"]:
            assert m["make"].lower() == "genus", f"Filter mismatch: {m['make']}"
        print(f"    -> OK: Found {data['total']} Genus meters.")

        # 4. Meter detail
        print("\n[4] Testing GET /meters/J100000...")
        r = await client.get("/meters/J100000")
        assert r.status_code == 200, f"Meter detail failed: {r.status_code}"
        m = r.json()
        assert m["meter_id"] == "J100000"
        assert m["dt_code"] == "DT-001"
        assert m["hierarchy"]["zone"]["name"] == "Jaipur Zone 1"
        assert m["location"]["latitude"] is not None
        print(f"    -> OK: J100000 details verified. DT: {m['dt_code']}, Lat: {m['location']['latitude']}")

        # 5. Consumption readings
        print("\n[5] Testing GET /meters/J100000/readings...")
        r = await client.get("/meters/J100000/readings")
        assert r.status_code == 200, f"Readings failed: {r.status_code}"
        readings = r.json()
        assert readings["count"] > 0, "No readings returned"
        first = readings["readings"][0]
        assert "timestamp" in first and "kwh" in first and "kvah" in first
        print(f"    -> OK: Retrieved {readings['count']} readings.")

        # 6. Distribution Transformers
        print("\n[6] Testing GET /transformers...")
        r = await client.get("/transformers?page=1&page_size=10")
        assert r.status_code == 200
        dts = r.json()
        assert dts["total"] == 40, f"Expected 40 DTs, got {dts['total']}"
        print(f"    -> OK: Total DTs = {dts['total']}")

        # 7. Network Hierarchy Tree
        print("\n[7] Testing GET /network...")
        r = await client.get("/network")
        assert r.status_code == 200
        tree = r.json()
        assert tree["level"] == "root"
        assert tree["meter_count"] == 403
        print(f"    -> OK: Root tree node has {tree['meter_count']} meters.")

        # 8. 404 Not Found handling
        print("\n[8] Testing GET /meters/NON_EXISTENT_ID (404)...")
        r = await client.get("/meters/NON_EXISTENT_METER")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        print("    -> OK: Returned 404 as expected:", r.json())

    print("\n" + "=" * 60)
    print("ALL 8 TESTS PASSED! SERVICE IS SOLID & OPERATIONAL.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())
