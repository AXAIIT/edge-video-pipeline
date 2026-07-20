#!/usr/bin/env python3
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


COCO_CLASS_NAMES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    4: "airplane",
    5: "bus",
    6: "train",
    7: "truck",
    8: "boat",
    9: "traffic_light",
    10: "fire_hydrant",
    11: "stop_sign",
    12: "parking_meter",
    13: "bench",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    18: "sheep",
    19: "cow",
    20: "elephant",
    21: "bear",
    22: "zebra",
    23: "giraffe",
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    27: "tie",
    28: "suitcase",
    29: "frisbee",
    30: "skis",
    31: "snowboard",
    32: "sports_ball",
    33: "kite",
    34: "baseball_bat",
    35: "baseball_glove",
    36: "skateboard",
    37: "surfboard",
    38: "tennis_racket",
    39: "bottle",
    40: "wine_glass",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    46: "banana",
    47: "apple",
    48: "sandwich",
    49: "orange",
    50: "broccoli",
    51: "carrot",
    52: "hot_dog",
    53: "pizza",
    54: "donut",
    55: "cake",
    56: "chair",
    57: "couch",
    58: "potted_plant",
    59: "bed",
    60: "dining_table",
    61: "toilet",
    62: "tv",
    63: "laptop",
    64: "mouse",
    65: "remote",
    66: "keyboard",
    67: "cell_phone",
    68: "microwave",
    69: "oven",
    70: "toaster",
    71: "sink",
    72: "refrigerator",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
    77: "teddy_bear",
    78: "hair_drier",
    79: "toothbrush",
}

SMALL_AREA_MAX = 32 * 32
MEDIUM_AREA_MAX = 96 * 96


def coco_name(class_id):
    return COCO_CLASS_NAMES.get(int(class_id), f"class_{class_id}")


def jsonl_files(path):
    path = Path(path)
    if path.is_dir():
        return sorted(path.glob("*.jsonl"))
    return [path]


def resolve_path(value, repo_root):
    path = Path(value)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def read_rows(path, default_sequence_id=None):
    rows = []
    for file_path in jsonl_files(path):
        sequence_id = default_sequence_id or file_path.stem
        with file_path.open("r", encoding="utf-8-sig") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if "frame_id" not in row:
                    raise SystemExit(f"{file_path}:{line_no}: missing frame_id")
                row.setdefault("sequence_id", sequence_id)
                rows.append(row)
    return rows


def row_key(row):
    return str(row["sequence_id"]), int(row["frame_id"])


def bool_attr(det, key):
    return bool((det.get("attributes") or {}).get(key, False))


def size_bucket(area):
    if area < SMALL_AREA_MAX:
        return "small"
    if area < MEDIUM_AREA_MAX:
        return "medium"
    return "large"


def is_difficult(record):
    return (
        record["size_bucket"] == "small"
        or record["occluded"]
        or record["truncated"]
        or record["crowd"]
    )


def gt_detections_for_focus(row, focus_class_ids):
    out = []
    for det in row.get("detections", []):
        class_id = int(det.get("class_id", -1))
        if class_id not in focus_class_ids:
            continue
        if "bbox_xywh" not in det:
            continue
        box = [float(v) for v in det["bbox_xywh"]]
        area = box[2] * box[3]
        record = {
            "class_id": class_id,
            "class_name": coco_name(class_id),
            "source_category": det.get("source_category", ""),
            "bbox_xywh": box,
            "area": area,
            "size_bucket": size_bucket(area),
            "occluded": bool_attr(det, "occluded"),
            "truncated": bool_attr(det, "truncated"),
            "crowd": bool_attr(det, "crowd"),
        }
        record["difficult"] = is_difficult(record)
        out.append(record)
    return out


def pred_detections(row, confidence_min):
    out = []
    for det in row.get("detections", []):
        confidence = float(det.get("confidence", 0.0))
        if confidence < confidence_min:
            continue
        if "bbox_xywh" not in det:
            continue
        class_id = int(det.get("class_id", -1))
        out.append({
            "class_id": class_id,
            "class_name": coco_name(class_id),
            "confidence": confidence,
            "bbox_xywh": [float(v) for v in det["bbox_xywh"]],
        })
    return out


def xywh_to_xyxy(box):
    x, y, w, h = [float(v) for v in box]
    return x, y, x + w, y + h


