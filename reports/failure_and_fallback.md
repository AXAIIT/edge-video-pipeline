# 项目三异常恢复与 Fallback 报告

## 当前状态

partial_executed

本报告现在只保留异常恢复 / 降级的**结构化主表**、**执行入口**、**证据路径**和**验收口径**。凡是“为什么失败、前因后果、详细修复过程、回归验证”这类问题分析，统一写入 `projects/03_video_pipeline/reports/troubleshooting.md`，本报告只通过 `related_troubleshooting_id` 做索引，不再重复展开长篇叙述。

异常注入记录必须符合 `benchmark/schemas/video_pipeline_failure_schema.yaml`。后端 fallback 需要同时在 run、raw result 和本报告中说明。

数据口径说明：表内 `video_short_001` 仅表示 `2026-06-18` 已完成故障注入所使用的无人工标注历史输入，不构成质量证据。当前及后续故障注入默认使用 `bdd100k_mot_mini_v1`；两者不是同一数据集，结果不得合并或直接比较。

这里的 `pass` 有明确含义：

- `input_open_failed`、`model_missing`、`invalid_shape`、`output_unwritable`、`queue_overflow` 这 5 个 CLI case 已验证；
- `systemd_restart` 生命周期留证已验证；
- `20260619_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_appfault` 已在真实 `IMX219` live-source 上完成 `INPUT_DISCONNECTED -> exit 11` 的板端自动化闭环。

因此它不是“所有驱动层故障都已穷尽验证”的意思，而是“03G 规范要求的 CLI 子集、systemd 生命周期和 live-source `input_disconnect` 主线证据都已经补齐”。`driver_unbind` 造成 SSH 断开的系统级风险仍保留在问题库，但不再阻塞 03G 主线收口。

双文件分工：

- `failure_and_fallback.md`：保留 `Failure Cases / CPU Fallback / Service Recovery / Benchmark 影响` 主表。
- `troubleshooting.md`：保留错误内容、退出码、根因、修复过程、回归结果。
- 两边通过 `related_troubleshooting_id` 互相索引；若某条 failure case 没有对应问题单，才允许只在本报告内做简短说明。

## Jetson TensorRT 异常恢复计划

相关问题详见：

- `P3-TRB-20260619-010`：IMX219 `input_disconnect` 默认改为应用内安全注入，`driver_unbind` 只保留排障用途。

Jetson 异常恢复先覆盖命令行运行，再覆盖 systemd。当前已准备 systemd 模板：

```text
projects/03_video_pipeline/scripts/service/systemd/edge-video-pipeline-jetson.service
```

Jetson systemd 验证入口已经补齐：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_systemd_service_test \
  bash projects/03_video_pipeline/scripts/service/test_jetson_systemd_service.sh
```

Jetson CLI 异常注入入口已经补齐：

```bash
python3 projects/03_video_pipeline/scripts/inject_failure_tests.py \
  --pipeline build/03_video_pipeline_jetson/video_pipeline_app \
  --pipeline-config projects/03_video_pipeline/configs/pipeline/jetson_tensorrt_pipeline.yaml \
  --model-config projects/03_video_pipeline/configs/models/yolo11n.yaml \
  --backend-config projects/03_video_pipeline/configs/boards/jetson_8gb.yaml \
  --stream-config projects/03_video_pipeline/configs/streams/bdd100k_mot_mini_v1.yaml \
  --cases input_open_failed model_missing invalid_shape output_unwritable queue_overflow \
  --output logs/failures/03_video_pipeline/jetson_8gb/<run_id>_failure_injection.jsonl
```

当前自动化覆盖边界：

- 已自动化：`input_open_failed`、`model_missing`、`invalid_shape`、`output_unwritable`、`queue_overflow`
- 已完成真实板端自动化 wrapper 验证：`input_disconnect`
- 已完成板端基础生命周期验证：`systemd_restart`

真实 IMX219 `input_disconnect` 自动化入口：

```bash
RUN_ID=$(date +%Y%m%d)_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_auto \
SAVE_OUTPUT_VIDEO=0 \
DISCONNECT_WARMUP_SEC=30 \
DISCONNECT_POST_RECOVERY_SEC=60 \
  bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_imx219_disconnect.sh
