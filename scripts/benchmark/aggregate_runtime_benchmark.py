#!/usr/bin/env python3
import argparse
import csv
import importlib.util
import json
from pathlib import Path


def load_aggregate_module():
    script = Path(__file__).resolve().parent / "aggregate_pipeline_benchmark.py"
    spec = importlib.util.spec_from_file_location("aggregate_pipeline_benchmark", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--excluded-output", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--exclude-subdir", action="append", default=[])
    parser.add_argument("--include-legacy", action="store_true")
    args = parser.parse_args()

    agg = load_aggregate_module()
    rows = []
    included, excluded_inputs = agg.collect_jsonl_inputs(
        args.input,
        include_legacy=args.include_legacy,
        exclude_subdirs=args.exclude_subdir,
    )
    for path in included:
        records = agg.read_jsonl(path)
        summary = agg.summarize_records(records)
        if summary:
            rows.append(summary)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=agg.FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    if args.excluded_output:
        excluded_path = Path(args.excluded_output)
        excluded_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Excluded Runs",
            "",
            f"当前脚本已默认排除：{agg.raw_scope.default_excluded_scope_reason()}",
            "",
            "| run_id | status | excluded_reason | missing_evidence | related_troubleshooting_id | source_path |",
            "|---|---|---|---|---|---|",
        ]

        for path, reason in excluded_inputs:
            run_id = path.stem
            try:
                with path.open("r", encoding="utf-8-sig") as f:
                    first_line = f.readline().strip()
                if first_line:
                    row = json.loads(first_line)
                    run_id = row.get("run_id", run_id)
            except Exception:
                pass

            related_id = ""
            if reason in {
                agg.raw_scope.REASON_LEGACY_INHERITED,
                agg.raw_scope.REASON_CROSS_PROJECT_ALIGNMENT,
            }:
                related_id = "P3-TRB-20260618-007"
            lines.append(
                "| `{run_id}` | `{status}` | `{reason}` | `{missing}` | `{related}` | `{path}` |".format(
                    run_id=run_id,
                    status="legacy_reference_only",
                    reason=reason,
                    missing="project3_frame_level_raw_schema_not_applicable",
                    related=related_id,
                    path=path,
                )
            )

        if not excluded_inputs:
            lines.append("|  |  |  |  |  |  |")

        excluded_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
