#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize RK3588 full COCO2017 quality recheck")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--eval-json", required=True)
    parser.add_argument("--baseline-quality", type=float, default=0.3865)
    parser.add_argument("--reference-quality", type=float, default=0.3814960637396267)
    parser.add_argument("--max-accuracy-drop", type=float, default=0.03)
    parser.add_argument("--expected-images", type=int, default=5000)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    model_path = Path(args.model)
    eval_path = Path(args.eval_json)
    result = json.loads(eval_path.read_text(encoding="utf-8"))
    metrics = result["official_pycocotools"]
    actual_hash = sha256(model_path)
    image_count = int(result.get("num_images", 0))
    quality = float(metrics["mAP50_95"])
    accuracy_drop = args.baseline_quality - quality
    delta_vs_reference = quality - args.reference_quality
    hash_pass = actual_hash == args.expected_sha256
    coverage_pass = image_count == args.expected_images
    quality_pass = accuracy_drop <= args.max_accuracy_drop
    status = "pass" if hash_pass and coverage_pass and quality_pass else "fail"

    row = {
        "run_id": args.run_id,
        "model_path": str(model_path),
        "model_sha256": actual_hash,
        "expected_sha256": args.expected_sha256,
        "evaluated_images": image_count,
        "expected_images": args.expected_images,
        "mAP50_95": quality,
        "mAP50": float(metrics["mAP50"]),
        "mAP75": float(metrics["mAP75"]),
        "mAP50_95_small": float(metrics["mAP50_95_small"]),
        "mAP50_95_medium": float(metrics["mAP50_95_medium"]),
        "mAP50_95_large": float(metrics["mAP50_95_large"]),
        "AR1": float(metrics["AR1"]),
        "AR10": float(metrics["AR10"]),
        "AR100": float(metrics["AR100"]),
        "baseline_quality": args.baseline_quality,
        "accuracy_drop": accuracy_drop,
        "max_accuracy_drop": args.max_accuracy_drop,
        "reference_ced0_quality": args.reference_quality,
        "delta_vs_reference_ced0": delta_vs_reference,
        "hash_status": "pass" if hash_pass else "fail",
        "coverage_status": "pass" if coverage_pass else "fail",
        "quality_status": "pass" if quality_pass else "fail",
        "status": status,
    }

    csv_path = Path(args.output_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# RK3588 COCO2017 Quality Recheck",
        "",
        f"- run_id: `{args.run_id}`",
        f"- eval_json: `{eval_path}`",
        f"- status: `{status}`",
        "",
        "| metric | value | gate | status |",
        "|---|---:|---:|---|",
        f"| model_sha256 | `{actual_hash}` | `{args.expected_sha256}` | {'pass' if hash_pass else 'fail'} |",
        f"| evaluated_images | {image_count} | {args.expected_images} | {'pass' if coverage_pass else 'fail'} |",
        f"| mAP50_95 | {quality:.12f} | >= {args.baseline_quality - args.max_accuracy_drop:.12f} | {'pass' if quality_pass else 'fail'} |",
        f"| accuracy_drop | {accuracy_drop:.12f} | <= {args.max_accuracy_drop:.12f} | {'pass' if quality_pass else 'fail'} |",
        f"| delta_vs_reference_ced0 | {delta_vs_reference:.12f} | reference={args.reference_quality:.12f} | informational |",
        f"| mAP50 | {row['mAP50']:.12f} | - | informational |",
        f"| mAP75 | {row['mAP75']:.12f} | - | informational |",
        f"| mAP50_95_small | {row['mAP50_95_small']:.12f} | - | informational |",
        f"| mAP50_95_medium | {row['mAP50_95_medium']:.12f} | - | informational |",
        f"| mAP50_95_large | {row['mAP50_95_large']:.12f} | - | informational |",
        f"| AR1 | {row['AR1']:.12f} | - | informational |",
        f"| AR10 | {row['AR10']:.12f} | - | informational |",
        f"| AR100 | {row['AR100']:.12f} | - | informational |",
        "",
        "`pass` 仅证明当前 RKNN artifact 通过项目二同口径完整 COCO2017 质量门；项目三 C++ 后处理仍需后续 fixed-input 对齐。",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"status={status}")
    print(f"mAP50_95={quality:.12f}")
    print(f"accuracy_drop={accuracy_drop:.12f}")
    print(f"delta_vs_reference_ced0={delta_vs_reference:.12f}")
    print(f"report={md_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
