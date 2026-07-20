# TensorRT wrapper

当前 Jetson 最小实现先集中在 `projects/03_video_pipeline/src/video_pipeline_app.cpp`，其中包含 TensorRT engine 加载、CUDA buffer、推理调用和 YOLO11n 输出解码。

当后续需要支持更多 INT8 engine、动态 shape、DLA 或更完整的错误码时，再将 TensorRT 后端拆分到本目录下的独立 wrapper 文件。拆分后必须保持 `03D_Jetson_TensorRT_CppPipeline规范.md` 中的 raw result 字段和 CPU fallback 证据不变。