```

默认说明：

- 默认 `DISCONNECT_METHOD=app_fault`，即在真实 IMX219 live-source 运行中，由应用内安全注入一次 `FAULT_INJECTED_DISCONNECT`，用于验证 `INPUT_DISCONNECTED` 错误路径和退出码闭环。
- `DISCONNECT_METHOD=driver_unbind` 仅保留为驱动/内核层排障模式；`2026-06-19` 现场已出现 active capture 期间执行 `unbind` 后 SSH 会话异常断开，疑似触发 Jetson 摄像头驱动/内核级不稳定，因此它不再作为默认主线闭环方法。

当前 `03G` 里所说的真实 live-source，已经收敛为 `CSI IMX219`。原因是当前 `03_video_pipeline` 已经补入 `RG10 raw -> debayer -> white balance` 的专用采集链路，`input_disconnect` 应该直接对着正式摄像头主线补证，而不是继续等待 USB/RTSP 占位输入。

必须执行的 Jetson 异常用例：

| case_id | stage | 触发方式 | 期望行为 | evidence | status |
|---|---|---|---|---|---|
| input_open_failed | capture | 将 `INPUT_PATH` 指向不存在的视频 | 返回 `INPUT_OPEN_FAILED`，退出码非 0，写 failure log | `logs/failures/03_video_pipeline/jetson_8gb/<run_id>.jsonl` | pass_cli_subset |
| input_disconnect | capture | 优先执行 `bash projects/03_video_pipeline/scripts/run/run_jetson_tensorrt_imx219_disconnect.sh`；默认由应用内注入 `FAULT_INJECTED_DISCONNECT`，可选 `driver_unbind` 排障模式 | 清晰失败并退出或恢复；记录错误路径与退出码 | automation log + runtime log + run.md | board_wrapper_available |
| model_missing | inference | 临时改错 `backend_artifact_path` | 返回 `MODEL_LOAD_FAILED` 或 `BACKEND_RUNTIME_FAILED`，不能假运行 | runtime log + troubleshooting | pass_cli_subset |
| invalid_shape | preprocess/inference | 改错输入尺寸或 engine 配置 | 拒绝启动或明确降级 | failure JSONL | pass_cli_subset |
| output_unwritable | output | 输出目录不可写 | 返回 `OUTPUT_FAILED`，保留日志 | runtime log | pass_cli_subset |
| queue_overflow | pipeline | 高 FPS 输入或注入 sleep | 有界队列限流，记录丢帧原因 | raw result + runtime log | pass_cli_subset |
| systemd_restart | service | `bash projects/03_video_pipeline/scripts/service/test_jetson_systemd_service.sh` 或等价 `systemctl` 序列 | start/restart/stop 状态可追溯，journal 保存 | journal log | pass_board_lifecycle |

Jetson fallback 原则：

- TensorRT engine 加载失败时不允许自动改用 CPU 并继续标记 TensorRT 成果。
- 如果临时启用 mock/CPU fallback，只能用于排查，正式性能结论必须写 `not_verified` 或 `degraded`。
- 队列堆积优先使用 `drop_oldest` 保持低延迟；若改为 `block_with_timeout`，必须在 runtime benchmark 中解释延迟影响。
- `input_disconnect` 是故障证据 run，不是常规 runtime pass run。只要 `runtime_log` 出现 `INPUT_DISCONNECTED` 或等价清晰错误，并能解释退出方式，就可以作为 03G 合格证据；不要求该 run 必须 `final_exit=0`。

## Failure Cases

| run_id | target | case_id | input_source_id | stage | error_code | expected_behavior | actual_behavior | recovery_action | max_recovery_time_sec | reconnect_count | frame_id_continuity_after_recovery | drop_frame_reason_after_recovery | service_status | log_path | related_troubleshooting_id | status |
|---|---|---|---|---|---|---|---|---|---:|---:|---|---|---|---|---|---|
| `20260618_jetson_8gb_pipeline_failure_service_test` | jetson_8gb | input_open_failed | missing_video_file | capture | INPUT_OPEN_FAILED | reject_missing_input_and_exit_nonzero | returned_INPUT_OPEN_FAILED_exit10 | exit |  | 0 | not_applicable | not_applicable | not_applicable | `logs/failures/03_video_pipeline/jetson_8gb/20260618_jetson_8gb_pipeline_failure_service_test_failure_injection_artifacts/20260618_jetson_8gb_pipeline_failure_service_test_input_open_failed.log` |  | pass |
| `20260619_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_appfault` | jetson_8gb | input_disconnect | imx219_csi_001 | capture | INPUT_DISCONNECTED | safe_injected_disconnect_should_emit_clear_error_and_exit11 | runtime_log_contains_INPUT_DISCONNECTED_and_FAULT_INJECTED_DISCONNECT_exit11 | exit_after_clear_error |  | 0 | not_applicable | not_applicable | not_applicable | `logs/failures/03_video_pipeline/jetson_8gb/20260619_jetson_8gb_yolo11n_tensorrt_imx219_disconnect_appfault_imx219_disconnect_automation.log` | `P3-TRB-20260619-010` | pass |
| `20260618_jetson_8gb_pipeline_failure_service_test` | jetson_8gb | model_missing | video_short_001 | inference | BACKEND_RUNTIME_FAILED | reject_missing_backend_artifact_and_exit_nonzero | backend_init_failed_with_exit21 | exit |  | 0 | not_applicable | not_applicable | not_applicable | `logs/failures/03_video_pipeline/jetson_8gb/20260618_jetson_8gb_pipeline_failure_service_test_failure_injection_artifacts/20260618_jetson_8gb_pipeline_failure_service_test_model_missing.log` |  | pass |
| `20260618_jetson_8gb_pipeline_failure_service_test` | jetson_8gb | invalid_shape | video_short_001 | preprocess | CONFIG_INVALID | reject_invalid_model_shape_or_layout_before_runtime | config_rejected_before_runtime_exit30 | exit |  | 0 | not_applicable | not_applicable | not_applicable | `logs/failures/03_video_pipeline/jetson_8gb/20260618_jetson_8gb_pipeline_failure_service_test_failure_injection_artifacts/20260618_jetson_8gb_pipeline_failure_service_test_invalid_shape.log` |  | pass |
| `20260618_jetson_8gb_pipeline_failure_service_test` | jetson_8gb | output_unwritable | video_short_001 | output | OUTPUT_FAILED | reject_unwritable_output_path_and_exit_nonzero | raw_output_open_failed_with_exit40 | exit |  | 0 | not_applicable | not_applicable | not_applicable | `logs/failures/03_video_pipeline/jetson_8gb/20260618_jetson_8gb_pipeline_failure_service_test_failure_injection_artifacts/20260618_jetson_8gb_pipeline_failure_service_test_output_unwritable.log` |  | pass |
| `20260618_jetson_8gb_pipeline_failure_service_test` | jetson_8gb | queue_overflow | video_set_runtime_v1 | capture | QUEUE_OVERFLOW | bounded_queue_should_limit_backpressure_and_record_queue_full_drop | queue_full_observed frames=60 drop_count=414 max_queue=1 | drop_or_limit_by_queue_policy |  | 0 | gap_with_reason | queue_full | not_applicable | `logs/failures/03_video_pipeline/jetson_8gb/20260618_jetson_8gb_pipeline_failure_service_test_failure_injection_artifacts/20260618_jetson_8gb_pipeline_failure_service_test_queue_overflow.log` |  | pass |

## CPU Fallback

| run_id | target | backend_runtime | execution_provider | loader_api | backend_artifact_path | runtime_evidence_path | accelerator_evidence_path | cpu_fallback | fallback_reason | status |
|---|---|---|---|---|---|---|---|---|---|---|
| `20260618_jetson_8gb_pipeline_failure_service_test` | jetson_8gb | tensorrt | TensorRT-GPU | TensorRT C++ API | `models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine` | `logs/failures/03_video_pipeline/jetson_8gb/20260618_jetson_8gb_pipeline_failure_service_test_failure_injection_artifacts/20260618_jetson_8gb_pipeline_failure_service_test_model_missing.log` | `not_applicable_for_cli_failure_subset` | false | `not_triggered_in_cli_subset` | pass_cli_subset |

## Service Recovery

| run_id | target | service_mode | start_status | restart_status | stop_status | journal_log_path | health_check | recovery_action | status |
|---|---|---|---|---|---|---|---|---|---|
| `20260618_jetson_8gb_systemd_service_test` | jetson_8gb | systemd | active | active | inactive | `logs/runtime/03_video_pipeline/jetson_8gb/20260618_jetson_8gb_systemd_service_test_journal.log` | `prepost_status=pass` 已写入 journal，`systemctl is-active` 在 start / restart 后为 `active` | `systemctl restart` 可重新拉起 service，`systemctl stop` 后状态回到 `inactive` | pass |

## RK3588 RKNN 异常恢复计划

RK3588 已补齐五项 CLI 自动故障注入入口和 systemd 生命周期测试入口。`20260621_rk3588_8gb_systemd_service_test` 已使用 BDD100K 视频集 playlist 完成 start/restart/stop 验证。这里必须区分两类输入：视频集是可复现的持续回放源，用于服务生命周期和稳定性；摄像头才是真正的 live source，用于实时采集与 `input_disconnect`。两者不能互相替代证据。

| case_id | stage | 触发方式 | 期望行为 | evidence | status |
|---|---|---|---|---|---|
| input_open_failed | capture | 使用不存在的视频路径 | `INPUT_OPEN_FAILED`，exit 10 | failure JSONL + case log | pass_exit10 |
| model_missing | inference | 覆盖为不存在的 `.rknn` 路径 | `BACKEND_RUNTIME_FAILED`，exit 21，不允许 CPU/mock fallback | failure JSONL + case log | pass_exit21 |
| invalid_shape | preprocess | 将 model layout 覆盖为 NHWC | `CONFIG_INVALID`，exit 30 | failure JSONL + case log | pass_exit30 |
| output_unwritable | output | raw 输出指向不存在的父目录 | `OUTPUT_FAILED`，exit 40 | failure JSONL + case log | pass_exit40 |
| queue_overflow | pipeline | 关闭文件节流并将 drop_oldest queue capacity 设为 1 | app 正常退出，raw 出现 `queue_full` 和 drop_count>0 | failure JSONL + case raw/log | pass_257_frames_drop346_queue1 |
| rknpu_unobservable | monitor | 两个 RKNPU load 节点均不可读 | 保留 RKNN runtime 证据，资源状态标 degraded，不伪造利用率 | monitor log | policy_defined_not_in_cli_subset |
| input_disconnect | capture | 在真实 RK3588 Astra S OpenNI 摄像头采集成功后安全注入断流 | 明确记录 `FAULT_INJECTED_DISCONNECT`、`INPUT_DISCONNECTED` 和 exit 11 | failure JSONL + runtime log | pass_astra_openni_board_verified |
| systemd_restart | service | start/restart/stop 标准生命周期 | active/active/inactive，journal 可追溯 | status log + journal + run.md | pass_video_playlist_and_camera |

RK3588 CLI 标准入口：

```bash
RUN_ID=$(date +%Y%m%d)_rk3588_8gb_pipeline_failure_test \
PYTHON_BIN="$HOME/venvs/rk3588_rknn/bin/python" \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_failure_injection.sh
```

systemd 标准入口：

```bash
RUN_ID=$(date +%Y%m%d)_rk3588_8gb_systemd_service_test \
  bash projects/03_video_pipeline/scripts/service/test_rk3588_systemd_service.sh
