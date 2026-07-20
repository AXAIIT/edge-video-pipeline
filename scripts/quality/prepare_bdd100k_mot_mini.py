#!/usr/bin/env python3
import argparse
import csv
import json
import hashlib
import shutil
from collections import Counter, defaultdict
from pathlib import Path


BDD_TO_COCO = {
    "pedestrian": {"class_id": 0, "class_name": "person", "include": True},
    "rider": {"class_id": 0, "class_name": "person", "include": True},
    "bicycle": {"class_id": 1, "class_name": "bicycle", "include": True},
    "car": {"class_id": 2, "class_name": "car", "include": True},
    "motorcycle": {"class_id": 3, "class_name": "motorcycle", "include": True},
    "bus": {"class_id": 5, "class_name": "bus", "include": True},
    "train": {"class_id": 6, "class_name": "train", "include": True},
    "truck": {"class_id": 7, "class_name": "truck", "include": True},
    "other person": {"include": False},
    "other vehicle": {"include": False},
    "trailer": {"include": False},
}


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_selected_sequences(path):
    if not path:
        return None
    selected = []
    with Path(path).open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("<"):
                selected.append(line)
    return set(selected)


def find_video_files(root):
    root = Path(root)
    videos = {}
    for pattern in ("*.mov", "*.mp4", "*.avi", "*.mkv"):
        for path in root.rglob(pattern):
            videos[path.stem] = path
    return videos


def parse_bool(value):
    return str(value).strip().lower() in {"true", "1", "yes"}


def csv_bbox_xywh(row):
    x1 = float(row["box2d.x1"])
    x2 = float(row["box2d.x2"])
    y1 = float(row["box2d.y1"])
    y2 = float(row["box2d.y2"])
    return [x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)]


def collect_csv_stats(csv_path, videos):
    stats = {}
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_name = row["videoName"]
            stat = stats.setdefault(video_name, {
                "frames": set(),
                "boxes": 0,
                "categories": Counter(),
                "included_categories": Counter(),
                "have_video": False,
            })
            stat["frames"].add(int(row["frameIndex"]))
            stat["boxes"] += 1
            category = row.get("category", "").strip()
            stat["categories"][category] += 1
            mapping = BDD_TO_COCO.get(category)
            if mapping and mapping.get("include"):
                stat["included_categories"][category] += 1
            stat["have_video"] = stat["have_video"] or parse_bool(row.get("haveVideo", ""))

    for video_name, stat in stats.items():
        stat["video_path"] = videos.get(video_name)
        stat["video_size_bytes"] = videos[video_name].stat().st_size if video_name in videos else None
        stat["matched_video"] = video_name in videos and stat["have_video"]
    return stats


def choose_with_budget(chosen, candidate, stats, budget_bytes, target_sequences):
    if candidate in chosen:
        return False
    if len(chosen) >= target_sequences:
        return False
    size = stats[candidate]["video_size_bytes"]
    if size is None:
        return False
    if sum(stats[name]["video_size_bytes"] for name in chosen) + size > budget_bytes:
        return False
    chosen.append(candidate)
    return True


def auto_select_sequences(stats, target_sequences, budget_bytes):
    matched = [
        name for name, stat in stats.items()
        if stat["matched_video"] and sum(stat["included_categories"].values()) > 0
    ]
    chosen = []

    priority_categories = ["train", "motorcycle", "rider", "bicycle", "bus", "truck", "pedestrian", "car"]
    for category in priority_categories:
        ranked = sorted(
            [name for name in matched if stats[name]["included_categories"].get(category, 0) > 0],
            key=lambda name: (
                -stats[name]["included_categories"][category],
                stats[name]["video_size_bytes"],
                name,
            ),
        )
        for name in ranked[:8]:
            choose_with_budget(chosen, name, stats, budget_bytes, target_sequences)

    by_density = sorted(matched, key=lambda name: (stats[name]["boxes"], stats[name]["video_size_bytes"], name))
    for name in by_density[:12]:
        choose_with_budget(chosen, name, stats, budget_bytes, target_sequences)
    for name in reversed(by_density[-12:]):
        choose_with_budget(chosen, name, stats, budget_bytes, target_sequences)

    def score(name):
        cats = stats[name]["included_categories"]
        diversity = sum(1 for value in cats.values() if value > 0)
        rare = (
            cats.get("train", 0) * 10
            + cats.get("motorcycle", 0) * 5
            + cats.get("rider", 0) * 4
            + cats.get("bicycle", 0) * 4
            + cats.get("bus", 0) * 3
            + cats.get("truck", 0) * 2
        )
        size_mb = stats[name]["video_size_bytes"] / (1024 * 1024)
        return (
            diversity * 10000
            + min(sum(cats.values()), 5000)
            + min(rare, 10000)
            + len(stats[name]["frames"]) * 5
            - size_mb * 10
        )

    for name in sorted(matched, key=lambda item: (-score(item), stats[item]["video_size_bytes"], item)):
        choose_with_budget(chosen, name, stats, budget_bytes, target_sequences)

    return chosen


