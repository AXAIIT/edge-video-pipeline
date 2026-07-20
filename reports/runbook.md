# 项目三执行 Runbook

## 执行顺序

项目三按阶段推进，但开发板之间互不作为前置条件。当前 Jetson TensorRT 参考主线使用项目二 INT8 PTQ engine；RK3588 和 RDK X5 可按各自 spec 独立推进。

1. Jetson 阶段 0：继承项目二环境基线 `20260609_jetson_8gb_env_baseline`，该基线已继承项目一 Jetson TensorRT/CUDA/OpenCV/tegrastats 信息。
2. Jetson 阶段 0：做项目三增量确认：engine hash、C++ 构建、固定视频可打开、`tegrastats` 可记录、raw schema 和 trace check 可生成。
3. Jetson 阶段 0：固定输入源：更新 `projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml` 和 `projects/03_video_pipeline/reports/input_sources.md`。
4. Jetson 阶段 1：执行 03A 单线程 demo，验证 frame-level raw result 和输出合法性。
5. Jetson 阶段 2：执行 03B 多线程 pipeline，生成 trace check。
6. Jetson 阶段 3：执行 03C 队列限流与 buffer 复用实验。
7. Jetson 阶段 4：执行 03D TensorRT C++ pipeline，并证明 TensorRT/GPU 实际参与推理。
8. Jetson 阶段 7：执行 03G 异常恢复与 systemd 服务化测试。
9. Jetson 阶段 8：执行 03H 稳定性测试，先 10 分钟 smoke，再 30 分钟 short sustained，最后 2 小时 acceptance。
10. Jetson 阶段 9：执行 03I 的 Jetson 单板汇总，更新 runtime、stability、failure 和 excluded runs。
11. RK3588 可在硬件、模型和配置就绪后按 `03E` 独立执行。
12. RDK X5 可在硬件、模型和配置就绪后按 `03F` 独立执行。

## Jetson 快速入口

在 Jetson 上进入仓库根目录：

```bash
cd &lt;BOARD_USER_HOME&gt;/edge-inference-deploy-lab
```

确认项目二 INT8 engine 存在并记录 hash：

```bash
sha256sum models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine
```

使用继承环境基线：

```bash
export ENVIRONMENT_BASELINE_ID=20260609_jetson_8gb_env_baseline
```

构建 C++ TensorRT pipeline：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_build \
  bash projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh
```

## Jetson 当前口径（2026-06-23）

当前 Jetson 的 video-file 主线、03A/03B/03C、03G 与 03H 证据仍成立；IMX219 live-source 的图像有效性复核也已经在 `2026-06-23` 关闭：

- `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` 保留为 sustained `runtime600` 吞吐证据：`47.67 FPS`、零 gap、零 drop
- `20260623_jetson_8gb_yolo11n_tensorrt_imx219_preview_rotate180_rg_bayerfix` 保留为视觉有效性证据：`rotate180 + RG + percentile + no_white_balance`，`runtime_pass_all_postchecks_pass`，`4390` 帧 / `120s`，且用户现场确认方向与颜色正常
- `BDD100K` 任务级质量仍为 `quality_threshold_fail`，继续按 `closed_nonblocking_task_fail` 单独归档

下文 Jetson 命令现在主要用于“追溯证据 / 后续优化”，而不是继续补 Jetson 主线 blocker。

## 新功能验证顺序

这轮新增功能不是一个点，而是三条新执行路径加一条长时编排路径：

1. `single_thread` 真正执行
2. `buffer_reuse=false` 真正执行
3. `IMX219 mipi_camera` 真正执行
4. `8h mixed` 编排脚本真正执行

验证时不要直接从 600 秒或 8 小时开始。推荐顺序如下：

### Step 0：同步代码并重建

目的：确认 Jetson 上运行的是新二进制，不是旧 build。

```bash
cd &lt;BOARD_USER_HOME&gt;/edge-inference-deploy-lab
export ENVIRONMENT_BASELINE_ID=20260609_jetson_8gb_env_baseline
rm -rf build/03_video_pipeline_jetson
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_build \
  bash projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh
```

通过标准：

- build 成功
- 新二进制路径为 `build/03_video_pipeline_jetson/video_pipeline_app`

### Step 1：先验 `single_thread` 新路径

目的：先验证最小新增路径，避免多线程因素干扰。

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_single_thread_smoke \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_single_thread.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=120 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

通过标准：

- `final_exit=0`
- raw/schema/trace/summary 都生成
- raw 中 `pipeline_mode=single_thread`

Step 1 通过后，再补正式 600 秒：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_single_thread_demo \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_single_thread.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

### Step 2：再验 `multithread` 主线未被新改动破坏

目的：确认补洞没有把现有主线打坏。

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_multithread_smoke \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=120 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

通过标准：

- `final_exit=0`
- raw 中 `pipeline_mode=backend_pipeline`
- 队列字段和 frame trace 正常

通过后再补正式 600 秒：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

### Step 3：验证 `buffer_reuse=false` 新路径

目的：确认 no-reuse 不是“配置改了但代码没生效”。

先做 120 秒 smoke：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_bufferreuse_on_smoke \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=120 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_bufferreuse_off_smoke \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline_noreuse.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=120 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

通过标准：

- 两轮都 `final_exit=0`
- raw 中分别记录 `buffer_reuse=true` 和 `buffer_reuse=false`

通过后再补正式 600 秒 A/B。

### Step 4：验证 IMX219 新采集路径

目的：先确认 `mipi_camera + V4L2 raw` 能稳定出帧，再上 formal run。

先做 120 秒 smoke：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_smoke \
INPUT_SOURCE_ID=imx219_csi_001 \
INPUT_SOURCE_TYPE=mipi_camera \
INPUT_PATH=/dev/video0 \
DURATION_SEC=120 \
SAVE_OUTPUT_VIDEO=0 \
PREVIEW_WINDOW=auto \
V4L2_RAW=1 \
V4L2_WIDTH=1920 \
V4L2_HEIGHT=1080 \
V4L2_SENSOR_MODE=2 \
V4L2_FPS=30 \
BAYER_PATTERN=RG \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

通过标准：

- `final_exit=0`
- raw 中 `input_source_type=mipi_camera`
- `input_width/input_height/input_fps` 合理
- runtime log 中没有 `INPUT_OPEN_FAILED`
- 如果板端存在图形环境，窗口应实时显示检测框、类别名、`FPS` 和 `DET`；若未显示，先查 runtime log 中的 `PREVIEW_WINDOW_STATUS`

通过后再补正式 600 秒：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_imx219_runtime600 \
INPUT_SOURCE_ID=imx219_csi_001 \
INPUT_SOURCE_TYPE=mipi_camera \
INPUT_PATH=/dev/video0 \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
V4L2_RAW=1 \
V4L2_WIDTH=1920 \
V4L2_HEIGHT=1080 \
V4L2_SENSOR_MODE=2 \
V4L2_FPS=30 \
BAYER_PATTERN=RG \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

### Step 5：IMX219 `input_disconnect`

目的：验证 03G 剩余缺口。

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_auto \
SAVE_OUTPUT_VIDEO=0 \
PREVIEW_WINDOW=off \
DISCONNECT_WARMUP_SEC=30 \
DISCONNECT_POST_RECOVERY_SEC=60 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_imx219_disconnect.sh
```

自动化说明：

- 默认 `DISCONNECT_METHOD=app_fault`。脚本会先正常跑 IMX219 live-source，等待 `DISCONNECT_WARMUP_SEC` 后，由应用内安全注入一次 `FAULT_INJECTED_DISCONNECT`，然后继续观察 `DISCONNECT_POST_RECOVERY_SEC` 秒。
- 这个默认模式不再依赖 `sysfs unbind`，因此不会要求第二个终端，也不会要求 sudo。
- 如果你是为了排查 Jetson 摄像头驱动/内核行为，而不是为了拿 03G 主线证据，才显式改成 `DISCONNECT_METHOD=driver_unbind`。

手工兜底：

- 不建议热插拔 CSI 排线。只有在明确排查驱动层问题时，才回退到第二个终端临时解绑 IMX219 驱动，再重新绑定恢复：

```bash
# 终端 B：先确认驱动节点存在
ls /sys/bus/i2c/drivers/imx219

# 终端 B：在终端 A 的 disconnect run 启动 30~60 秒后执行
echo 10-0010 | sudo tee /sys/bus/i2c/drivers/imx219/unbind

# 保持 5~10 秒，等待终端 A 侧出现 INPUT_DISCONNECTED 或 clear failure

# 需要恢复摄像头时再执行
echo 10-0010 | sudo tee /sys/bus/i2c/drivers/imx219/bind
```

- 如果 `/sys/bus/i2c/drivers/imx219/` 不存在，不要临时改成别的 sysfs 路径硬试，先停下来同步现场信息。
- 记录 `runtime_log` 中是否出现 `INPUT_DISCONNECTED`，以及 app 是“清晰失败退出”还是“恢复后继续运行”。
- 自动化脚本会额外写 `logs/failures/03_video_pipeline/jetson_8gb/<run_id>_imx219_disconnect_automation.log`，并把 automation 结果追加到 `runs/<run_id>/run.md`。
- `2026-06-19` 现场已观察到：在 active capture 期间直接 `driver_unbind` 可能导致 SSH 会话异常断开，疑似触发 Jetson 摄像头驱动/内核级不稳定，因此它不再作为默认闭环方法。

### Step 6：最后才跑 8 小时 mixed

