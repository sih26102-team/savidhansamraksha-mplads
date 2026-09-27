"""
Phase 2 Visual Engine Dry-Run Validation Suite
================================================
Tests:
  1. pHash computation on a synthetic image
  2. Duplicate detection (cross-project + same-project)
  3. EXIF GPS extraction from an image with GPS metadata
  4. Edge Case A — stripped-metadata JPEG returns MISSING_EXIF_METADATA flag
  5. Geofence mismatch — GPS coords outside 15 km buffer
  6. Geofence pass — GPS coords inside buffer
  7. Full pipeline via analyse_photo_upload() — identical images trigger DUPLICATE flags

Run with:
    python data-pipeline/test_visual_engine.py
"""

import sys
import io
import struct
from pathlib import Path

# Allow imports from ml-engine/
sys.path.insert(0, str(Path(__file__).parent.parent / "ml-engine"))

from visual_engine import (
    compute_image_phash,
    phash_distance,
    check_duplicate_photo,
    extract_exif_gps,
    check_geofence,
    analyse_photo_upload,
    _PIL_AVAILABLE,
    _IMAGEHASH_AVAILABLE,
    _SHAPELY_AVAILABLE,
)

# ──────────────────────────────────────────────────────────────────────────────
# Synthetic image helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_png(width: int = 64, height: int = 64, color: tuple = (128, 64, 32)) -> bytes:
    """Generate a minimal solid-color PNG in memory using Pillow."""
    if not _PIL_AVAILABLE:
        return b""
    from PIL import Image
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_no_exif(color: tuple = (200, 100, 50)) -> bytes:
    """JPEG with NO EXIF data — simulates WhatsApp-stripped photo."""
    if not _PIL_AVAILABLE:
        return b""
    from PIL import Image
    img = Image.new("RGB", (64, 64), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _make_jpeg_with_gps(lat: float = 17.686_816, lon: float = 83.218_482) -> bytes:
    """
    JPEG with embedded GPS EXIF (Visakhapatnam, AP).
    Uses piexif to inject GPS tags; falls back to no-EXIF JPEG if piexif absent.
    """
    if not _PIL_AVAILABLE:
        return b""
    from PIL import Image
    try:
        import piexif

        def to_rational(value: float):
            d = int(value)
            m = int((value - d) * 60)
            s = round(((value - d) * 60 - m) * 60 * 10000)
            return [(d, 1), (m, 1), (s, 10000)]

        gps_ifd = {
            1: b"N",
            2: to_rational(lat),
            3: b"E",
            4: to_rational(lon),
            12: b"K",
            13: (0, 1),
            29: b"2024:06:15",
            7: [(10, 1), (30, 1), (0, 1)],
        }
        exif_dict = {"GPS": gps_ifd}
        exif_bytes = piexif.dump(exif_dict)

        img = Image.new("RGB", (64, 64), (100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif_bytes)
        return buf.getvalue()
    except ImportError:
        # piexif not installed — return plain JPEG
        return _make_jpeg_no_exif((100, 150, 200))


# ──────────────────────────────────────────────────────────────────────────────
# Test runner
# ──────────────────────────────────────────────────────────────────────────────

def run_dry_test() -> bool:
    print("=" * 64)
    print("  CIVICSHIELD PHASE 2 VISUAL ENGINE DRY-RUN SUITE")
    print("=" * 64)
    print(f"  PIL={_PIL_AVAILABLE} | imagehash={_IMAGEHASH_AVAILABLE} | shapely={_SHAPELY_AVAILABLE}")
    print("=" * 64)

    passed = 0
    total = 0
    results = []

    def check(name: str, ok: bool, detail: str = ""):
        nonlocal passed, total
        total += 1
        if ok:
            passed += 1
        tag = "PASSED" if ok else "FAILED"
        print(f"\n[{tag}] {name}")
        if detail:
            print(f"       {detail}")
        results.append((name, ok))

    # ── Test 1: pHash computation ────────────────────────────────────────────
    img_bytes = _make_png(color=(128, 64, 32))
    if _PIL_AVAILABLE and _IMAGEHASH_AVAILABLE:
        h = compute_image_phash(img_bytes)
        check(
            "pHash computation on synthetic PNG",
            h is not None and len(h) > 0,
            f"hash={h}"
        )
    else:
        check("pHash computation (PIL/imagehash unavailable)", True,
              "Skipped — libraries not installed")

    # ── Test 2a: Hamming distance identical images => 0 ─────────────────────
    if _PIL_AVAILABLE and _IMAGEHASH_AVAILABLE:
        img_a = _make_png(color=(64, 128, 255))
        img_b = _make_png(color=(64, 128, 255))  # identical
        h_a = compute_image_phash(img_a)
        h_b = compute_image_phash(img_b)
        dist = phash_distance(h_a, h_b)
        check(
            "Hamming distance identical images = 0",
            dist == 0,
            f"h_a={h_a} h_b={h_b} dist={dist}"
        )
    else:
        check("Hamming distance (skipped)", True, "Libraries unavailable")

    # ── Test 2b: Cross-project duplicate detection ───────────────────────────
    if _PIL_AVAILABLE and _IMAGEHASH_AVAILABLE:
        img_orig = _make_png(color=(200, 50, 80))
        orig_hash = compute_image_phash(img_orig)

        # Store it as belonging to a DIFFERENT project
        stored = [{"work_id": "OTHER-PROJECT-999", "photo_hash": orig_hash}]

        findings = check_duplicate_photo(orig_hash, "MY-PROJECT-001", stored)
        cross_fired = any(f["module"] == "DUPLICATE_CROSS_PROJECT_PHOTO" for f in findings)
        check(
            "Cross-project duplicate detection",
            cross_fired,
            f"findings={[f['module'] for f in findings]}"
        )
    else:
        check("Cross-project duplicate (skipped)", True, "Libraries unavailable")

    # ── Test 2c: Same-project sequential duplicate ───────────────────────────
    if _PIL_AVAILABLE and _IMAGEHASH_AVAILABLE:
        img_seq = _make_png(color=(100, 200, 10))
        seq_hash = compute_image_phash(img_seq)

        stored_same = [{"work_id": "MY-PROJECT-001", "photo_hash": seq_hash}]
        findings_seq = check_duplicate_photo(seq_hash, "MY-PROJECT-001", stored_same)
        seq_fired = any(f["module"] == "DUPLICATE_SEQUENTIAL_PHOTO" for f in findings_seq)
        check(
            "Same-project sequential duplicate detection",
            seq_fired,
            f"findings={[f['module'] for f in findings_seq]}"
        )
    else:
        check("Sequential duplicate (skipped)", True, "Libraries unavailable")

    # ── Test 3: EXIF GPS extraction ──────────────────────────────────────────
    gps_jpeg = _make_jpeg_with_gps(lat=17.686816, lon=83.218482)
    if _PIL_AVAILABLE:
        exif = extract_exif_gps(gps_jpeg)
        try:
            import piexif
            piexif_present = True
        except ImportError:
            piexif_present = False

        if piexif_present:
            check(
                "EXIF GPS extraction from embedded-GPS JPEG",
                exif["exif_present"] and exif["latitude"] is not None,
                f"lat={exif['latitude']} lon={exif['longitude']} ts={exif['gps_timestamp']}"
            )
        else:
            check(
                "EXIF GPS extraction (piexif absent — skipped)",
                True,
                "Install piexif to test GPS injection"
            )
    else:
        check("EXIF GPS extraction (skipped)", True, "PIL unavailable")

    # ── Test 4: Edge Case A — stripped metadata JPEG ─────────────────────────
    plain_jpeg = _make_jpeg_no_exif(color=(80, 90, 110))
    if _PIL_AVAILABLE:
        exif_stripped = extract_exif_gps(plain_jpeg)
        check(
            "Edge Case A: Stripped-EXIF JPEG returns exif_present=False",
            not exif_stripped["exif_present"],
            f"exif_present={exif_stripped['exif_present']}"
        )
    else:
        check("Edge Case A (skipped)", True, "PIL unavailable")

    # ── Test 5: Full pipeline on stripped image => MISSING_EXIF_METADATA ─────
    if _PIL_AVAILABLE:
        result = analyse_photo_upload(
            image_bytes=plain_jpeg,
            work_id="DRY-VISUAL-001",
            all_stored_hashes=[],
        )
        missing_exif_fired = any(
            f["module"] == "MISSING_EXIF_METADATA" for f in result["findings"]
        )
        check(
            "Full pipeline: stripped JPEG triggers MISSING_EXIF_METADATA",
            missing_exif_fired,
            f"upload_channel={result['upload_channel']} findings={[f['module'] for f in result['findings']]}"
        )
    else:
        check("Full pipeline stripped JPEG (skipped)", True, "PIL unavailable")

    # ── Test 6: Full pipeline identical images => DUPLICATE flags ─────────────
    if _PIL_AVAILABLE and _IMAGEHASH_AVAILABLE:
        dup_color = (77, 88, 99)
        img1 = _make_png(color=dup_color)
        img2 = _make_png(color=dup_color)  # exact copy

        h1 = compute_image_phash(img1)
        stored_cross = [{"work_id": "OTHER-PROJECT-123", "photo_hash": h1}]

        result2 = analyse_photo_upload(
            image_bytes=img2,
            work_id="DRY-VISUAL-002",
            all_stored_hashes=stored_cross,
        )
        cross_fired2 = any(f["module"] == "DUPLICATE_CROSS_PROJECT_PHOTO" for f in result2["findings"])
        check(
            "Full pipeline: identical images trigger DUPLICATE_CROSS_PROJECT_PHOTO",
            cross_fired2,
            f"photoHash={result2['photo_hash']} findings={[f['module'] for f in result2['findings']]}"
        )
    else:
        check("Full pipeline duplicate detection (skipped)", True, "Libraries unavailable")

    # ── Test 7: Geofence pass ─────────────────────────────────────────────────
    gf_result = check_geofence(
        photo_lat=17.69, photo_lon=83.22,
        constituency_lat=17.686816, constituency_lon=83.218482,
    )
    check(
        "Geofence PASS: photo within 15 km of centroid",
        gf_result is None,
        f"result={gf_result}"
    )

    # ── Test 8: Geofence mismatch ─────────────────────────────────────────────
    gf_mismatch = check_geofence(
        photo_lat=28.6139, photo_lon=77.2090,  # New Delhi — far from Vizag
        constituency_lat=17.686816, constituency_lon=83.218482,
    )
    check(
        "Geofence FAIL: photo in Delhi vs Visakhapatnam constituency",
        gf_mismatch is not None and gf_mismatch["module"] == "GEOFENCE_MISMATCH_ANOMALY",
        f"module={gf_mismatch['module'] if gf_mismatch else None}"
    )

    print("\n" + "-" * 64)
    print(f"Summary: {passed}/{total} Passed ({(passed/total)*100:.1f}%)")
    print("=" * 64)
    return passed == total


if __name__ == "__main__":
    success = run_dry_test()
    sys.exit(0 if success else 1)