def csv_label_row(row, source_frame_stride):
    category = row.get("category", "").strip()
    mapping = BDD_TO_COCO.get(category)
    if not mapping or not mapping.get("include"):
        return None, category or "blank"
    xywh = csv_bbox_xywh(row)
    if xywh[2] <= 0 or xywh[3] <= 0:
        return None, f"{category}:invalid_box2d"
    return {
        "class_id": mapping["class_id"],
        "class_name": mapping["class_name"],
        "source_category": category,
        "track_id": str(row.get("id", "")),
        "bbox_xywh": xywh,
        "attributes": {
            "crowd": parse_bool(row.get("attributes.crowd", "")),
            "occluded": parse_bool(row.get("attributes.occluded", "")),
            "truncated": parse_bool(row.get("attributes.truncated", "")),
        },
    }, None


def write_selected_sequences(path, selected):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for sequence_id in selected:
            f.write(sequence_id + "\n")


def write_selection_report(path, manifest):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("# BDD100K MOT Mini v1 Selection Report\n\n")
        f.write(f"- dataset_id: `{manifest['dataset_id']}`\n")
        f.write(f"- status: `{manifest['status']}`\n")
        f.write(f"- source: {manifest['source']}\n")
        f.write(f"- source_url: `{manifest['source_url']}`\n")
        f.write(f"- sequence_count: {manifest['sequence_count']}\n")
        f.write(f"- labeled_frame_count: {manifest['labeled_frame_count']}\n")
        f.write(f"- label_box_count: {manifest['label_box_count']}\n")
        f.write(f"- prepared_video_size_gb: {manifest['prepared_video_size_gb']:.3f}\n")
        f.write(f"- storage_budget_gb: {manifest['storage_budget_gb']:.3f}\n")
        f.write(f"- frame_alignment: {manifest['frame_alignment']['policy']}\n")
        f.write("\n## Category Counts\n\n")
        f.write("| category | count |\n")
        f.write("|---|---:|\n")
        for category, count in sorted(manifest["category_counts"].items(), key=lambda item: (-item[1], item[0])):
            f.write(f"| {category} | {count} |\n")
        f.write("\n## Ignored Counts\n\n")
        f.write("| category | count |\n")
        f.write("|---|---:|\n")
        for category, count in sorted(manifest["ignored_counts"].items(), key=lambda item: (-item[1], item[0])):
            f.write(f"| {category} | {count} |\n")
        f.write("\n## Limitations\n\n")
        f.write("- Quality evaluation is valid only on labeled frames.\n")
        f.write("- Labels are aligned to raw video frames with `frame_id = frameIndex * source_frame_stride`.\n")
        f.write("- The Kaggle subset does not include BDD100K weather/time/scene metadata, so scene coverage is `not_verified` unless manually audited.\n")
        f.write("- `other person`, `other vehicle`, `trailer` and blank categories are ignored in the main detector-quality metric.\n")
        f.write("\n## Selected Sequences\n\n")
        f.write("| sequence_id | video_size_mb | labeled_frames | label_boxes | video_sha256 |\n")
        f.write("|---|---:|---:|---:|---|\n")
        for seq in manifest["sequences"]:
            label_boxes = sum(seq["category_counts"].values())
            f.write(
                f"| `{seq['sequence_id']}` | {seq['video_size_bytes'] / (1024 * 1024):.2f} | "
                f"{seq['labeled_frame_count']} | {label_boxes} | `{seq['video_sha256']}` |\n"
            )


