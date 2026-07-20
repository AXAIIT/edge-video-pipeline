#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fail-on-gaps", action="store_true")
    args = parser.parse_args()

    frame_ids = []
    missing_stage = []
    statuses = {}
    with open(args.raw, "r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            frame_ids.append(row.get("frame_id"))
            statuses[row.get("status", "unknown")] = statuses.get(row.get("status", "unknown"), 0) + 1
            for field in [
                "capture_ts",
                "decode_ts",
                "preprocess_ts",
                "infer_start_ts",
                "infer_end_ts",
                "postprocess_ts",
                "output_ts",
            ]:
                if not row.get(field):
                    missing_stage.append((line_no, row.get("frame_id"), field))

    gaps = []
    out_of_order = []
    valid_ids = [x for x in frame_ids if isinstance(x, int)]
    for prev, cur in zip(valid_ids, valid_ids[1:]):
        if cur <= prev:
            out_of_order.append((prev, cur))
        elif cur != prev + 1:
            gaps.append((prev, cur))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write("# Pipeline Trace Check\n\n")
        f.write(f"- raw: `{args.raw}`\n")
        f.write(f"- frames: {len(frame_ids)}\n")
        f.write(f"- status_counts: `{statuses}`\n")
        f.write(f"- frame_id_gaps: {len(gaps)}\n")
        f.write(f"- frame_id_out_of_order: {len(out_of_order)}\n")
        f.write(f"- missing_stage_timestamps: {len(missing_stage)}\n")
        status = "pass" if not missing_stage and not gaps and not out_of_order else "degraded"
        if out_of_order or (args.fail_on_gaps and gaps):
            status = "fail"
        f.write(f"- fail_on_gaps: {str(args.fail_on_gaps).lower()}\n")
        f.write(f"- status: {status}\n")
        if gaps:
            f.write("\n## Frame ID gaps\n\n")
            for prev, cur in gaps[:50]:
                f.write(f"- {prev} -> {cur}\n")
        if out_of_order:
            f.write("\n## Duplicate or out-of-order frame IDs\n\n")
            for prev, cur in out_of_order[:50]:
                f.write(f"- {prev} -> {cur}\n")
        if missing_stage:
            f.write("\n## Missing stage timestamps\n\n")
            for line_no, frame_id, field in missing_stage[:50]:
                f.write(f"- line {line_no}, frame {frame_id}, field `{field}`\n")

    if missing_stage or out_of_order or (args.fail_on_gaps and gaps):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
