#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

from evaluate_bdd100k_mot_detection import (
    alignment_summary,
    compute_ap50,
    evaluable_label_rows,
    evaluate_class,
    read_rows,
    row_key,
)


def parse_list(value, cast):
    return [cast(item.strip()) for item in value.split(",") if item.strip()]


def status_for(ap50, recall, ap50_min, recall_min):
    return "pass" if ap50 >= ap50_min and recall >= recall_min else "fail"


def read_batch_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"empty batch csv: {path}")
    required = ["sequence_id", "raw_path", "label_path"]
    for field in required:
        if field not in rows[0]:
            raise SystemExit(f"missing required field in batch csv: {field}")
    return rows


def load_sequence(row):
    sequence_id = row["sequence_id"]
    label_rows = read_rows(row["label_path"], default_sequence_id=sequence_id)
    pred_rows = read_rows(row["raw_path"], default_sequence_id=sequence_id)
    evaluated_label_rows, _ = evaluable_label_rows(label_rows, pred_rows)
    pred_by_key = {row_key(item): item for item in pred_rows}
    return {
        "sequence_id": sequence_id,
        "raw_path": row["raw_path"],
        "label_path": row["label_path"],
        "label_rows": label_rows,
        "evaluated_label_rows": evaluated_label_rows,
        "pred_rows": pred_rows,
        "pred_by_key": pred_by_key,
        "alignment": alignment_summary(label_rows, pred_rows),
    }


def evaluate_sequence(sequence, class_ids, confidence_min, iou_min, ap50_by_class):
    summary_rows = []
    for class_id in class_ids:
        summary, _ = evaluate_class(
            sequence["evaluated_label_rows"],
            sequence["pred_by_key"],
            class_id,
            confidence_min,
            iou_min,
        )
        summary["ap50"] = ap50_by_class[class_id]
        summary_rows.append(summary)

    evaluated = [row for row in summary_rows if row["gt_count"] > 0]
    total_gt = sum(row["gt_count"] for row in evaluated)
    total_pred = sum(row["pred_count"] for row in evaluated)
    total_tp = sum(row["tp"] for row in evaluated)
    total_fp = sum(row["fp"] for row in evaluated)
    total_fn = sum(row["fn"] for row in evaluated)
    ap50 = (
        sum(float(row["ap50"] or 0.0) * row["gt_count"] for row in evaluated) / total_gt
        if total_gt else 0.0
    )
    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "sequence_id": sequence["sequence_id"],
        "confidence_min": confidence_min,
        "labeled_frames": sequence["alignment"]["labeled_frames"],
        "evaluable_labeled_frames": sequence["alignment"]["evaluable_labeled_frames"],
        "trailing_unavailable_labeled_frames": sequence["alignment"][
            "trailing_unavailable_labeled_frames"
        ],
        "labeled_frame_coverage": sequence["alignment"]["labeled_frame_coverage"],
        "total_gt": total_gt,
        "total_pred": total_pred,
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "ap50_weighted": ap50,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def aggregate(rows, confidence_min, ap50_min, recall_min):
    total_gt = sum(row["total_gt"] for row in rows)
    total_pred = sum(row["total_pred"] for row in rows)
    total_tp = sum(row["total_tp"] for row in rows)
    total_fp = sum(row["total_fp"] for row in rows)
    total_fn = sum(row["total_fn"] for row in rows)
    ap50 = (
        sum(row["ap50_weighted"] * row["total_gt"] for row in rows) / total_gt
        if total_gt else 0.0
    )
    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "confidence_min": confidence_min,
        "sequence_count": len(rows),
        "pass_count": sum(1 for row in rows if status_for(row["ap50_weighted"], row["recall"], ap50_min, recall_min) == "pass"),
        "fail_count": sum(1 for row in rows if status_for(row["ap50_weighted"], row["recall"], ap50_min, recall_min) != "pass"),
        "total_gt": total_gt,
        "total_pred": total_pred,
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "weighted_ap50_by_gt": ap50,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "status": status_for(ap50, recall, ap50_min, recall_min),
    }


def fmt_float(value):
    if isinstance(value, float):
        return f"{value:.6f}"
    return value


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt_float(row.get(field, "")) for field in fields})