前面 1-5 都通过后，再执行：

```bash
RUN_GROUP_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_8h_video4h_imx2194h \
SAVE_OUTPUT_VIDEO=0 \
PREVIEW_WINDOW_VIDEO=off \
PREVIEW_WINDOW_CAMERA=off \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_8h_mixed.sh
```

原则：

- 任一步 smoke 不通过，就不要直接升级到对应 600 秒 formal run。
- 600 秒 formal run 不通过，就不要进入 8 小时 mixed。

运行 10 分钟 Jetson TensorRT pipeline：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_cpp_pipeline \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

该脚本现在会先执行前后处理一致性检查；若 `projects/03_video_pipeline/src/video_pipeline_app.cpp` 与项目一/二基线不一致，run 会在真正启动推理前直接失败。

下面这组顺序是 Jetson 收口前的历史推荐执行顺序，现保留为复现实验参考：

```text
BDD100K runtime playlist smoke
-> 03A single_thread 正式 run
-> 03B multithread 正式 run
-> 03C buffer_reuse true/false A/B
-> IMX219 10 分钟正式 live-source run
-> IMX219 input_disconnect / service 补证
-> 30 分钟 / 2 小时 sustained
-> 8 小时 mixed: 视频 4h + IMX219 4h
```

这样做的原因是：BDD100K runtime playlist 可复现且覆盖多个道路场景，适合定位 TensorRT wrapper、前后处理、单线程/多线程行为和 buffer 复用问题；这些基础项闭环后再切到 IMX219 live-source，可将摄像头问题和 pipeline 问题分开验证。

## Jetson 关键复现实验命令

### 03A 单线程正式 run

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_single_thread_demo \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_single_thread.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

### 03B 多线程正式 run

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_multithread_pipeline \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

### 03C buffer reuse A/B

`buffer_reuse=true`：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_bufferreuse_on \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

`buffer_reuse=false`：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_int8_bufferreuse_off \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline_noreuse.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

如需一条命令顺序跑完并自动生成比较表，可直接执行：

```bash
DATE=$(date +%Y%m%d) \
DURATION_SEC=600 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_bufferreuse_ab.sh
```

该脚本会额外生成：

- `benchmark/processed/03_video_pipeline/<date>_jetson_8gb_yolo11n_tensorrt_bufferreuse_ab600.csv`
- `benchmark/processed/03_video_pipeline/<date>_jetson_8gb_yolo11n_tensorrt_bufferreuse_ab600.md`

### 03D IMX219 正式 live-source run

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5 \
INPUT_SOURCE_ID=imx219_csi_001 \
INPUT_SOURCE_TYPE=mipi_camera \
INPUT_PATH=/dev/video0 \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
PREVIEW_WINDOW=auto \
V4L2_RAW=1 \
V4L2_WIDTH=1280 \
V4L2_HEIGHT=720 \
V4L2_SENSOR_MODE=5 \
V4L2_FPS=60 \
BAYER_PATTERN=RG \
V4L2_NORMALIZE_MODE=fixed_10bit \
V4L2_DISABLE_WHITE_BALANCE=1 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

说明：

- `PREVIEW_WINDOW=auto` 是当前 Jetson 摄像头实时预览的正式入口。
- 当输入源属于 `mipi_camera` / `mipi_camera_hbn` / `mipi_camera_argus` / `usb_camera` / `openni_camera` / `rtsp`，且板端存在 `DISPLAY` / `WAYLAND_DISPLAY` / `XDG_SESSION_TYPE=x11|wayland` 时，窗口会自动显示检测框、英文类别名、`FPS` 和 `DET`。
- 如果板端是 headless、SSH 纯终端或 systemd 环境，`auto` 会自动降级为不显示，不需要额外改命令。
- 因此凡是要人工看画面、判断颜色/曝光/朝向的步骤，必须直接在 Jetson 本地桌面会话里执行；通过 SSH 启动不算预览验证。
- 如果这轮 run 的目标是做严格 benchmark 对比，而不希望 GUI 影响资源占用，可显式改成 `PREVIEW_WINDOW=off`。
- `fixed_10bit` 当前必须按“IMX219 `RG10` 16-bit word 保留高 8 bit”的口径理解；如果仍按“低 10 bit 直接线性缩放”理解，预览会退化成白屏。
- `BAYER_PATTERN=RG` 在本项目配置里表示常规传感器 `RGGB` 排列；OpenCV 历史两字母 `COLOR_Bayer*` 枚举不是这个常规命名，代码内部会把 `RGGB` 映射到正确的 BGR 输出转换码。
- 如果这块 IMX219 的物理安装方向是倒置的，可直接追加 `INPUT_ORIENTATION_CORRECTION=rotate180`；这属于朝向问题，不应和 Bayer pattern、曝光、白平衡混为一谈。
- 当前 raw 路径的 `v4l2-ctl -d /dev/video0 --list-ctrls -L` 证据显示，板端主要可控项是 `gain`、`exposure` 与 `override_enable`；但当前项目已不再暴露手动曝光命令入口，只在启动时强制把 `override_enable` 复位到 `0`，避免上一轮实验污染下一轮默认 run。

板端本地预览最小复核：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_preview_rotate180_rg_local \
INPUT_SOURCE_ID=imx219_csi_001 \
INPUT_SOURCE_TYPE=mipi_camera \
INPUT_PATH=/dev/video0 \
DURATION_SEC=120 \
SAVE_OUTPUT_VIDEO=0 \
PREVIEW_WINDOW=on \
INPUT_ORIENTATION_CORRECTION=rotate180 \
V4L2_RAW=1 \
V4L2_WIDTH=1280 \
V4L2_HEIGHT=720 \
V4L2_SENSOR_MODE=5 \
V4L2_FPS=60 \
BAYER_PATTERN=RG \
V4L2_NORMALIZE_MODE=percentile \
V4L2_DISABLE_WHITE_BALANCE=1 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

当前口径补充：

- `2026-06-23` 的 `counterclockwise + GB` 与 `clockwise + GR` 两组现场结果已被证伪：蓝色椅子变绿、画面接近黑白，不能作为正式修复方向。
- 同日确认 raw 摄像头路径此前没有调用方向修正初始化，导致 `INPUT_ORIENTATION_CORRECTION` 参数虽写入 run 记录，但实际预览画面不旋转。修复后 runtime log 必须出现 `INPUT_ORIENTATION_CORRECTION: source=/dev/video0 mode=rotate180 normalized=1280x720`。
- 当前复核口径收敛为 `INPUT_ORIENTATION_CORRECTION=rotate180 + BAYER_PATTERN=RG + V4L2_NORMALIZE_MODE=percentile + V4L2_DISABLE_WHITE_BALANCE=1`。
- 如果蓝色物体显示为橙色，应优先检查 Bayer 到 BGR 的转换映射，不应通过修改 YOLO 的 RGB 输入口径来修预览颜色。
- `20260623_jetson_8gb_yolo11n_tensorrt_imx219_preview_rotate180_rg_bayerfix` 已完成这条口径的板端闭环：runtime log 中 `INPUT_ORIENTATION_CORRECTION`、`PREVIEW_WINDOW_STATUS`、`grayworld_white_balance=false` 均符合预期，summary 为 `4390` 帧 / `120s` / `36.58 FPS` / `drop_frame_rate_total_estimated=0.0`。
- `manual exposure` 试验已经判定为低收益错误方向，当前项目已移除对应命令入口，不再继续推进。

执行后优先检查：

```bash
grep -E 'PREVIEW_WINDOW_STATUS|INPUT_ORIENTATION_CORRECTION|V4L2_EFFECTIVE_CONFIG|V4L2_CAPTURE_PROFILE' \
  logs/runtime/03_video_pipeline/jetson_8gb/${RUN_ID}.log
```

### 03D IMX219 Argus/ISP 诊断入口（当前不作为正式主线）

用途：当 `imx219_csi_001` 的 raw 路径已经稳定但仍低于 `30 FPS` 时，可临时切到 Jetson ISP/Argus 支路做板端诊断，对比 “同一块 IMX219，是否仅靠采集链路切换就能接近实时”。

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_argus_runtime600 \
INPUT_SOURCE_ID=imx219_csi_argus_001 \
INPUT_SOURCE_TYPE=mipi_camera_argus \
INPUT_PATH=jetson_argus_default \
ARGUS_SENSOR_ID=0 \
ARGUS_WIDTH=1280 \
ARGUS_HEIGHT=720 \
ARGUS_FPS=30 \
ARGUS_FLIP_METHOD=0 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

当前口径：

- `20260621_jetson_8gb_yolo11n_tensorrt_imx219_argus_smoke`
- `20260621_jetson_8gb_yolo11n_tensorrt_imx219_argus_runtime600`
- `20260622_jetson_8gb_yolo11n_tensorrt_imx219_argus_simple_ab`

这三轮都未能建立有效帧，其中 `simple_ab` 已去掉默认 capture caps 仍以 `app_exit=11` 失败。因此当前项目的 IMX219 正式主线仍应使用 `mipi_camera` / `V4L2 raw`，Argus 只保留为板端环境或 BSP 排障入口；对当前板端应明确记为“Argus 修复失败，放弃主线化”。

要求：

- `input_source_type` 必须写成 `mipi_camera_argus`，不能继续沿用 `mipi_camera`，否则脚本会默认走 raw V4L2 路径。
- `INPUT_PATH=jetson_argus_default` 会由脚本展开成内置 `nvarguscamerasrc -> nvvidconv -> videoconvert -> appsink` pipeline。
- 这轮的目标不是替代已经闭环的 raw 证据，而是验证 IMX219 的 FPS 瓶颈是否主要来自 CPU raw Bayer 处理。
- 在板端 camera stack 未变化前，不应再把这组命令当作正式主线或必须复测项。

