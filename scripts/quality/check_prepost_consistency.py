#!/usr/bin/env python3
import argparse
import ast
from pathlib import Path


def strip_comments(line):
    in_single = False
    in_double = False
    out = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse_scalar(value):
    value = value.strip()
    if value == "":
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if value.startswith("[") or value.startswith("{"):
        return ast.literal_eval(value)
    try:
        if any(ch in value for ch in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value.strip("\"'")


def parse_simple_yaml(path):
    data = {}
    stack = [(-1, data)]
    for raw_line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = strip_comments(raw_line)
        if not line.strip():
            continue
        stripped = line.lstrip(" ")
        if stripped.startswith("- "):
            continue
        indent = len(line) - len(stripped)
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            node = {}
            parent[key] = node
            stack.append((indent, node))
        else:
            parent[key] = parse_scalar(value)
    return data


def get_path(data, path, default=None):
    cur = data
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def bool_text(value):
    return "true" if value else "false"


def approx_equal(lhs, rhs, tol=1e-9):
    return abs(float(lhs) - float(rhs)) <= tol


def read_source(path):
    return Path(path).read_text(encoding="utf-8-sig")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project1-preprocess",
        default="projects/01_vision_deploy/configs/preprocess/yolo11n_640.yaml",
    )
    parser.add_argument(
        "--project1-postprocess",
        default="projects/01_vision_deploy/configs/postprocess/yolo11n_nms.yaml",
    )
    parser.add_argument(
        "--project3-model",
        default="projects/03_video_pipeline/configs/models/yolo11n.yaml",
    )
    parser.add_argument(
        "--project3-source",
        default="projects/03_video_pipeline/src/video_pipeline_app.cpp",
    )
    parser.add_argument("--project3-board", default="")
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    p1_pre = parse_simple_yaml(args.project1_preprocess)
    p1_post = parse_simple_yaml(args.project1_postprocess)
    p3_model = parse_simple_yaml(args.project3_model)
    p3_board = parse_simple_yaml(args.project3_board) if args.project3_board else {}
    source = read_source(args.project3_source)

    p1_input_size = get_path(p1_pre, "preprocess.input_size")
    p1_letterbox_color = get_path(p1_pre, "preprocess.letterbox_color")
    p1_resize_mode = get_path(p1_pre, "preprocess.resize_mode")
    p1_input_format = str(get_path(p1_pre, "preprocess.input_format", "rgb")).upper()
    p1_input_layout = str(get_path(p1_pre, "preprocess.input_layout", "nchw")).upper()
    p1_normalize = bool(get_path(p1_pre, "preprocess.normalize", True))
    p1_effective_scale = 1.0 / 255.0 if p1_normalize else 1.0
    p1_agnostic_nms = bool(get_path(p1_post, "postprocess.agnostic_nms", False))
    p1_iou = get_path(p1_post, "postprocess.iou_threshold")
    p1_max_det = get_path(p1_post, "postprocess.max_detections")
    p1_conf = get_path(p1_post, "postprocess.confidence_threshold")

    p3_width = get_path(p3_model, "input.width")
    p3_height = get_path(p3_model, "input.height")
    p3_color = str(get_path(p3_model, "input.color_format", "RGB")).upper()
    p3_layout = str(get_path(p3_model, "input.layout", "NCHW")).upper()
    p3_resize_type = get_path(p3_model, "input.resize.type")
    p3_keep_ratio = bool(get_path(p3_model, "input.resize.keep_ratio", True))
    p3_pad = get_path(p3_model, "input.resize.pad_value")
    p3_backend = get_path(p3_board, "runtime.backend_runtime", "")
    p3_pad_override = get_path(p3_board, "runtime.preprocess_pad_value")
    p3_effective_pad = p3_pad_override if p3_pad_override is not None else p3_pad
    expected_pad = 0 if str(p3_backend).lower() == "rknn" else p1_letterbox_color[0]
    p3_scale = get_path(p3_model, "input.normalize.scale")
    p3_agnostic_nms = bool(get_path(p3_model, "postprocess.class_agnostic_nms", False))
    p3_iou = get_path(p3_model, "postprocess.nms_iou_threshold")
    p3_max_det = get_path(p3_model, "postprocess.max_detections")
    p3_conf = get_path(p3_model, "postprocess.confidence_threshold")

    rows = []

    def add_row(item, severity, expected, actual, ok, note):
        rows.append({
            "item": item,
            "severity": severity,
            "expected": expected,
            "actual": actual,
            "status": "pass" if ok else "fail",
            "note": note,
        })

    add_row(
        "input_size",
        "must_match",
        f"{p1_input_size[0]}x{p1_input_size[1]}",
        f"{p3_width}x{p3_height}",
        list(p1_input_size) == [p3_width, p3_height],
        "项目一/二与项目三输入尺寸必须一致。",
    )
    add_row(
        "resize_mode",
        "must_match",
        "letterbox",
        str(p3_resize_type),
        str(p1_resize_mode).lower() == "letterbox" and str(p3_resize_type).lower() == "letterbox",
        "项目三必须保持 letterbox。",
    )
    add_row(
        "keep_ratio",
        "must_match",
        "true",
        bool_text(p3_keep_ratio),
        p3_keep_ratio,
        "letterbox 必须保持长宽比。",
    )
    add_row(
        "pad_value",
        "must_match",
        str(expected_pad),
        str(p3_effective_pad),
        approx_equal(expected_pad, p3_effective_pad),
        "RKNN official 实际链路使用 0；其他后端沿用项目一 letterbox 配置。",
    )
    add_row(
        "color_format",
        "must_match",
        p1_input_format,
        p3_color,
        p1_input_format == p3_color,
        "颜色通道顺序必须一致。",
    )
    add_row(
        "layout",
        "must_match",
        p1_input_layout,
        p3_layout,
        p1_input_layout == p3_layout,
        "张量 layout 必须一致。",
    )
    add_row(
        "normalize_scale",
        "must_match",
        f"{p1_effective_scale:.12f}",
        f"{float(p3_scale):.12f}",
        approx_equal(p1_effective_scale, p3_scale, tol=1e-12),
        "当前项目一/二运行时等效为 /255，项目三必须等效一致。",
    )
    add_row(
        "nms_mode",
        "must_match",
        bool_text(p1_agnostic_nms),
        bool_text(p3_agnostic_nms),
        p1_agnostic_nms == p3_agnostic_nms,
        "项目一/二后处理基线是 agnostic_nms=false。",
    )
    add_row(
        "nms_iou_threshold",
        "tunable",
        str(p1_iou),
        str(p3_iou),
        approx_equal(p1_iou, p3_iou),
        "IoU 阈值通常应保持一致，单独实验可以调整。",
    )
    add_row(
        "max_detections",
        "tunable",
        str(p1_max_det),
        str(p3_max_det),
        int(p1_max_det) == int(p3_max_det),
        "最大保留框数通常应保持一致。",
    )
    add_row(
        "confidence_threshold",
        "tunable",
        str(p1_conf),
        str(p3_conf),
        approx_equal(p1_conf, p3_conf),
        "confidence 可做 sweep，但必须在 run 记录中显式声明。",
    )
    add_row(
        "source_has_class_aware_switch",
        "must_match",
        "class_agnostic_nms wired",
        "present" if "class_agnostic_nms" in source else "missing",
        "class_agnostic_nms" in source,
        "C++ 必须消费 model_config 中的 class_agnostic_nms。",
    )
    add_row(
        "source_no_opencv_class_agnostic_nms",
        "must_match",
        "no cv::dnn::NMSBoxes",
        "found" if "cv::dnn::NMSBoxes(" in source else "not_found",
        "cv::dnn::NMSBoxes(" not in source,
        "避免无意退回类无关 NMS。",
    )
    add_row(
        "source_has_custom_nms",
        "must_match",
        "NmsIndices helper",
        "present" if "NmsIndices(" in source else "missing",
        "NmsIndices(" in source,
        "项目三应显式实现与项目一/二一致的按类 NMS。",
    )

    must_failures = [row for row in rows if row["severity"] == "must_match" and row["status"] != "pass"]
    status = "pass" if not must_failures else "fail"

    output_path = Path(args.output_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write("# Pre/Post Consistency Check\n\n")
        f.write(f"- project1_preprocess: `{args.project1_preprocess}`\n")
        f.write(f"- project1_postprocess: `{args.project1_postprocess}`\n")
        f.write(f"- project3_model: `{args.project3_model}`\n")
        f.write(f"- project3_board: `{args.project3_board or 'not_provided'}`\n")
        f.write(f"- project3_source: `{args.project3_source}`\n")
        f.write(f"- status: {status}\n")
        f.write(f"- must_match_failures: {len(must_failures)}\n\n")
        f.write("| item | severity | expected | actual | status | note |\n")
        f.write("|---|---|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| {row['item']} | {row['severity']} | {row['expected']} | "
                f"{row['actual']} | {row['status']} | {row['note']} |\n"
            )

    print(f"prepost_status={status}")
    print(f"prepost_report={output_path}")
    if status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
