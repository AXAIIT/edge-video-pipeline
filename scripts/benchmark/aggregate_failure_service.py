#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


DEFAULT_REQUIRED_FIELDS = [
    "run_id",
    "timestamp",
    "case_id",
    "input_source_id",
    "stage",
    "error_code",
    "expected_behavior",
    "actual_behavior",
    "recovery_action",
    "max_recovery_time_sec",
    "reconnect_count",
    "frame_id_continuity_after_recovery",
    "drop_frame_reason_after_recovery",
    "exit_code",
    "service_status",
    "log_path",
    "status",
    "related_troubleshooting_id",
]


def read_yaml_list(path, key, fallback):
    if not path:
        return list(fallback)
    schema = Path(path)
    if not schema.exists():
        return list(fallback)

    values = []
    in_list = False
    base_indent = None
    for raw_line in schema.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.strip() == f"{key}:":
            in_list = True
            base_indent = len(line) - len(line.lstrip())
            continue
        if not in_list:
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent <= base_indent and not stripped.startswith("- "):
            break
        if stripped.startswith("- "):
            values.append(stripped[2:].strip().strip("'\""))
        elif values:
            break
    return values or list(fallback)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--schema", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    required_fields = read_yaml_list(args.schema, "required_fields", DEFAULT_REQUIRED_FIELDS)
    root = Path(args.input)
    files = [root] if root.is_file() else sorted(root.rglob("*.jsonl"))
    rows = []
    for path in files:
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if line.strip():
                    row = json.loads(line)
                    missing = [field for field in required_fields if field not in row]
                    row["source_path"] = str(path)
                    row["source_line"] = line_no
                    row["schema_status"] = "fail" if missing else "pass"
                    row["missing_required_fields"] = ";".join(missing)
                    rows.append(row)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        if rows:
            keys = sorted(set().union(*(row.keys() for row in rows)))
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
        else:
            f.write("run_id,status\n")


if __name__ == "__main__":
    main()
