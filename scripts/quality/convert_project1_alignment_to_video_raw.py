#!/usr/bin/env python3
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
FRAME_NAME_RE = re.compile(r"_frame_(\d+)\.(png|jpe?g)$", re.IGNORECASE)


def load_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid json: {exc}") from exc
    return rows


def resolve_artifact_path(path_str):
    raw_path = str(path_str).strip()
    normalized = raw_path.replace("\\", "/")
    candidates = []
    for candidate_str in (raw_path, normalized):
        if not candidate_str:
            continue
        candidate = Path(candidate_str)
        candidates.append(candidate)
        if not candidate.is_absolute():
            candidates.append(REPO_ROOT / candidate)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    fallback = Path(normalized)
    if fallback.is_absolute():
        return fallback
    return REPO_ROOT / fallback


def decoded_artifact_exists(record):
    path = record.get("decoded_output_path")
    if not path or str(path).startswith("<skipped>"):
        return False
    return resolve_artifact_path(path).exists()


def select_alignment_record(records):
    for record in records:
        if decoded_artifact_exists(record):
            return record
    return records[0]


def load_decoded_detections(record):
    path_str = record.get("decoded_output_path")
    if not path_str or str(path_str).startswith("<skipped>"):
        return []
    path = resolve_artifact_path(path_str)
    if not path.exists():
        raise SystemExit(f"decoded_output_path not found: {path}")
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("detections", [])
    if isinstance(data, list):
        return data
    raise SystemExit(f"Unsupported decoded payload format: {path}")


def xyxy_to_xywh(box):
    if len(box) != 4:
        raise SystemExit(f"bbox_xyxy must have 4 values, got {box}")
    x1, y1, x2, y2 = [float(v) for v in box]
    return [x1, y1, x2 - x1, y2 - y1]


def extract_frame_id(input_id):
    match = FRAME_NAME_RE.search(str(input_id))
    if not match:
        return None
    return int(match.group(1))


def manifest_frame_ids(manifest):
    frame_scope = (manifest.get("alignment_use") or {}).get("frame_scope")
    if frame_scope == "full_video_frames":
        return list(range(int(manifest["frame_count"])))
    return [int(x) for x in manifest["frame_ids"]]


def build_output_row(record, manifest, frame_id, detections):
    normalized = []
    for det in detections:
        if "bbox_xyxy" not in det:
            raise SystemExit(
                f"{record.get('decoded_output_path')}: detection missing bbox_xyxy"
            )
        normalized.append({
            "class_id": int(det["class_id"]),
            "confidence": float(det["confidence"]),
            "bbox_xywh": xyxy_to_xywh(det["bbox_xyxy"]),
        })
    return {
        "run_id": record.get("run_id"),
        "project": "03_video_pipeline",
        "source_project": "01_vision_deploy",
        "measurement_scope": "frame",
        "input_source_id": manifest["source_input_source_id"],
        "input_source_type": "video_file",
        "input_width": manifest.get("width"),
        "input_height": manifest.get("height"),
        "input_fps": manifest.get("fps"),
        "source_video_path": manifest.get("source_video_path"),
        "source_video_sha256": manifest.get("source_video_sha256"),
        "frame_id": frame_id,
        "frame_image_id": record.get("input_id"),
        "output_valid": True,
        "detection_count": len(normalized),
        "detections": normalized,
        "status": "pass",
        "quality_metric_name": "fixed_input_alignment",
        "decoded_output_path": record.get("decoded_output_path"),
        "source_raw_result_path": record.get("_source_raw_result_path"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project1-raw", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8-sig"))
    expected_frame_ids = manifest_frame_ids(manifest)
    expected_frame_set = set(expected_frame_ids)

    groups = defaultdict(list)
    for record in load_jsonl(args.project1_raw):
        input_id = record.get("input_id")
        if not input_id:
            continue
        frame_id = extract_frame_id(input_id)
        if frame_id is None:
            continue
        if frame_id not in expected_frame_set:
            continue
        record["_source_raw_result_path"] = args.project1_raw
        groups[frame_id].append(record)

    missing = [frame_id for frame_id in expected_frame_ids if frame_id not in groups]
    if missing:
        sample = ", ".join(str(x) for x in missing[:10])
        raise SystemExit(
            f"missing {len(missing)} manifest frames in project1 raw: {sample}"
        )

    output_rows = []
    for frame_id in expected_frame_ids:
        record = select_alignment_record(groups[frame_id])
        detections = load_decoded_detections(record)
        output_rows.append(build_output_row(record, manifest, frame_id, detections))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"frames={len(output_rows)}")
    print(f"output={output_path}")
    print(f"source_project1_raw={args.project1_raw}")


if __name__ == "__main__":
    main()
