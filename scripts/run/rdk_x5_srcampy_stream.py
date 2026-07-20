#!/usr/bin/env python3
"""RDK X5 IMX219 srcampy 连续取帧并通过 stdout 输出 NV12 帧流。

用途：
1. 复用板端已验证可用的 HBN/srcampy MIPI 取帧路径；
2. 由项目三 C++ app 作为父进程拉起并消费连续 NV12 帧；
3. 避免继续假设 RDK X5 一定存在 `/dev/video0` 的 V4L2 入口。

协议：
- stdout 只输出二进制帧流，不打印任何日志；
- 每帧先输出一行 ASCII header：`FRAME <frame_id> <width> <height> <bytes>\n`
- 紧接着输出对应的 NV12 原始字节；
- 所有运行状态和诊断信息都写到 stderr。
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time

try:
    from hobot_vio import libsrcampy as srcampy
except Exception:
    from hobot_vio_rdkx5 import libsrcampy as srcampy


_STOP = False


def _handle_signal(signum, frame):
    del signum, frame
    global _STOP
    _STOP = True


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stream RDK X5 MIPI NV12 frames to stdout for the C++ pipeline."
    )
    parser.add_argument("--video-idx", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=640)
    parser.add_argument("--sensor-width", type=int, default=1920)
    parser.add_argument("--sensor-height", type=int, default=1080)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--startup-timeout-sec", type=float, default=8.0)
    parser.add_argument("--print-every", type=int, default=120)
    parser.add_argument(
        "--stream-fd",
        type=int,
        default=1,
        help="Write frame protocol to this inherited file descriptor. Default: 1 (stdout).",
    )
    return parser.parse_args()


def stderr(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def main() -> int:
    args = parse_args()
    if args.width <= 0 or args.height <= 0:
        stderr("ERROR: width/height must be positive")
        return 2
    expected = args.width * args.height * 3 // 2

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    cam = srcampy.Camera()
    stderr(
        "SRCAMPY_STREAM_OPEN "
        f"video_idx={args.video_idx} output={args.width}x{args.height} "
        f"sensor={args.sensor_width}x{args.sensor_height} warmup={args.warmup}"
    )
    cam.open_cam(
        args.video_idx,
        -1,
        -1,
        [args.width, args.sensor_width],
        [args.height, args.sensor_height],
        args.sensor_height,
        args.sensor_width,
    )

    start = time.time()
    frame_id = 0
    seen_frame = False
    try:
        raw_stream = os.fdopen(args.stream_fd, "wb", buffering=0, closefd=False)
    except OSError as exc:
        stderr(f"ERROR: failed to open stream fd {args.stream_fd}: {exc}")
        return 5
    try:
        loop_index = 0
        while not _STOP:
            frame = cam.get_img(2, args.width, args.height)
            if frame is None:
                if not seen_frame and time.time() - start > args.startup_timeout_sec:
                    stderr(
                        "SRCAMPY_STREAM_ERROR no_frame_captured "
                        f"startup_timeout_sec={args.startup_timeout_sec}"
                    )
                    return 3
                continue
            if loop_index < args.warmup:
                loop_index += 1
                continue

            payload = memoryview(frame)
            if len(payload) != expected:
                stderr(
                    "SRCAMPY_STREAM_ERROR unexpected_nv12_size "
                    f"got={len(payload)} expected={expected}"
                )
                return 4

            header = f"FRAME {frame_id} {args.width} {args.height} {expected}\n".encode("ascii")
            try:
                raw_stream.write(header)
                raw_stream.write(payload)
                raw_stream.flush()
            except BrokenPipeError:
                stderr("SRCAMPY_STREAM_EOF parent_pipe_closed")
                return 0

            seen_frame = True
            if args.print_every > 0 and frame_id % args.print_every == 0:
                stderr(
                    "SRCAMPY_STREAM_STATUS "
                    f"frame_id={frame_id} elapsed_sec={time.time() - start:.3f}"
                )
            frame_id += 1
            loop_index += 1
    finally:
        cam.close_cam()
        stderr(f"SRCAMPY_STREAM_CLOSE frames={frame_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