当前正式下一步已经不再是继续试 Argus。`V4L2 raw 720p60 mode5` 的持续验证命令如下，且该命令已在 `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5` 跑通：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_720p60_runtime600_mode5 \
INPUT_SOURCE_ID=imx219_csi_001 \
INPUT_SOURCE_TYPE=mipi_camera \
INPUT_PATH=/dev/video0 \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
V4L2_RAW=1 \
V4L2_WIDTH=1280 \
V4L2_HEIGHT=720 \
V4L2_SENSOR_MODE=5 \
V4L2_FPS=60 \
BAYER_PATTERN=RG \
V4L2_NORMALIZE_MODE=fixed_10bit \
V4L2_DISABLE_WHITE_BALANCE=1 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

板端已完成的短探针口径：

- `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_probe_mode4`
- `20260622_jetson_8gb_yolo11n_tensorrt_imx219_720p60_probe_mode5`

其中 `mode5` 当前更优，且 `runtime600` 已通过：

- `V4L2_EFFECTIVE_CONFIG: actual=1280x720@60.000`
- 30 秒短探针：`fps_estimated=49.0689`
- 600 秒正式 run：`fps_estimated=47.6711`
- `capture_p50_ms=20.8059`
- `inference_p50_ms=12.1605`
- `drop_frame_rate_total_estimated=0.0`
- `frame_id_gaps=0`

如需回看历史 `1920x1080@30` 阶段为何曾只有 `IMX219 ≈ 14.6 FPS`，可用下面两条命令做短时 profiling / A-B：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_profile_baseline \
INPUT_SOURCE_ID=imx219_csi_001 \
INPUT_SOURCE_TYPE=mipi_camera \
INPUT_PATH=/dev/video0 \
DURATION_SEC=120 \
SAVE_OUTPUT_VIDEO=0 \
V4L2_RAW=1 \
V4L2_WIDTH=1920 \
V4L2_HEIGHT=1080 \
V4L2_SENSOR_MODE=2 \
V4L2_FPS=30 \
BAYER_PATTERN=RG \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_profile_nowb \
INPUT_SOURCE_ID=imx219_csi_001 \
INPUT_SOURCE_TYPE=mipi_camera \
INPUT_PATH=/dev/video0 \
DURATION_SEC=120 \
SAVE_OUTPUT_VIDEO=0 \
V4L2_RAW=1 \
V4L2_WIDTH=1920 \
V4L2_HEIGHT=1080 \
V4L2_SENSOR_MODE=2 \
V4L2_FPS=30 \
BAYER_PATTERN=RG \
V4L2_DISABLE_WHITE_BALANCE=1 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

两轮都要检查 runtime log 是否出现：

- `V4L2_EFFECTIVE_CONFIG`
- `V4L2_CAPTURE_PROFILE`
- `INPUT_PACING ... source_fps_basis=...`

解释口径：

- `V4L2_EFFECTIVE_CONFIG` 用来区分“请求配置”与“设备实际生效配置”。
- `V4L2_CAPTURE_PROFILE` 用来拆分 capture 阶段的 `wait_and_dequeue / normalize / debayer / white_balance`。
- 当前正式主线默认关闭 gray-world white balance；`V4L2_DISABLE_WHITE_BALANCE=1` 既用于降低 CPU 开销，也用于避免白平衡在颜色有效性复核中引入额外变量。

如果 profiling 结果显示 `avg_normalize_ms` 仍然占大头，再继续跑一条 `fixed_10bit` 快路径复测：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_profile_fixed10_nowb \
INPUT_SOURCE_ID=imx219_csi_001 \
INPUT_SOURCE_TYPE=mipi_camera \
INPUT_PATH=/dev/video0 \
DURATION_SEC=120 \
SAVE_OUTPUT_VIDEO=0 \
V4L2_RAW=1 \
V4L2_WIDTH=1920 \
V4L2_HEIGHT=1080 \
V4L2_SENSOR_MODE=2 \
V4L2_FPS=30 \
BAYER_PATTERN=RG \
V4L2_NORMALIZE_MODE=fixed_10bit \
V4L2_DISABLE_WHITE_BALANCE=1 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

这一轮重点看：

- `V4L2_EFFECTIVE_CONFIG ... normalize_mode=fixed_10bit`
- `V4L2_CAPTURE_PROFILE.avg_normalize_ms`
- `fps_estimated`

### 03G IMX219 `input_disconnect` 自动化补证

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_auto \
SAVE_OUTPUT_VIDEO=0 \
DISCONNECT_WARMUP_SEC=30 \
DISCONNECT_POST_RECOVERY_SEC=60 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_imx219_disconnect.sh
```

说明：

- 默认 `DISCONNECT_METHOD=app_fault`，由应用在真实 IMX219 live-source 运行中安全注入一次 `FAULT_INJECTED_DISCONNECT`，用于验证 `INPUT_DISCONNECTED -> exit 11` 的应用层闭环。
- 只有当你明确要调查驱动/内核层对 `driver_unbind` 的反应时，才改成 `DISCONNECT_METHOD=driver_unbind`。
- 只有自动化脚本不可用时，才回退到下面这组手工动作：

```bash
# 终端 B：先确认驱动节点
ls /sys/bus/i2c/drivers/imx219

# 终端 A 的 disconnect run 启动 30~60 秒后执行
echo 10-0010 | sudo tee /sys/bus/i2c/drivers/imx219/unbind

# 等待 5~10 秒

# 需要恢复摄像头时执行
echo 10-0010 | sudo tee /sys/bus/i2c/drivers/imx219/bind
```

- 验收不是“命令名叫 disconnect 就算通过”，而是 `runtime_log` 必须出现 `INPUT_DISCONNECTED` 或等价清晰错误。
- 当前代码口径里，“清晰失败并退出”也算合格证据，不强行伪造自动重连；因此这轮 run 出现非 0 退出码并不一定代表实验无效。

### 03H / 最终 8 小时 mixed

```bash
RUN_GROUP_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_8h_video4h_imx2194h \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_8h_mixed.sh
```

说明：

- 当前 Jetson 正式 live-source 已切换为 `IMX219`，不再继续把 `usb_camera_001` / `rtsp_stream_001` 当默认闭环入口。
- `projects/03_video_pipeline/src/video_pipeline_app.cpp` 现已补入 `V4L2 RG10 raw -> percentile normalize -> RGGB debayer -> gray-world white balance` 链路。
- 这套 IMX219 链路是 **当前项目三内部自带实现**，不是运行时去调用旧仓库脚本，也不是把旧仓库目录挂进来混用。
- 这批命令对应的关键重跑在当前对话里已经完成，Jetson 现已按“video-file 主线 + IMX219 live-source + 稳定性/异常恢复”完成工程收口；这里保留它们仅用于复现实验和追溯证据。

运行脚本结束后会自动生成：

| artifact | path |
|---|---|
| raw result | `benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl` |
| pre/post consistency | `benchmark/processed/03_video_pipeline/<run_id>_prepost_consistency.md` |
| schema check | `benchmark/processed/03_video_pipeline/<run_id>_schema_check.md` |
| trace check | `benchmark/processed/03_video_pipeline/<run_id>_trace_check.md` |
| runtime summary | `benchmark/processed/03_video_pipeline/<run_id>_summary.csv` |
| runtime log | `logs/runtime/03_video_pipeline/jetson_8gb/<run_id>.log` |
| monitor log | `logs/monitor/03_video_pipeline/jetson_8gb/<run_id>_tegrastats.log` |

运行 Jetson 稳定性测试：

```bash
TIER=smoke bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh
TIER=short_sustained bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh
TIER=acceptance_sustained bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_stability.sh
```

说明：

- `run_jetson_tensorrt_stability.sh` 当前默认导出 `PREVIEW_WINDOW=off`。
- 如果只是想人工观察一次摄像头实时检测画面，请不要直接拿稳定性脚本做现场预览，优先使用上面的 `imx219_smoke + PREVIEW_WINDOW=auto`。

systemd 模板位置：

```text
projects/03_video_pipeline/scripts/service/systemd/edge-video-pipeline-jetson.service
```

安装时必须按实际仓库路径修改 `WorkingDirectory`，然后记录：

```bash
sudo cp projects/03_video_pipeline/scripts/service/systemd/edge-video-pipeline-jetson.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start edge-video-pipeline-jetson
sudo systemctl status edge-video-pipeline-jetson
journalctl -u edge-video-pipeline-jetson --since "10 min ago"
sudo systemctl restart edge-video-pipeline-jetson
sudo systemctl stop edge-video-pipeline-jetson
```

如果希望用仓库标准入口一次性落盘 systemd 证据，优先使用：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_systemd_service_test \
  bash projects/03_video_pipeline/scripts/service/test_jetson_systemd_service.sh
```

该脚本会输出：

```text
logs/runtime/03_video_pipeline/jetson_8gb/<run_id>_systemd_status.log
logs/runtime/03_video_pipeline/jetson_8gb/<run_id>_journal.log
```