```

摄像头设备探测与断流入口：

```bash
python3 projects/03_video_pipeline/scripts/probe/probe_openni2_astra.py \
  --device 2bc5/0402 \
  --json-output benchmark/processed/03_video_pipeline/<run_id>_astra_probe.json

RUN_ID=$(date +%Y%m%d)_rk3588_8gb_yolo11n_rknn_astra_disconnect_appfault \
OPENNI_DEVICE_SELECTOR=2bc5/0402 \
PYTHON_BIN="$HOME/venvs/rk3588_rknn/bin/python" \
  bash projects/03_video_pipeline/scripts/run/run_rk3588_camera_disconnect.sh
```

RK3588 当前执行口径必须同时保留两个 source：

- 视频集持续回放 source：`video_set_runtime_v1` / `video_set_stability_v1`，用于可复现 runtime、稳定性和视频集 service。
- 真实摄像头 source：`astra_s_openni_001`，即 Astra S OpenNI，`input_source_type=openni_camera`、`INPUT_PATH=2bc5/0402`、默认 color `640x480 RGB888@30`，用于 smoke、`input_disconnect` 和 camera service。

断流脚本对的是真实 Astra S color stream，不是视频文件模拟摄像头。

### RK3588 Failure Cases 实测

| run_id | case_id | stage | error_code | exit_code | actual_behavior | recovery_action | continuity_after_recovery | drop_reason_after_recovery | schema | status |
|---|---|---|---|---:|---|---|---|---|---|---|
| `20260621_rk3588_8gb_pipeline_failure_test` | input_open_failed | capture | INPUT_OPEN_FAILED | 10 | returned_INPUT_OPEN_FAILED_exit10 | exit | not_applicable | not_applicable | pass | pass |
| `20260621_rk3588_8gb_pipeline_failure_test` | model_missing | inference | BACKEND_RUNTIME_FAILED | 21 | backend_init_failed_with_exit21 | exit | not_applicable | not_applicable | pass | pass |
| `20260621_rk3588_8gb_pipeline_failure_test` | invalid_shape | preprocess | CONFIG_INVALID | 30 | config_rejected_before_runtime_exit30 | exit | not_applicable | not_applicable | pass | pass |
| `20260621_rk3588_8gb_pipeline_failure_test` | output_unwritable | output | OUTPUT_FAILED | 40 | raw_output_open_failed_with_exit40 | exit | not_applicable | not_applicable | pass | pass |
| `20260621_rk3588_8gb_pipeline_failure_test` | queue_overflow | capture | QUEUE_OVERFLOW | 0 | queue_full_observed frames=257 drop_count=346 max_queue=1 | drop_or_limit_by_queue_policy | gap_with_reason | queue_full | pass | pass |
| `20260622_rk3588_8gb_yolo11n_rknn_astra_disconnect_appfault_v2` | input_disconnect | capture | INPUT_DISCONNECTED | 139 | segfault_before_disconnect_evidence_runtime_log_empty | exit_after_clear_error_expected_but_not_reached | not_applicable | not_applicable | pass | fail_regression |
| `20260622_rk3588_8gb_yolo11n_rknn_astra_disconnect_appfault_v3` | input_disconnect | capture | INPUT_DISCONNECTED | 11 | runtime_log_contains_INPUT_DISCONNECTED_and_FAULT_INJECTED_DISCONNECT_exit11 | exit_after_clear_error | not_applicable | not_applicable | pass | pass |

证据：

- `logs/failures/03_video_pipeline/rk3588_8gb/20260621_rk3588_8gb_pipeline_failure_test_failure_injection.jsonl`
- `benchmark/processed/03_video_pipeline/20260621_rk3588_8gb_pipeline_failure_test_failure_summary.csv`
- `projects/03_video_pipeline/runs/20260621_rk3588_8gb_pipeline_failure_test/run.md`

口径：

- RK3588 CLI 子集当前为 `5/5 pass`。
- `input_disconnect` 的回归与修复细节见 `P3-TRB-20260622-014`。
- 与实时稳定性误判相关的退出码和 trace 门禁问题见 `P3-TRB-20260621-013`。

### RK3588 Service Recovery 实测

| run_id | input profile | start_status | restart_status | stop_status | health_check | status |
|---|---|---|---|---|---|---|
| `20260621_rk3588_8gb_systemd_service_test` | `video_set_stability_v1` / video playlist | active | active | inactive | `prepost_status=pass` | pass |
| `20260622_rk3588_8gb_astra_camera_systemd_service_test_v2` | `astra_s_openni_001` / OpenNI camera | activating | activating | inactive | `prepost_status=pass` | fail_current_retest |
| `20260622_rk3588_8gb_astra_camera_systemd_service_test_v3` | `astra_s_openni_001` / OpenNI camera | active | active | inactive | `prepost_status=pass` | pass |

证据：
- `logs/runtime/03_video_pipeline/rk3588_8gb/20260621_rk3588_8gb_systemd_service_test_systemd_status.log`
- `logs/runtime/03_video_pipeline/rk3588_8gb/20260621_rk3588_8gb_systemd_service_test_journal.log`
- `logs/runtime/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_astra_camera_systemd_service_test_v2_systemd_status.log`
- `logs/runtime/03_video_pipeline/rk3588_8gb/20260622_rk3588_8gb_astra_camera_systemd_service_test_v2_journal.log`

摄像头使用独立模板 `edge-video-pipeline-rk3588-camera.service`，并且当前已经切换为 `astra_s_openni_001` / `openni_camera` / `2bc5/0402`。板端同时补入 `/etc/udev/rules.d/99-orbbec-astra.rules`，把 USB 设备 `2bc5:0402` 赋给 `plugdev`，从而允许 non-root 直接打开 Astra S。`20260622` 最新复测显示 camera service 已恢复为 active/active/inactive。

相关问题详见：

- `P3-TRB-20260622-014`：Astra S OpenNI 接入、权限、selector、断流与 camera service 闭环。

### RK3588 CPU Fallback

| run_id | target | backend_runtime | execution_provider | loader_api | backend_artifact_path | runtime_evidence_path | accelerator_evidence_path | cpu_fallback | fallback_reason | status |
|---|---|---|---|---|---|---|---|---|---|---|
| `20260621_rk3588_8gb_yolo11n_rknn_stability_acceptance_sustained` | rk3588_8gb | rknn | RKNPU | RKNN C API | `models/yolo11n/rknn/yolo11n_640_rk3588_rknnopt_int8_ptq_calib500.rknn` | `logs/runtime/03_video_pipeline/rk3588_8gb/20260621_rk3588_8gb_yolo11n_rknn_stability_acceptance_sustained.log` | `logs/monitor/03_video_pipeline/rk3588_8gb/20260621_rk3588_8gb_yolo11n_rknn_stability_acceptance_sustained_rknpu.log` | false |  | pass_acceptance_7199s |

## Benchmark 影响

异常和 fallback 结果不能替代 runtime benchmark，但会决定 runtime 表中的状态能否进入正式结论。

| condition | runtime_benchmark_status | stability_status | required action |
|---|---|---|---|
| TensorRT runtime log 缺失 | not_verified | not_verified | 补跑 03D，保留 runtime log |
| `tegrastats` 或等价 monitor 缺失 | not_verified 或 degraded | not_verified 或 degraded | 补采资源；无法采集时说明不可观测原因 |
| `cpu_fallback=true` | fail 或 degraded | fail 或 degraded | 记录 fallback reason；正式 TensorRT 性能表不得写 `pass` |
| 输入断流后恢复成功 | pass 或 degraded | pass 或 degraded | 写明重连次数、最大恢复时间和丢帧原因 |
| 输入断流后假运行或无错误码 | fail | fail | 进入问题库，修复后重新执行 failure run |
| 队列堆积但可解释丢帧 | degraded 或 pass | degraded | 在 Queue / Buffer 表记录策略和延迟影响 |
| systemd 启停不可追溯 | not_verified | not_verified | 补 journal、service status 和 run 记录 |

## 结论

| 平台 | 当前异常恢复口径 | 主表证据 | 相关问题库 |
|---|---|---|---|
| Jetson TensorRT | `03G pass` | CLI `5/5`、systemd 生命周期、IMX219 `input_disconnect` 主线闭环 | `P3-TRB-20260619-010` |
| RK3588 RKNN | `03G pass` | CLI `5/5`、video playlist service、Astra camera service、Astra `input_disconnect` 闭环 | `P3-TRB-20260622-014`、`P3-TRB-20260621-013` |
| RDK X5 BPU | `03G pass` | CLI `5/5`、systemd `v2`、IMX219 HBN `input_disconnect` 闭环 | `P3-TRB-20260630-015` 及相关 RDK X5 条目 |

说明：

- 本节只给异常恢复 / fallback 的收口口径，不重复问题分析。
- 若需查看某次失败为什么发生、错误码如何解释、修复过程如何闭环，一律回到 `troubleshooting.md`。

## RDK X5 BPU 异常恢复计划

RDK X5 的 CLI failure wrapper 和 systemd 生命周期都已形成板端闭环。历史失败样本继续保留在本报告的主表里作为排障证据；其根因、退出码解释和修复过程统一见 `troubleshooting.md` 相关条目。

当前仓库中已经额外收紧 `test_rdk_x5_systemd_service.sh`：

- 默认 `WORKDIR` 改为脚本自动解析出的仓库根；
- 若用户把 `/path/to/edge-inference-deploy-lab` 占位符原样传入，脚本会直接拒绝执行；
- service unit 的 `ExecStart` 也改成了绝对脚本路径占位符，减少路径误配风险。

RDK X5 CLI 异常注入入口：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_pipeline_failure_test \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_failure_injection.sh
```

