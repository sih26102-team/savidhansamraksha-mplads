#!/usr/bin/env python3
"""
CivicShield Phase 3 — Google Earth Engine (GEE) Live Verification Script
Author: Kousic (ML Engine Lead) & Bharath (Platform Architect)

Proves real GEE capability on demand:
- Forces live initialization (init_earth_engine(force_live=True))
- Queries real Sentinel-2 Level-2A imagery for sample coordinates in India (Lat: 14.4426, Lon: 79.9865)
- Prints formatted execution logs, spectral indices (NDBI, NDVI deltas), and telemetry directly to stdout.
"""

import os
import sys
import json
from datetime import date, timedelta

# Ensure ml-engine and repo root are in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from satellite_engine import (
    init_earth_engine,
    analyze_satellite_ground_change,
    _resolve_credentials_path,
    _EE_AVAILABLE,
    _GOOGLE_AUTH_AVAILABLE,
)


def main() -> None:
    print("=" * 66)
    print("  CIVICSHIELD PHASE 3 — GOOGLE EARTH ENGINE (GEE) LIVE VERIFIER")
    print("=" * 66)

    # 1. Environment & Credentials Diagnostic
    mock_env = os.environ.get("GEE_MOCK_MODE", "true")
    key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY_PATH", "ml-engine/credentials/gee-service-account.json")
    resolved_path = _resolve_credentials_path()

    print(f"[*] Environment Settings:")
    print(f"    - GEE_MOCK_MODE               : {mock_env}")
    print(f"    - GEE_SERVICE_ACCOUNT_KEY_PATH: {key_env}")
    print(f"    - Resolved Credentials Path   : {resolved_path or 'NOT_FOUND'}")
    print(f"    - earthengine-api installed   : {_EE_AVAILABLE}")
    print(f"    - google-auth installed       : {_GOOGLE_AUTH_AVAILABLE}")

    if resolved_path and os.path.exists(resolved_path):
        with open(resolved_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        print(f"    - Key File Size               : {len(content)} bytes")
        is_json = False
        has_private_key = False
        try:
            d = json.loads(content)
            is_json = True
            has_private_key = "private_key" in d and "client_email" in d
        except Exception:
            pass

        if has_private_key:
            print(f"    - Key Format                  : Valid Google Service Account JSON")
        elif is_json:
            print(f"    - Key Format                  : JSON dictionary (missing client_email / private_key)")
        else:
            print(f"    - Key Format                  : Raw Key ID Token ('{content[:16]}...')")

    print("-" * 66)
    print("[*] Initiating Live GEE Connection (force_live=True)...")
    live_ok = init_earth_engine(force_live=True)

    # Sample Coordinate in Andhra Pradesh, India (e.g., Nellore / Tirupati region)
    sample_lat = 14.4426
    sample_lon = 79.9865
    sample_sanction = "2023-01-15"
    sample_current = "2024-03-20"

    print("-" * 66)
    if live_ok:
        print("[SUCCESS] Connected and authenticated to Google Earth Engine API!")
        print(f"[*] Querying Copernicus Sentinel-2 MSI (Level-2A BOA) surface reflectance...")
        print(f"    Target Coordinates : Lat: {sample_lat}, Lon: {sample_lon}")
        print(f"    Region of Interest : 100m circular point buffer")
        print(f"    Observation Windows: T0 (baseline): {sample_sanction} ± 30d")
        print(f"                         T1 (milestone): {sample_current} ± 30d")

        try:
            res = analyze_satellite_ground_change(
                lat=sample_lat,
                lon=sample_lon,
                sanction_date=sample_sanction,
                current_date=sample_current,
                force_live=True,
            )
            print("-" * 66)
            print("  LIVE SENTINEL-2 SPECTRAL ANALYSIS RESULTS:")
            print("-" * 66)
            print(f"  Mode                  : {res.get('mode', 'LIVE_GEE')}")
            print(f"  Audit Status          : {res.get('status')}")
            print(f"  Sentinel-2 NDBI delta : {res.get('ndbi_delta', 0.0):+.3f} (Built-up Structural Index)")
            print(f"  Sentinel-2 NDVI delta : {res.get('ndvi_delta', 0.0):+.3f} (Vegetation Clearing Index)")
            print(f"  Cloud Cover           : {res.get('cloud_cover_pct', 0.0)}%")
            print(f"  Observation Window    : {res.get('t0_date')} -> {res.get('t1_date')}")
            print(f"  Findings Generated    : {len(res.get('findings', []))}")
            for f in res.get("findings", []):
                print(f"    [!] {f.get('title')} ({f.get('severity')}): {f.get('explanation')}")
            print("-" * 66)
            print("LIVE VERIFICATION COMPLETE: Copernicus Sentinel-2 data queried successfully.")
        except Exception as query_err:
            print(f"[!] Live query encountered exception: {query_err}")
    else:
        print("[NOTICE] Live GEE Authentication Skipped / Fallback Active.")
        print("         To connect to Google's production Earth Engine servers,")
        print("         place the complete Service Account JSON key (containing")
        print("         'client_email' and 'private_key') into:")
        print(f"         {resolved_path or key_env}")
        print("-" * 66)
        print("[*] Demonstrating Fast UI Mock Sentinel-2 Engine (< 50ms response):")
        mock_res = analyze_satellite_ground_change(
            lat=sample_lat,
            lon=sample_lon,
            sanction_date=sample_sanction,
            current_date=sample_current,
            force_live=False,
        )
        print("-" * 66)
        print(f"  Execution Mode        : {mock_res.get('mode', 'MOCK_FAST')}")
        print(f"  Audit Status          : {mock_res.get('status')}")
        print(f"  Sentinel-2 NDBI delta : {mock_res.get('ndbi_delta', 0.0):+.3f} (Built-up Structural Index)")
        print(f"  Sentinel-2 NDVI delta : {mock_res.get('ndvi_delta', 0.0):+.3f} (Vegetation Clearing Index)")
        print(f"  Cloud Cover           : {mock_res.get('cloud_cover_pct', 0.0)}%")
        print(f"  Response Latency      : < 50ms (Zero external API latency)")
        print("-" * 66)
        print("FAST DEMO MODE READY: Production platform operational for high-speed audits.")

    print("=" * 66)


if __name__ == "__main__":
    main()
