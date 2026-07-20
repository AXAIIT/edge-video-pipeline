#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


COCO_CLASS_NAMES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    6: "train",
    7: "truck",
}

SMALL_AREA_MAX = 32 * 32
MEDIUM_AREA_MAX = 96 * 96


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


def gt_detections_for_class(row, class_id):
    out = []
    for det in row.get("detections", []):
        if int(det.get("class_id", -1)) != class_id:
            continue
        if "bbox_xywh" not in det:
            continue
        box = [float(v) for v in det["bbox_xywh"]]
        out.append({
            "class_id": class_id,
            "bbox_xywh": box,
            "area": box[2] * box[3],
            "occluded": bool_attr(det, "occluded"),
            "truncated": bool_attr(det, "truncated"),
            "crowd": bool_attr(det, "crowd"),
            "source_category": det.get("source_category", ""),
        })
    return out


def pred_detections_for_class(row, class_id, confidence_min):
    out = []
    for det in row.get("detections", []):
        if int(det.get("class_id", -1)) != class_id:
            continue
        confidence = float(det.get("confidence", 0.0))
        if confidence < confidence_min:
            continue
        if "bbox_xywh" not in det:
            continue
        out.append({
            "class_id": class_id,
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


def match_frame_pairs(gt_dets, pred_dets, iou_min):
    candidates = []
    for pred_idx, pred in enumerate(pred_dets):
        for gt_idx, gt in enumerate(gt_dets):
            score = box_iou(pred["bbox_xywh"], gt["bbox_xywh"])
            if score >= iou_min:
                candidates.append((score, pred_idx, gt_idx))

    used_pred = set()
    used_gt = set()
    matches = []
    for score, pred_idx, gt_idx in sorted(candidates, reverse=True):
        if pred_idx in used_pred or gt_idx in used_gt:
            continue
        used_pred.add(pred_idx)
        used_gt.add(gt_idx)
        matches.append((pred_idx, gt_idx, score))

    return matches, used_pred, used_gt


def compute_ap50(label_rows, pred_rows, class_id, iou_min):
    labels_by_key = {row_key(row): row for row in label_rows}
    labeled_keys = set(labels_by_key.keys())
    total_gt = 0
    pred_items = []

    for key, row in labels_by_key.items():
        total_gt += len(gt_detections_for_class(row, class_id))
    if total_gt == 0:
        return None

    for row in pred_rows:
        key = row_key(row)
        if key not in labeled_keys:
            continue
        for pred in pred_detections_for_class(row, class_id, confidence_min=0.0):
            pred_items.append((pred["confidence"], key, pred))
    pred_items.sort(reverse=True, key=lambda item: item[0])

    matched = {}
    tp_flags = []
    fp_flags = []
    for _, key, pred in pred_items:
        gt_dets = gt_detections_for_class(labels_by_key.get(key, {}), class_id)
        used_gt = matched.setdefault(key, set())
        best_gt = None
        best_iou = 0.0
        for gt_idx, gt in enumerate(gt_dets):
            if gt_idx in used_gt:
                continue
            score = box_iou(pred["bbox_xywh"], gt["bbox_xywh"])
            if score > best_iou:
                best_iou = score
                best_gt = gt_idx
        if best_gt is not None and best_iou >= iou_min:
            used_gt.add(best_gt)
            tp_flags.append(1)
            fp_flags.append(0)
        else:
            tp_flags.append(0)
            fp_flags.append(1)

    precisions = []
    recalls = []
    tp_cum = 0
    fp_cum = 0
    for tp, fp in zip(tp_flags, fp_flags):
        tp_cum += tp
        fp_cum += fp
        precisions.append(tp_cum / (tp_cum + fp_cum) if tp_cum + fp_cum else 0.0)
        recalls.append(tp_cum / total_gt)

    ap = 0.0
    for threshold in [x / 100 for x in range(101)]:
        values = [precision for precision, recall in zip(precisions, recalls) if recall >= threshold]
        ap += max(values) if values else 0.0
    return ap / 101


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


SLICE_DEFS = [
    ("all", lambda r: True),
    ("size_small", lambda r: r["size_bucket"] == "small"),
    ("size_medium", lambda r: r["size_bucket"] == "medium"),
    ("size_large", lambda r: r["size_bucket"] == "large"),
    ("occluded_true", lambda r: r["occluded"]),
    ("occluded_false", lambda r: not r["occluded"]),
    ("truncated_true", lambda r: r["truncated"]),
    ("truncated_false", lambda r: not r["truncated"]),
    ("crowd_true", lambda r: r["crowd"]),
    ("crowd_false", lambda r: not r["crowd"]),
    ("difficult", lambda r: r["difficult"]),
    ("non_difficult", lambda r: not r["difficult"]),
]


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


def analyze_run(batch_csv, tag, repo_root, class_ids, iou_min, default_confidence_min):
    batch_rows = load_batch_rows(batch_csv, repo_root)
    class_stats = {}
    object_records = []
    all_label_rows = []
    all_pred_rows = []

    for batch_row in batch_rows:
        conf_min_str = batch_row.get("confidence_min", "")
        confidence_min = float(conf_min_str) if conf_min_str else default_confidence_min
        label_rows = read_rows(batch_row["label_path_abs"], default_sequence_id=batch_row["sequence_id"])
        pred_rows = read_rows(batch_row["raw_path_abs"], default_sequence_id=batch_row["sequence_id"])
        pred_by_key = {row_key(row): row for row in pred_rows}
        all_label_rows.extend(label_rows)
        all_pred_rows.extend(pred_rows)

        for class_id in class_ids:
            stat = class_stats.setdefault(class_id, {
                "gt_count": 0,
                "pred_count": 0,
                "tp": 0,
                "fp": 0,
                "fn": 0,
                "matched_ious": [],
            })
            for label_row in label_rows:
                key = row_key(label_row)
                pred_row = pred_by_key.get(key, {"detections": []})
                gt_dets = gt_detections_for_class(label_row, class_id)
                pred_dets = pred_detections_for_class(pred_row, class_id, confidence_min)
                matches, used_pred, used_gt = match_frame_pairs(gt_dets, pred_dets, iou_min)

                stat["gt_count"] += len(gt_dets)
                stat["pred_count"] += len(pred_dets)
                stat["tp"] += len(matches)
                stat["fp"] += len(pred_dets) - len(matches)
                stat["fn"] += len(gt_dets) - len(matches)
                stat["matched_ious"].extend(score for _, _, score in matches)

                matched_iou_by_gt = {gt_idx: score for _, gt_idx, score in matches}
                for gt_idx, gt in enumerate(gt_dets):
                    record = {
                        "run_tag": tag,
                        "sequence_id": key[0],
                        "frame_id": key[1],
                        "class_id": class_id,
                        "class_name": COCO_CLASS_NAMES.get(class_id, str(class_id)),
                        "matched": int(gt_idx in used_gt),
                        "matched_iou": matched_iou_by_gt.get(gt_idx, ""),
                        "gt_area": gt["area"],
                        "size_bucket": size_bucket(gt["area"]),
                        "occluded": gt["occluded"],
                        "truncated": gt["truncated"],
                        "crowd": gt["crowd"],
                        "source_category": gt["source_category"],
                    }
                    record["difficult"] = is_difficult(record)
                    object_records.append(record)

    summary_rows = []
    for class_id in class_ids:
        stat = class_stats.setdefault(class_id, {
            "gt_count": 0,
            "pred_count": 0,
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "matched_ious": [],
        })
        precision = stat["tp"] / stat["pred_count"] if stat["pred_count"] else 0.0
        recall = stat["tp"] / stat["gt_count"] if stat["gt_count"] else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        ap50 = compute_ap50(all_label_rows, all_pred_rows, class_id, iou_min)
        summary_rows.append({
            "run_tag": tag,
            "class_id": class_id,
            "class_name": COCO_CLASS_NAMES.get(class_id, str(class_id)),
            "gt_count": stat["gt_count"],
            "pred_count": stat["pred_count"],
            "tp": stat["tp"],
            "fp": stat["fp"],
            "fn": stat["fn"],
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "ap50": ap50 if ap50 is not None else 0.0,
            "mean_matched_iou": (
                sum(stat["matched_ious"]) / len(stat["matched_ious"])
                if stat["matched_ious"] else 0.0
            ),
        })

    slice_rows = []
    by_class = {}
    for record in object_records:
        by_class.setdefault(record["class_id"], []).append(record)

    for class_id in class_ids:
        records = by_class.get(class_id, [])
        class_gt = len(records)
        for slice_name, predicate in SLICE_DEFS:
            subset = [record for record in records if predicate(record)]
            gt_count = len(subset)
            matched = sum(record["matched"] for record in subset)
            recall = matched / gt_count if gt_count else 0.0
            matched_ious = [float(record["matched_iou"]) for record in subset if record["matched"]]
            slice_rows.append({
                "run_tag": tag,
                "class_id": class_id,
                "class_name": COCO_CLASS_NAMES.get(class_id, str(class_id)),
                "slice_name": slice_name,
                "gt_count": gt_count,
                "matched_gt": matched,
                "recall": recall,
                "mean_matched_iou": sum(matched_ious) / len(matched_ious) if matched_ious else 0.0,
                "share_of_class_gt": gt_count / class_gt if class_gt else 0.0,
            })

    return summary_rows, slice_rows


def summary_map(rows):
    return {(row["run_tag"], row["class_id"]): row for row in rows}


def slice_map(rows):
    return {(row["run_tag"], row["class_id"], row["slice_name"]): row for row in rows}


def pct(value):
    return f"{value:.6f}"


def render_markdown(
    primary_batch_csv,
    compare_batch_csv,
    primary_tag,
    compare_tag,
    class_rows,
    slice_rows,
    focus_class_ids,
):
    class_by_key = summary_map(class_rows)
    slice_by_key = slice_map(slice_rows)

    primary_gt_total = sum(
        class_by_key.get((primary_tag, class_id), {}).get("gt_count", 0)
        for class_id in focus_class_ids
    )

    lines = [
        "# BDD100K Difficult-case Analysis",
        "",
        "## Inputs",
        "",
        f"- primary_batch_csv: `{primary_batch_csv}`",
        f"- primary_tag: `{primary_tag}`",
    ]
    if compare_batch_csv:
        lines.extend([
            f"- compare_batch_csv: `{compare_batch_csv}`",
            f"- compare_tag: `{compare_tag}`",
        ])
    lines.extend([
        "- size_bucket_policy: `COCO area buckets (small < 32^2, medium < 96^2, large >= 96^2)`",
        "- difficult_policy: `small OR occluded OR truncated OR crowd`",
        "",
        "## Focus Class GT Distribution",
        "",
        "| class_name | gt_count | gt_share_among_focus | small | medium | large | occluded | truncated | crowd | difficult |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])

    for class_id in focus_class_ids:
        all_row = slice_by_key.get((primary_tag, class_id, "all"))
        if not all_row or all_row["gt_count"] == 0:
            continue
        lines.append(
            f"| {all_row['class_name']} | {all_row['gt_count']} | "
            f"{all_row['gt_count'] / primary_gt_total if primary_gt_total else 0.0:.6f} | "
            f"{slice_by_key[(primary_tag, class_id, 'size_small')]['gt_count']} | "
            f"{slice_by_key[(primary_tag, class_id, 'size_medium')]['gt_count']} | "
            f"{slice_by_key[(primary_tag, class_id, 'size_large')]['gt_count']} | "
            f"{slice_by_key[(primary_tag, class_id, 'occluded_true')]['gt_count']} | "
            f"{slice_by_key[(primary_tag, class_id, 'truncated_true')]['gt_count']} | "
            f"{slice_by_key[(primary_tag, class_id, 'crowd_true')]['gt_count']} | "
            f"{slice_by_key[(primary_tag, class_id, 'difficult')]['gt_count']} |"
        )

    lines.extend([
        "",
        "## Aggregate Class Summary",
        "",
    ])

    if compare_batch_csv:
        lines.extend([
            f"| class_name | gt_count | {compare_tag}_ap50 | {primary_tag}_ap50 | delta_ap50 | {compare_tag}_precision | {primary_tag}_precision | delta_precision | {compare_tag}_recall | {primary_tag}_recall | delta_recall |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for class_id in focus_class_ids:
            base = class_by_key.get((compare_tag, class_id))
            cur = class_by_key.get((primary_tag, class_id))
            if not base or not cur:
                continue
            lines.append(
                f"| {cur['class_name']} | {cur['gt_count']} | "
                f"{base['ap50']:.6f} | {cur['ap50']:.6f} | {cur['ap50'] - base['ap50']:.6f} | "
                f"{base['precision']:.6f} | {cur['precision']:.6f} | {cur['precision'] - base['precision']:.6f} | "
                f"{base['recall']:.6f} | {cur['recall']:.6f} | {cur['recall'] - base['recall']:.6f} |"
            )
    else:
        lines.extend([
            f"| class_name | gt_count | {primary_tag}_ap50 | {primary_tag}_precision | {primary_tag}_recall | {primary_tag}_f1 |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for class_id in focus_class_ids:
            cur = class_by_key.get((primary_tag, class_id))
            if not cur:
                continue
            lines.append(
                f"| {cur['class_name']} | {cur['gt_count']} | {cur['ap50']:.6f} | "
                f"{cur['precision']:.6f} | {cur['recall']:.6f} | {cur['f1']:.6f} |"
            )

    lines.extend([
        "",
        "## Slice Recall",
        "",
    ])

    if compare_batch_csv:
        lines.extend([
            f"| class_name | slice_name | gt_count | gt_share | {compare_tag}_recall | {primary_tag}_recall | delta_recall |",
            "|---|---|---:|---:|---:|---:|---:|",
        ])
        for class_id in focus_class_ids:
            for slice_name, _ in SLICE_DEFS:
                base = slice_by_key.get((compare_tag, class_id, slice_name))
                cur = slice_by_key.get((primary_tag, class_id, slice_name))
                if not base or not cur or cur["gt_count"] == 0:
                    continue
                lines.append(
                    f"| {cur['class_name']} | {slice_name} | {cur['gt_count']} | {cur['share_of_class_gt']:.6f} | "
                    f"{base['recall']:.6f} | {cur['recall']:.6f} | {cur['recall'] - base['recall']:.6f} |"
                )
    else:
        lines.extend([
            f"| class_name | slice_name | gt_count | gt_share | {primary_tag}_recall |",
            "|---|---|---:|---:|---:|",
        ])
        for class_id in focus_class_ids:
            for slice_name, _ in SLICE_DEFS:
                cur = slice_by_key.get((primary_tag, class_id, slice_name))
                if not cur or cur["gt_count"] == 0:
                    continue
                lines.append(
                    f"| {cur['class_name']} | {slice_name} | {cur['gt_count']} | {cur['share_of_class_gt']:.6f} | "
                    f"{cur['recall']:.6f} |"
                )

    lines.extend([
        "",
        "## Findings",
        "",
    ])

    if compare_batch_csv:
        for class_id in focus_class_ids:
            base = class_by_key.get((compare_tag, class_id))
            cur = class_by_key.get((primary_tag, class_id))
            if not base or not cur or cur["gt_count"] == 0:
                continue
            lines.append(
                f"- `{cur['class_name']}`: gt={cur['gt_count']}, recall `{compare_tag}` -> `{primary_tag}` = "
                f"`{base['recall']:.6f}` -> `{cur['recall']:.6f}` (delta `{cur['recall'] - base['recall']:.6f}`)."
            )
            difficult = slice_by_key.get((primary_tag, class_id, "difficult"))
            large = slice_by_key.get((primary_tag, class_id, "size_large"))
            if difficult and large:
                lines.append(
                    f"  difficult_gt={difficult['gt_count']}, difficult_recall={difficult['recall']:.6f}, "
                    f"large_recall={large['recall']:.6f}."
                )
    else:
        for class_id in focus_class_ids:
            cur = class_by_key.get((primary_tag, class_id))
            if not cur or cur["gt_count"] == 0:
                continue
            difficult = slice_by_key.get((primary_tag, class_id, "difficult"))
            lines.append(
                f"- `{cur['class_name']}`: gt={cur['gt_count']}, recall={cur['recall']:.6f}, "
                f"difficult_recall={difficult['recall']:.6f if difficult else 0.0}."
            )

    return "\n".join(lines) + "\n"


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Analyze BDD100K difficult cases from batch raw outputs")
    parser.add_argument("--primary-batch-csv", required=True)
    parser.add_argument("--compare-batch-csv")
    parser.add_argument("--primary-tag")
    parser.add_argument("--compare-tag")
    parser.add_argument("--class-ids", default="0,1,2,3,5,6,7")
    parser.add_argument("--focus-class-ids", default="0,1,2,6")
    parser.add_argument("--iou-min", type=float, default=0.50)
    parser.add_argument("--default-confidence-min", type=float, default=0.25)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-slice-csv", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    class_ids = [int(x) for x in args.class_ids.split(",") if x.strip()]
    focus_class_ids = [int(x) for x in args.focus_class_ids.split(",") if x.strip()]
    primary_tag = args.primary_tag or Path(args.primary_batch_csv).stem
    compare_tag = args.compare_tag or (Path(args.compare_batch_csv).stem if args.compare_batch_csv else "")

    primary_summary, primary_slices = analyze_run(
        args.primary_batch_csv,
        primary_tag,
        repo_root,
        class_ids,
        args.iou_min,
        args.default_confidence_min,
    )

    all_summary_rows = list(primary_summary)
    all_slice_rows = list(primary_slices)
    if args.compare_batch_csv:
        compare_summary, compare_slices = analyze_run(
            args.compare_batch_csv,
            compare_tag,
            repo_root,
            class_ids,
            args.iou_min,
            args.default_confidence_min,
        )
        all_summary_rows.extend(compare_summary)
        all_slice_rows.extend(compare_slices)

    class_fields = [
        "run_tag",
        "class_id",
        "class_name",
        "gt_count",
        "pred_count",
        "tp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
        "ap50",
        "mean_matched_iou",
    ]
    slice_fields = [
        "run_tag",
        "class_id",
        "class_name",
        "slice_name",
        "gt_count",
        "matched_gt",
        "recall",
        "mean_matched_iou",
        "share_of_class_gt",
    ]
    write_csv(args.output_csv, all_summary_rows, class_fields)
    write_csv(args.output_slice_csv, all_slice_rows, slice_fields)

    md_text = render_markdown(
        args.primary_batch_csv,
        args.compare_batch_csv,
        primary_tag,
        compare_tag,
        all_summary_rows,
        all_slice_rows,
        focus_class_ids,
    )
    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_text, encoding="utf-8")

    print(f"report={md_path}")
    print(f"class_summary={Path(args.output_csv)}")
    print(f"slice_summary={Path(args.output_slice_csv)}")
    print(f"primary_tag={primary_tag}")
    if args.compare_batch_csv:
        print(f"compare_tag={compare_tag}")


if __name__ == "__main__":
    main()
