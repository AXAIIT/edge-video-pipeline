#!/usr/bin/env python3
"""Resolve the pixel rotation required by a MOV track transformation matrix."""

import argparse
import mmap
import struct
from pathlib import Path


CONTAINER_TYPES = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"udta"}


def iter_boxes(data, start, end):
    offset = start
    while offset + 8 <= end:
        size, box_type = struct.unpack_from(">I4s", data, offset)
        header_size = 8
        if size == 1:
            if offset + 16 > end:
                raise ValueError("truncated extended-size MOV box")
            size = struct.unpack_from(">Q", data, offset + 8)[0]
            header_size = 16
        elif size == 0:
            size = end - offset
        if size < header_size or offset + size > end:
            raise ValueError(f"invalid MOV box at offset {offset}")
        yield offset, size, header_size, box_type
        if box_type in CONTAINER_TYPES:
            yield from iter_boxes(data, offset + header_size, offset + size)
        offset += size


def read_track_matrices(path):
    matrices = []
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for offset, size, header_size, box_type in iter_boxes(data, 0, len(data)):
            if box_type != b"tkhd":
                continue
            payload = offset + header_size
            version = data[payload]
            matrix_offset = 52 if version == 1 else 40 if version == 0 else None
            if matrix_offset is None or payload + matrix_offset + 36 > offset + size:
                raise ValueError(f"unsupported or truncated tkhd box in {path}")
            matrices.append(struct.unpack_from(">9i", data, payload + matrix_offset))
    if not matrices:
        raise ValueError(f"no tkhd transformation matrix found in {path}")
    return matrices


def matrix_to_correction(matrix):
    a, b, _, c, d, _, _, _, _ = matrix
    if a > 0 and d > 0 and b == 0 and c == 0:
        return "none"
    if a == 0 and d == 0 and b > 0 and c < 0:
        return "clockwise"
    if a == 0 and d == 0 and b < 0 and c > 0:
        return "counterclockwise"
    raise ValueError(f"unsupported MOV track matrix: {matrix}")


def detect_orientation(path):
    corrections = {matrix_to_correction(matrix) for matrix in read_track_matrices(path)}
    if len(corrections) != 1:
        raise ValueError(f"conflicting MOV track orientations in {path}: {sorted(corrections)}")
    return corrections.pop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    args = parser.parse_args()
    path = Path(args.video)
    if not path.is_file():
        raise SystemExit(f"video not found: {path}")
    try:
        print(detect_orientation(path))
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"MOV_ORIENTATION_DETECTION_FAILED: {exc}") from exc


if __name__ == "__main__":
    main()