RDK X5 systemd 生命周期入口：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_systemd_service_test \
WORKDIR=/edge-inference-deploy-lab \
SERVICE_USER=root \
  bash projects/03_video_pipeline/scripts/service/test_rdk_x5_systemd_service.sh
```

RDK X5 真实 live-source `input_disconnect` 入口：

当前正式口径收敛为 `imx219_rdkx5_hbn_001`，也就是板端 IMX219 CSI 摄像头的 `HBN/srcampy` 接入链路。该 run 允许 `PREVIEW_WINDOW=auto`：只要板端检测到 `DISPLAY` / `WAYLAND_DISPLAY` / `XDG_SESSION_TYPE=x11|wayland`，就实时显示窗口；普通 SSH 终端不会把“没窗口”算成失败。
当前这路 IMX219 的正式朝向口径已固定为 `INPUT_ORIENTATION_CORRECTION=rotate180`；如果 runtime log 没有出现 `effective=rotate180`，就不能把该次结果当成视觉有效。

IMX219 方案：

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

如果板端 IMX219 的实际输出尺寸、video index 或 sensor 分辨率不同，就按板端 `srcampy` / probe 实测结果覆盖 `SRCAMPY_VIDEO_IDX / SRCAMPY_WIDTH / SRCAMPY_HEIGHT / SRCAMPY_SENSOR_WIDTH / SRCAMPY_SENSOR_HEIGHT`，不要再按 `/dev/video0` 假设硬套。

这条 disconnect run 现在也应显式沿用当前 live-source 正式主线 worker 拓扑：`INFERENCE_WORKERS=2`、`POSTPROCESS_WORKERS=2`。这样做的目的不是追求更高 FPS，而是确保 03G 的 live-source failure evidence 与 03F 当前正式主线口径一致，避免后续回看时出现“性能 run 用 2/2、disconnect run 却用历史 1/1”的审计歧义。

RTSP 只保留为备选诊断入口，不再作为当前 RDK X5 正式闭环口径：

```bash
RUN_ID=$(date +%Y%m%d)_rdk_x5_8gb_yolo11n_bpu_rtsp_disconnect_appfault \
INPUT_SOURCE_ID=rtsp_stream_001 \
INPUT_SOURCE_TYPE=rtsp \
INPUT_PATH='rtsp://<user>:<password>@<host>:<port>/<path>' \
INPUT_PATH_RECORD='rtsp://<redacted>@<host>:<port>/<path>' \
  bash projects/03_video_pipeline/scripts/run/run_rdk_x5_input_disconnect.sh