def box_iou(a, b):
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


def best_pred_for_gt(gt_det, pred_dets, class_filter=None):
    best = None
    for pred in pred_dets:
        if class_filter is not None and pred["class_id"] != class_filter:
            continue
        score = box_iou(gt_det["bbox_xywh"], pred["bbox_xywh"])
        if best is None or score > best["iou"] or (
            score == best["iou"] and pred["confidence"] > best["confidence"]
        ):
            best = {
                "class_id": pred["class_id"],
                "class_name": pred["class_name"],
                "confidence": pred["confidence"],
                "iou": score,
            }
    return best


def load_batch_rows(batch_csv, repo_root):
    rows = []
    with Path(batch_csv).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                **row,
                "raw_path_abs": resolve_path(row["raw_path"], repo_root),
                "label_path_abs": resolve_path(row["label_path"], repo_root),
            })
    return rows


def analyze_run(batch_csv, tag, repo_root, focus_class_ids, iou_min, default_confidence_min, coarse_iou_min):
    batch_rows = load_batch_rows(batch_csv, repo_root)
    object_rows = []

    for batch_row in batch_rows:
        conf_min_str = batch_row.get("confidence_min", "")
        confidence_min = float(conf_min_str) if conf_min_str else default_confidence_min
        label_rows = read_rows(batch_row["label_path_abs"], default_sequence_id=batch_row["sequence_id"])
        pred_rows = read_rows(batch_row["raw_path_abs"], default_sequence_id=batch_row["sequence_id"])
        pred_by_key = {row_key(row): row for row in pred_rows}

        for label_row in label_rows:
            key = row_key(label_row)
            pred_row = pred_by_key.get(key, {"detections": []})
            gt_dets = gt_detections_for_focus(label_row, focus_class_ids)
            pred_dets = pred_detections(pred_row, confidence_min)
            for gt_idx, gt in enumerate(gt_dets):
                best_same = best_pred_for_gt(gt, pred_dets, class_filter=gt["class_id"])
                best_any = best_pred_for_gt(gt, pred_dets)
                matched_same_class = bool(best_same and best_same["iou"] >= iou_min)
                any_iou50 = bool(best_any and best_any["iou"] >= iou_min)
                any_iou_coarse = bool(best_any and best_any["iou"] >= coarse_iou_min)

                if matched_same_class:
                    error_mode = "matched_same_class"
                elif any_iou50:
                    error_mode = "wrong_class_iou50"
                elif any_iou_coarse:
                    error_mode = "coarse_localization_only"
                else:
                    error_mode = "no_overlap"

                object_rows.append({
                    "run_tag": tag,
                    "sequence_id": key[0],
                    "frame_id": key[1],
                    "focus_class_id": gt["class_id"],
                    "focus_class_name": gt["class_name"],
                    "source_category": gt["source_category"],
                    "size_bucket": gt["size_bucket"],
                    "occluded": gt["occluded"],
                    "truncated": gt["truncated"],
                    "crowd": gt["crowd"],
                    "difficult": gt["difficult"],
                    "matched_same_class": int(matched_same_class),
                    "best_same_iou": f"{best_same['iou']:.6f}" if best_same else "",
                    "best_same_confidence": f"{best_same['confidence']:.6f}" if best_same else "",
                    "best_any_iou": f"{best_any['iou']:.6f}" if best_any else "",
                    "best_any_class_id": best_any["class_id"] if best_any else "",
                    "best_any_class_name": best_any["class_name"] if best_any else "",
                    "best_any_confidence": f"{best_any['confidence']:.6f}" if best_any else "",
                    "error_mode": error_mode,
                })

    return object_rows


def aggregate_source_category(rows, run_tags, focus_class_ids):
    out = []
    for class_id in focus_class_ids:
        class_name = coco_name(class_id)
        source_categories = sorted({
            row["source_category"] for row in rows
            if int(row["focus_class_id"]) == class_id
        })
        for source_category in source_categories:
            base = {
                "class_id": class_id,
                "class_name": class_name,
                "source_category": source_category,
            }
            for tag in run_tags:
                subset = [
                    row for row in rows
                    if row["run_tag"] == tag
                    and int(row["focus_class_id"]) == class_id
                    and row["source_category"] == source_category
                ]
                gt_count = len(subset)
                matched = sum(int(row["matched_same_class"]) for row in subset)
                recall = matched / gt_count if gt_count else 0.0
                base[f"{tag}_gt_count"] = gt_count
                base[f"{tag}_matched_gt"] = matched
                base[f"{tag}_recall"] = f"{recall:.6f}"
            out.append(base)
    return out


