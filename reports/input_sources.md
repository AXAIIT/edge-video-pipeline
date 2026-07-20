# 项目三输入源清单

本文件记录 `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml` 中每个输入源的实际状态。所有 runtime、stability 和 failure run 必须引用 `input_source_id`，不能只写临时文件名或设备名。

## 数据集口径区别

| 项目 | `video_short_001` | `bdd100k_mot_mini_v1` |
|---|---|---|
| 来源 | OpenCV `vtest.avi` 单个样例视频 | BDD100K MOT 筛选并制备的 80 段道路视频 |
| 规模 | 795 帧 | 15,631 个人工标注帧、230,698 个 GT 框 |
| 人工标注 | 无 | 有 |
| 可用范围 | 仅保留历史问题诊断和既有结果追溯 | 当前及后续 runtime、stability、failure 和正式视频质量评估 |
| 可计算质量指标 | 不能计算正式 AP50、precision、recall、F1 | 可计算 AP50、precision、recall、F1、TP、FP、FN 和 coverage |

两者不是同一数据集，输入内容、分辨率、帧率、场景分布和标注口径均不同，指标不得直接横向合并。除问题库和历史证据行外，项目三统一使用 `bdd100k_mot_mini_v1`。

| input_source_id | type | uri/device | sha256 | codec | width | height | fps | duration | frame_count | availability | notes |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| `video_short_001` | video_file | `data/videos/video_fixed_v1/video_short_001.avi` | `45cddc9490be69345cbdab64ca583be65987e864ca408038e648db99e10516cf` | div3 | 768 | 576 | 10.0 | 79.5 sec | 795 | deprecated_historical_only | 无人工标注 OpenCV 样例；仅用于历史问题诊断和证据追溯，不得用于新 run 或正式质量结论 |
| `video_long_loop_001` | video_file | `data/videos/video_fixed_v1/video_short_001.avi` | `45cddc9490be69345cbdab64ca583be65987e864ca408038e648db99e10516cf` | div3 | 768 | 576 | 10.0 | 79.5 sec looped | 795 per loop | deprecated_historical_only | 与旧短视频为同一无标注文件，仅保留历史回退诊断，不再用于新 run |
| `video_set_runtime_v1` | video_playlist | `data/videos/runtime_playlist_v1.txt` | `null` | mixed BDD100K MOV | 1280 | 720 | about 30.0 | looped playlist | 20 clips | ready | 固定 20 条 BDD100K MOT mini 子集，用于可复现的 600s runtime 主线 benchmark |
| `video_set_stability_v1` | video_playlist | `data/videos/stability_playlist_v1.txt` | `null` | mixed BDD100K MOV | 1280 | 720 | about 30.0 | looped playlist | 80 clips | ready | 全量 80 条 BDD100K MOT mini 视频集，用于 paced sustained realtime-like stability 运行，优先替代单一短视频循环 |
| `imx219_csi_001` | mipi_camera | `/dev/video0` | null | RG10 raw Bayer | 1920 | 1080 | 30.0 | live stream | null | jetson_board_verified | Jetson CSI IMX219 正式 live-source；当前正式可用口径为 `V4L2 raw 720p60 mode5 + fixed_10bit + no_white_balance` |
| `imx219_rdkx5_hbn_001` | mipi_camera_hbn | `srcampy://video_idx0` | null | srcampy NV12 | 640 | 640 | 30.0 | live stream | null | board_verified_perf_acceptance_disconnect_pass | RDK X5 IMX219 正式 live-source。板端已完成 HBN/srcampy 探测、no-preview 性能主线、`30 分钟` 与 `2 小时` 稳定性补证，以及真实 `input_disconnect`：`20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` 提供 `30.08 FPS / 0 drop / 0 gap`，`20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained` 提供 `1798s / 30.3921 FPS / 0 gap / 0 drop / trace pass`，`20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained` 提供 `7198s / 30.3865 FPS / 0 gap / 0 drop / trace pass / schema revalidation pass`，`20260630_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault` 则明确记录 `FAULT_INJECTED_DISCONNECT`、`INPUT_DISCONNECTED` 和 `pipeline_exit=11`；当前正式朝向口径为 `INPUT_ORIENTATION_CORRECTION=rotate180` |
| `imx219_csi_argus_001` | mipi_camera_argus | `jetson_argus_default` | null | nvargus NV12/BGR | 1280 | 720 | 30.0 | live stream | null | probe_failed_current_board | Jetson CSI IMX219 的 Argus/ISP 优化支路；目标是通过 `nvarguscamerasrc -> nvvidconv -> videoconvert -> appsink` 把 raw Bayer normalize/debayer 从 CPU 热路径移出。但 `20260621_jetson_8gb_yolo11n_tensorrt_imx219_argus_smoke`、`..._runtime600` 以及 `20260622_jetson_8gb_yolo11n_tensorrt_imx219_argus_simple_ab` 都在板端失败；其中 `simple_ab` 已经去掉默认 capture caps，仍以 `app_exit=11` 收口。当前应把该 source 视为板端诊断入口，而不是正式主线候选，也不能作为 FPS 对比证据 |
| `rtsp_stream_001` | rtsp |  | null |  |  |  |  | null | null | candidate_requires_board_uri | 共享 RTSP live-source 候选。RDK X5 当前可用它执行 `input_disconnect`，但正式 run 必须在 `run.md` 里记录已脱敏 URI、编码、分辨率、fps 和断流证据，不能只写“RTSP 可用” |
| `astra_s_openni_001` | openni_camera | `2bc5/0402`（OpenNI selector） | null | OpenNI RGB888 | 640 | 480 | 30.0 | live stream | null | board_verified_smoke_disconnect_service_pass | RK3588 Astra S 正式 live source；`20260621` 板端 probe 已确认 `color/depth/ir` 三路可读，其中 color 默认 `640x480 RGB888@30`。非 root 运行依赖 `/etc/udev/rules.d/99-orbbec-astra.rules` 将 USB 设备 `2bc5:0402` 赋给 `plugdev`；`20260622` 已完成 non-root smoke、`input_disconnect` 和 camera service 生命周期复测 |
| `usb_camera_001` | usb_camera | `/dev/video0`（默认候选） | null | 由板端探测确定 | 由板端探测确定 | 由板端探测确定 | 由板端探测确定 | live stream | null | candidate_requires_board_probe | 共享 USB/UVC live-source 候选（RK3588 / RDK X5）。正式运行前必须用 `v4l2-ctl --list-devices` 和 `--list-formats-ext` 确认实际节点与格式，不能仅凭默认节点认定可用 |