03G 的 Jetson CLI 异常注入快速入口：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_pipeline_failure_service_test \
python3 projects/03_video_pipeline/scripts/inject_failure_tests.py \
  --pipeline build/03_video_pipeline_jetson/video_pipeline_app \
  --pipeline-config projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml \
  --model-config projects/03_video_pipeline/configs/models/yolo11n.yaml \
  --backend-config projects/03_video_pipeline/configs/boards/jetson_8gb.yaml \
  --stream-config projects/03_video_pipeline/configs/streams/video_fixed_v1.yaml \
  --cases input_open_failed model_missing invalid_shape output_unwritable queue_overflow \
  --output logs/failures/03_video_pipeline/jetson_8gb/${RUN_ID}_failure_injection.jsonl
```

说明：

- 这条命令覆盖的是当前已自动化的 CLI 子集。
- `input_disconnect` 现已改为真实板端自动化 wrapper，默认命令见上面的 `run_jetson_tensorrt_imx219_disconnect.sh`；`driver_unbind` 只保留为驱动/内核排障动作。
- `systemd_restart` 已有标准化板端证据：`20260618_jetson_8gb_systemd_service_test`。

## Jetson 证据边界

| 结论类型 | 可引用证据 | 不可替代项 |
|---|---|---|
| 模型质量 baseline | 项目一/二 Jetson TensorRT 报告 | 不能替代项目三 pipeline raw result |
| 项目三 runtime 性能 | `benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl` 和 processed summary | 不能引用项目一/二单模型 FPS |
| TensorRT 后端证据 | runtime log、TensorRT 初始化日志、`tegrastats` | 不能只看 engine 文件存在 |
| 稳定性 | 03H stability run、monitor log、failure log | 不能用 10 分钟 smoke 替代 2 小时目标 |
| 服务化 | systemd unit、journal、异常注入记录 | 不能只保留手动命令 |

## RK3588 快速入口

RK3588 直接继承项目二环境基线：

```bash
cd &lt;BOARD_USER_HOME&gt;/edge-inference-deploy-lab
export ENVIRONMENT_BASELINE_ID=20260611_rk3588_8gb_env_baseline
```

先复核项目二 INT8 RKNN artifact。当前工作区同名文件 hash 与项目二正式报告不一致，因此正式 03E benchmark 前必须执行：

```bash
sha256sum models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn
```

项目二正式记录的 SHA256 是：

```text
40bce507d584498825267287cbb44c8dd860c8ddc3413677767891aeb225b69c
```

构建 RKNN C++ pipeline：

```bash
RUN_ID=$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_build \
  bash projects/03_video_pipeline/scripts/build/build_rk3588_rknn.sh
```

如果构建报 `fatal error: rknn_api.h: 没有那个文件或目录`，先定位 RKNN C API 头文件和运行库：

```bash
find /usr /usr/local /opt /home -name rknn_api.h 2>/dev/null | head -n 20
find /usr /usr/local /opt /home -name 'librknnrt.so*' 2>/dev/null | head -n 20
```

若找到了头文件和库，清理旧 CMake cache 后显式传路径：

```bash
rm -rf build/03_video_pipeline_rk3588
RUN_ID=$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_build \
RKNN_INCLUDE_DIR=/path/to/include \
RKNNRT_LIBRARY=/path/to/librknnrt.so \
  bash projects/03_video_pipeline/scripts/build/build_rk3588_rknn.sh
```

若板端找不到 `rknn_api.h`，说明当前只具备 Python/Lite2 runtime 或系统运行库，不具备 C++ 开发头文件；需要从 RKNN Toolkit2 / rknn_model_zoo 对应版本同步 `librknn_api/include/rknn_api.h`。

运行 10 分钟 RK3588 RKNN pipeline：

```bash
RUN_ID=$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_cpp_pipeline \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=600 \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh
```

实时模式优化先执行相同输入下的单核/三核 120 秒 A/B。两轮之间只允许改变 `RKNN_CORE_MASK`：

推荐使用一键入口，它会顺序执行两轮并生成对比 CSV/Markdown：

```bash
DATE=20260618 DURATION_SEC=120 \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_core_ab.sh
```

```bash
RUN_ID=20260618_rk3588_8gb_yolo11n_rknn_core0_ab120 \
RKNN_CORE_MASK=core0 DURATION_SEC=120 \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh

RUN_ID=20260618_rk3588_8gb_yolo11n_rknn_core012_ab120 \
RKNN_CORE_MASK=0_1_2 DURATION_SEC=120 \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh
```

上述单 context A/B 已完成：`0_1_2` 相比 `core0` 的 FPS 仅提升 `0.1082%`，没有实质改善。三个独立 RKNN context 分别绑定 core0/core1/core2 的 120 秒 A/B 也已完成，达到 30.0417 FPS、零丢帧、零乱序。以下入口用于复现同一版二进制下的 1-worker/3-worker 比较：

运行前先确认板端源码和二进制均包含 multi-context 参数。源码没有匹配项表示尚未同步最新版；二进制没有匹配项表示必须删除 build 目录后重建：

```bash
grep -n -- '--inference-workers' projects/03_video_pipeline/src/video_pipeline_app.cpp
strings build/03_video_pipeline_rk3588/video_pipeline_app | grep -- '--inference-workers'
```

```bash
DATE=20260618 DURATION_SEC=120 \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_parallel_ab.sh
```

3-worker runtime log 必须同时出现 `worker=0 core_mask=core0`、`worker=1 core_mask=core1`、`worker=2 core_mask=core2`；raw 必须记录 `inference_workers=3` 和 `rknn_core_binding=core0,core1,core2`。当前 120 秒结果已满足 FPS 不低于 29、丢帧率不高于 3%、零乱序且无新增 timeout/reset，可以进入 600 秒 clean runtime。

600 秒 clean runtime 通过后，RK3588 正式视频质量使用 BDD100K MOT mini 标注数据。先用一段序列验证 no-drop、标签映射和报告链路：

```bash
RUN_PREFIX=20260619_rk3588_8gb_yolo11n_rknn_bdd100k_limit1 \
START_INDEX=0 LIMIT=1 EVALUATE_STRICT=0 \
PYTHON_BIN="$HOME/venvs/rk3588_rknn/bin/python" \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_bdd100k_mini.sh
```

在实时 A/B 前，可先对项目三选定的 `40bce507...` artifact 执行完整 COCO2017 质量复检：

```bash
RUN_ID=20260618_rk3588_8gb_yolo11n_rknn_40bce_coco2017_recheck \
  bash projects/03_video_pipeline/scripts/quality/run_rk3588_coco_recheck.sh
```

该命令固定使用完整 5000 张 val2017、`confidence=0.001`、`IoU=0.7`、`max_detections=300` 和官方 `pycocotools COCOeval`。通过条件为 artifact hash 一致、覆盖 5000 张且相对 FP32 baseline `0.3865` 的下降不超过 `0.03`。

如果需要先做诊断 run，但 hash 尚未对齐，可以显式设置：

```bash
ALLOW_HASH_MISMATCH=1 RUN_ID=$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_diagnostic \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh
```

该 run 只能写 `not_verified`，不能进入正式 benchmark 收益结论。

RK3588 USB 摄像头运行示例：

```bash
RUN_ID=$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_usb_camera \
INPUT_SOURCE_ID=usb_camera_001 \
INPUT_SOURCE_TYPE=usb_camera \
INPUT_PATH=0 \
DURATION_SEC=600 \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh
```

RK3588 RTSP 输入运行示例：

```bash
RUN_ID=$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_rtsp \
INPUT_SOURCE_ID=rtsp_stream_001 \
INPUT_SOURCE_TYPE=rtsp \
INPUT_PATH='rtsp://<user>:<password>@<host>:<port>/<path>' \
DURATION_SEC=600 \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_pipeline.sh
```

运行脚本结束后应生成：

| artifact | path |
|---|---|
| raw result | `benchmark/raw/03_video_pipeline/rk3588_8gb/<run_id>.jsonl` |
| pre/post consistency | `benchmark/processed/03_video_pipeline/<run_id>_prepost_consistency.md` |
| schema check | `benchmark/processed/03_video_pipeline/<run_id>_schema_check.md` |
| trace check | `benchmark/processed/03_video_pipeline/<run_id>_trace_check.md` |
| runtime summary | `benchmark/processed/03_video_pipeline/<run_id>_summary.csv` |
| runtime log | `logs/runtime/03_video_pipeline/rk3588_8gb/<run_id>.log` |
| monitor log | `logs/monitor/03_video_pipeline/rk3588_8gb/<run_id>_rknpu.log` |

运行 RK3588 稳定性测试：

```bash
TIER=smoke bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_stability.sh
TIER=short_sustained bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_stability.sh
TIER=acceptance_sustained bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_stability.sh
```

正式 8 小时 mixed 长稳使用单独编排入口：

```bash
RUN_GROUP_ID=$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_8h_astra4h_video4h \
INFERENCE_WORKERS=3 \
SAVE_OUTPUT_VIDEO=0 \
PREVIEW_WINDOW_CAMERA=auto \
PREVIEW_WINDOW_VIDEO=off \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_rknn_8h_mixed.sh
```

RK3588 证据边界：

| 结论类型 | 可引用证据 | 不可替代项 |
|---|---|---|
| 模型质量 baseline | 项目一/二 RK3588 RKNN 报告 | 不能替代项目三 C++ video pipeline raw result |
| 项目三 runtime 性能 | `benchmark/raw/03_video_pipeline/rk3588_8gb/<run_id>.jsonl` 和 processed summary | 不能引用项目二单模型 FPS |
| RKNN 后端证据 | runtime log、RKNN C API 初始化日志、RKNPU sysfs/dmesg monitor | 不能只看 `.rknn` 文件存在 |
| 稳定性 | 03H stability run、monitor log、failure log | 不能用项目二单模型稳定性替代 |
| CPU fallback | raw result、runtime log、monitor log | 不能默认假设没有 fallback |

### RK3588 03G CLI 异常注入

先执行五项自动化 CLI 用例：

```bash
cd &lt;BOARD_USER_HOME&gt;/edge-inference-deploy-lab
source "$HOME/venvs/rk3588_rknn/bin/activate"
export ENVIRONMENT_BASELINE_ID=20260611_rk3588_8gb_env_baseline

