#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def manifest_frame_ids(manifest):
    frame_scope = (manifest.get("alignment_use") or {}).get("frame_scope")
    if frame_scope == "full_video_frames":
        return list(range(int(manifest["frame_count"])))
    return [int(x) for x in manifest["frame_ids"]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--image-ext", default="png", choices=["png", "jpg", "jpeg"])
    args = parser.parse_args()

    try:
        import cv2
    except ImportError as exc:
        raise SystemExit("OpenCV Python is required on the board to extract alignment frames.") from exc

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    video_path = Path(manifest["source_video_path"])
    frame_ids = manifest_frame_ids(manifest)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"failed to open video: {video_path}")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    next_frame_id = 0
    for frame_id in frame_ids:
        if frame_id != next_frame_id:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ok, frame = cap.read()
        next_frame_id = frame_id + 1
        if not ok:
            records.append({"frame_id": frame_id, "status": "fail", "path": None})
            continue
        out_path = out_dir / f"{manifest['source_input_source_id']}_frame_{frame_id:06d}.{args.image_ext}"
        if not cv2.imwrite(str(out_path), frame):
            records.append({"frame_id": frame_id, "status": "fail", "path": str(out_path)})
            continue
        records.append({"frame_id": frame_id, "status": "pass", "path": str(out_path)})

    cap.release()
    record_path = out_dir / "extracted_frames.jsonl"
    with record_path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    passed = sum(1 for r in records if r["status"] == "pass")
    print(f"extracted={passed}/{len(records)}")
    print(f"record={record_path}")
    if passed != len(records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
