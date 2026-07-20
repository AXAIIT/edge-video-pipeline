#!/usr/bin/env python3
from pathlib import Path


REASON_LEGACY_INHERITED = "legacy_inherited_raw_scope"
REASON_CROSS_PROJECT_ALIGNMENT = "cross_project_alignment_reference_only"
REASON_INVALID_INPUT_ORIENTATION = "invalid_input_orientation_720x1280"
REASON_HISTORICAL_INVALID_JSON = "historical_invalid_json_diagnostic"
REASON_ADHOC_SERVICE_RAW = "adhoc_service_raw_outside_formal_scope"
REASON_ADHOC_PREVIEW_RAW = "adhoc_preview_raw_outside_formal_scope"

DEFAULT_EXCLUDED_SUBDIRS = (
    "02_quantization",
)

DEFAULT_EXCLUDED_NAME_KEYWORDS = {
    "project1_baseline": REASON_CROSS_PROJECT_ALIGNMENT,
    "project2_int8_baseline": REASON_CROSS_PROJECT_ALIGNMENT,
    "20260619_rk3588_8gb_yolo11n_rknn_bdd100k_full80_": REASON_INVALID_INPUT_ORIENTATION,
    "20260619_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_v3": REASON_HISTORICAL_INVALID_JSON,
    "20260619_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_v4": REASON_HISTORICAL_INVALID_JSON,
    "20260623_jetson_8gb_yolo11n_tensorrt_imx219_preview_": REASON_ADHOC_PREVIEW_RAW,
    "20260622_rk3588_8gb_astra_preview_": REASON_ADHOC_PREVIEW_RAW,
    "rdk_x5_8gb_yolo11n_bpu_imx219_hbn_preview_": REASON_ADHOC_PREVIEW_RAW,
    "rdk_x5_8gb_yolo11n_bpu_service": REASON_ADHOC_SERVICE_RAW,
"rk3588_8gb_yolo11n_rknn_service": REASON_ADHOC_SERVICE_RAW,
"rk3588_8gb_yolo11n_rknn_camera_service": REASON_ADHOC_SERVICE_RAW,
}


def default_excluded_scope_reason():
    return (
        "Exclude legacy inherited raw, cross-project baseline/alignment raw, "
        "known-invalid-orientation RK3588 BDD100K raw, historical invalid-JSON "
        "Jetson disconnect diagnostics, ad-hoc preview/visual-debug raw, and "
        "temporary/ad-hoc service raw."
    )


def resolve_excluded_subdirs(extra_excluded=None, include_legacy=False):
    excluded = [] if include_legacy else list(DEFAULT_EXCLUDED_SUBDIRS)
    if extra_excluded:
        excluded.extend(extra_excluded)

    deduped = []
    seen = set()
    for item in excluded:
        name = str(item).strip()
        if not name or name in seen:
            continue
        deduped.append(name)
        seen.add(name)
    return deduped


def classify_jsonl_path(path, exclude_subdirs=None, include_legacy=False):
    candidate = Path(path)
    parts = set(candidate.parts)
    for subdir in exclude_subdirs or ():
        if subdir in parts:
            if subdir == "02_quantization":
                return REASON_LEGACY_INHERITED
            return f"excluded_subdir:{subdir}"
    if not include_legacy:
        lower_name = candidate.name.lower()
        for keyword, reason in DEFAULT_EXCLUDED_NAME_KEYWORDS.items():
            if keyword in lower_name:
                return reason
    return ""


def collect_jsonl_inputs(root, pattern="*.jsonl", exclude_subdirs=None, include_legacy=False):
    base = Path(root)
    resolved_excludes = resolve_excluded_subdirs(exclude_subdirs, include_legacy)

    if base.is_file():
        candidates = [base]
    else:
        candidates = sorted(base.rglob(pattern))

    included = []
    excluded = []
    for path in candidates:
        reason = classify_jsonl_path(path, resolved_excludes, include_legacy=include_legacy)
        if reason:
            excluded.append((path, reason))
        else:
            included.append(path)
    return included, excluded