def aggregate_error_modes(rows, target_tag, focus_class_ids):
    out = []
    for class_id in focus_class_ids:
        subset = [
            row for row in rows
            if row["run_tag"] == target_tag and int(row["focus_class_id"]) == class_id
        ]
        gt_count = len(subset)
        counts = Counter(row["error_mode"] for row in subset)
        out.append({
            "run_tag": target_tag,
            "class_id": class_id,
            "class_name": coco_name(class_id),
            "gt_count": gt_count,
            "matched_same_class": counts["matched_same_class"],
            "wrong_class_iou50": counts["wrong_class_iou50"],
            "coarse_localization_only": counts["coarse_localization_only"],
            "no_overlap": counts["no_overlap"],
            "matched_same_class_rate": f"{counts['matched_same_class'] / gt_count if gt_count else 0.0:.6f}",
            "wrong_class_iou50_rate": f"{counts['wrong_class_iou50'] / gt_count if gt_count else 0.0:.6f}",
            "coarse_localization_only_rate": f"{counts['coarse_localization_only'] / gt_count if gt_count else 0.0:.6f}",
            "no_overlap_rate": f"{counts['no_overlap'] / gt_count if gt_count else 0.0:.6f}",
        })
    return out


def aggregate_wrong_class(rows, target_tag, focus_class_ids):
    grouped = Counter()
    totals = Counter()
    for row in rows:
        if row["run_tag"] != target_tag:
            continue
        class_id = int(row["focus_class_id"])
        if class_id not in focus_class_ids:
            continue
        if row["error_mode"] != "wrong_class_iou50":
            continue
        pred_name = row["best_any_class_name"] or "unknown"
        grouped[(class_id, pred_name)] += 1
        totals[class_id] += 1

    out = []
    for (class_id, pred_name), count in sorted(grouped.items(), key=lambda item: (-item[1], item[0][0], item[0][1])):
        total = totals[class_id]
        out.append({
            "run_tag": target_tag,
            "focus_class_id": class_id,
            "focus_class_name": coco_name(class_id),
            "predicted_class_name": pred_name,
            "count": count,
            "share_of_wrong_class_iou50": f"{count / total if total else 0.0:.6f}",
        })
    return out


