#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict
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


def jsonl_files(path):
    path = Path(path)
    if path.is_dir():
        return sorted(path.glob("*.jsonl"))
    return [path]


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


def frame_range(rows):
    frame_ids = [int(row["frame_id"]) for row in rows]
    if not frame_ids:
        return "", ""
    return min(frame_ids), max(frame_ids)


def evaluable_label_rows(label_rows, pred_rows):
    if not pred_rows:
        return [], len(label_rows)
    prediction_frame_last = max(int(row["frame_id"]) for row in pred_rows)
    evaluable = [row for row in label_rows if int(row["frame_id"]) <= prediction_frame_last]
    return evaluable, len(label_rows) - len(evaluable)


def alignment_summary(label_rows, pred_rows):
    label_keys = {row_key(row) for row in label_rows}
    evaluable_rows, trailing_unavailable = evaluable_label_rows(label_rows, pred_rows)
    evaluable_label_keys = {row_key(row) for row in evaluable_rows}
    pred_keys = {row_key(row) for row in pred_rows}
    covered_keys = evaluable_label_keys & pred_keys
    missing_keys = sorted(evaluable_label_keys - pred_keys, key=lambda item: (item[0], item[1]))
    extra_pred_keys = sorted(pred_keys - label_keys, key=lambda item: (item[0], item[1]))
    label_first, label_last = frame_range(label_rows)
    pred_first, pred_last = frame_range(pred_rows)
    return {
        "labeled_frames": len(label_keys),
        "evaluable_labeled_frames": len(evaluable_label_keys),
        "trailing_unavailable_labeled_frames": trailing_unavailable,
        "prediction_frames": len(pred_keys),
        "labeled_frames_with_predictions": len(covered_keys),
        "labeled_frame_coverage": (
            len(covered_keys) / len(evaluable_label_keys) if evaluable_label_keys else 0.0
        ),
        "missing_labeled_frames": len(missing_keys),
        "extra_prediction_frames": len(extra_pred_keys),
        "label_frame_first": label_first,
        "label_frame_last": label_last,
        "prediction_frame_first": pred_first,
        "prediction_frame_last": pred_last,
        "missing_labeled_frame_ids_sample": [f"{seq}:{frame_id}" for seq, frame_id in missing_keys[:20]],
    }


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


def detections_for_class(row, class_id, confidence_min):
    out = []
    for det in row.get("detections", []):
        if int(det.get("class_id", -1)) != class_id:
            continue
        if float(det.get("confidence", 1.0)) < confidence_min:
            continue
        if "bbox_xywh" not in det:
            continue
        out.append({
            "class_id": class_id,
            "confidence": float(det.get("confidence", 1.0)),
            "bbox_xywh": det["bbox_xywh"],
        })
    return out


def match_frame(gt_dets, pred_dets, iou_min):
    candidates = []
    for pred_idx, pred in enumerate(pred_dets):
        for gt_idx, gt in enumerate(gt_dets):
            score = box_iou(pred["bbox_xywh"], gt["bbox_xywh"])
            if score >= iou_min:
                candidates.append((score, pred_idx, gt_idx))

    used_pred = set()
    used_gt = set()
    matched_ious = []
    for score, pred_idx, gt_idx in sorted(candidates, reverse=True):
        if pred_idx in used_pred or gt_idx in used_gt:
            continue
        used_pred.add(pred_idx)
        used_gt.add(gt_idx)
        matched_ious.append(score)

    tp = len(matched_ious)
    fp = len(pred_dets) - tp
    fn = len(gt_dets) - tp
    return tp, fp, fn, matched_ious


def compute_ap50(label_rows, pred_rows, class_id, iou_min):
    labels_by_key = {row_key(row): row for row in label_rows}
    pred_items = []
    total_gt = 0
    for key, row in labels_by_key.items():
        total_gt += len(detections_for_class(row, class_id, confidence_min=0.0))
    if total_gt == 0:
        return None

    labeled_keys = set(labels_by_key.keys())
    for row in pred_rows:
        key = row_key(row)
        if key not in labeled_keys:
            continue
        for pred in detections_for_class(row, class_id, confidence_min=0.0):
            pred_items.append((pred["confidence"], key, pred))
    pred_items.sort(reverse=True, key=lambda item: item[0])

    matched = defaultdict(set)
    tp_flags = []
    fp_flags = []
    for _, key, pred in pred_items:
        gt_dets = detections_for_class(labels_by_key.get(key, {}), class_id, confidence_min=0.0)
        best_gt = None
        best_iou = 0.0
        for gt_idx, gt in enumerate(gt_dets):
            if gt_idx in matched[key]:
                continue
            score = box_iou(pred["bbox_xywh"], gt["bbox_xywh"])
            if score > best_iou:
                best_iou = score
                best_gt = gt_idx
        if best_gt is not None and best_iou >= iou_min:
            matched[key].add(best_gt)
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


