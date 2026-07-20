# Project 03 Scripts Layout

This directory follows the project-wide structure rule in `docs/standards/项目方案.md`: project scripts live under `projects/<project>/scripts/`, grouped by execution role.

## Canonical Entry Points

| Directory | Purpose |
|---|---|
| `build/` | Build entry scripts for C++/backend artifacts. |
| `run/` | Runtime benchmark and board execution entry scripts. |
| `benchmark/` | Raw schema checks, trace checks, runtime/stability/failure aggregation. |
| `quality/` | Dataset preparation and detection quality evaluation. |
| `monitor/` | Device and stability monitoring helpers. |
| `service/` | systemd and service management assets. |

## Current Board Entry Points

- `run/run_jetson_tensorrt_pipeline.sh`: 项目三 Jetson C++ TensorRT runtime benchmark 主入口；当前 IMX219 正式主线为 `V4L2 raw 720p60 mode5 + fixed_10bit + no_white_balance`，并应检查 runtime log 里的 `V4L2_EFFECTIVE_CONFIG` / `V4L2_CAPTURE_PROFILE`。实时源默认支持 `PREVIEW_WINDOW=auto`：检测到图形环境时显示实时检测窗口，headless 时自动关闭。
- `run/run_jetson_tensorrt_bufferreuse_ab.sh`: Jetson `buffer_reuse=true/false` A/B 一键入口；顺序执行两轮 runtime600，并输出比较表。
- `run/run_jetson_tensorrt_imx219_disconnect.sh`: Jetson IMX219 `input_disconnect` 自动化入口；默认使用应用内安全断流注入，`driver_unbind` 仅保留给驱动/内核排障。
- `run/run_jetson_tensorrt_8h_mixed.sh`: Jetson 8h mixed 编排入口；默认按 `video playlist 4h + IMX219 720p60 mode5 4h` 顺序执行。
- Jetson 非交互脚本默认口径：`stability`、`8h_mixed`、`bufferreuse_ab`、`imx219_disconnect` 默认导出 `PREVIEW_WINDOW=off`，避免正式 benchmark 受桌面预览干扰；需要人工观测摄像头画面时，再在单次 run 上显式传 `PREVIEW_WINDOW=auto`。
- `run/run_jetson_bdd100k_mini.sh`: Jetson 正式 labeled-video 质量入口，使用 BDD100K MOT mini。
- `run/run_rk3588_bdd100k_mini.sh`: RK3588 正式 labeled-video 质量入口，使用 BDD100K MOT mini 输出 AP50、precision、recall、F1、TP、FP、FN。
- `run/run_rk3588_failure_injection.sh`: RK3588 03G 五项 CLI 故障注入、failure schema JSONL 和汇总门禁。
- `service/test_rk3588_systemd_service.sh`: RK3588 systemd start/restart/stop 与 journal 留证。
- `build/build_rdk_x5_bpu.sh`: RDK X5 hbDNN C API 构建入口；支持 `HOBOT_DNN_ROOT`、`HORIZON_DNN_ROOT`、`HB_DNN_INCLUDE_DIR`、`HB_DNN_LIBRARY`、`HB_HBRT_LIBRARY`。
- `run/run_rdk_x5_bpu_pipeline.sh`: RDK X5 项目三 C++ BPU runtime benchmark 主入口；固定继承项目二 split-head INT8 `.bin` 主线。当前 `imx219_rdkx5_hbn_001` / `mipi_camera_hbn` 默认朝向修正为 `rotate180`，可用 `INPUT_ORIENTATION_CORRECTION` 显式覆盖。
- `run/run_rdk_x5_bpu_stability.sh`: RDK X5 10 分钟 / 30 分钟 / 2 小时稳定性入口。
- `run/run_rdk_x5_failure_injection.sh`: RDK X5 03G CLI 故障注入、failure schema JSONL 和汇总门禁。
- `run/run_rdk_x5_input_disconnect.sh`: RDK X5 真实 live-source `input_disconnect` 自动化入口；当前默认使用 `imx219_rdkx5_hbn_001`（`mipi_camera_hbn + HBN/srcampy`），也可覆盖成 RTSP。默认 `PREVIEW_WINDOW=auto`，检测到图形环境时显示实时窗口；当前 IMX219 默认朝向修正为 `rotate180`。
- `run/rdk_x5_srcampy_stream.py`: RDK X5 板端 IMX219 `srcampy` 连续取帧 helper。它只负责把 NV12 帧流送给当前 C++ app，不负责推理主链路。
- `monitor/monitor_rdk_x5_bpu.sh`: RDK X5 BPU devfreq、thermal、process memory 和可选 `hrut_somstatus` 监控入口。
- `service/test_rdk_x5_systemd_service.sh`: RDK X5 systemd start/restart/stop 与 journal 留证。
- `quality/convert_project1_alignment_to_video_raw.py`: 把项目一 `benchmark_tensorrt.py` 的 decoded detections 转成项目三 `frame_id + detections[]` 对齐格式。
- `quality/analyze_bdd100k_focus_gap.py`: 面向 `person / bicycle / train` 的 Jetson BDD100K 域差与类别口径分析，输出 source-category recall、错类强重叠、粗定位和 no-overlap 汇总。
Do not add implementation scripts to the scripts root. Use the categorized directories above as the canonical paths.

`projects/03_video_pipeline/CMakeLists.txt` stays at the project root by design: it is the CMake project entry point required by `specs/03D_Jetson_TensorRT_CppPipeline规范.md`.