RUN_ID=$(date +%Y%m%d)_rk3588_8gb_pipeline_failure_test \
PYTHON_BIN="$HOME/venvs/rk3588_rknn/bin/python" \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_failure_injection.sh
```

必须得到五项 `status=pass`，并生成：

```text
logs/failures/03_video_pipeline/rk3588_8gb/<run_id>_failure_injection.jsonl
logs/failures/03_video_pipeline/rk3588_8gb/<run_id>_failure_injection_artifacts/*.log
benchmark/processed/03_video_pipeline/<run_id>_failure_summary.csv
projects/03_video_pipeline/runs/<run_id>/run.md
```

该脚本不执行真实 `input_disconnect`。断流必须绑定已登记 camera/RTSP live source，并记录 reconnect count、max recovery time、恢复后 frame_id 连续性或丢帧原因。

### RK3588 03G systemd 生命周期

CLI 子集通过后执行：

```bash
RUN_ID=$(date +%Y%m%d)_rk3588_8gb_systemd_service_test \
  bash projects/03_video_pipeline/scripts/service/test_rk3588_systemd_service.sh
```

验收值为 `start_status=active`、`restart_status=active`、`stop_status=inactive`。证据落到：

```text
logs/runtime/03_video_pipeline/rk3588_8gb/<run_id>_systemd_status.log
logs/runtime/03_video_pipeline/rk3588_8gb/<run_id>_journal.log
projects/03_video_pipeline/runs/<run_id>/run.md
```

## 每次 run 必填证据

| evidence | required path |
|---|---|
| run 记录 | `projects/03_video_pipeline/runs/<run_id>/run.md` |
| raw result | `benchmark/raw/03_video_pipeline/<target>/<run_id>.jsonl` |
| 前后处理一致性 | `benchmark/processed/03_video_pipeline/<run_id>_prepost_consistency.md` |
| runtime 日志 | `logs/runtime/03_video_pipeline/<target>/<run_id>.log` |
| monitor 日志 | `logs/monitor/03_video_pipeline/<target>/<run_id>.*` |
| failure 日志 | `logs/failures/03_video_pipeline/<target>/<run_id>.jsonl` |
| 输出样例 | `projects/03_video_pipeline/runs/<run_id>/outputs/` |

## Jetson Benchmark 填表顺序

| step | action | command / input | output | update table |
|---:|---|---|---|---|
| 1 | 引用继承环境基线 | `export ENVIRONMENT_BASELINE_ID=20260609_jetson_8gb_env_baseline` | run 记录中的 baseline id | `video_pipeline.md` 当前状态、`runtime_benchmark.md` Reproducibility |
| 2 | 构建 TensorRT C++ pipeline 并完成增量确认 | `RUN_ID=<run_id> bash projects/03_video_pipeline/scripts/build/build_jetson_tensorrt.sh` | build log、engine hash、C++/TensorRT 证据 | `runtime_benchmark.md` Reproducibility |
| 3 | 单线程短视频 smoke | `jetson_tensorrt_single_thread.yaml` | single-thread raw/log/output | `runtime_benchmark.md` Runtime Summary、Stage Latency、Quality Gate |
| 4 | 多线程 10 分钟 benchmark | `RUN_ID=<run_id> DURATION_SEC=600 bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh` | frame-level raw、`<run_id>_prepost_consistency.md`、runtime log、`tegrastats` | Runtime Summary、Stage Latency、Resource / Accelerator |
| 5 | 队列策略对比 | `drop_oldest`、`drop_newest`、`block_with_timeout` 配置 | queue raw、memory monitor | Queue / Buffer |
| 6 | schema 与 trace 校验 | `validate_pipeline_raw_schema.py`、`check_pipeline_trace.py` | schema check、trace check | Quality Gate、Reproducibility |
| 7 | 聚合 runtime 指标 | `aggregate_pipeline_benchmark.py` 或 03I 聚合脚本 | `<run_id>_summary.csv` | Runtime Summary、Stage Latency、Queue / Buffer |
| 8 | BDD100K MOT mini 质量评估 | `bdd100k_mot_mini_v1` + `evaluate_bdd100k_mot_detection.py` | per-class / overall AP50、precision、recall、F1 | `runtime_benchmark.md` Labeled Video Quality Evidence |
| 10 | 异常和 systemd 测试 | 03G failure/service cases | failure JSONL、journal log | `failure_and_fallback.md` Failure Cases、CPU Fallback、Service Recovery |
| 11 | 稳定性测试 | `TIER=smoke|short_sustained|acceptance_sustained bash ...` | stability raw、monitor log | `stability_report.md` Stability Summary、Resource Trace |
| 12 | 最终汇总 | 03I 汇总命令 | runtime/stability/failure summary、excluded runs | 所有 reports 的 MLPerf-style Summary |

当前默认行为说明：

- `run_jetson_tensorrt_pipeline.sh` 默认 `SAVE_OUTPUT_VIDEO=0`
- `run_jetson_tensorrt_stability.sh` 继承该默认值，因此 stability 也默认不保存输出视频
- 只有在明确需要保留可视化视频证据时，才手动追加 `SAVE_OUTPUT_VIDEO=1`

## 历史固定视频诊断流程（停止作为正式质量门）

历史上曾使用无人工标注固定视频诊断 baseline/current 实现漂移，并由此定位 RKNN padding 差异。该流程已停止且不提供可执行命令，只保留既有报告作为问题追溯证据。项目三的正式视频质量运行统一使用 `bdd100k_mot_mini_v1`。

## BDD100K MOT Mini 质量评估流程

`bdd100k_mot_mini_v1` 是项目三正式带标注视频质量数据集。它从 BDD100K MOT 中选取 40-80 段固定序列，制备后总量不超过 5 GB。质量评估只在 BDD100K MOT 标注帧上执行，不能对未标注帧计算 AP/recall。

类别映射：

| BDD category | YOLO/COCO class | 主评估 |
|---|---|---|
| pedestrian | person | yes |
| rider | person | yes，保留 source_category |
| bicycle | bicycle | yes |
| car | car | yes |
| motorcycle | motorcycle | yes |
| bus | bus | yes |
| train | train | yes |
| truck | truck | yes |
| other person / trailer / other vehicle | ignored | no |

Kaggle BDD100K tracking subset 原始候选池放在：

```bash
data/raw/bdd100k_mot_kaggle/archive/
```

制备 mini 数据集：

```bash
python3 projects/03_video_pipeline/scripts/quality/prepare_bdd100k_mot_mini.py \
  --csv-labels data/raw/bdd100k_mot_kaggle/archive/mot_labels.csv \
  --video-root data/raw/bdd100k_mot_kaggle/archive \
  --selected-sequences data/validation/bdd100k_mot_mini_v1/selected_sequences.txt \
  --copy-videos \
  --source-frame-stride 6 \
  --target-sequences 80 \
  --max-total-size-gb 5
```

制备完成后必须检查：

- `data/validation/bdd100k_mot_mini_v1/bdd100k_mot_mini_v1_manifest.json`
- `data/videos/bdd100k_mot_mini_v1/*.mov`
- `data/validation/bdd100k_mot_mini_v1/labels/*.jsonl`
- 总制备视频大小 `<= 5 GB`
- 每个视频和标签都有 SHA256

运行 Jetson pipeline。每个 BDD 序列单独生成一个 run：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_bdd100k_<sequence_id> \
INPUT_SOURCE_ID=bdd100k_mot_mini_v1_<sequence_id> \
INPUT_SOURCE_TYPE=video_file \
INPUT_PATH=data/videos/bdd100k_mot_mini_v1/<sequence_id>.mov \
DURATION_SEC=0 \
LOOP_VIDEO_FILE=0 \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_bdd100k_quality.yaml \
SAVE_OUTPUT_VIDEO=0 \
TRACE_FAIL_ON_GAPS=1 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_pipeline.sh
```

批量运行 BDD mini 并逐序列生成质量报告：

```bash
RUN_PREFIX=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_bdd100k_mini \
  bash projects/03_video_pipeline/scripts/run/run_jetson_bdd100k_mini.sh
```

BDD100K MOT mini 是带标注质量评估，不是实时丢帧策略 benchmark。该流程默认使用 `jetson_tensorrt_bdd100k_quality.yaml`，要求 `queue_policy=block`、`drop_frame_count_max=0`、`frame_id_gaps=0`。如果使用 `drop_oldest` 或任何会产生 frame gap 的配置，相关 AP/recall 只能记录为无效质量证据，不能写入 quality pass。

对已同步回本地的 BDD batch 做离线置信度扫描：

```bash
python3 projects/03_video_pipeline/scripts/quality/sweep_bdd100k_confidence.py \
  --batch-csv benchmark/processed/03_video_pipeline/<run_prefix>_batch.csv \
  --confidence-mins 0.05,0.10,0.15,0.20,0.25,0.30 \
  --output-csv benchmark/processed/03_video_pipeline/<run_prefix>_confidence_sweep_summary.csv \
  --output-detail-csv benchmark/processed/03_video_pipeline/<run_prefix>_confidence_sweep_details.csv \
  --output-md benchmark/processed/03_video_pipeline/<run_prefix>_confidence_sweep.md
```

离线 sweep 只会在 raw 已经写出的 `detections[]` 上调整评估阈值。如果 raw 的最小 confidence 已经接近 `0.25`，说明 C++ postprocess 已经提前过滤了更低分候选框；此时不能只改 `CONFIDENCE_MIN`，必须重新上板降低 `MODEL_CONFIG` 中的 `postprocess.confidence_threshold`。

低置信度 Jetson rerun 示例：

```bash
RUN_PREFIX=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf010_limit5 \
PYTHON_BIN=python3 \
MODEL_CONFIG=projects/03_video_pipeline/configs/models/yolo11n_conf010.yaml \
CONFIDENCE_MIN=0.10 \
LIMIT=5 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_bdd100k_mini.sh
```

该命令同时降低 pipeline 输出阈值和评估阈值。只设置 `CONFIDENCE_MIN=0.10` 而不设置 `MODEL_CONFIG=...yolo11n_conf010.yaml`，不会让 raw 增加 0.25 以下候选框。

截至 2026-06-16，`conf010` 路线已实测：aggregate recall 从 `0.304832` 提升到 `0.372144`，但仍低于当前 `0.50` 门槛，且 precision 明显下降。因此 `conf010` 只能说明阈值过高是部分原因，不能说明阈值调优本身足以通过质量门槛。

如果需要继续补阈值前沿，使用 `conf005` 诊断配置：

```bash
RUN_PREFIX=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_bdd100k_mini_nodrop_conf005_limit5 \
PYTHON_BIN=python3 \
MODEL_CONFIG=projects/03_video_pipeline/configs/models/yolo11n_conf005.yaml \
CONFIDENCE_MIN=0.05 \
LIMIT=5 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_bdd100k_mini.sh
```

更高优先级的后续工作是直接分析现有 `conf010` raw 的 per-class 和 difficult-case 分布，确认 `person`、`bicycle`、`train` 等类的失败模式是否真的还能靠阈值解决。

评估预测结果：

```bash
python3 projects/03_video_pipeline/scripts/quality/evaluate_bdd100k_mot_detection.py \
  --pred-raw benchmark/raw/03_video_pipeline/jetson_8gb/<run_id>.jsonl \
  --labels data/validation/bdd100k_mot_mini_v1/labels/<sequence_id>.jsonl \
  --sequence-id <sequence_id> \
  --output-md benchmark/processed/03_video_pipeline/<run_id>_bdd100k_mot_quality.md \
  --output-csv benchmark/processed/03_video_pipeline/<run_id>_bdd100k_mot_quality.csv \
  --output-summary-csv benchmark/processed/03_video_pipeline/<run_id>_bdd100k_mot_quality_summary.csv
```

最低判定：

- pipeline raw 必须包含 `detections[]` 中的 `class_id`、`confidence`、`bbox_xywh`。
- 评估指标至少记录 per-class 和 overall 的 AP50、precision、recall、F1、TP、FP、FN、prediction frame coverage、missing labeled frames、mean matched IoU。
- BDD100K MOT mini `pass` 必须有 manifest、视频 SHA256、标签 SHA256、raw result、质量报告五类证据。
- `vtest.avi` 不能写入 task-level quality pass；它只保留 smoke/runtime 和固定输入回归用途。

## Jetson Benchmark 最低表格检查

| report | table | must be filled before `pass` |
|---|---|---|
| `runtime_benchmark.md` | Runtime Summary | FPS、p50/p90/p95/p99、drop_frame_rate、cpu_fallback、status |
| `runtime_benchmark.md` | Stage Latency | capture、decode、preprocess、inference、postprocess、output 的 p50/p95/p99 |
| `runtime_benchmark.md` | Queue / Buffer | queue policy、capacity、p95/max、drop count/rate、memory growth |
| `runtime_benchmark.md` | Resource / Accelerator | memory、temperature、power mode/power、CPU/GPU util、runtime/accelerator evidence |
| `runtime_benchmark.md` | Quality Gate | fixed-input alignment、task-level quality、frame trace、output validity |
| `stability_report.md` | Stability Summary | 10 分钟、30 分钟、2 小时目标状态和实际时长 |
| `stability_report.md` | Resource Trace | 内存、温度、功耗、电源模式、降频事件 |
| `failure_and_fallback.md` | Failure Cases | 断流、模型缺失、输入尺寸错误、输出不可写、队列堆积、systemd 重启 |
| `failure_and_fallback.md` | CPU Fallback | `cpu_fallback`、`fallback_reason`、runtime/accelerator evidence |

## 状态规则

`pass` 和可解释的 `degraded` 可以进入汇总；`not_verified`、`fail`、`blocked`、`not_executed` 不能作为正式结论。

## RDK X5 快速入口

RDK X5 直接继承项目二环境基线与正式 split-head `.bin` artifact。当前项目三主线要求是：

- C++ `hbDNN` / `hbSys` runtime
- NV12 bytes 输入
- split-head external DFL + class-aware NMS
- 独立的 runtime / stability / failure / service 证据

### RDK X5 首次上板执行单

| 顺序 | 目标 | 命令 / 配置 | 通过门槛 | 必须落盘的产物 | 回填文档 |
|---|---|---|---|---|---|
| 0 | 环境和 artifact 基线确认 | `export ENVIRONMENT_BASELINE_ID=20260612_rdk_x5_8gb_env_baseline`；`sha256sum ...split_head_int8_ptq_calib500.bin` | baseline id 与 SHA256 正确 | shell 记录、run.md | `03F`、`runtime_benchmark.md` Reproducibility |
| 1 | 构建 BPU C++ app | `bash projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh` | 生成 `build/03_video_pipeline_rdk_x5/video_pipeline_app` | configure/build log | `runbook.md`、`video_pipeline.md` |
| 2 | 单线程最小链路 smoke | `PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_single_thread.yaml INPUT_SOURCE_TYPE=video_playlist INPUT_PATH=data/videos/runtime_playlist_v1.txt DURATION_SEC=60 ... bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh` | `hbDNN` 初始化成功，raw/schema/trace 生成，`cpu_fallback=false` | raw、runtime log、monitor log、summary | `runtime_benchmark.md` Runtime Summary / Stage Latency |
| 3 | IMX219 live-source 正式性能 benchmark | `INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 INPUT_SOURCE_TYPE=mipi_camera_hbn INPUT_PATH=srcampy://video_idx0 PREVIEW_WINDOW=off INPUT_ORIENTATION_CORRECTION=rotate180 INFERENCE_WORKERS=2 POSTPROCESS_WORKERS=2 DURATION_SEC=60 ... bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh` | `30 FPS` 档吞吐、`0` gap、`0` drop，live-source summary 生成 | raw、runtime log、monitor log、summary | `runtime_benchmark.md`、`video_pipeline.md` |
| 4 | 稳定性 smoke/30min/2h | `TIER=smoke|short_sustained|acceptance_sustained bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh` | stability CSV 生成，内存/温度/异常计数可追溯 | stability raw、monitor log、stability csv | `stability_report.md` |
| 5 | CLI failure | `bash projects/03_video_pipeline/scripts/run/run_rdk_x5_failure_injection.sh` | failure summary 通过 | failure jsonl/csv | `failure_and_fallback.md` |
| 6 | systemd 生命周期 | `bash projects/03_video_pipeline/scripts/service/test_rdk_x5_systemd_service.sh` | systemd start/restart/stop 留证 | status log、journal | `failure_and_fallback.md` |
| 7 | 真实 IMX219 live-source `input_disconnect` | `bash projects/03_video_pipeline/scripts/run/run_rdk_x5_input_disconnect.sh` | runtime log 出现 `FAULT_INJECTED_DISCONNECT` 和 `INPUT_DISCONNECTED`，wrapper `disconnect_status=pass` | failure jsonl/csv、automation log、runtime log | `failure_and_fallback.md`、`video_pipeline.md` |

当前推荐顺序是 `单线程最小链路 -> IMX219 live-source 性能 benchmark -> 稳定性 -> failure/systemd`。不要跳过单线程 smoke 直接上 live-source 主线，否则一旦 `hbDNN` 初始化、NV12 输入或 split-head decode 有偏差，定位成本会明显升高。

### Step 0：进入仓库并确认 baseline

```bash
cd /edge-inference-deploy-lab
export ENVIRONMENT_BASELINE_ID=20260612_rdk_x5_8gb_env_baseline
```

确认正式主线 artifact：

```bash
sha256sum models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin
```

期望输出：

```text
2a90fb0783742b8f663458dd9a043b34ff046a98753ec7ee87275b8faa6b411c  models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin
```

### Step 1：构建 RDK X5 BPU C++ pipeline

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_build \
  bash projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh
```

如果 SDK 不在默认路径，显式传入：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_build \
HOBOT_DNN_ROOT=/path/to/sdk \
HB_DNN_INCLUDE_DIR=/path/to/include \
HB_DNN_LIBRARY=/path/to/libdnn.so \
HB_HBRT_LIBRARY=/path/to/libhbrt.so \
  bash projects/03_video_pipeline/scripts/build/build_rdk_x5_bpu.sh
```

### Step 2：运行单线程最小链路 smoke

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_single_thread_demo \
PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_single_thread.yaml \
INPUT_SOURCE_ID=video_set_runtime_v1 \
INPUT_SOURCE_TYPE=video_playlist \
INPUT_PATH=data/videos/runtime_playlist_v1.txt \
DURATION_SEC=60 \
SAVE_OUTPUT_VIDEO=0 \
PREVIEW_WINDOW=off \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
```

该步的目标不是性能结论，而是先确认：

- `hbDNNInitializeFromFiles` / `hbDNNInfer` 正常
- `runtime_playlist_v1.txt` 可正常打开并被单线程配置消费
- NV12 输入路径可跑通
- split-head 输出能被当前 C++ decode 正确消费
- raw/schema/trace/monitor 产物都能生成

### Step 3：运行 IMX219 live-source 正式性能 benchmark

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2 \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=off \
INPUT_ORIENTATION_CORRECTION=rotate180 \
INFERENCE_WORKERS=2 \
POSTPROCESS_WORKERS=2 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
DURATION_SEC=60 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
```

当前默认口径：

- `PIPELINE_CONFIG=projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_pipeline.yaml`
- `BOARD_CONFIG=projects/03_video_pipeline/configs/boards/rdk_x5_8gb.yaml`
- `MODEL_CONFIG=projects/03_video_pipeline/configs/models/yolo11n.yaml`
- `INPUT_SOURCE_ID=imx219_rdkx5_hbn_001`
- `INPUT_SOURCE_TYPE=mipi_camera_hbn`
- `INPUT_PATH=srcampy://video_idx0`
- `INPUT_ORIENTATION_CORRECTION=rotate180`
- `queue_policy=drop_oldest`
- `queue_capacity=8`
- `inference_workers=2`
- `postprocess_workers=2`
- `buffer_reuse=true`
- 当前 app 真实消费的是全局 `mainline_policy / queue_capacity / queue_push_timeout_ms / inference_threads / postprocess_threads / reuse`
- YAML 中 `capture_to_preprocess.full_policy` 等 per-stage 字段当前用于记录目标设计，不应误写为“已独立生效”

当前证据拆分：

- `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` 仍是当前 playlist `600s` runtime 与长时 stability 口径。
- `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` 是当前 IMX219 live-source 正式性能主线。

当前 worker 对照：

| run_id | workers | fps_estimated | drop_frame_rate | frame_id_gaps | 结论 |
|---|---|---:|---:|---:|---|
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt2` | `1 infer / 1 postprocess` | 20.0169 | 0.3346 | 594 | 正确性恢复，但单 worker 吞吐不足 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p1` | `2 infer / 1 postprocess` | 19.9322 | 0.3375 | 599 | 单 postprocess worker 成为瓶颈 |
| `20260629_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2` | `2 infer / 2 postprocess` | 30.0847 | 0.0000 | 0 | 当前正式性能主线 |

如需完整复现实验过程，而不是只复现最终主线，按下面顺序跑：

1. 先跑 `opt2`，建立单 worker 基线。
2. 再跑 `opt3_i2_p1`，证明“只加 infer worker”无效。
3. 最后跑 `opt3_i2_p2`，确认 `2 infer / 2 postprocess` 收敛。

`opt2`：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt2 \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=off \
INPUT_ORIENTATION_CORRECTION=rotate180 \
INFERENCE_WORKERS=1 \
POSTPROCESS_WORKERS=1 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
DURATION_SEC=60 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
```

`opt3_i2_p1`：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p1 \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=off \
INPUT_ORIENTATION_CORRECTION=rotate180 \
INFERENCE_WORKERS=2 \
POSTPROCESS_WORKERS=1 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
DURATION_SEC=60 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
```

`opt3_i2_p2`：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_nopreview_perf_opt3_i2_p2 \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=off \
INPUT_ORIENTATION_CORRECTION=rotate180 \
INFERENCE_WORKERS=2 \
POSTPROCESS_WORKERS=2 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
DURATION_SEC=60 \
SAVE_OUTPUT_VIDEO=0 \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
```

验收时不要只比 `FPS`，还要同时核对：

- `trace_check.md` 是否为 `pass`
- `frame_id_gaps` 是否为 `0`
- `drop_frame_rate_total_estimated` 是否为 `0.0`
- runtime log 中是否出现 `INFERENCE_WORKERS: count=2` 和 `POSTPROCESS_WORKERS: count=2`

### Step 4：运行稳定性

```bash
TIER=smoke bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh
TIER=short_sustained bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh
TIER=acceptance_sustained bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh
```

说明：

- `run_rdk_x5_bpu_stability.sh` 的默认输入仍是 `video_set_stability_v1` playlist。
- 如果当前目标是给 **IMX219 live-source 正式主线**补 `03H short_sustained`，必须显式覆盖为 `imx219_rdkx5_hbn_001 + mipi_camera_hbn + HBN/srcampy + rotate180 + 2 infer / 2 postprocess`，不要直接照抄默认三条命令。

RDK X5 IMX219 live-source `short_sustained` 推荐命令：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained \
TIER=short_sustained \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=off \
INPUT_ORIENTATION_CORRECTION=rotate180 \
INFERENCE_WORKERS=2 \
POSTPROCESS_WORKERS=2 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
SAVE_OUTPUT_VIDEO=0 \
bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh
```

当前已回填的实测结果：

- `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_short_sustained`
- `actual_duration_sec=1798.0`
- `fps=30.3921`
- `p95/p99=165.8410 / 169.9096 ms`
- `drop_frame_rate=0.0`
- `frame_id_gaps=0`
- `trace_check=pass`
- `stability.csv=pass`
- `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained`
- `actual_duration_sec=7198.0`
- `fps=30.3865`
- `p95/p99=165.4440 / 169.4286 ms`
- `drop_frame_rate=0.0`
- `frame_id_gaps=0`
- `trace_check=pass`
- `stability.csv=pass`
- `local schema revalidation=pass`

同口径的 `acceptance_sustained` 复现实验命令如下：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_hbn_stability_acceptance_sustained \
TIER=acceptance_sustained \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=off \
INPUT_ORIENTATION_CORRECTION=rotate180 \
INFERENCE_WORKERS=2 \
POSTPROCESS_WORKERS=2 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
SAVE_OUTPUT_VIDEO=0 \
bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_stability.sh
```

验收重点：

- `benchmark/processed/03_video_pipeline/<run_id>_stability.csv` 必须生成
- `logs/runtime/.../<run_id>.log` 中应出现 `INFERENCE_WORKERS: count=2` 和 `POSTPROCESS_WORKERS: count=2`
- 若目标是“live-source 主线稳定性补证”，优先看 `actual_duration_sec≈1800`、`completed=true`、`drop_frame_rate_total_estimated`、`frame_id_gaps`、`temperature_c_peak`、`memory_growth_mb_per_hour`
- 当前 `03H` live-source 的 `short_sustained` 与 `acceptance_sustained` 两档都已补齐；后续不再优先重复 stability，而应转入任务级质量或 03I 汇总。

### Step 5：运行 CLI 异常注入

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_pipeline_failure_test \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_failure_injection.sh
```

该脚本会覆盖：

- `input_open_failed`
- `model_missing`
- `invalid_shape`
- `output_unwritable`
- `queue_overflow`

并生成：

- `logs/failures/03_video_pipeline/rdk_x5_8gb/<run_id>_failure_injection.jsonl`
- `benchmark/processed/03_video_pipeline/<run_id>_failure_summary.csv`
- `projects/03_video_pipeline/runs/<run_id>/run.md`

### Step 6：运行 systemd 生命周期

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_systemd_service_test \
WORKDIR=/edge-inference-deploy-lab \
SERVICE_USER=root \
  bash projects/03_video_pipeline/scripts/service/test_rdk_x5_systemd_service.sh
```

当前 `edge-video-pipeline-rdkx5.service` 模板使用占位符，由测试脚本在安装前替换：

- `__WORKDIR__`
- `__SERVICE_USER__`
- `__ENV_BASELINE__`

注意：

- `WORKDIR` 必须是开发板上的真实仓库根目录，不能把文档里的占位路径原样粘贴进去。
- 当前脚本已经对 `/path/to/edge-inference-deploy-lab` 增加显式拒绝；若触发 `WORKDIR_PLACEHOLDER_NOT_REPLACED`，说明命令没有替换成真实路径。

### Step 7：运行真实 live-source `input_disconnect`

当前 RDK X5 的正式 live-source 收敛为：

- `imx219_rdkx5_hbn_001`

视频集 playlist 虽然可以持续循环，但技术口径仍是 file/playlist source，不能替代真实 live-source 的 `input_disconnect` 证据。

当前 IMX219 断流补证命令：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=auto \
INPUT_ORIENTATION_CORRECTION=rotate180 \
INFERENCE_WORKERS=2 \
POSTPROCESS_WORKERS=2 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_input_disconnect.sh
```

说明：

- `PREVIEW_WINDOW=auto` 是当前 RDK X5 IMX219 实时预览的正式入口。检测到图形显示器和桌面会话时，会实时显示窗口；headless 或普通 SSH 下会自动关闭，不算失败。
- 当前这路 `imx219_rdkx5_hbn_001` 的正式朝向口径已经固定为 `rotate180`。如果使用脚本默认值，wrapper 会自动带上；如果你手工拼命令，仍建议显式写出 `INPUT_ORIENTATION_CORRECTION=rotate180`，并在 runtime log 中检查 `effective=rotate180`。
- 当前正式 disconnect 补证也应沿用 live-source 主线 worker 拓扑：`INFERENCE_WORKERS=2`、`POSTPROCESS_WORKERS=2`。不要再退回历史 `1 / 1` 组合，否则 failure evidence 与正式主线口径会分叉。
- 如果这块板子的 IMX219 video index、输出分辨率或 sensor 分辨率不同，就按板端 `srcampy` / probe 实测结果覆盖 `SRCAMPY_VIDEO_IDX / SRCAMPY_WIDTH / SRCAMPY_HEIGHT / SRCAMPY_SENSOR_WIDTH / SRCAMPY_SENSOR_HEIGHT`，不要再按 `/dev/video0` 强行照抄。

验收门槛：

- `projects/03_video_pipeline/runs/<run_id>/run.md` 追加 `RDK X5 Live Disconnect Evidence`
- `disconnect_status=pass`
- `runtime_log` 出现 `FAULT_INJECTED_DISCONNECT`
- `runtime_log` 出现 `INPUT_DISCONNECTED`
- `pipeline_exit=11`
- `logs/failures/03_video_pipeline/rdk_x5_8gb/<run_id>_failure_injection.jsonl` 和 `benchmark/processed/03_video_pipeline/<run_id>_failure_summary.csv` 生成

### RDK X5 产物检查表

| artifact | path |
|---|---|
| raw result | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/<run_id>.jsonl` |
| pre/post consistency | `benchmark/processed/03_video_pipeline/<run_id>_prepost_consistency.md` |
| schema check | `benchmark/processed/03_video_pipeline/<run_id>_schema_check.md` |
| trace check | `benchmark/processed/03_video_pipeline/<run_id>_trace_check.md` |
| runtime summary | `benchmark/processed/03_video_pipeline/<run_id>_summary.csv` |
| single-thread smoke config | `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_single_thread.yaml` |
| stability summary | `benchmark/processed/03_video_pipeline/<run_id>_stability.csv` |
| runtime log | `logs/runtime/03_video_pipeline/rdk_x5_8gb/<run_id>.log` |
| monitor log | `logs/monitor/03_video_pipeline/rdk_x5_8gb/<run_id>_bpu.log` |
| failure jsonl | `logs/failures/03_video_pipeline/rdk_x5_8gb/<run_id>_failure_injection.jsonl` |
| disconnect automation log | `logs/failures/03_video_pipeline/rdk_x5_8gb/<run_id>_input_disconnect_automation.log` |
| service journal | `logs/runtime/03_video_pipeline/rdk_x5_8gb/<run_id>_journal.log` |

### RDK X5 当前证据边界

| 结论类型 | 可引用证据 | 不可替代项 |
|---|---|---|
| 模型质量 baseline | 项目二 RDK X5 split-head Python runtime 正式报告 | 不能替代项目三 C++ video pipeline raw result |
| 项目三 runtime 性能 | `benchmark/raw/03_video_pipeline/rdk_x5_8gb/<run_id>.jsonl` 和 processed summary | 不能引用项目二 Python runtime FPS 作为项目三 C++ FPS |
| BPU 后端证据 | runtime log、BPU monitor、devfreq、`hrut_somstatus` | 不能只看 `.bin` 文件存在 |
| 稳定性 | 03H stability run、monitor log、failure log | 不能用项目二 resource monitor 替代 |
| CPU fallback | raw result、runtime log、failure/service 报告 | 不能默认假设没有 fallback |

## RDK X5 剩余收口步骤

按当前规范和已同步产物，RDK X5 工程主线已经通了，但还差两类正式证据：

1. `03C` 的 RDK X5 自身队列策略对照
2. quality gate 的 fixed-input / labeled quality 闭环

推荐顺序不要改，先补 03C，再补 fixed-input，最后补 labeled quality。这样后续写 `runtime_benchmark.md` 和 `video_pipeline.md` 时，证据链最干净。

### Step A：补 RDK X5 `03C` 队列策略对照

当前正式 live-source 主线固定为 IMX219 `mipi_camera_hbn + rotate180 + 2 infer / 2 postprocess + PREVIEW_WINDOW=off`。为了把 `drop_oldest / drop_newest / block_with_timeout` 放进同一张 RDK X5 队列表，建议三条都在相同口径下各跑 `600s`。

`drop_oldest` 基线：

```bash
cd /edge-inference-deploy-lab
export ENVIRONMENT_BASELINE_ID=20260612_rdk_x5_8gb_env_baseline

RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_queue_drop_oldest_live600 \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=off \
INPUT_ORIENTATION_CORRECTION=rotate180 \
QUEUE_POLICY=drop_oldest \
INFERENCE_WORKERS=2 \
POSTPROCESS_WORKERS=2 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
```

`drop_newest` 对照：

```bash
cd /edge-inference-deploy-lab
export ENVIRONMENT_BASELINE_ID=20260612_rdk_x5_8gb_env_baseline

RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_queue_drop_newest_live600 \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=off \
INPUT_ORIENTATION_CORRECTION=rotate180 \
QUEUE_POLICY=drop_newest \
INFERENCE_WORKERS=2 \
POSTPROCESS_WORKERS=2 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
```

`block_with_timeout(33ms)` 对照：

```bash
cd /edge-inference-deploy-lab
export ENVIRONMENT_BASELINE_ID=20260612_rdk_x5_8gb_env_baseline

RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_imx219_queue_block_timeout33_live600 \
INPUT_SOURCE_ID=imx219_rdkx5_hbn_001 \
INPUT_SOURCE_TYPE=mipi_camera_hbn \
INPUT_PATH=srcampy://video_idx0 \
PREVIEW_WINDOW=off \
INPUT_ORIENTATION_CORRECTION=rotate180 \
QUEUE_POLICY=block_with_timeout \
QUEUE_PUSH_TIMEOUT_MS=33 \
INFERENCE_WORKERS=2 \
POSTPROCESS_WORKERS=2 \
SRCAMPY_VIDEO_IDX=0 \
SRCAMPY_WIDTH=640 \
SRCAMPY_HEIGHT=640 \
SRCAMPY_SENSOR_WIDTH=1920 \
SRCAMPY_SENSOR_HEIGHT=1080 \
SRCAMPY_FPS=30 \
SRCAMPY_WARMUP=10 \
DURATION_SEC=600 \
SAVE_OUTPUT_VIDEO=0 \
bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bpu_pipeline.sh
```

### Step B：补 RDK X5 fixed-input alignment

这一步新入口已经补好，会自动：

- 抽取 `alignment_frames_manifest.json` 指定帧
- 跑项目二 RDK X5 Python `pyeasy_dnn` baseline
- 转成项目三可比较的 frame raw
- 再跑项目三当前 C++ pipeline
- 最后生成 fixed-input 对齐报告

命令：

```bash
cd /edge-inference-deploy-lab
export ENVIRONMENT_BASELINE_ID=20260612_rdk_x5_8gb_env_baseline

RUN_PREFIX=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_fixed_input_alignment \
PYTHON_BIN=python3 \
bash projects/03_video_pipeline/scripts/run/run_rdk_x5_fixed_input_alignment.sh
```

关键产物：

- `benchmark/processed/03_video_pipeline/<run_prefix>_fixed_input_alignment.md`
- `benchmark/processed/03_video_pipeline/<run_prefix>_fixed_input_alignment.csv`
- `benchmark/raw/03_video_pipeline/rdk_x5_8gb/<run_prefix>_project3_current.jsonl`

### Step C：补 RDK X5 BDD100K labeled quality

这一步新入口也已经补好，会复用通用批跑脚本，但切到 RDK X5 BPU pipeline 和 RDK X5 专用 quality config。默认口径是：

- `PREVIEW_WINDOW=off`
- `INFERENCE_WORKERS=2`
- `POSTPROCESS_WORKERS=2`
- `QUEUE_POLICY=block`
- `PACE_VIDEO_FILE=0`

命令：

```bash
cd /edge-inference-deploy-lab
export ENVIRONMENT_BASELINE_ID=20260612_rdk_x5_8gb_env_baseline

RUN_PREFIX=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_bdd100k_mini \
PYTHON_BIN=python3 \
bash projects/03_video_pipeline/scripts/run/run_rdk_x5_bdd100k_mini.sh
```

关键产物：

- `benchmark/processed/03_video_pipeline/<run_prefix>_batch.csv`
- `benchmark/processed/03_video_pipeline/<run_prefix>_bdd100k_mot_quality_aggregate.csv`
- `benchmark/processed/03_video_pipeline/<run_prefix>_bdd100k_mot_quality_aggregate.md`

### Step D：完成后再回填正式报告

只有在 A/B/C 三步都完成并同步回仓库后，RDK X5 才值得重新判定“是否全部完成”。回填顺序建议固定为：

1. `projects/03_video_pipeline/reports/runtime_benchmark.md`
2. `projects/03_video_pipeline/reports/stability_report.md`
3. `projects/03_video_pipeline/reports/video_pipeline.md`
4. `projects/03_video_pipeline/reports/troubleshooting.md`

当前新增的 RDK X5 入口文件如下：

- `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_fixed_input_alignment.yaml`
- `projects/03_video_pipeline/configs/pipeline/rdk_x5_bpu_bdd100k_quality.yaml`
- `projects/03_video_pipeline/scripts/run/run_rdk_x5_fixed_input_alignment.sh`
- `projects/03_video_pipeline/scripts/run/run_rdk_x5_bdd100k_mini.sh`
- `projects/03_video_pipeline/scripts/quality/convert_project2_alignment_to_video_raw.py`