def evaluate_class(label_rows, pred_by_key, class_id, confidence_min, iou_min):
    tp_total = 0
    fp_total = 0
    fn_total = 0
    matched_ious = []
    frame_rows = []
    for label_row in label_rows:
        key = row_key(label_row)
        pred_row = pred_by_key.get(key, {"detections": []})
        gt_dets = detections_for_class(label_row, class_id, confidence_min=0.0)
        pred_dets = detections_for_class(pred_row, class_id, confidence_min)
        tp, fp, fn, ious = match_frame(gt_dets, pred_dets, iou_min)
        tp_total += tp
        fp_total += fp
        fn_total += fn
        matched_ious.extend(ious)
        frame_rows.append({
            "sequence_id": key[0],
            "frame_id": key[1],
            "class_id": class_id,
            "gt_count": len(gt_dets),
            "pred_count": len(pred_dets),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "mean_matched_iou": sum(ious) / len(ious) if ious else "",
        })

    precision = tp_total / (tp_total + fp_total) if tp_total + fp_total else 0.0
    recall = tp_total / (tp_total + fn_total) if tp_total + fn_total else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    mean_iou = sum(matched_ious) / len(matched_ious) if matched_ious else 0.0
    return {
        "class_id": class_id,
        "class_name": COCO_CLASS_NAMES.get(class_id, str(class_id)),
        "gt_count": tp_total + fn_total,
        "pred_count": tp_total + fp_total,
        "tp": tp_total,
        "fp": fp_total,
        "fn": fn_total,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mean_matched_iou": mean_iou,
    }, frame_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pred-raw", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--sequence-id")
    parser.add_argument("--class-ids", default="0,1,2,3,5,6,7")
    parser.add_argument("--iou-min", type=float, default=0.50)
    parser.add_argument("--confidence-min", type=float, default=0.25)
    parser.add_argument("--overall-ap50-min", type=float, default=0.25)
    parser.add_argument("--overall-recall-min", type=float, default=0.50)
    parser.add_argument("--output-summary-csv")
    args = parser.parse_args()

    label_rows = read_rows(args.labels, default_sequence_id=args.sequence_id)
    pred_rows = read_rows(args.pred_raw, default_sequence_id=args.sequence_id)
    evaluated_label_rows, _ = evaluable_label_rows(label_rows, pred_rows)
    pred_by_key = {row_key(row): row for row in pred_rows}
    class_ids = [int(value) for value in args.class_ids.split(",") if value.strip()]
    alignment = alignment_summary(label_rows, pred_rows)

    summary_rows = []
    detail_rows = []
    for class_id in class_ids:
        summary, frame_rows = evaluate_class(
            evaluated_label_rows, pred_by_key, class_id, args.confidence_min, args.iou_min
        )
        ap50 = compute_ap50(evaluated_label_rows, pred_rows, class_id, args.iou_min)
        summary["ap50"] = ap50 if ap50 is not None else ""
        summary_rows.append(summary)
        detail_rows.extend(frame_rows)

    evaluated = [row for row in summary_rows if row["gt_count"] > 0]
    total_gt = sum(row["gt_count"] for row in evaluated)
    total_pred = sum(row["pred_count"] for row in evaluated)
    overall_ap50 = (
        sum(float(row["ap50"]) * row["gt_count"] for row in evaluated if row["ap50"] != "") / total_gt
        if total_gt else 0.0
    )
    total_tp = sum(row["tp"] for row in evaluated)
    total_fp = sum(row["fp"] for row in evaluated)
    total_fn = sum(row["fn"] for row in evaluated)
    overall_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    overall_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    overall_f1 = (
        2 * overall_precision * overall_recall / (overall_precision + overall_recall)
        if overall_precision + overall_recall else 0.0
    )
    status = "pass" if overall_ap50 >= args.overall_ap50_min and overall_recall >= args.overall_recall_min else "fail"

    csv_path = Path(args.output_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()) if detail_rows else ["sequence_id", "frame_id"])
        writer.writeheader()
        writer.writerows(detail_rows)

    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# BDD100K MOT Detection Quality\n\n")
        f.write(f"- prediction_raw: `{args.pred_raw}`\n")
        f.write(f"- labels: `{args.labels}`\n")
        f.write(f"- labeled_frames: {len(label_rows)}\n")
        f.write(f"- evaluable_labeled_frames: {alignment['evaluable_labeled_frames']}\n")
        f.write(
            "- trailing_unavailable_labeled_frames: "
            f"{alignment['trailing_unavailable_labeled_frames']}\n"
        )
        f.write(f"- confidence_min: {args.confidence_min}\n")
        f.write(f"- iou_min: {args.iou_min}\n")
        f.write(f"- overall_ap50_min: {args.overall_ap50_min}\n")
        f.write(f"- overall_recall_min: {args.overall_recall_min}\n")
        f.write(f"- prediction_frames: {alignment['prediction_frames']}\n")
        f.write(
            f"- prediction_frame_range: {alignment['prediction_frame_first']}.."
            f"{alignment['prediction_frame_last']}\n"
        )
        f.write(f"- labeled_frames_with_predictions: {alignment['labeled_frames_with_predictions']}\n")
        f.write(f"- labeled_frame_coverage: {alignment['labeled_frame_coverage']:.6f}\n")
        f.write(f"- missing_labeled_frames: {alignment['missing_labeled_frames']}\n")
        if alignment["missing_labeled_frame_ids_sample"]:
            sample = ", ".join(alignment["missing_labeled_frame_ids_sample"])
            f.write(f"- missing_labeled_frame_ids_sample: `{sample}`\n")
        f.write(f"- overall_ap50_weighted: {overall_ap50:.6f}\n")
        f.write(f"- overall_precision: {overall_precision:.6f}\n")
        f.write(f"- overall_recall: {overall_recall:.6f}\n")
        f.write(f"- overall_f1: {overall_f1:.6f}\n")
        f.write(f"- total_gt: {total_gt}\n")
        f.write(f"- total_pred: {total_pred}\n")
        f.write(f"- total_tp: {total_tp}\n")
        f.write(f"- total_fp: {total_fp}\n")
        f.write(f"- total_fn: {total_fn}\n")
        f.write(f"- status: {status}\n\n")
        f.write("| class_id | class_name | gt_count | pred_count | tp | fp | fn | ap50 | precision | recall | f1 | mean_matched_iou |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for row in summary_rows:
            ap50 = row["ap50"] if row["ap50"] != "" else 0.0
            f.write(
                f"| {row['class_id']} | {row['class_name']} | {row['gt_count']} | "
                f"{row['pred_count']} | {row['tp']} | {row['fp']} | {row['fn']} | "
                f"{float(ap50):.6f} | {row['precision']:.6f} | {row['recall']:.6f} | "
                f"{row['f1']:.6f} | {row['mean_matched_iou']:.6f} |\n"
            )

    if args.output_summary_csv:
        summary_path = Path(args.output_summary_csv)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("w", encoding="utf-8", newline="") as f:
            fields = [
                "sequence_id",
                "prediction_raw",
                "labels",
                "labeled_frames",
                "evaluable_labeled_frames",
                "trailing_unavailable_labeled_frames",
                "prediction_frames",
                "labeled_frames_with_predictions",
                "labeled_frame_coverage",
                "missing_labeled_frames",
                "overall_ap50_weighted",
                "overall_precision",
                "overall_recall",
                "overall_f1",
                "total_gt",
                "total_pred",
                "total_tp",
                "total_fp",
                "total_fn",
                "confidence_min",
                "iou_min",
                "overall_ap50_min",
                "overall_recall_min",
                "status",
            ]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "sequence_id": args.sequence_id or "",
                "prediction_raw": args.pred_raw,
                "labels": args.labels,
                "labeled_frames": alignment["labeled_frames"],
                "evaluable_labeled_frames": alignment["evaluable_labeled_frames"],
                "trailing_unavailable_labeled_frames": alignment[
                    "trailing_unavailable_labeled_frames"
                ],
                "prediction_frames": alignment["prediction_frames"],
                "labeled_frames_with_predictions": alignment["labeled_frames_with_predictions"],
                "labeled_frame_coverage": f"{alignment['labeled_frame_coverage']:.6f}",
                "missing_labeled_frames": alignment["missing_labeled_frames"],
                "overall_ap50_weighted": f"{overall_ap50:.6f}",
                "overall_precision": f"{overall_precision:.6f}",
                "overall_recall": f"{overall_recall:.6f}",
                "overall_f1": f"{overall_f1:.6f}",
                "total_gt": total_gt,
                "total_pred": total_pred,
                "total_tp": total_tp,
                "total_fp": total_fp,
                "total_fn": total_fn,
                "confidence_min": args.confidence_min,
                "iou_min": args.iou_min,
                "overall_ap50_min": args.overall_ap50_min,
                "overall_recall_min": args.overall_recall_min,
                "status": status,
            })

    print(f"status={status}")
    print(f"overall_ap50_weighted={overall_ap50:.6f}")
    print(f"overall_precision={overall_precision:.6f}")
    print(f"overall_recall={overall_recall:.6f}")
    print(f"overall_f1={overall_f1:.6f}")
    print(f"labeled_frame_coverage={alignment['labeled_frame_coverage']:.6f}")
    print(f"report={md_path}")
    print(f"details={csv_path}")
    if args.output_summary_csv:
        print(f"summary={Path(args.output_summary_csv)}")
    if status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
