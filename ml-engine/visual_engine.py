"""
CivicShield Visual Intelligence Engine — Phase 2
================================================
Implements perceptual image hashing (pHash) for photo deduplication and
EXIF GPS metadata extraction for geofence verification.

Modules:
  compute_image_phash()       -> 64-bit pHash from image bytes or file path
  check_duplicate_photo()     -> cross-project + same-project hash comparison
  extract_exif_gps()          -> lat/lon/timestamp from EXIF tags
  analyse_photo_upload()      -> single-call entry point used by FastAPI routes

Flags emitted (module name, never a crash):
  DUPLICATE_CROSS_PROJECT_PHOTO  - pHash matches another project's photo
  DUPLICATE_SEQUENTIAL_PHOTO     - pHash matches same project's earlier photo
  MISSING_EXIF_METADATA          - EXIF GPS absent or stripped
  GEOFENCE_MISMATCH_ANOMALY      - GPS coords outside 15 km constituency buffer

All functions degrade gracefully when optional libraries are unavailable so
the FastAPI server boots even if imagehash/Pillow/shapely aren't installed yet.
"""

import io
import math
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union

# ---- Pillow (required for pHash and EXIF) ----------------------------------
try:
    from PIL import Image, ExifTags
    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PIL_AVAILABLE = False

# ---- imagehash (perceptual hash) -------------------------------------------
try:
    import imagehash
    _IMAGEHASH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _IMAGEHASH_AVAILABLE = False

# ---- Shapely (geofence polygon) --------------------------------------------
try:
    from shapely.geometry import Point, Polygon
    _SHAPELY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SHAPELY_AVAILABLE = False


# ============================================================================
# Constants
# ============================================================================

PHASH_DUPLICATE_THRESHOLD = 5          # Hamming distance < 5 => duplicate
GEOFENCE_BUFFER_KM = 15.0              # 15 km tolerance around centroid


# ============================================================================
# STEP 2a — Perceptual hash computation
# ============================================================================

def compute_image_phash(
    source: Union[bytes, str]
) -> Optional[str]:
    """
    Compute a 64-bit perceptual hash (pHash) for the given image.

    Args:
        source: Raw image bytes OR a file-system path string.

    Returns:
        Hex-string pHash (e.g. ``"f8c8f0e8f0e0e0e0"``), or ``None`` when
        Pillow/imagehash are not available or the bytes are not a valid image.
    """
    if not (_PIL_AVAILABLE and _IMAGEHASH_AVAILABLE):
        return None

    try:
        if isinstance(source, (bytes, bytearray)):
            img = Image.open(io.BytesIO(source))
        else:
            img = Image.open(str(source))
        img = img.convert("RGB")
        return str(imagehash.phash(img))
    except Exception as exc:
        print(f"[VisualEngine] pHash computation failed: {exc}")
        return None


def phash_distance(hash_a: str, hash_b: str) -> Optional[int]:
    """
    Compute Hamming distance between two hex pHash strings.
    Returns None when either hash is falsy.
    """
    if not (_IMAGEHASH_AVAILABLE and hash_a and hash_b):
        return None
    try:
        return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)
    except Exception:
        return None


# ============================================================================
# STEP 2b — Duplicate detection
# ============================================================================