def prepare_from_kaggle_csv(args):
    videos = find_video_files(args.video_root)
    stats = collect_csv_stats(args.csv_labels, videos)
    selected = read_selected_sequences(args.selected_sequences)
    if selected:
        selected = [name for name in selected if name in stats and stats[name]["matched_video"]]
    else:
        selected = auto_select_sequences(
            stats,
            target_sequences=args.target_sequences,
            budget_bytes=int(args.max_total_size_gb * (1024 ** 3)),
        )
    if not selected:
        raise SystemExit("no matched Kaggle BDD100K MOT sequences selected")

    selected_set = set(selected)
    frames_by_sequence = defaultdict(lambda: defaultdict(list))
    ignored_counts = Counter()
    with Path(args.csv_labels).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sequence_id = row["videoName"]
            if sequence_id not in selected_set:
                continue
            det, ignored = csv_label_row(row, args.source_frame_stride)
            if ignored:
                ignored_counts[ignored] += 1
                continue
            label_frame_index = int(row["frameIndex"])
            pipeline_frame_id = label_frame_index * args.source_frame_stride
            frames_by_sequence[sequence_id][pipeline_frame_id].append(det)

    output_video_dir = Path(args.output_video_dir)
    output_label_dir = Path(args.output_label_dir)
    output_video_dir.mkdir(parents=True, exist_ok=True)
    output_label_dir.mkdir(parents=True, exist_ok=True)

    manifest_sequences = []
    total_video_bytes = 0
    category_counts = Counter()
    total_label_boxes = 0
    for sequence_id in selected:
        frame_map = frames_by_sequence[sequence_id]
        rows = []
        for frame_id in sorted(frame_map):
            detections = frame_map[frame_id]
            rows.append({
                "sequence_id": sequence_id,
                "frame_id": frame_id,
                "source_label_frame_index": frame_id // args.source_frame_stride,
                "source_video_frame_id": frame_id,
                "frame_id_mapping": f"source_video_frame_id = source_label_frame_index * {args.source_frame_stride}",
                "detections": detections,
            })
            for det in detections:
                category_counts[det["source_category"]] += 1
                total_label_boxes += 1

        label_path = output_label_dir / f"{sequence_id}.jsonl"
        write_jsonl(label_path, rows)

        src_video = stats[sequence_id]["video_path"]
        dst_video = output_video_dir / src_video.name
        if args.copy_videos:
            shutil.copy2(src_video, dst_video)
            video_path = dst_video
        else:
            video_path = src_video
        video_size = video_path.stat().st_size
        total_video_bytes += video_size

        manifest_sequences.append({
            "sequence_id": sequence_id,
            "input_source_id": f"bdd100k_mot_mini_v1_{sequence_id}",
            "video_path": video_path.as_posix(),
            "video_sha256": sha256_file(video_path),
            "video_size_bytes": video_size,
            "label_path": label_path.as_posix(),
            "label_sha256": sha256_file(label_path),
            "labeled_frame_count": len(rows),
            "source_frame_stride": args.source_frame_stride,
            "category_counts": dict(Counter(det["source_category"] for row in rows for det in row["detections"])),
        })

    total_size_gb = total_video_bytes / (1024 ** 3)
    if total_size_gb > args.max_total_size_gb:
        raise SystemExit(f"prepared videos exceed budget: {total_size_gb:.3f} GB > {args.max_total_size_gb:.3f} GB")

    write_selected_sequences(args.output_selected_sequences, selected)
    manifest = {
        "dataset_id": "bdd100k_mot_mini_v1",
        "status": "ready",
        "source": "Kaggle BDD100K tracking subset",
        "source_url": "http://kaggle.com/datasets/robikscube/driving-video-with-object-tracking?resource=download",
        "csv_labels": Path(args.csv_labels).as_posix(),
        "video_root": Path(args.video_root).as_posix(),
        "storage_budget_gb": args.max_total_size_gb,
        "prepared_video_size_gb": total_size_gb,
        "sequence_count": len(manifest_sequences),
        "labeled_frame_count": sum(seq["labeled_frame_count"] for seq in manifest_sequences),
        "label_box_count": total_label_boxes,
        "category_counts": dict(category_counts),
        "ignored_counts": dict(ignored_counts),
        "class_mapping": BDD_TO_COCO,
        "frame_alignment": {
            "raw_video_fps": "about 30",
            "label_rate": "about 5 fps",
            "source_frame_stride": args.source_frame_stride,
            "policy": "label frameIndex k is evaluated against pipeline frame_id k * source_frame_stride",
        },
        "coverage_status": {
            "object_category_coverage": "ready",
            "weather_time_scene_metadata": "not_verified",
        },
        "sequences": manifest_sequences,
    }
    manifest_path = Path(args.output_manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_selection_report(args.output_selection_report, manifest)

    print("dataset_id=bdd100k_mot_mini_v1")
    print("status=ready")
    print(f"sequence_count={manifest['sequence_count']}")
    print(f"labeled_frame_count={manifest['labeled_frame_count']}")
    print(f"label_box_count={manifest['label_box_count']}")
    print(f"prepared_video_size_gb={total_size_gb:.3f}")
    print(f"manifest={manifest_path}")


def label_files(root):
    return sorted(Path(root).rglob("*.json"))


def load_bdd_frames(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("frames", "frameLabels", "labels"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        if "name" in data and "labels" in data:
            return [data]
    raise SystemExit(f"unsupported BDD label JSON structure: {path}")


def frame_sequence_id(frame, fallback):
    return str(frame.get("videoName") or frame.get("video_name") or fallback)


def frame_name(frame):
    return str(frame.get("name") or frame.get("frameName") or frame.get("frame_name") or "")


def frame_index(frame, fallback):
    value = frame.get("frameIndex", frame.get("frame_index", fallback))
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def bbox_xywh(box):
    x1 = float(box["x1"])
    y1 = float(box["y1"])
    x2 = float(box["x2"])
    y2 = float(box["y2"])
    return [x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)]


def convert_frame(frame, sequence_id, local_frame_id):
    detections = []
    ignored = Counter()
    for label in frame.get("labels", []):
        category = str(label.get("category", "")).strip()
        mapping = BDD_TO_COCO.get(category)
        if not mapping or not mapping.get("include"):
            ignored[category or "unknown"] += 1
            continue
        box = label.get("box2d")
        if not box:
            ignored[f"{category}:missing_box2d"] += 1
            continue
        xywh = bbox_xywh(box)
        if xywh[2] <= 0 or xywh[3] <= 0:
            ignored[f"{category}:invalid_box2d"] += 1
            continue
        detections.append({
            "class_id": mapping["class_id"],
            "class_name": mapping["class_name"],
            "source_category": category,
            "track_id": str(label.get("id", "")),
            "bbox_xywh": xywh,
            "attributes": label.get("attributes", {}),
        })

    return {
        "sequence_id": sequence_id,
        "frame_id": local_frame_id,
        "source_frame_index": frame_index(frame, local_frame_id),
        "source_frame_name": frame_name(frame),
        "attributes": frame.get("attributes", {}),
        "detections": detections,
    }, ignored


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def find_image(images_root, sequence_id, name):
    root = Path(images_root)
    candidates = [
        root / sequence_id / name,
        root / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    hits = list(root.rglob(name))
    return hits[0] if hits else None


def write_video(rows, images_root, output_path, fps, codec):
    try:
        import cv2
    except ImportError as exc:
        raise SystemExit("OpenCV Python is required for --write-video.") from exc

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    first_image = None
    for row in rows:
        first_image = find_image(images_root, row["sequence_id"], row["source_frame_name"])
        if first_image:
            break
    if not first_image:
        raise SystemExit(f"no images found for sequence {rows[0]['sequence_id']} under {images_root}")

    first_frame = cv2.imread(str(first_image), cv2.IMREAD_COLOR)
    if first_frame is None:
        raise SystemExit(f"failed to read first image: {first_image}")
    height, width = first_frame.shape[:2]
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*codec),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise SystemExit(f"failed to open video writer: {output_path}")

    for row in rows:
        image_path = find_image(images_root, row["sequence_id"], row["source_frame_name"])
        if not image_path:
            writer.release()
            raise SystemExit(f"missing image: sequence={row['sequence_id']} frame={row['source_frame_name']}")
        frame = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if frame is None:
            writer.release()
            raise SystemExit(f"failed to read image: {image_path}")
        writer.write(frame)
    writer.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels-root")
    parser.add_argument("--csv-labels")
    parser.add_argument("--video-root")
    parser.add_argument("--images-root")
    parser.add_argument("--selected-sequences")
    parser.add_argument("--output-video-dir", default="data/videos/bdd100k_mot_mini_v1")
    parser.add_argument("--output-label-dir", default="data/validation/bdd100k_mot_mini_v1/labels")
    parser.add_argument("--output-manifest", default="data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json")
    parser.add_argument("--output-selected-sequences", default="data/validation/bdd100k_mot_mini_v1/selected_sequences.txt")
    parser.add_argument("--output-selection-report", default="data/validation/bdd100k_mot_mini_v1/selection_report.md")
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--codec", default="MJPG")
    parser.add_argument("--max-total-size-gb", type=float, default=5.0)
    parser.add_argument("--target-sequences", type=int, default=80)
    parser.add_argument("--source-frame-stride", type=int, default=6)
    parser.add_argument("--copy-videos", action="store_true")
    parser.add_argument("--write-video", action="store_true")
    args = parser.parse_args()

    if args.csv_labels:
        if not args.video_root:
            raise SystemExit("--video-root is required with --csv-labels")
        prepare_from_kaggle_csv(args)
        return

    if not args.labels_root:
        raise SystemExit("--labels-root is required unless --csv-labels is used")
    if args.write_video and not args.images_root:
        raise SystemExit("--images-root is required with --write-video")

    selected = read_selected_sequences(args.selected_sequences)
    sequences = defaultdict(list)
    for path in label_files(args.labels_root):
        frames = load_bdd_frames(path)
        fallback_sequence_id = path.stem
        for frame in frames:
            sequence_id = frame_sequence_id(frame, fallback_sequence_id)
            if selected is not None and sequence_id not in selected:
                continue
            sequences[sequence_id].append(frame)

    if not sequences:
        raise SystemExit("no selected BDD100K MOT sequences found")

    manifest_sequences = []
    total_video_bytes = 0
    total_label_boxes = 0
    category_counts = Counter()
    ignored_counts = Counter()
    for sequence_id, frames in sorted(sequences.items()):
        rows = []
        for local_frame_id, frame in enumerate(sorted(frames, key=lambda x: frame_index(x, 0))):
            row, ignored = convert_frame(frame, sequence_id, local_frame_id)
            rows.append(row)
            ignored_counts.update(ignored)
            for det in row["detections"]:
                category_counts[det["source_category"]] += 1

        label_path = Path(args.output_label_dir) / f"{sequence_id}.jsonl"
        write_jsonl(label_path, rows)
        total_label_boxes += sum(len(row["detections"]) for row in rows)

        video_path = Path(args.output_video_dir) / f"{sequence_id}.avi"
        video_sha = None
        video_bytes = None
        if args.write_video:
            write_video(rows, args.images_root, video_path, args.fps, args.codec)
            video_sha = sha256_file(video_path)
            video_bytes = video_path.stat().st_size
            total_video_bytes += video_bytes

        manifest_sequences.append({
            "sequence_id": sequence_id,
            "input_source_id": f"bdd100k_mot_mini_v1_{sequence_id}",
            "frame_count": len(rows),
            "fps": args.fps,
            "label_path": label_path.as_posix(),
            "label_sha256": sha256_file(label_path),
            "video_path": video_path.as_posix() if args.write_video else None,
            "video_sha256": video_sha,
            "video_size_bytes": video_bytes,
            "category_counts": dict(Counter(det["source_category"] for row in rows for det in row["detections"])),
        })

    total_size_gb = total_video_bytes / (1024 ** 3)
    if args.write_video and total_size_gb > args.max_total_size_gb:
        raise SystemExit(f"prepared videos exceed budget: {total_size_gb:.3f} GB > {args.max_total_size_gb:.3f} GB")

    manifest = {
        "dataset_id": "bdd100k_mot_mini_v1",
        "status": "ready" if args.write_video else "labels_ready_video_pending",
        "source": "BDD100K MOT",
        "storage_budget_gb": args.max_total_size_gb,
        "prepared_video_size_gb": total_size_gb if args.write_video else None,
        "fps": args.fps,
        "codec": args.codec,
        "sequence_count": len(manifest_sequences),
        "labeled_frame_count": sum(seq["frame_count"] for seq in manifest_sequences),
        "label_box_count": total_label_boxes,
        "category_counts": dict(category_counts),
        "ignored_counts": dict(ignored_counts),
        "class_mapping": BDD_TO_COCO,
        "sequences": manifest_sequences,
    }

    manifest_path = Path(args.output_manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"dataset_id=bdd100k_mot_mini_v1")
    print(f"status={manifest['status']}")
    print(f"sequence_count={manifest['sequence_count']}")
    print(f"labeled_frame_count={manifest['labeled_frame_count']}")
    print(f"label_box_count={manifest['label_box_count']}")
    print(f"manifest={manifest_path}")


if __name__ == "__main__":
    main()