def aggregate_slice(rows, target_tag, focus_class_ids):
    slice_defs = [
        ("all", lambda r: True),
        ("source_pedestrian", lambda r: r["source_category"] == "pedestrian"),
        ("source_rider", lambda r: r["source_category"] == "rider"),
        ("size_small", lambda r: r["size_bucket"] == "small"),
        ("size_medium", lambda r: r["size_bucket"] == "medium"),
        ("size_large", lambda r: r["size_bucket"] == "large"),
        ("difficult", lambda r: bool(r["difficult"])),
        ("non_difficult", lambda r: not bool(r["difficult"])),
        ("large_non_difficult", lambda r: r["size_bucket"] == "large" and not bool(r["difficult"])),
        ("occluded_true", lambda r: bool(r["occluded"])),
        ("truncated_true", lambda r: bool(r["truncated"])),
    ]
    out = []
    for class_id in focus_class_ids:
        class_rows = [
            row for row in rows
            if row["run_tag"] == target_tag and int(row["focus_class_id"]) == class_id
        ]
        class_gt = len(class_rows)
        for slice_name, predicate in slice_defs:
            subset = [row for row in class_rows if predicate(row)]
            gt_count = len(subset)
            matched = sum(int(row["matched_same_class"]) for row in subset)
            out.append({
                "run_tag": target_tag,
                "class_id": class_id,
                "class_name": coco_name(class_id),
                "slice_name": slice_name,
                "gt_count": gt_count,
                "matched_gt": matched,
                "recall": f"{matched / gt_count if gt_count else 0.0:.6f}",
                "share_of_class_gt": f"{gt_count / class_gt if class_gt else 0.0:.6f}",
            })
    return out


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(input_pairs, source_rows, error_rows, wrong_rows, slice_rows, target_tag):
    source_by_key = {(row["class_name"], row["source_category"]): row for row in source_rows}
    error_by_class = {row["class_name"]: row for row in error_rows}
    slice_by_key = {(row["class_name"], row["slice_name"]): row for row in slice_rows}

    run_tags = [tag for _, tag in input_pairs]
    lines = [
        "# BDD100K Focus-class Domain-gap Analysis",
        "",
        "## Inputs",
        "",
    ]
    for batch_csv, tag in input_pairs:
        lines.append(f"- {tag}: `{batch_csv}`")
    lines.extend([
        f"- target_run_for_error_breakdown: `{target_tag}`",
        "- focus_classes: `person, bicycle, train`",
        "- miss_pattern_policy: `matched_same_class / wrong_class_iou50 / coarse_localization_only / no_overlap`",
        "- inference note: `wrong_class_iou50` is stronger evidence for category/label-definition mismatch; `no_overlap` is stronger evidence for domain/representation mismatch.",
        "",
        "## Source-category Recall",
        "",
    ])

    source_headers = ["class_name", "source_category"]
    for tag in run_tags:
        source_headers.extend([f"{tag}_gt_count", f"{tag}_recall"])
    lines.append("| " + " | ".join(source_headers) + " |")
    lines.append("|" + "|".join(["---"] + ["---:" if h.endswith("_count") or h.endswith("_recall") else "---" for h in source_headers[1:]]) + "|")
    for key in sorted(source_by_key.keys()):
        row = source_by_key[key]
        values = [row["class_name"], row["source_category"]]
        for tag in run_tags:
            values.extend([str(row.get(f"{tag}_gt_count", 0)), row.get(f"{tag}_recall", "0.000000")])
        lines.append("| " + " | ".join(values) + " |")

    lines.extend([
        "",
        f"## Miss Pattern on `{target_tag}`",
        "",
        "| class_name | gt_count | matched_same_class | wrong_class_iou50 | coarse_localization_only | no_overlap |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for class_name in ("person", "bicycle", "train"):
        row = error_by_class.get(class_name)
        if not row:
            continue
        lines.append(
            f"| {class_name} | {row['gt_count']} | "
            f"{row['matched_same_class']} ({row['matched_same_class_rate']}) | "
            f"{row['wrong_class_iou50']} ({row['wrong_class_iou50_rate']}) | "
            f"{row['coarse_localization_only']} ({row['coarse_localization_only_rate']}) | "
            f"{row['no_overlap']} ({row['no_overlap_rate']}) |"
        )

    lines.extend([
        "",
        f"## Wrong-class Strong Overlap on `{target_tag}`",
        "",
        "| focus_class | predicted_class | count | share_of_wrong_class_iou50 |",
        "|---|---|---:|---:|",
    ])
    if wrong_rows:
        for row in wrong_rows:
            lines.append(
                f"| {row['focus_class_name']} | {row['predicted_class_name']} | "
                f"{row['count']} | {row['share_of_wrong_class_iou50']} |"
            )
    else:
        lines.append("| none | none | 0 | 0.000000 |")

    lines.extend([
        "",
        f"## Key Slices on `{target_tag}`",
        "",
        "| class_name | slice_name | gt_count | share_of_class_gt | recall |",
        "|---|---|---:|---:|---:|",
    ])
    for class_name in ("person", "bicycle", "train"):
        for slice_name in ("source_pedestrian", "source_rider", "size_large", "large_non_difficult", "difficult", "non_difficult"):
            row = slice_by_key.get((class_name, slice_name))
            if not row or int(row["gt_count"]) == 0:
                continue
            lines.append(
                f"| {class_name} | {slice_name} | {row['gt_count']} | "
                f"{row['share_of_class_gt']} | {row['recall']} |"
            )

    lines.extend([
        "",
        "## Reading Guide",
        "",
        "- `person/source_rider` 若显著低于 `person/source_pedestrian`，说明 BDD `rider -> person` 映射存在明显类别语义张力。",
        "- `bicycle` 若主要落在 `wrong_class_iou50`，而错类集中到 `person` / `motorcycle`，更像骑行场景的类别口径问题。",
        "- `train` 若大框且非 difficult 仍长期 0 recall，同时大量落在 `no_overlap` 或 `coarse_localization_only`，更像 COCO->BDD 域差或训练分布不足，而不是单纯阈值问题。",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Analyze focus-class domain-gap signals on BDD100K outputs")
    parser.add_argument("--batch-csv", action="append", required=True)
    parser.add_argument("--tag", action="append", required=True)
    parser.add_argument("--focus-class-ids", default="0,1,6")
    parser.add_argument("--iou-min", type=float, default=0.50)
    parser.add_argument("--coarse-iou-min", type=float, default=0.10)
    parser.add_argument("--default-confidence-min", type=float, default=0.25)
    parser.add_argument("--target-tag")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-source-csv", required=True)
    parser.add_argument("--output-error-csv", required=True)
    parser.add_argument("--output-wrong-class-csv", required=True)
    parser.add_argument("--output-slice-csv", required=True)
    parser.add_argument("--output-detail-csv", required=True)
    args = parser.parse_args()

    if len(args.batch_csv) != len(args.tag):
        raise SystemExit("--batch-csv and --tag must appear the same number of times")

    repo_root = Path(args.repo_root).resolve()
    focus_class_ids = [int(x) for x in args.focus_class_ids.split(",") if x.strip()]
    input_pairs = list(zip(args.batch_csv, args.tag))
    target_tag = args.target_tag or args.tag[-1]

    all_rows = []
    for batch_csv, tag in input_pairs:
        all_rows.extend(
            analyze_run(
                batch_csv=batch_csv,
                tag=tag,
                repo_root=repo_root,
                focus_class_ids=focus_class_ids,
                iou_min=args.iou_min,
                default_confidence_min=args.default_confidence_min,
                coarse_iou_min=args.coarse_iou_min,
            )
        )

    source_rows = aggregate_source_category(all_rows, args.tag, focus_class_ids)
    error_rows = aggregate_error_modes(all_rows, target_tag, focus_class_ids)
    wrong_rows = aggregate_wrong_class(all_rows, target_tag, focus_class_ids)
    slice_rows = aggregate_slice(all_rows, target_tag, focus_class_ids)

    write_csv(
        args.output_detail_csv,
        all_rows,
        [
            "run_tag",
            "sequence_id",
            "frame_id",
            "focus_class_id",
            "focus_class_name",
            "source_category",
            "size_bucket",
            "occluded",
            "truncated",
            "crowd",
            "difficult",
            "matched_same_class",
            "best_same_iou",
            "best_same_confidence",
            "best_any_iou",
            "best_any_class_id",
            "best_any_class_name",
            "best_any_confidence",
            "error_mode",
        ],
    )
    write_csv(
        args.output_source_csv,
        source_rows,
        list(source_rows[0].keys()) if source_rows else ["class_id", "class_name", "source_category"],
    )
    write_csv(
        args.output_error_csv,
        error_rows,
        [
            "run_tag",
            "class_id",
            "class_name",
            "gt_count",
            "matched_same_class",
            "wrong_class_iou50",
            "coarse_localization_only",
            "no_overlap",
            "matched_same_class_rate",
            "wrong_class_iou50_rate",
            "coarse_localization_only_rate",
            "no_overlap_rate",
        ],
    )
    write_csv(
        args.output_wrong_class_csv,
        wrong_rows,
        [
            "run_tag",
            "focus_class_id",
            "focus_class_name",
            "predicted_class_name",
            "count",
            "share_of_wrong_class_iou50",
        ],
    )
    write_csv(
        args.output_slice_csv,
        slice_rows,
        [
            "run_tag",
            "class_id",
            "class_name",
            "slice_name",
            "gt_count",
            "matched_gt",
            "recall",
            "share_of_class_gt",
        ],
    )

    md_text = render_markdown(input_pairs, source_rows, error_rows, wrong_rows, slice_rows, target_tag)
    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_text, encoding="utf-8")

    print(f"report={md_path}")
    print(f"source_summary={Path(args.output_source_csv)}")
    print(f"error_summary={Path(args.output_error_csv)}")
    print(f"wrong_class_summary={Path(args.output_wrong_class_csv)}")
    print(f"slice_summary={Path(args.output_slice_csv)}")
    print(f"detail_csv={Path(args.output_detail_csv)}")


if __name__ == "__main__":
    main()