```

如果使用 RTSP，优先同时传 `INPUT_PATH_RECORD`，让 `run.md` 自动落脱敏 URI；不要把明文凭据同步回仓库。

当前自动化覆盖边界：

- 已补脚本：`input_open_failed`、`model_missing`、`invalid_shape`、`output_unwritable`、`queue_overflow`
- 已补脚本：`systemd_restart`
- 已补脚本：真实 live-source `input_disconnect` wrapper（`run_rdk_x5_input_disconnect.sh`）
- 已完成板端补证：`20260630_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault`

### RDK X5 Failure Cases

| run_id | target | case_id | input_source_id | stage | error_code | expected_behavior | actual_behavior | recovery_action | max_recovery_time_sec | reconnect_count | frame_id_continuity_after_recovery | drop_frame_reason_after_recovery | service_status | log_path | related_troubleshooting_id | evidence_scope | status |
|---|---|---|---|---|---|---|---|---|---:|---:|---|---|---|---|---|---|---|
| `20260624_rdk_x5_8gb_pipeline_failure_test` | rdk_x5_8gb | input_open_failed | `missing_video_file` | capture | INPUT_OPEN_FAILED | reject_missing_input_and_exit_nonzero | `returned_INPUT_OPEN_FAILED_exit10` | exit | not_applicable | 0 | not_applicable | not_applicable | not_applicable | `logs/failures/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_pipeline_failure_test_failure_injection_artifacts/20260624_rdk_x5_8gb_pipeline_failure_test_input_open_failed.log` |  | project3_cpp_board_run_synced_back | pass |
| `20260624_rdk_x5_8gb_pipeline_failure_test` | rdk_x5_8gb | model_missing | `bdd100k_mot_mini_v1_02344f0c-d5d916ff` | inference | BACKEND_RUNTIME_FAILED | reject_missing_backend_artifact_and_exit_nonzero | `backend_init_failed_with_exit21` | exit | not_applicable | 0 | not_applicable | not_applicable | not_applicable | `logs/failures/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_pipeline_failure_test_failure_injection_artifacts/20260624_rdk_x5_8gb_pipeline_failure_test_model_missing.log` |  | project3_cpp_board_run_synced_back | pass |
| `20260624_rdk_x5_8gb_pipeline_failure_test` | rdk_x5_8gb | invalid_shape | `bdd100k_mot_mini_v1_02344f0c-d5d916ff` | preprocess | CONFIG_INVALID | reject_invalid_model_shape_or_layout_before_runtime | `config_rejected_before_runtime_exit30` | exit | not_applicable | 0 | not_applicable | not_applicable | not_applicable | `logs/failures/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_pipeline_failure_test_failure_injection_artifacts/20260624_rdk_x5_8gb_pipeline_failure_test_invalid_shape.log` |  | project3_cpp_board_run_synced_back | pass |
| `20260624_rdk_x5_8gb_pipeline_failure_test` | rdk_x5_8gb | output_unwritable | `bdd100k_mot_mini_v1_02344f0c-d5d916ff` | output | OUTPUT_FAILED | reject_unwritable_output_path_and_exit_nonzero | `raw_output_open_failed_with_exit40` | exit | not_applicable | 0 | not_applicable | not_applicable | not_applicable | `logs/failures/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_pipeline_failure_test_failure_injection_artifacts/20260624_rdk_x5_8gb_pipeline_failure_test_output_unwritable.log` |  | project3_cpp_board_run_synced_back | pass |
| `20260624_rdk_x5_8gb_pipeline_failure_test` | rdk_x5_8gb | queue_overflow | `video_set_runtime_v1` | capture | QUEUE_OVERFLOW | bounded_queue_should_limit_backpressure_and_record_queue_full_drop | `queue_full_observed frames=90 drop_count=72 max_queue=1` | drop_or_limit_by_queue_policy | not_applicable | 0 | gap_with_reason | queue_full | not_applicable | `logs/failures/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_pipeline_failure_test_failure_injection_artifacts/20260624_rdk_x5_8gb_pipeline_failure_test_queue_overflow.log` |  | project3_cpp_board_run_synced_back | pass |
| `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault` | rdk_x5_8gb | input_disconnect | `imx219_rdkx5_hbn_001` | capture | INPUT_DISCONNECTED | reconnect_or_fail_with_clear_log_and_recovery_metrics | `runtime_log_contains_INPUT_DISCONNECTED_and_FAULT_INJECTED_DISCONNECT_exit11` | exit_after_clear_error |  | 0 | not_applicable | not_applicable | not_applicable | `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260630_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault.log` |  | project3_cpp_board_run_synced_back | pass |

### RDK X5 CPU Fallback

| run_id | target | backend_runtime | execution_provider | loader_api | backend_artifact_path | runtime_evidence_path | accelerator_evidence_path | cpu_fallback | fallback_reason | evidence_scope | status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor` | rdk_x5_8gb | bpu | BPU | `hobot_dnn.pyeasy_dnn` | `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin` | `projects/02_quantization/runs/20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor/run.md` | `logs/monitor/02_quantization/rdk_x5_8gb/20260615_rdk_x5_yolo11n_split_head_int8_python_runtime_letterbox_full_val2017_resource_monitor_resource_monitor.jsonl` | false | `mixed_execution_recorded_in_project2_profile_not_equal_project3_cpp_fallback_status` | reference_from_project2_only | reference_from_project2_only |
| `20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline` | rdk_x5_8gb | bpu | BPU | `Horizon hbDNN C API` | `models/yolo11n/rdk_x5_bpu_split_head/yolo11n_640_rdkx5_split_head_int8_ptq_calib500.bin` | `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline.log` | `logs/monitor/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_yolo11n_bpu_cpp_pipeline_bpu.log` | false | `not_applicable` | project3_cpp_board_run_synced_back | pass |