def check_duplicate_photo(
    new_hash: str,
    work_id: str,
    all_hashes: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    Compare ``new_hash`` against the corpus of stored photo hashes.

    Args:
        new_hash:    pHash string of the newly uploaded image.
        work_id:     Work-ID of the project being updated.
        all_hashes:  List of dicts with keys ``work_id`` and ``photo_hash``
                     pulled from the ``progress_updates`` table.

    Returns:
        List of finding dicts (may be empty).  Each finding has:
        ``severity``, ``title``, ``explanation``, ``evidence``, ``module``
    """
    findings: List[Dict[str, str]] = []
    if not new_hash:
        return findings

    cross_project_match: Optional[str] = None
    same_project_match: Optional[str] = None

    for row in all_hashes:
        stored_hash = row.get("photo_hash") or ""
        stored_wid = row.get("work_id") or ""
        if not stored_hash:
            continue

        dist = phash_distance(new_hash, stored_hash)
        if dist is None:
            continue

        if dist < PHASH_DUPLICATE_THRESHOLD:
            if stored_wid == work_id:
                same_project_match = stored_wid
            else:
                cross_project_match = stored_wid

    if cross_project_match:
        findings.append({
            "severity": "HIGH",
            "title": "Cross-Project Duplicate Photo Detected",
            "explanation": (
                "This progress update photo is an identical or near-identical "
                "duplicate of a photo submitted for another project."
            ),
            "evidence": (
                f"pHash Hamming distance < {PHASH_DUPLICATE_THRESHOLD} against "
                f"photo already filed under project '{cross_project_match}'. "
                "Photo reuse across distinct work sites is a strong ghost-work indicator."
            ),
            "module": "DUPLICATE_CROSS_PROJECT_PHOTO",
        })

    if same_project_match:
        findings.append({
            "severity": "MODERATE",
            "title": "Sequential Duplicate Photo Detected",
            "explanation": (
                "This progress update photo is identical to a photo submitted "
                "in a previous milestone for this project."
            ),
            "evidence": (
                f"pHash Hamming distance < {PHASH_DUPLICATE_THRESHOLD} against "
                "a photo previously uploaded for the same work ID. "
                "Sequential photo reuse suggests milestone fabrication."
            ),
            "module": "DUPLICATE_SEQUENTIAL_PHOTO",
        })

    return findings


# ============================================================================
# STEP 3a — EXIF GPS extraction
# ============================================================================

def _convert_gps_coord(values: Tuple) -> float:
    """
    Convert a GPS coordinate in DMS rational format
    (degrees, minutes, seconds as IFDRational tuples) to decimal degrees.
    """
    def to_float(v: Any) -> float:
        try:
            return float(v.numerator) / float(v.denominator)
        except AttributeError:
            return float(v)

    d, m, s = values
    return to_float(d) + to_float(m) / 60.0 + to_float(s) / 3600.0


def extract_exif_gps(
    source: Union[bytes, str]
) -> Dict[str, Any]:
    """
    Extract GPS coordinates and timestamp from image EXIF data.

    Returns a dict with keys:
        latitude      float | None
        longitude     float | None
        altitude      float | None
        gps_timestamp str | None   ("HH:MM:SS")
        gps_date      str | None   ("YYYY:MM:DD")
        exif_present  bool         (True = GPS block found in EXIF)
        raw_datetime  str | None   (DateTimeOriginal from EXIF)
    """
    result: Dict[str, Any] = {
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "gps_timestamp": None,
        "gps_date": None,
        "exif_present": False,
        "raw_datetime": None,
    }

    if not _PIL_AVAILABLE:
        return result

    try:
        if isinstance(source, (bytes, bytearray)):
            img = Image.open(io.BytesIO(source))
        else:
            img = Image.open(str(source))

        raw_exif = img._getexif()  # type: ignore[attr-defined]
        if not raw_exif:
            return result

        # Build reverse tag map
        tag_map = {v: k for k, v in ExifTags.TAGS.items()}
        gps_tag = ExifTags.TAGS.get(34853, "GPSInfo")  # 34853 = GPSInfo IFD

        # DateTimeOriginal
        dt_tag = tag_map.get("DateTimeOriginal")
        if dt_tag and dt_tag in raw_exif:
            result["raw_datetime"] = str(raw_exif[dt_tag])

        gps_ifd_tag = 34853  # GPSInfo IFD tag number
        gps_data = raw_exif.get(gps_ifd_tag)
        if not gps_data:
            return result

        # Build GPS sub-tag map: {tag_name: value}
        gps_tag_map = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_data.items()}

        lat_vals = gps_tag_map.get("GPSLatitude")
        lat_ref = gps_tag_map.get("GPSLatitudeRef", "N")
        lon_vals = gps_tag_map.get("GPSLongitude")
        lon_ref = gps_tag_map.get("GPSLongitudeRef", "E")
        alt_val = gps_tag_map.get("GPSAltitude")
        ts_val = gps_tag_map.get("GPSTimeStamp")
        date_val = gps_tag_map.get("GPSDateStamp")

        if lat_vals and lon_vals:
            lat = _convert_gps_coord(lat_vals)
            lon = _convert_gps_coord(lon_vals)
            if lat_ref == "S":
                lat = -lat
            if lon_ref == "W":
                lon = -lon
            result["latitude"] = round(lat, 7)
            result["longitude"] = round(lon, 7)
            result["exif_present"] = True

        if alt_val:
            try:
                result["altitude"] = round(float(alt_val.numerator) / float(alt_val.denominator), 2)
            except Exception:
                pass

        if ts_val:
            try:
                h, m, s = [float(x.numerator) / float(x.denominator) for x in ts_val]
                result["gps_timestamp"] = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
            except Exception:
                pass

        if date_val:
            result["gps_date"] = str(date_val)

    except Exception as exc:
        print(f"[VisualEngine] EXIF extraction failed: {exc}")

    return result


# ============================================================================
# STEP 3b — Geofence verification (Haversine fallback when Shapely absent)
# ============================================================================

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two GPS points using Haversine formula."""
    R = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def check_geofence(
    photo_lat: float,
    photo_lon: float,
    constituency_lat: Optional[float],
    constituency_lon: Optional[float],
    polygon_coords: Optional[List[Tuple[float, float]]] = None,
    buffer_km: float = GEOFENCE_BUFFER_KM,
) -> Optional[Dict[str, str]]:
    """
    Verify that a photo's GPS location is within the project's constituency.

    Uses Shapely polygon containment when ``polygon_coords`` is provided;
    falls back to Haversine centroid distance otherwise.

    Returns:
        A finding dict if the photo falls outside the boundary, else ``None``.
    """
    if constituency_lat is None or constituency_lon is None:
        return None  # No reference coordinates — skip geofence check

    # Shapely path: exact polygon containment with buffer
    if _SHAPELY_AVAILABLE and polygon_coords and len(polygon_coords) >= 3:
        try:
            poly = Polygon(polygon_coords)
            # Approximate 1 degree ~ 111 km for buffer expansion
            deg_buffer = buffer_km / 111.0
            buffered = poly.buffer(deg_buffer)
            if not buffered.contains(Point(photo_lon, photo_lat)):
                dist = poly.centroid.distance(Point(photo_lon, photo_lat)) * 111.0
                return _geofence_finding(dist, buffer_km)
            return None
        except Exception as exc:
            print(f"[VisualEngine] Shapely geofence error: {exc}")

    # Haversine fallback
    dist = _haversine_km(photo_lat, photo_lon, constituency_lat, constituency_lon)
    if dist > buffer_km:
        return _geofence_finding(dist, buffer_km)
    return None


def _geofence_finding(dist_km: float, buffer_km: float) -> Dict[str, str]:
    return {
        "severity": "HIGH",
        "title": "Photo Location Outside Constituency Boundary",
        "explanation": (
            "Photo location falls outside the designated constituency boundary. "
            "This may indicate that the photograph was taken at a different site."
        ),
        "evidence": (
            f"GPS coordinates are {dist_km:.1f} km from the constituency centroid, "
            f"exceeding the {buffer_km:.0f} km verification buffer. "
            "Manual field inspection is required to confirm authenticity."
        ),
        "module": "GEOFENCE_MISMATCH_ANOMALY",
    }


# ============================================================================
# STEP 4 — Single-call orchestrator used by FastAPI upload route
# ============================================================================

def analyse_photo_upload(
    image_bytes: bytes,
    work_id: str,
    all_stored_hashes: List[Dict[str, Any]],
    constituency_lat: Optional[float] = None,
    constituency_lon: Optional[float] = None,
    polygon_coords: Optional[List[Tuple[float, float]]] = None,
) -> Dict[str, Any]:
    """
    Full Phase 2 analysis pipeline for a single uploaded image.

    Args:
        image_bytes:         Raw bytes of the uploaded file.
        work_id:             Work ID of the project this photo belongs to.
        all_stored_hashes:   List of ``{work_id, photo_hash}`` dicts from DB.
        constituency_lat:    Reference latitude for geofence check.
        constituency_lon:    Reference longitude for geofence check.
        polygon_coords:      Optional boundary polygon [(lat, lon), ...].

    Returns:
        Dict with:
          photo_hash        str | None   — hex pHash to persist in DB
          sha256            str          — SHA-256 of raw bytes (integrity)
          upload_channel    str          — "DIRECT_UPLOAD" | "STRIPPED_OR_EXTERNAL"
          exif              dict         — output of extract_exif_gps()
          findings          list         — list of visual flag dicts
          gps_status        str          — human-readable GPS status label
          exif_status       str          — human-readable EXIF status label
          duplicate_status  str          — human-readable duplicate status label
    """
    findings: List[Dict[str, str]] = []

    # 1. Cryptographic hash (integrity, always computed)
    sha256 = hashlib.sha256(image_bytes).hexdigest()

    # 2. Perceptual hash (pHash)
    photo_hash = compute_image_phash(image_bytes)

    # 3. Duplicate checks
    if photo_hash:
        dup_findings = check_duplicate_photo(photo_hash, work_id, all_stored_hashes)
        findings.extend(dup_findings)

    # 4. EXIF GPS extraction
    exif = extract_exif_gps(image_bytes)

    # 5. Edge Case A — Missing/stripped metadata
    upload_channel = "DIRECT_UPLOAD"
    if not exif["exif_present"]:
        upload_channel = "STRIPPED_OR_EXTERNAL"
        findings.append({
            "severity": "MODERATE",
            "title": "Missing EXIF Metadata",
            "explanation": (
                "Image metadata is absent or has been stripped. "
                "This commonly occurs when images are shared via WhatsApp or "
                "other messaging apps that remove EXIF data."
            ),
            "evidence": (
                "No GPS block found in image EXIF headers. "
                "Manual verification of the physical site is required."
            ),
            "module": "MISSING_EXIF_METADATA",
        })
    else:
        # 6. Geofence verification (only when GPS is present)
        if exif["latitude"] is not None and exif["longitude"] is not None:
            gf_finding = check_geofence(
                photo_lat=exif["latitude"],
                photo_lon=exif["longitude"],
                constituency_lat=constituency_lat,
                constituency_lon=constituency_lon,
                polygon_coords=polygon_coords,
            )
            if gf_finding:
                findings.append(gf_finding)

    # 7. Build human-readable status labels (consumed by existing `assets` query)
    has_cross_dup = any(f["module"] == "DUPLICATE_CROSS_PROJECT_PHOTO" for f in findings)
    has_seq_dup = any(f["module"] == "DUPLICATE_SEQUENTIAL_PHOTO" for f in findings)
    has_geofence = any(f["module"] == "GEOFENCE_MISMATCH_ANOMALY" for f in findings)

    if has_cross_dup:
        duplicate_status = "DUPLICATE_CROSS_PROJECT"
    elif has_seq_dup:
        duplicate_status = "DUPLICATE_SEQUENTIAL"
    else:
        duplicate_status = "Unique Image Hash"

    if not exif["exif_present"]:
        exif_status = "Metadata Stripped / Missing"
        gps_status = "GPS Unavailable"
    elif has_geofence:
        exif_status = "Valid Camera EXIF Metadata"
        gps_status = "GPS OUTSIDE BOUNDARY"
    else:
        exif_status = "Valid Camera EXIF Metadata"
        gps_status = "Verified GPS Coordinate Match"

    return {
        "photo_hash": photo_hash,
        "sha256": sha256,
        "upload_channel": upload_channel,
        "exif": exif,
        "findings": findings,
        "gps_status": gps_status,
        "exif_status": exif_status,
        "duplicate_status": duplicate_status,
    }
