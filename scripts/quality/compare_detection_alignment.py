#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def read_jsonl(path):
    rows = {}
    with Path(path).open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "frame_id" not in row:
                raise SystemExit(f"{path}:{line_no}: missing frame_id")
            rows[int(row["frame_id"])] = row
    return rows


def load_manifest(path):
    manifest = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    frame_scope = (manifest.get("alignment_use") or {}).get(
        "frame_scope", "provided_quality_frames"
    )
    raw_frame_ids = manifest.get("frame_ids") or []
    source_frame_count = int(manifest.get("frame_count", len(raw_frame_ids)))
    if frame_scope == "full_video_frames":
        expected = list(range(source_frame_count))
        frame_ids = [int(x) for x in (raw_frame_ids or expected)]
        if frame_ids != expected:
            raise SystemExit(
                "full_video_frames manifest must contain every frame_id from 0 to "
                f"{source_frame_count - 1} in order"
            )
    elif frame_scope == "provided_quality_frames":
        frame_ids = [int(x) for x in raw_frame_ids]
        provided_count = int(
            (manifest.get("alignment_use") or {}).get(
                "provided_quality_frame_count", len(frame_ids)
            )
        )
        if len(frame_ids) != provided_count:
            raise SystemExit(
                "provided_quality_frame_count does not match manifest frame_ids: "
                f"{provided_count} != {len(frame_ids)}"
            )
    else:
        raise SystemExit(f"unsupported alignment frame_scope: {frame_scope}")
    return manifest, frame_ids, frame_scope, source_frame_count


def load_pipeline_summary(path):
    if not path:
        return None
    summary_path = Path(path)
    if not summary_path.is_file():
        raise SystemExit(f"pipeline summary not found: {summary_path}")
    with summary_path.open("r", encoding="utf-8-sig", newline="") as f:
        row = next(csv.DictReader(f), None)
    if row is None:
        raise SystemExit(f"pipeline summary is empty: {summary_path}")
    return row


def format_summary_value(value):
    if value in (None, ""):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.6f}".rstrip("0").rstrip(".")


def xywh_to_xyxy(box):
    x, y, w, h = [float(v) for v in box]
    return x, y, x + w, y + h


def iou(a, b):
    ax1, ay1, ax2, ay2 = xywh_to_xyxy(a)
    bx1, by1, bx2, by2 = xywh_to_xyxy(b)
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def detections(row, conf_min):
    dets = row.get("detections") or []
    out = []
    for det in dets:
        if float(det.get("confidence", 0.0)) < conf_min:
            continue
        if "bbox_xywh" not in det:
            continue
        out.append({
            "class_id": int(det["class_id"]),
            "confidence": float(det["confidence"]),
            "bbox_xywh": det["bbox_xywh"],
        })
    return out


def detection_payload_status(row):
    if not row:
        return "missing_frame"
    if "detections" not in row:
        return "missing_detections"
    if not isinstance(row["detections"], list):
        return "invalid_detections"
    return "ok"