### RDK X5 Service Recovery

| run_id | target | service_mode | start_status | restart_status | stop_status | journal_log_path | health_check | recovery_action | evidence_scope | status |
|---|---|---|---|---|---|---|---|---|---|---|
| `20260624_rdk_x5_8gb_systemd_service_test` | rdk_x5_8gb | systemd | `activating` | `activating` | `inactive` | `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_systemd_service_test_journal.log` | fail | `replace placeholder WORKDIR, then rerun service lifecycle test` | project3_cpp_board_run_synced_back | historical_placeholder_fail |
| `20260624_rdk_x5_8gb_systemd_service_test_v2` | rdk_x5_8gb | systemd | `active` | `active` | `inactive` | `logs/runtime/03_video_pipeline/rdk_x5_8gb/20260624_rdk_x5_8gb_systemd_service_test_v2_journal.log` | pass | `workdir_fixed_rerun_pass` | project3_cpp_board_run_synced_back | pass |

### RDK X5 结论口径

| item | current_status | notes |
|---|---|---|
| failure wrapper | pass_cli_5of5 | `input_open_failed / model_missing / invalid_shape / output_unwritable / queue_overflow` 全部板端通过 |
| systemd lifecycle script | hardened_and_board_verified | 脚本现已拒绝 `/path/to/edge-inference-deploy-lab` 占位符，并改用绝对 `ExecStart`；`systemd_service_test_v2` 已验证 `active/active/inactive` |
| project3 cpp failure evidence | pass_board_verified | `20260624_rdk_x5_8gb_pipeline_failure_test` 已完成正式回填 |
| project3 cpp service evidence | pass_board_verified | `20260624_rdk_x5_8gb_systemd_service_test_v2` 已通过；原始 `status=200/CHDIR` 样本保留作排障证据 |
| live-source input_disconnect | pass_board_verified | `20260630_rdk_x5_8gb_yolo11n_bpu_imx219_disconnect_appfault` 已在 `imx219_rdkx5_hbn_001` 上完成：`FAULT_INJECTED_DISCONNECT`、`INPUT_DISCONNECTED`、`pipeline_exit=11` 与 wrapper `disconnect_status=pass` 全部成立 |

补充说明：

- 这轮 `input_disconnect` 的**权威结论**是 wrapper 追加的 `RDK X5 Live Disconnect Evidence` 和 `failure_summary.csv`，不是内层 runtime wrapper 的 `final_status=fail`。
- 原因是这类 03G run 的目标本来就是“安全注入真实 live-source 断流，并清晰报错退出”；因此 `exit 11` 属于预期行为，不应按常规 runtime pass/fail 口径解读。
- 板端首份同步回来的 `schema_check.md` 还沿用了旧 schema，把 `input_source_type=mipi_camera_hbn` 误判成非法值；当前仓库已按最新 schema 本地重刷，该 run 的 raw schema 现在为 `pass`。

相关问题详见：

- `P3-TRB-20260630-015`：BDD100K batch wrapper / postcheck 误判。
- RDK X5 live-source 与断流闭环的工程演进详见 `troubleshooting.md` 中 RDK X5 相关条目。
