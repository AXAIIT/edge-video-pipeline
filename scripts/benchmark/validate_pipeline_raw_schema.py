#!/usr/bin/env python3
import argparse
import ast
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import raw_scope


DEFAULT_REQUIRED_FIELDS = [
    "run_id",
    "timestamp",
    "schema_version",
    "project",
    "measurement_scope",
    "frame_id",
    "end_to_end_latency_ms",
    "status",
]

DEFAULT_FORBIDDEN_SUMMARY_FIELDS = [
    "fps",
    "p50_end_to_end_latency_ms",
    "p90_end_to_end_latency_ms",
    "p95_end_to_end_latency_ms",
    "p99_end_to_end_latency_ms",
    "memory_growth_mb",
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


def read_field_allowed_values(path):
    if not path:
        return {}
    schema = Path(path)
    if not schema.exists():
        return {}

    allowed = {}
    in_fields = False
    current_field = None
    fields_indent = None
    for raw_line in schema.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        if stripped == "fields:":
            in_fields = True
            fields_indent = indent
            current_field = None
            continue
        if not in_fields:
            continue
        if indent <= fields_indent:
            break
        if stripped.endswith(":") and indent == fields_indent + 2:
            current_field = stripped[:-1]
            continue
        if current_field and stripped.startswith("allowed:"):
            raw_values = stripped.split(":", 1)[1].strip()
            try:
                parsed = ast.literal_eval(raw_values)
            except (SyntaxError, ValueError):
                continue
            if isinstance(parsed, list):
                allowed[current_field] = parsed
    return allowed


def validate_file(path, required_fields, forbidden_fields, allowed_values):
    errors = []
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            count += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_no}: invalid JSON: {exc}")
                continue
            missing = [field for field in required_fields if field not in row]
            if missing:
                errors.append(f"{path}:{line_no}: missing fields: {', '.join(missing)}")
            forbidden = [field for field in forbidden_fields if field in row]
            if forbidden:
                errors.append(f"{path}:{line_no}: raw result contains derived summary fields: {', '.join(forbidden)}")
            for field, allowed in allowed_values.items():
                if field in row and row[field] is not None and row[field] not in allowed:
                    errors.append(
                        f"{path}:{line_no}: {field}={row[field]!r} not in allowed set {allowed}"
                    )
            if row.get("measurement_scope") != "frame":
                errors.append(f"{path}:{line_no}: measurement_scope must be frame")
            if row.get("project") != "03_video_pipeline":
                errors.append(f"{path}:{line_no}: project must be 03_video_pipeline")
            if not isinstance(row.get("frame_id"), int):
                errors.append(f"{path}:{line_no}: frame_id must be integer")
            if row.get("cpu_fallback") is not None and not isinstance(row.get("cpu_fallback"), bool):
                errors.append(f"{path}:{line_no}: cpu_fallback must be boolean")
    return count, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--schema", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--exclude-subdir", action="append", default=[])
    parser.add_argument("--include-legacy", action="store_true")
    args = parser.parse_args()

    required_fields = read_yaml_list(args.schema, "required_fields", DEFAULT_REQUIRED_FIELDS)
    forbidden_fields = read_yaml_list(args.schema, "raw_forbidden_summary_fields", DEFAULT_FORBIDDEN_SUMMARY_FIELDS)
    allowed_values = read_field_allowed_values(args.schema)

    total = 0
    all_errors = []
    files, excluded = raw_scope.collect_jsonl_inputs(
        args.input,
        exclude_subdirs=args.exclude_subdir,
        include_legacy=args.include_legacy,
    )
    if not files:
        all_errors.append(f"{args.input}: no jsonl files found")
    for path in files:
        count, errors = validate_file(path, required_fields, forbidden_fields, allowed_values)
        total += count
        all_errors.extend(errors)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write("# video pipeline raw schema check\n\n")
        f.write(f"- input: `{args.input}`\n")
        f.write(f"- schema: `{args.schema}`\n")
        f.write(f"- files: {len(files)}\n")
        f.write(f"- excluded_files: {len(excluded)}\n")
        f.write(f"- records: {total}\n")
        f.write(f"- required_fields: {len(required_fields)}\n")
        f.write(f"- forbidden_summary_fields: {len(forbidden_fields)}\n")
        f.write(f"- allowed_value_rules: {len(allowed_values)}\n")
        if excluded:
            f.write(f"- excluded_scope_reason: {raw_scope.default_excluded_scope_reason()}\n")
        f.write(f"- status: {'fail' if all_errors else 'pass'}\n\n")
        if excluded:
            f.write("## Excluded Inputs\n\n")
            for path, reason in excluded:
                f.write(f"- {path}: {reason}\n")
            f.write("\n")
        if all_errors:
            f.write("## Errors\n\n")
            for err in all_errors:
                f.write(f"- {err}\n")

    if all_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