def match_frame(base_dets, cur_dets, iou_min):
    used = set()
    matches = []
    unmatched_base = []
    for b_idx, base in enumerate(base_dets):
        best_idx = None
        best_iou = 0.0
        for c_idx, cur in enumerate(cur_dets):
            if c_idx in used or cur["class_id"] != base["class_id"]:
                continue
            score = iou(base["bbox_xywh"], cur["bbox_xywh"])
            if score > best_iou:
                best_iou = score
                best_idx = c_idx
        if best_idx is not None and best_iou >= iou_min:
            used.add(best_idx)
            cur = cur_dets[best_idx]
            matches.append({
                "base_class_id": base["class_id"],
                "cur_class_id": cur["class_id"],
                "iou": best_iou,
                "confidence_abs_diff": abs(base["confidence"] - cur["confidence"]),
            })
        else:
            unmatched_base.append(base)
    unmatched_cur = [cur for idx, cur in enumerate(cur_dets) if idx not in used]
    return matches, unmatched_base, unmatched_cur


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--pipeline-summary", default="")
    parser.add_argument("--iou-min", type=float, default=0.50)
    parser.add_argument("--confidence-min", type=float, default=0.25)
    parser.add_argument("--class-match-rate-min", type=float, default=0.98)
    parser.add_argument("--mean-iou-min", type=float, default=0.90)
    parser.add_argument(
        "--require-no-unmatched-current",
        action="store_true",
        help="Fail when current has detections that cannot be matched to baseline.",
    )
    args = parser.parse_args()

    baseline = read_jsonl(args.baseline)
    current = read_jsonl(args.current)
    manifest, frame_ids, frame_scope, source_frame_count = load_manifest(args.manifest)
    frame_coverage = len(frame_ids) / source_frame_count if source_frame_count else 0.0
    pipeline_summary = load_pipeline_summary(args.pipeline_summary)

    detail_rows = []
    total_base = 0
    total_current = 0
    total_matches = 0
    total_unmatched_baseline = 0
    total_unmatched_current = 0
    ious = []
    conf_diffs = []
    payload_issues = []
    for frame_id in frame_ids:
        base_row = baseline.get(frame_id, {})
        cur_row = current.get(frame_id, {})
        base_payload_status = detection_payload_status(base_row)
        cur_payload_status = detection_payload_status(cur_row)
        if base_payload_status != "ok" or cur_payload_status != "ok":
            payload_issues.append({
                "frame_id": frame_id,
                "baseline_payload_status": base_payload_status,
                "current_payload_status": cur_payload_status,
            })

        base_dets = detections(base_row, args.confidence_min)
        cur_dets = detections(cur_row, args.confidence_min)
        matches, unmatched_base, unmatched_cur = match_frame(base_dets, cur_dets, args.iou_min)
        total_base += len(base_dets)
        total_current += len(cur_dets)
        total_matches += len(matches)
        total_unmatched_baseline += len(unmatched_base)
        total_unmatched_current += len(unmatched_cur)
        ious.extend(m["iou"] for m in matches)
        conf_diffs.extend(m["confidence_abs_diff"] for m in matches)
        detail_rows.append({
            "frame_id": frame_id,
            "baseline_count": len(base_dets),
            "current_count": len(cur_dets),
            "matched_count": len(matches),
            "unmatched_baseline_count": len(unmatched_base),
            "unmatched_current_count": len(unmatched_cur),
            "baseline_payload_status": base_payload_status,
            "current_payload_status": cur_payload_status,
            "mean_matched_iou": sum(m["iou"] for m in matches) / len(matches) if matches else "",
            "mean_conf_abs_diff": sum(m["confidence_abs_diff"] for m in matches) / len(matches) if matches else "",
        })

    class_match_rate = total_matches / total_base if total_base else 0.0
    mean_iou = sum(ious) / len(ious) if ious else 0.0
    mean_conf_diff = sum(conf_diffs) / len(conf_diffs) if conf_diffs else 0.0
    status = "pass" if (
        not payload_issues
        and total_base > 0
        and class_match_rate >= args.class_match_rate_min
        and mean_iou >= args.mean_iou_min
        and (not args.require_no_unmatched_current or total_unmatched_current == 0)
    ) else "fail"

    csv_path = Path(args.output_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()) if detail_rows else ["frame_id"])
        writer.writeheader()
        writer.writerows(detail_rows)

    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# Fixed-input Detection Alignment\n\n")
        f.write(f"- baseline: `{args.baseline}`\n")
        f.write(f"- current: `{args.current}`\n")
        f.write(f"- manifest: `{args.manifest}`\n")
        f.write(f"- frame_scope: {frame_scope}\n")
        f.write(f"- source_video_frames: {source_frame_count}\n")
        f.write(f"- frames: {len(frame_ids)}\n")
        f.write(f"- quality_frame_coverage: {frame_coverage:.6f}\n")
        f.write(f"- payload_issue_count: {len(payload_issues)}\n")
        f.write(f"- total_baseline_detections: {total_base}\n")
        f.write(f"- total_current_detections: {total_current}\n")
        f.write(f"- total_matches: {total_matches}\n")
        f.write(f"- total_unmatched_baseline: {total_unmatched_baseline}\n")
        f.write(f"- total_unmatched_current: {total_unmatched_current}\n")
        f.write(f"- require_no_unmatched_current: {str(args.require_no_unmatched_current).lower()}\n")
        f.write(f"- class_match_rate: {class_match_rate:.6f}\n")
        f.write(f"- mean_matched_iou: {mean_iou:.6f}\n")
        f.write(f"- mean_conf_abs_diff: {mean_conf_diff:.6f}\n")
        f.write(f"- status: {status}\n")
        if pipeline_summary:
            metrics = [
                ("frames", "frames"),
                ("duration_sec_estimated", "duration_sec"),
                ("fps_estimated", "fps"),
                ("latency_p50_ms", "end_to_end_p50_ms"),
                ("latency_p95_ms", "end_to_end_p95_ms"),
                ("latency_p99_ms", "end_to_end_p99_ms"),
                ("preprocess_p50_ms", "preprocess_p50_ms"),
                ("preprocess_p95_ms", "preprocess_p95_ms"),
                ("preprocess_p99_ms", "preprocess_p99_ms"),
                ("inference_p50_ms", "inference_p50_ms"),
                ("inference_p95_ms", "inference_p95_ms"),
                ("inference_p99_ms", "inference_p99_ms"),
                ("postprocess_p50_ms", "postprocess_p50_ms"),
                ("postprocess_p95_ms", "postprocess_p95_ms"),
                ("postprocess_p99_ms", "postprocess_p99_ms"),
                ("output_p50_ms", "output_p50_ms"),
                ("output_p95_ms", "output_p95_ms"),
                ("output_p99_ms", "output_p99_ms"),
                ("drop_frame_count_total_estimated", "drop_frames"),
                ("drop_frame_rate_total_estimated", "drop_rate"),
                ("memory_mb_peak", "process_memory_peak_mb"),
                ("temperature_c_peak", "temperature_peak_c"),
            ]
            f.write("\n## Pipeline Timing Context\n\n")
            f.write(
                "This fixed-input run is paced at the source video's FPS and is intended for quality "
                "alignment. These timings are diagnostic context, not the formal realtime benchmark.\n\n"
            )
            f.write(f"- pipeline_summary: `{args.pipeline_summary}`\n\n")
            f.write("| metric | value |\n")
            f.write("|---|---:|\n")
            for source_key, label in metrics:
                f.write(f"| {label} | {format_summary_value(pipeline_summary.get(source_key))} |\n")
        if payload_issues:
            f.write("\n## Payload Issues\n\n")
            f.write("| frame_id | baseline_payload_status | current_payload_status |\n")
            f.write("|---:|---|---|\n")
            for issue in payload_issues:
                f.write(
                    f"| {issue['frame_id']} | {issue['baseline_payload_status']} | "
                    f"{issue['current_payload_status']} |\n"
                )

    print(f"status={status}")
    print(f"report={md_path}")
    print(f"details={csv_path}")
    if pipeline_summary:
        for key in (
            "fps_estimated",
            "latency_p50_ms",
            "latency_p95_ms",
            "latency_p99_ms",
            "inference_p50_ms",
            "inference_p95_ms",
            "inference_p99_ms",
        ):
            print(f"{key}={format_summary_value(pipeline_summary.get(key))}")
    if status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