def write_markdown(
    path,
    batch_csv,
    thresholds,
    summary_rows,
    detail_rows,
    ap50_min,
    recall_min,
):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("# BDD100K Confidence Sweep\n\n")
        f.write(f"- batch_csv: `{batch_csv}`\n")
        f.write(f"- confidence_mins: `{','.join(f'{item:.2f}' for item in thresholds)}`\n")
        f.write(f"- sequence_count: {summary_rows[0]['sequence_count'] if summary_rows else 0}\n\n")

        f.write("## Aggregate\n\n")
        f.write("| confidence_min | pass_count | fail_count | weighted_ap50_by_gt | precision | recall | f1 | total_pred | status |\n")
        f.write("|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
        for row in summary_rows:
            f.write(
                f"| {row['confidence_min']:.2f} | {row['pass_count']} | {row['fail_count']} | "
                f"{row['weighted_ap50_by_gt']:.6f} | {row['precision']:.6f} | "
                f"{row['recall']:.6f} | {row['f1']:.6f} | {row['total_pred']} | {row['status']} |\n"
            )

        f.write("\n## Per Sequence\n\n")
        f.write("| confidence_min | sequence_id | ap50_weighted | precision | recall | f1 | total_pred | status |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|---|\n")
        for row in detail_rows:
            status = status_for(row["ap50_weighted"], row["recall"], ap50_min, recall_min)
            f.write(
                f"| {row['confidence_min']:.2f} | `{row['sequence_id']}` | "
                f"{row['ap50_weighted']:.6f} | {row['precision']:.6f} | "
                f"{row['recall']:.6f} | {row['f1']:.6f} | {row['total_pred']} | {status} |\n"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-csv", required=True)
    parser.add_argument("--confidence-mins", default="0.05,0.10,0.15,0.20,0.25,0.30")
    parser.add_argument("--class-ids", default="0,1,2,3,5,6,7")
    parser.add_argument("--iou-min", type=float, default=0.50)
    parser.add_argument("--overall-ap50-min", type=float, default=0.25)
    parser.add_argument("--overall-recall-min", type=float, default=0.50)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-detail-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    thresholds = parse_list(args.confidence_mins, float)
    class_ids = parse_list(args.class_ids, int)
    sequences = [load_sequence(row) for row in read_batch_rows(args.batch_csv)]

    ap50_cache = {}
    for sequence in sequences:
        ap50_cache[sequence["sequence_id"]] = {
            class_id: compute_ap50(
                sequence["evaluated_label_rows"], sequence["pred_rows"], class_id, args.iou_min
            ) or 0.0
            for class_id in class_ids
        }

    detail_rows = []
    summary_rows = []
    for threshold in thresholds:
        rows_for_threshold = []
        for sequence in sequences:
            row = evaluate_sequence(
                sequence,
                class_ids,
                threshold,
                args.iou_min,
                ap50_cache[sequence["sequence_id"]],
            )
            row["status"] = status_for(
                row["ap50_weighted"],
                row["recall"],
                args.overall_ap50_min,
                args.overall_recall_min,
            )
            rows_for_threshold.append(row)
            detail_rows.append(row)
        summary_rows.append(
            aggregate(rows_for_threshold, threshold, args.overall_ap50_min, args.overall_recall_min)
        )

    summary_fields = [
        "confidence_min",
        "sequence_count",
        "pass_count",
        "fail_count",
        "total_gt",
        "total_pred",
        "total_tp",
        "total_fp",
        "total_fn",
        "weighted_ap50_by_gt",
        "precision",
        "recall",
        "f1",
        "status",
    ]
    detail_fields = [
        "confidence_min",
        "sequence_id",
        "labeled_frames",
        "evaluable_labeled_frames",
        "trailing_unavailable_labeled_frames",
        "labeled_frame_coverage",
        "total_gt",
        "total_pred",
        "total_tp",
        "total_fp",
        "total_fn",
        "ap50_weighted",
        "precision",
        "recall",
        "f1",
        "status",
    ]
    write_csv(args.output_csv, summary_rows, summary_fields)
    write_csv(args.output_detail_csv, detail_rows, detail_fields)
    write_markdown(
        args.output_md,
        args.batch_csv,
        thresholds,
        summary_rows,
        detail_rows,
        args.overall_ap50_min,
        args.overall_recall_min,
    )

    best = max(summary_rows, key=lambda row: (row["status"] == "pass", row["recall"], row["f1"]))
    print(f"summary={args.output_csv}")
    print(f"details={args.output_detail_csv}")
    print(f"report={args.output_md}")
    print(f"best_confidence_min={best['confidence_min']:.2f}")
    print(f"best_weighted_ap50_by_gt={best['weighted_ap50_by_gt']:.6f}")
    print(f"best_precision={best['precision']:.6f}")
    print(f"best_recall={best['recall']:.6f}")
    print(f"best_f1={best['f1']:.6f}")
    print(f"best_status={best['status']}")


if __name__ == "__main__":
    main()
