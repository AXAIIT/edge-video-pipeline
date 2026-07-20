# 项目三环境基线模板

项目三环境基线覆盖 C++ 构建、视频输入、后端 runtime、服务化和监控环境。第一次执行前必须建立环境基线；编译器、OpenCV/GStreamer/FFmpeg、后端 runtime、驱动、电源模式、摄像头、RTSP 网络或服务化方式变化后必须重建。

环境基线也使用目录式 run：

```text
projects/03_video_pipeline/runs/<yyyymmdd>_<target>_env_baseline/run.md
```

## YAML 记录区

```yaml
environment_baseline_id:
date:
target:
board_name:
module:
executor_type:
baseline_reason:
previous_environment_baseline_id:
status:

build_env:
  os:
  compiler:
  cmake_version:
  opencv_version:
  gstreamer_version:
  ffmpeg_version:
  cxx_standard:
  build_type:

runtime_env:
  os:
  kernel:
  driver_versions:
  runtime_versions:
  backend_runtime:
  power_mode:
  clock_lock:
  cooling:
  swap:
  storage_free:

video_io:
  camera_devices:
  rtsp_network:
  codec_support:
  hardware_decode:
  display_backend:

service_env:
  systemd_available:
  docker_available:
  user:
  permissions:
  device_mounts:

monitor_tools:
  cpu:
  gpu:
  npu:
  bpu:
  memory:
  temperature:
  power:
  throttle:

logs:
  collect_env_log:
  video_io_probe_log:
  runtime_probe_log:
  monitor_probe_log:
```

## 验收要求

- 能说明 C++ pipeline 在哪个环境构建和运行。
- 能说明视频输入、硬件解码、显示/输出能力。
- 能说明后端 runtime、驱动和加速器监控能力。
- 监控不可读时必须写明不可读原因和替代证据。
