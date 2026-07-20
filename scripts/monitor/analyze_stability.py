#!/usr/bin/env python3
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--monitor", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    raw_path = Path(args.raw)
    monitor_path = Path(args.monitor)
    frame_count = 0
    if raw_path.exists():
        with raw_path.open("r", encoding="utf-8") as f:
            frame_count = sum(1 for line in f if line.strip())

    monitor_exists = monitor_path.exists()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write("\n## Stability Analyze Append\n\n")
        f.write(f"- raw: `{args.raw}`\n")
        f.write(f"- monitor: `{args.monitor}`\n")
        f.write(f"- frame_count: {frame_count}\n")
        f.write(f"- monitor_exists: {str(monitor_exists).lower()}\n")
        f.write(f"- status: {'not_verified' if not monitor_exists else 'processed'}\n")


if __name__ == "__main__":
    main()