## RK3588 双 source 口径

RK3588 当前文档和执行都必须同时保留两类 source，不能只写其中一个：

| source role | input_source_id | purpose | current status |
|---|---|---|---|
| 视频集持续回放 source | `video_set_runtime_v1` / `video_set_stability_v1` | 可复现 runtime、30 分钟/2 小时稳定性、视频集 systemd 生命周期 | ready |
| 真实摄像头 source | `astra_s_openni_001` | 真实 live capture、Astra S smoke、`input_disconnect`、camera systemd | pass |

当前摄像头 source 信息固定写法如下：

- `input_source_id=astra_s_openni_001`
- `input_source_type=openni_camera`
- `INPUT_PATH=2bc5/0402`
- device family: `Orbbec Astra S`
- runtime path: `OpenNI2 + liborbbec.so`
- default validated color mode: `640x480 RGB888 @ 30 FPS`
- permission prerequisite: `/etc/udev/rules.d/99-orbbec-astra.rules` 把 USB `2bc5:0402` 赋给 `plugdev`

## 固定输入对齐资产

| input_source_id | alignment_manifest | selected_frames | required raw field | alignment scope | limitation | status |
|---|---|---:|---|---|---|---|
| `video_short_001` | `data/validation/video_fixed_v1_alignment/alignment_frames_manifest.json` | 80 | `detections[]` with `class_id`、`confidence`、`bbox_xywh` | historical fixed-input diagnostic | 无人工标注，不能计算正式质量指标，也不能替代 BDD100K 任务级质量评估 | deprecated_historical_only |

## 带标注视频质量资产

| dataset_id | source_dataset | source_url | prepared_videos | labels | budget | metric_script | report_output | status |
|---|---|---|---|---|---:|---|---|---|
| `bdd100k_mot_mini_v1` | Kaggle BDD100K tracking subset | `http://kaggle.com/datasets/robikscube/driving-video-with-object-tracking?resource=download` | `data/videos/bdd100k_mot_mini_v1/*.mov` | `data/validation/bdd100k_mot_mini_v1/labels/*.jsonl` | 1.499 GB / 5 GB | `projects/03_video_pipeline/scripts/quality/evaluate_bdd100k_mot_detection.py` | `benchmark/processed/03_video_pipeline/<run_id>_bdd100k_mot_quality.md` | ready |

## 要求

- 固定视频必须记录 SHA256；实时源不能计算 SHA256 时写 `null`，但必须记录设备、URL、分辨率、FPS 和可用时间窗口。
- 当前 Jetson 正式 live-source 已切换为 `imx219_csi_001`，不是继续沿用 `usb_camera_001` / `rtsp_stream_001` 的占位口径。
- 当前 RDK X5 正式 live-source 已切换为 `imx219_rdkx5_hbn_001`，技术口径是 `mipi_camera_hbn + HBN/srcampy`，不是 `/dev/video0`。
- 当前这路 IMX219 的正式朝向口径为 `rotate180`；若后续换了不同物理安装方向的传感器，再显式覆盖 `INPUT_ORIENTATION_CORRECTION`，不要把朝向问题误记为颜色或 ISP 问题。
- RK3588 当前正式 source 口径是“视频集持续回放 source + Astra S 实时摄像头 source”同时保留。`video_set_stability_v1` 用于可复现 benchmark 和 playlist systemd；`astra_s_openni_001` 用于真实摄像头采集、`input_disconnect` 和 camera systemd。
- `usb_camera_001` 现在只保留为通用 UVC 候选占位，不再作为 RK3588 当前正式摄像头口径。
- 同一份 raw result 必须能反向追溯到本表和 stream config。
- 输入源变化后必须更新 `stream_config_sha256` 并重新生成 run。
