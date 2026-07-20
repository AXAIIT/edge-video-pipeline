#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <cctype>
#include <cstring>
#include <cstdio>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <numeric>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/dnn.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#if defined(__linux__)
#include <cerrno>
#include <dlfcn.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

#if defined(PIPELINE_BACKEND_TENSORRT)
#include <NvInfer.h>
#include <cuda_runtime_api.h>
#endif

#if defined(PIPELINE_BACKEND_RKNN)
#include <rknn_api.h>
#endif

#if defined(PIPELINE_BACKEND_BPU)
#include <dnn/hb_dnn.h>
#include <dnn/hb_sys.h>
#endif

namespace {

using Clock = std::chrono::steady_clock;

struct Args {
  std::string config;
  std::string model_config;
  std::string backend_config;
  std::string stream_config;
  std::string input_source_id = "bdd100k_mot_mini_v1";
  std::string input_source_type = "video_file";
  std::string input;
  std::string raw_output;
  std::string output_video;
  std::string runtime_log_path;
  std::string monitor_log_path;
  std::string preview_window_mode = "auto";
  std::string queue_policy_override;
  std::string rknn_core_mask_override;
  std::string input_orientation_correction = "auto";
  int duration_sec = 600;
  int queue_capacity_override = -1;
  int queue_push_timeout_ms_override = -1;
  int inference_workers_override = -1;
  int postprocess_workers_override = -1;
  bool loop_video_file = true;
  int pace_video_file_override = -1;
  bool v4l2_raw = false;
  int v4l2_width = 1920;
  int v4l2_height = 1080;
  int v4l2_sensor_mode = 2;
  double v4l2_fps = 30.0;
  std::string bayer_pattern = "RG";
  std::string v4l2_normalize_mode = "percentile";
  bool v4l2_disable_white_balance = false;
  std::string srcampy_python = "python3";
  std::string srcampy_stream_script =
      "projects/03_video_pipeline/scripts/run/rdk_x5_srcampy_stream.py";
  int srcampy_video_idx = 0;
  int srcampy_width = 640;
  int srcampy_height = 640;
  int srcampy_sensor_width = 1920;
  int srcampy_sensor_height = 1080;
  double srcampy_fps = 30.0;
  int srcampy_warmup = 10;
  double srcampy_startup_timeout_sec = 8.0;
  int fault_inject_disconnect_after_sec = -1;
};

struct ModelConfig {
  int input_w = 640;
  int input_h = 640;
  int num_classes = 80;
  float conf_thres = 0.25f;
  float nms_thres = 0.45f;
  int max_detections = 300;
  std::string color_format = "RGB";
  std::string layout = "NCHW";
  float normalize_scale = 1.0f / 255.0f;
  float pad_value = 114.0f;
  bool keep_ratio = true;
  bool class_agnostic_nms = false;
};

struct BoardConfig {
  std::string board = "Jetson Xavier NX 8GB";
  std::string target = "jetson_8gb";
  std::string backend_runtime = "tensorrt";
  std::string execution_provider = "TensorRT-GPU";
  std::string loader_api = "TensorRT C++ API";
  std::string precision = "int8_ptq";
  std::string artifact_format = "engine";
  std::string artifact_path = "models/yolo11n/tensorrt/yolo11n_640_jetson_trt_int8_ptq_calib500_minmax_b8.engine";
  std::string artifact_sha256 = "1e966f10db6742476414294f931948b4732a4a44c07479022eca34869ab5ca9d";
  std::string rknn_core_mask = "auto";
  float preprocess_pad_value = std::numeric_limits<float>::quiet_NaN();
};

struct PipelineConfig {
  std::string pipeline_mode = "backend_pipeline";
  std::string queue_policy = "drop_oldest";
  int queue_capacity = 4;
  int queue_push_timeout_ms = 20;
  int inference_workers = 1;
  int postprocess_workers = 1;
  bool buffer_reuse = true;
  bool pace_video_file = true;
};

struct TensorInfo {
  std::vector<int> dims;
  size_t elem_count = 0;
};

struct LetterboxInfo {
  float scale = 1.0f;
  int pad_x = 0;
  int pad_y = 0;
};

struct Box {
  float x = 0.0f;
  float y = 0.0f;
  float width = 0.0f;
  float height = 0.0f;
};

struct Detection {
  int class_id = -1;
  float confidence = 0.0f;
  Box box;
};

constexpr std::array<const char*, 80> kCocoClassNames = {
    "person",        "bicycle",      "car",           "motorcycle",   "airplane",
    "bus",           "train",        "truck",         "boat",         "traffic light",
    "fire hydrant",  "stop sign",    "parking meter", "bench",        "bird",
    "cat",           "dog",          "horse",         "sheep",        "cow",
    "elephant",      "bear",         "zebra",         "giraffe",      "backpack",
    "umbrella",      "handbag",      "tie",           "suitcase",     "frisbee",
    "skis",          "snowboard",    "sports ball",   "kite",         "baseball bat",
    "baseball glove","skateboard",   "surfboard",     "tennis racket","bottle",
    "wine glass",    "cup",          "fork",          "knife",        "spoon",
    "bowl",          "banana",       "apple",         "sandwich",     "orange",
    "broccoli",      "carrot",       "hot dog",       "pizza",        "donut",
    "cake",          "chair",        "couch",         "potted plant", "bed",
    "dining table",  "toilet",       "tv",            "laptop",       "mouse",
    "remote",        "keyboard",     "cell phone",    "microwave",    "oven",
    "toaster",       "sink",         "refrigerator",  "book",         "clock",
    "vase",          "scissors",     "teddy bear",    "hair drier",   "toothbrush",
};

const char* CocoClassName(int class_id) {
  if (class_id >= 0 && class_id < static_cast<int>(kCocoClassNames.size())) {
    return kCocoClassNames[static_cast<size_t>(class_id)];
  }
  return nullptr;
}

std::string FormatDetectionLabel(const Detection& det) {
  std::ostringstream label;
  if (const char* class_name = CocoClassName(det.class_id)) {
    label << class_name;
  } else {
    label << "class_" << det.class_id;
  }
  label << " " << std::fixed << std::setprecision(2) << det.confidence;
  return label.str();
}

struct Trace {
  std::string capture_ts;
  std::string decode_ts;
  std::string preprocess_ts;
  std::string infer_start_ts;
  std::string infer_end_ts;
  std::string postprocess_ts;
  std::string output_ts;
  double capture_ms = 0.0;
  double decode_ms = 0.0;
  double preprocess_ms = 0.0;
  double inference_ms = 0.0;
  double postprocess_ms = 0.0;
  double output_ms = 0.0;
};

std::string Trim(const std::string& s);
std::string ToLower(std::string value);

bool IsRealtimePreviewEligibleSource(const std::string& input_source_type) {
  return input_source_type == "mipi_camera" ||
         input_source_type == "mipi_camera_hbn" ||
         input_source_type == "mipi_camera_argus" ||
         input_source_type == "openni_camera" ||
         input_source_type == "usb_camera" ||
         input_source_type == "rtsp";
}

bool HasDisplayEnvironment() {
  const auto has_nonempty = [](const char* value) {
    return value != nullptr && *value != '\0';
  };
  if (has_nonempty(std::getenv("DISPLAY"))) return true;
  if (has_nonempty(std::getenv("WAYLAND_DISPLAY"))) return true;
  const char* session_type = std::getenv("XDG_SESSION_TYPE");
  if (has_nonempty(session_type)) {
    const std::string normalized = ToLower(Trim(session_type));
    if (normalized == "x11" || normalized == "wayland") return true;
  }
  return false;
}

class PreviewWindow {
 public:
  PreviewWindow(const Args& args, const std::string& board_target)
      : requested_mode_(ToLower(Trim(args.preview_window_mode))),
        eligible_source_(IsRealtimePreviewEligibleSource(args.input_source_type)),
        display_env_present_(HasDisplayEnvironment()),
        window_name_("edge_video_pipeline_" + board_target + "_" + args.input_source_id) {
    if (requested_mode_.empty()) requested_mode_ = "auto";
    if (requested_mode_ == "off") {
      LogStatus("disabled", "requested_off");
      return;
    }
    if (!eligible_source_ && requested_mode_ == "auto") {
      LogStatus("disabled", "non_realtime_source");
      return;
    }
    if (!display_env_present_) {
      LogStatus("disabled", "display_env_missing");
      return;
    }
    try {
      cv::namedWindow(window_name_, cv::WINDOW_NORMAL);
      enabled_ = true;
      LogStatus("enabled", "window_created");
    } catch (const cv::Exception& e) {
      enabled_ = false;
      LogStatus("disabled", std::string("opencv_highgui_failed: ") + e.what());
    }
  }

  ~PreviewWindow() {
    if (!enabled_) return;
    try {
      cv::destroyWindow(window_name_);
    } catch (const cv::Exception&) {
    }
  }

  bool enabled() const { return enabled_; }

  void Show(cv::Mat& frame, size_t detection_count) {
    if (!enabled_ || frame.empty()) return;
    try {
      UpdatePreviewFps();
      DrawHud(frame, detection_count);
      cv::imshow(window_name_, frame);
      const int key = cv::waitKey(1);
      if (key == 27 || key == 'q' || key == 'Q') {
        enabled_ = false;
        std::cerr << "PREVIEW_WINDOW_STATUS: requested=" << requested_mode_
                  << " enabled=false reason=user_requested_close_key" << std::endl;
        try {
          cv::destroyWindow(window_name_);
        } catch (const cv::Exception&) {
        }
      }
    } catch (const cv::Exception& e) {
      enabled_ = false;
      std::cerr << "PREVIEW_WINDOW_STATUS: requested=" << requested_mode_
                << " enabled=false reason=opencv_runtime_failed message=" << e.what()
                << std::endl;
    }
  }

 private:
  void UpdatePreviewFps() {
    const auto now = Clock::now();
    if (preview_frame_count_ > 0) {
      const double interval_ms =
          std::chrono::duration<double, std::milli>(now - last_presented_ts_).count();
      if (interval_ms > 0.0) {
        const double instantaneous_fps = 1000.0 / interval_ms;
        if (preview_fps_ <= 0.0) {
          preview_fps_ = instantaneous_fps;
        } else {
          preview_fps_ = preview_fps_ * 0.85 + instantaneous_fps * 0.15;
        }
      }
    }
    last_presented_ts_ = now;
    ++preview_frame_count_;
  }

  void DrawHud(cv::Mat& frame, size_t detection_count) const {
    std::ostringstream text;
    if (preview_fps_ > 0.0 && preview_frame_count_ > 1) {
      text << "FPS " << std::fixed << std::setprecision(1) << preview_fps_;
    } else {
      text << "FPS --";
    }
    text << " | DET " << detection_count;

    const double font_scale =
        std::max(0.55, std::min(static_cast<double>(frame.cols), static_cast<double>(frame.rows)) /
                           900.0);
    const int thickness = std::max(1, static_cast<int>(std::round(font_scale * 2.0)));
    int baseline = 0;
    const cv::Size text_size =
        cv::getTextSize(text.str(), cv::FONT_HERSHEY_SIMPLEX, font_scale, thickness, &baseline);
    const int padding = std::max(6, thickness * 4);
    const cv::Rect panel(12, 12, text_size.width + padding * 2, text_size.height + padding * 2);
    const cv::Rect canvas(0, 0, frame.cols, frame.rows);
    const cv::Rect clipped = panel & canvas;
    cv::rectangle(frame, clipped, cv::Scalar(16, 16, 16), cv::FILLED);
    cv::rectangle(frame, clipped, cv::Scalar(0, 255, 255), 1);
    cv::putText(frame, text.str(),
                cv::Point(clipped.x + padding, clipped.y + padding + text_size.height),
                cv::FONT_HERSHEY_SIMPLEX, font_scale, cv::Scalar(0, 255, 255), thickness,
                cv::LINE_AA);
  }

  void LogStatus(const std::string& state, const std::string& reason) const {
    std::cerr << "PREVIEW_WINDOW_STATUS: requested=" << requested_mode_
              << " eligible_source=" << (eligible_source_ ? "true" : "false")
              << " display_env_present=" << (display_env_present_ ? "true" : "false")
              << " enabled=" << (state == "enabled" ? "true" : "false")
              << " reason=" << reason << std::endl;
  }

  std::string requested_mode_;
  bool eligible_source_ = false;
  bool display_env_present_ = false;
  bool enabled_ = false;
  std::string window_name_;
  Clock::time_point last_presented_ts_{};
  double preview_fps_ = 0.0;
  uint64_t preview_frame_count_ = 0;
};

struct FramePacket {
  int frame_id = 0;
  double input_fps = 0.0;
  cv::Mat frame;
  Trace trace;
};

struct TensorPacket {
  int frame_id = 0;
  double input_fps = 0.0;
  cv::Mat frame;
  Trace trace;
  LetterboxInfo letterbox;
  std::vector<float> input_tensor;
  std::vector<uint8_t> nv12_input;
};

struct InferPacket {
  int inference_sequence = 0;
  int frame_id = 0;
  double input_fps = 0.0;
  cv::Mat frame;
  Trace trace;
  LetterboxInfo letterbox;
  std::vector<float> output_tensor;
  bool ok = true;
  std::string error_code = "OK";
};

struct ResultPacket {
  int inference_sequence = 0;
  int frame_id = 0;
  double input_fps = 0.0;
  cv::Mat frame;
  Trace trace;
  std::vector<Detection> detections;
  bool ok = true;
  std::string error_code = "OK";
};

std::string Trim(const std::string& s) {
  const auto begin = s.find_first_not_of(" \t\r\n\"'");
  if (begin == std::string::npos) return "";
  const auto end = s.find_last_not_of(" \t\r\n\"'");
  return s.substr(begin, end - begin + 1);
}

std::string ToUpper(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(),
                 [](unsigned char c) { return static_cast<char>(std::toupper(c)); });
  return value;
}

std::string ToLower(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return value;
}

bool ParseBool(const std::string& value, bool fallback) {
  const auto upper = ToUpper(Trim(value));
  if (upper == "TRUE" || upper == "YES" || upper == "ON" || upper == "1") return true;
  if (upper == "FALSE" || upper == "NO" || upper == "OFF" || upper == "0") return false;
  return fallback;
}

std::string CanonicalizeQueuePolicy(const std::string& value) {
  const auto lower = ToLower(Trim(value));
  if (lower == "dropoldest" || lower == "drop_oldest") return "drop_oldest";
  if (lower == "dropnewest" || lower == "drop_newest") return "drop_newest";
  if (lower == "blocktimeout" || lower == "block_timeout" || lower == "block_with_timeout") {
    return "block_with_timeout";
  }
  if (lower == "blockforever" || lower == "block_forever") return "block_forever";
  if (lower == "nodrop" || lower == "no_drop") return "no_drop";
  if (lower == "block") return "block";
  if (lower == "none") return "none";
  if (lower == "keep_key_frame") return "keep_key_frame";
  return Trim(value);
}

std::string CanonicalizeV4l2NormalizeMode(const std::string& value) {
  const auto lower = ToLower(Trim(value));
  if (lower == "percentile" || lower == "dynamic_percentile" || lower == "auto") {
    return "percentile";
  }
  if (lower == "fixed10" || lower == "fixed_10bit" || lower == "fixed10bit" ||
      lower == "linear10" || lower == "linear_10bit") {
    return "fixed_10bit";
  }
  return Trim(value);
}

std::string FindYamlScalar(const std::string& path, const std::string& key) {
  std::ifstream in(path);
  if (!in) return "";
  std::string line;
  const std::string needle = key + ":";
  while (std::getline(in, line)) {
    const auto comment = line.find('#');
    if (comment != std::string::npos) line = line.substr(0, comment);
    const auto trimmed = Trim(line);
    if (trimmed.rfind(needle, 0) == 0) {
      return Trim(trimmed.substr(needle.size()));
    }
  }
  return "";
}

int FindYamlInt(const std::string& path, const std::string& key, int fallback) {
  const auto value = FindYamlScalar(path, key);
  if (value.empty()) return fallback;
  try {
    return std::stoi(value);
  } catch (...) {
    return fallback;
  }
}

float FindYamlFloat(const std::string& path, const std::string& key, float fallback) {
  const auto value = FindYamlScalar(path, key);
  if (value.empty()) return fallback;
  try {
    return std::stof(value);
  } catch (...) {
    return fallback;
  }
}

std::string NowIso() {
  const std::time_t t = std::time(nullptr);
  std::tm tm{};
#if defined(_WIN32)
  localtime_s(&tm, &t);
#else
  localtime_r(&t, &tm);
#endif
  std::ostringstream os;
  os << std::put_time(&tm, "%Y-%m-%dT%H:%M:%S") << "+08:00";
  return os.str();
}

double MsSince(const Clock::time_point& start) {
  return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
}

std::string JsonEscape(const std::string& s) {
  std::ostringstream os;
  for (char c : s) {
    switch (c) {
      case '"': os << "\\\""; break;
      case '\\': os << "\\\\"; break;
      case '\n': os << "\\n"; break;
      case '\r': os << "\\r"; break;
      case '\t': os << "\\t"; break;
      default: os << c; break;
    }
  }
  return os.str();
}

std::string JsonStringOrNull(const std::string& s) {
  if (s.empty() || s == "null") return "null";
  return "\"" + JsonEscape(s) + "\"";
}

bool EndsWith(const std::string& value, const std::string& suffix) {
  return value.size() >= suffix.size() &&
         value.compare(value.size() - suffix.size(), suffix.size(), suffix) == 0;
}

bool IsNonNegativeInteger(const std::string& value) {
  return !value.empty() &&
         std::all_of(value.begin(), value.end(), [](unsigned char c) { return std::isdigit(c) != 0; });
}

bool IsLikelyGStreamerPipeline(const std::string& source) {
  return source.find('!') != std::string::npos ||
         source.find("appsink") != std::string::npos ||
         source.find("nvarguscamerasrc") != std::string::npos ||
         source.find("v4l2src") != std::string::npos;
}

bool OpenCvCapture(cv::VideoCapture& cap, const std::string& source) {
  cap.release();
  if (IsNonNegativeInteger(source)) {
    return cap.open(std::stoi(source), cv::CAP_V4L2);
  }
  if (IsLikelyGStreamerPipeline(source)) {
    return cap.open(source, cv::CAP_GSTREAMER);
  }
  if (!cap.open(source)) return false;

  // OpenCV builds disagree on whether MOV rotation metadata is applied by
  // default. BDD100K labels use the encoded 1280x720 frame coordinates.
  constexpr int kCapPropOrientationAuto = 49;
  cap.set(kCapPropOrientationAuto, 0.0);
  return true;
}

std::vector<std::string> LoadPlaylistPaths(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    throw std::runtime_error("PLAYLIST_OPEN_FAILED: " + path);
  }
  std::vector<std::string> items;
  std::string line;
  while (std::getline(in, line)) {
    const auto comment = line.find('#');
    if (comment != std::string::npos) line = line.substr(0, comment);
    const auto trimmed = Trim(line);
    if (!trimmed.empty()) items.push_back(trimmed);
  }
  if (items.empty()) {
    throw std::runtime_error("PLAYLIST_EMPTY: " + path);
  }
  return items;
}

uint16_t PercentileValue(std::vector<uint16_t> values, double q) {
  if (values.empty()) return 0;
  q = std::clamp(q, 0.0, 1.0);
  const size_t index = static_cast<size_t>(std::round(q * static_cast<double>(values.size() - 1)));
  auto nth = values.begin();
  std::advance(nth, static_cast<long>(index));
  std::nth_element(values.begin(), nth, values.end());
  return values[index];
}

std::string FourCcToString(uint32_t fourcc) {
  std::string s(4, ' ');
  s[0] = static_cast<char>(fourcc & 0xFF);
  s[1] = static_cast<char>((fourcc >> 8) & 0xFF);
  s[2] = static_cast<char>((fourcc >> 16) & 0xFF);
  s[3] = static_cast<char>((fourcc >> 24) & 0xFF);
  for (char& c : s) {
    if (!std::isprint(static_cast<unsigned char>(c))) c = '?';
  }
  return s;
}

double FpsFromTimePerFrame(uint32_t numerator, uint32_t denominator) {
  if (numerator == 0 || denominator == 0) return 0.0;
  return static_cast<double>(denominator) / static_cast<double>(numerator);
}

void NormalizeRaw16To8(const cv::Mat& raw16,
                       cv::Mat& raw8,
                       const std::string& mode,
                       std::vector<uint16_t>* scratch_samples = nullptr) {
  if (raw16.empty() || raw16.type() != CV_16UC1) {
    throw std::runtime_error("V4L2 raw frame must be CV_16UC1");
  }

  const std::string normalized_mode = CanonicalizeV4l2NormalizeMode(mode);
  if (normalized_mode == "fixed_10bit") {
    // Jetson IMX219 RG10 frames are exposed as 16-bit words whose useful
    // intensity bits are effectively carried in the high byte. The earlier
    // "scale low 10 bits by 255/1023" assumption saturates most pixels to
    // white and produces an unusable preview. Keeping the high 8 bits matches
    // the historical decode probe (`msb10_shift8_*`) that retained scene
    // structure while preserving the fixed-cost fast path.
    raw16.convertTo(raw8, CV_8U, 1.0 / 256.0);
    return;
  }
  if (normalized_mode != "percentile") {
    throw std::runtime_error("unsupported V4L2 normalize mode: " + mode);
  }

  std::vector<uint16_t> local_samples;
  std::vector<uint16_t>& samples = scratch_samples != nullptr ? *scratch_samples : local_samples;
  samples.clear();
  const int step = 8;
  samples.reserve(static_cast<size_t>((raw16.rows / step + 1) * (raw16.cols / step + 1)));
  for (int y = 0; y < raw16.rows; y += step) {
    const uint16_t* row = raw16.ptr<uint16_t>(y);
    for (int x = 0; x < raw16.cols; x += step) {
      samples.push_back(row[x]);
    }
  }

  uint16_t lo = PercentileValue(samples, 0.01);
  uint16_t hi = PercentileValue(samples, 0.99);
  if (hi <= lo + 16) {
    double min_value = 0.0;
    double max_value = 0.0;
    cv::minMaxLoc(raw16, &min_value, &max_value);
    lo = static_cast<uint16_t>(std::max(0.0, min_value));
    hi = static_cast<uint16_t>(std::min(65535.0, max_value));
  }
  if (hi <= lo + 16) {
    raw16.convertTo(raw8, CV_8U, 1.0 / 256.0);
    return;
  }

  const double scale = 255.0 / static_cast<double>(hi - lo);
  raw16.convertTo(raw8, CV_8U, scale, -static_cast<double>(lo) * scale);
}

int BayerPatternToBgrCode(const std::string& pattern) {
  const std::string value = ToUpper(pattern);
  // The config uses the conventional top-left 2x2 Bayer names. OpenCV's
  // legacy two-letter COLOR_Bayer* constants use a different naming scheme,
  // so RGGB maps to COLOR_BayerBG2BGR rather than COLOR_BayerRG2BGR.
  if (value == "RG" || value == "RGGB") return cv::COLOR_BayerBG2BGR;
  if (value == "BG" || value == "BGGR") return cv::COLOR_BayerRG2BGR;
  if (value == "GR" || value == "GRBG") return cv::COLOR_BayerGB2BGR;
  if (value == "GB" || value == "GBRG") return cv::COLOR_BayerGR2BGR;
  throw std::runtime_error("unsupported Bayer pattern: " + pattern);
}

void ApplyGrayWorldWhiteBalance(cv::Mat& bgr) {
  if (bgr.empty() || bgr.type() != CV_8UC3) return;
  cv::Mat bgr_float;
  bgr.convertTo(bgr_float, CV_32F);
  std::vector<cv::Mat> channels;
  cv::split(bgr_float, channels);
  const cv::Scalar means = cv::mean(bgr_float);
  const double gray = (means[0] + means[1] + means[2]) / 3.0;
  for (int channel = 0; channel < 3; ++channel) {
    if (means[channel] > 1e-6) {
      channels[channel] *= gray / means[channel];
    }
  }
  cv::merge(channels, bgr_float);
  bgr_float.convertTo(bgr, CV_8U);
}

struct RawBayerConversionProfile {
  double normalize_ms = 0.0;
  double debayer_ms = 0.0;
  double white_balance_ms = 0.0;
};

cv::Mat Raw16BayerToBgr(const cv::Mat& raw16,
                        const std::string& bayer_pattern,
                        const std::string& normalize_mode,
                        bool apply_white_balance,
                        RawBayerConversionProfile* profile = nullptr,
                        cv::Mat* raw8_scratch = nullptr,
                        std::vector<uint16_t>* scratch_samples = nullptr) {
  cv::Mat local_raw8;
  cv::Mat& raw8 = raw8_scratch != nullptr ? *raw8_scratch : local_raw8;
  const auto normalize_started = Clock::now();
  NormalizeRaw16To8(raw16, raw8, normalize_mode, scratch_samples);
  if (profile != nullptr) profile->normalize_ms = MsSince(normalize_started);

  cv::Mat bgr;
  const auto debayer_started = Clock::now();
  cv::cvtColor(raw8, bgr, BayerPatternToBgrCode(bayer_pattern));
  if (profile != nullptr) profile->debayer_ms = MsSince(debayer_started);
  if (apply_white_balance) {
    const auto white_balance_started = Clock::now();
    ApplyGrayWorldWhiteBalance(bgr);
    if (profile != nullptr) profile->white_balance_ms = MsSince(white_balance_started);
  }
  return bgr;
}

#if defined(__linux__)
int Xioctl(int fd, unsigned long request, void* arg) {
  int ret = 0;
  do {
    ret = ioctl(fd, request, arg);
  } while (ret == -1 && errno == EINTR);
  return ret;
}

[[noreturn]] void ThrowErrno(const std::string& message) {
  throw std::runtime_error(message + ": " + std::strerror(errno));
}

std::string CameraDevicePath(const std::string& source) {
  if (IsNonNegativeInteger(source)) {
    return "/dev/video" + source;
  }
  return source;
}

struct OpenNIOniVersion {
  int major = 0;
  int minor = 0;
  int maintenance = 0;
  int build = 0;
};

struct OpenNIOniVideoMode {
  int pixelFormat = 0;
  int resolutionX = 0;
  int resolutionY = 0;
  int fps = 0;
};

struct OpenNIOniSensorInfo {
  int sensorType = 0;
  int numSupportedVideoModes = 0;
  OpenNIOniVideoMode* pSupportedVideoModes = nullptr;
};

struct OpenNIOniDeviceInfo {
  char uri[256];
  char vendor[256];
  char name[256];
  uint16_t usbVendorId = 0;
  uint16_t usbProductId = 0;
};

struct OpenNIOniFrame {
  int dataSize = 0;
  void* data = nullptr;
  int sensorType = 0;
  uint64_t timestamp = 0;
  int frameIndex = 0;
  int width = 0;
  int height = 0;
  OpenNIOniVideoMode videoMode;
  int croppingEnabled = 0;
  int cropOriginX = 0;
  int cropOriginY = 0;
  int stride = 0;
};

using OpenNIOniDeviceHandle = void*;
using OpenNIOniStreamHandle = void*;

class OpenNI2Api {
 public:
  static constexpr int kStatusOk = 0;
  static constexpr int kStatusTimeOut = 102;
  static constexpr int kSensorIr = 1;
  static constexpr int kSensorColor = 2;
  static constexpr int kSensorDepth = 3;
  static constexpr int kPixelFormatDepth1Mm = 100;
  static constexpr int kPixelFormatDepth100Um = 101;
  static constexpr int kPixelFormatRgb888 = 200;
  static constexpr int kPixelFormatYuv422 = 201;
  static constexpr int kPixelFormatGray8 = 202;
  static constexpr int kPixelFormatGray16 = 203;
  static constexpr int kPixelFormatJpeg = 204;
  static constexpr int kPixelFormatYuyv = 205;
  static constexpr int kStreamPropertyVideoMode = 3;

  explicit OpenNI2Api(const std::string& library_path) : library_path_(library_path) {
    handle_ = dlopen(library_path.c_str(), RTLD_LAZY | RTLD_LOCAL);
    if (handle_ == nullptr) {
      throw std::runtime_error("OPENNI_LIBRARY_LOAD_FAILED: " + library_path + ": " + DlError());
    }
    oniInitialize = LoadSymbol<FnOniInitialize>("oniInitialize");
    oniShutdown = LoadSymbol<FnOniShutdown>("oniShutdown");
    oniGetVersion = LoadSymbol<FnOniGetVersion>("oniGetVersion");
    oniGetExtendedError = LoadSymbol<FnOniGetExtendedError>("oniGetExtendedError");
    oniGetDeviceList = LoadSymbol<FnOniGetDeviceList>("oniGetDeviceList");
    oniReleaseDeviceList = LoadSymbol<FnOniReleaseDeviceList>("oniReleaseDeviceList");
    oniDeviceOpen = LoadSymbol<FnOniDeviceOpen>("oniDeviceOpen");
    oniDeviceClose = LoadSymbol<FnOniDeviceClose>("oniDeviceClose");
    oniDeviceGetSensorInfo = LoadSymbol<FnOniDeviceGetSensorInfo>("oniDeviceGetSensorInfo");
    oniDeviceCreateStream = LoadSymbol<FnOniDeviceCreateStream>("oniDeviceCreateStream");
    oniStreamDestroy = LoadSymbol<FnOniStreamDestroy>("oniStreamDestroy");
    oniStreamStart = LoadSymbol<FnOniStreamStart>("oniStreamStart");
    oniStreamStop = LoadSymbol<FnOniStreamStop>("oniStreamStop");
    oniWaitForAnyStream = LoadSymbol<FnOniWaitForAnyStream>("oniWaitForAnyStream");
    oniStreamReadFrame = LoadSymbol<FnOniStreamReadFrame>("oniStreamReadFrame");
    oniFrameRelease = LoadSymbol<FnOniFrameRelease>("oniFrameRelease");
    oniStreamGetProperty = LoadSymbol<FnOniStreamGetProperty>("oniStreamGetProperty");
  }

  ~OpenNI2Api() {
    if (handle_ != nullptr) {
      dlclose(handle_);
      handle_ = nullptr;
    }
  }

  OpenNI2Api(const OpenNI2Api&) = delete;
  OpenNI2Api& operator=(const OpenNI2Api&) = delete;

  std::string ExtendedError() const {
    if (oniGetExtendedError == nullptr) return "";
    const char* error = oniGetExtendedError();
    if (error == nullptr) return "";
    return error;
  }

  static std::string StatusString(int status) {
    switch (status) {
      case 0: return "OK";
      case 1: return "ERROR";
      case 2: return "NOT_IMPLEMENTED";
      case 3: return "NOT_SUPPORTED";
      case 4: return "BAD_PARAMETER";
      case 5: return "OUT_OF_FLOW";
      case 6: return "NO_DEVICE";
      case 102: return "TIME_OUT";
      default: {
        std::ostringstream oss;
        oss << "STATUS_" << status;
        return oss.str();
      }
    }
  }

  static std::string PixelFormatString(int pixel_format) {
    switch (pixel_format) {
      case kPixelFormatDepth1Mm: return "DEPTH_1_MM";
      case kPixelFormatDepth100Um: return "DEPTH_100_UM";
      case kPixelFormatRgb888: return "RGB888";
      case kPixelFormatYuv422: return "YUV422";
      case kPixelFormatGray8: return "GRAY8";
      case kPixelFormatGray16: return "GRAY16";
      case kPixelFormatJpeg: return "JPEG";
      case kPixelFormatYuyv: return "YUYV";
      default: {
        std::ostringstream oss;
        oss << "PIXEL_" << pixel_format;
        return oss.str();
      }
    }
  }

  using FnOniInitialize = int (*)(int);
  using FnOniShutdown = void (*)();
  using FnOniGetVersion = OpenNIOniVersion (*)();
  using FnOniGetExtendedError = const char* (*)();
  using FnOniGetDeviceList = int (*)(OpenNIOniDeviceInfo**, int*);
  using FnOniReleaseDeviceList = int (*)(OpenNIOniDeviceInfo*);
  using FnOniDeviceOpen = int (*)(const char*, OpenNIOniDeviceHandle*);
  using FnOniDeviceClose = int (*)(OpenNIOniDeviceHandle);
  using FnOniDeviceGetSensorInfo =
      const OpenNIOniSensorInfo* (*)(OpenNIOniDeviceHandle, int);
  using FnOniDeviceCreateStream =
      int (*)(OpenNIOniDeviceHandle, int, OpenNIOniStreamHandle*);
  using FnOniStreamDestroy = void (*)(OpenNIOniStreamHandle);
  using FnOniStreamStart = int (*)(OpenNIOniStreamHandle);
  using FnOniStreamStop = void (*)(OpenNIOniStreamHandle);
  using FnOniWaitForAnyStream =
      int (*)(OpenNIOniStreamHandle*, int, int*, int);
  using FnOniStreamReadFrame =
      int (*)(OpenNIOniStreamHandle, OpenNIOniFrame**);
  using FnOniFrameRelease = void (*)(OpenNIOniFrame*);
  using FnOniStreamGetProperty =
      int (*)(OpenNIOniStreamHandle, int, void*, int*);

  FnOniInitialize oniInitialize = nullptr;
  FnOniShutdown oniShutdown = nullptr;
  FnOniGetVersion oniGetVersion = nullptr;
  FnOniGetExtendedError oniGetExtendedError = nullptr;
  FnOniGetDeviceList oniGetDeviceList = nullptr;
  FnOniReleaseDeviceList oniReleaseDeviceList = nullptr;
  FnOniDeviceOpen oniDeviceOpen = nullptr;
  FnOniDeviceClose oniDeviceClose = nullptr;
  FnOniDeviceGetSensorInfo oniDeviceGetSensorInfo = nullptr;
  FnOniDeviceCreateStream oniDeviceCreateStream = nullptr;
  FnOniStreamDestroy oniStreamDestroy = nullptr;
  FnOniStreamStart oniStreamStart = nullptr;
  FnOniStreamStop oniStreamStop = nullptr;
  FnOniWaitForAnyStream oniWaitForAnyStream = nullptr;
  FnOniStreamReadFrame oniStreamReadFrame = nullptr;
  FnOniFrameRelease oniFrameRelease = nullptr;
  FnOniStreamGetProperty oniStreamGetProperty = nullptr;

 private:
  template <typename Fn>
  Fn LoadSymbol(const char* name) {
    dlerror();
    void* symbol = dlsym(handle_, name);
    if (symbol == nullptr) {
      throw std::runtime_error(
          std::string("OPENNI_SYMBOL_LOAD_FAILED: ") + name + ": " + DlError());
    }
    return reinterpret_cast<Fn>(symbol);
  }

  static std::string DlError() {
    const char* error = dlerror();
    return error == nullptr ? "unknown" : error;
  }

  std::string library_path_;
  void* handle_ = nullptr;
};

class OpenNIColorCamera {
 public:
  OpenNIColorCamera(const std::string& source, const Args& args)
      : source_(source),
        wait_timeout_ms_(std::max(1000, args.queue_push_timeout_ms_override > 0
                                            ? args.queue_push_timeout_ms_override
                                            : 3000)) {
    Open();
  }

  ~OpenNIColorCamera() { Close(); }

  OpenNIColorCamera(const OpenNIColorCamera&) = delete;
  OpenNIColorCamera& operator=(const OpenNIColorCamera&) = delete;

  int width() const { return width_; }
  int height() const { return height_; }
  double fps() const { return fps_ > 0.0 ? fps_ : 30.0; }
  const std::string& fps_basis() const { return fps_basis_; }

  cv::Mat Read() {
    if (stream_ == nullptr) {
      throw std::runtime_error("OPENNI_STREAM_NOT_OPEN");
    }
    OpenNIOniStreamHandle streams[1] = {stream_};
    int ready_index = -1;
    const int wait_status = api_->oniWaitForAnyStream(streams, 1, &ready_index, wait_timeout_ms_);
    if (wait_status != OpenNI2Api::kStatusOk) {
      throw std::runtime_error(
          "OPENNI_WAIT_FAILED: " + FormatStatus("oniWaitForAnyStream", wait_status));
    }
    OpenNIOniFrame* frame = nullptr;
    const int read_status = api_->oniStreamReadFrame(stream_, &frame);
    if (read_status != OpenNI2Api::kStatusOk || frame == nullptr) {
      throw std::runtime_error(
          "OPENNI_READ_FAILED: " + FormatStatus("oniStreamReadFrame", read_status));
    }
    cv::Mat bgr;
    try {
      bgr = ConvertFrameToBgr(*frame);
    } catch (...) {
      api_->oniFrameRelease(frame);
      throw;
    }
    api_->oniFrameRelease(frame);
    return bgr;
  }

 private:
  static std::string ResolveLibraryPath() {
    const char* env = std::getenv("OPENNI2_LIBRARY");
    if (env != nullptr && *env != '\0') return env;
    return "/usr/lib/libOpenNI2.so";
  }

  void Open() {
    try {
      api_ = std::make_unique<OpenNI2Api>(ResolveLibraryPath());
      const OpenNIOniVersion version = api_->oniGetVersion();
      const int api_version = version.major * 1000 + version.minor;
      const int init_status = api_->oniInitialize(api_version);
      if (init_status != OpenNI2Api::kStatusOk) {
        throw std::runtime_error("OPENNI_INIT_FAILED: " + FormatStatus("oniInitialize", init_status));
      }
      initialized_ = true;

      OpenNIOniDeviceInfo* device_list = nullptr;
      int device_count = 0;
      const int list_status = api_->oniGetDeviceList(&device_list, &device_count);
      if (list_status != OpenNI2Api::kStatusOk) {
        throw std::runtime_error("OPENNI_ENUM_FAILED: " + FormatStatus("oniGetDeviceList", list_status));
      }
      if (device_count <= 0 || device_list == nullptr) {
        api_->oniReleaseDeviceList(device_list);
        throw std::runtime_error("OPENNI_NO_DEVICE");
      }

      const int device_index = SelectDeviceIndex(device_list, device_count);
      source_description_ = DescribeDevice(device_list[device_index]);
      const int open_status = api_->oniDeviceOpen(device_list[device_index].uri, &device_);
      api_->oniReleaseDeviceList(device_list);
      if (open_status != OpenNI2Api::kStatusOk) {
        throw std::runtime_error("OPENNI_DEVICE_OPEN_FAILED: " + FormatStatus("oniDeviceOpen", open_status));
      }

      const OpenNIOniSensorInfo* sensor_info =
          api_->oniDeviceGetSensorInfo(device_, OpenNI2Api::kSensorColor);
      if (sensor_info == nullptr) {
        throw std::runtime_error("OPENNI_COLOR_SENSOR_MISSING");
      }

      const int create_status =
          api_->oniDeviceCreateStream(device_, OpenNI2Api::kSensorColor, &stream_);
      if (create_status != OpenNI2Api::kStatusOk) {
        throw std::runtime_error(
            "OPENNI_STREAM_CREATE_FAILED: " + FormatStatus("oniDeviceCreateStream", create_status));
      }

      RefreshModeMetadata();
      const int start_status = api_->oniStreamStart(stream_);
      if (start_status != OpenNI2Api::kStatusOk) {
        throw std::runtime_error("OPENNI_STREAM_START_FAILED: " + FormatStatus("oniStreamStart", start_status));
      }
    } catch (...) {
      Close();
      throw;
    }
  }

  void Close() {
    if (api_ != nullptr && stream_ != nullptr) {
      api_->oniStreamStop(stream_);
      api_->oniStreamDestroy(stream_);
      stream_ = nullptr;
    }
    if (api_ != nullptr && device_ != nullptr) {
      api_->oniDeviceClose(device_);
      device_ = nullptr;
    }
    if (api_ != nullptr && initialized_) {
      api_->oniShutdown();
      initialized_ = false;
    }
    api_.reset();
  }

  int SelectDeviceIndex(const OpenNIOniDeviceInfo* devices, int count) const {
    const std::string selector = Trim(source_);
    if (selector.empty() || selector == "openni_default") return 0;
    if (IsNonNegativeInteger(selector)) {
      const int index = std::stoi(selector);
      if (index < 0 || index >= count) {
        throw std::runtime_error(
            "OPENNI_DEVICE_INDEX_OUT_OF_RANGE: index=" + std::to_string(index) +
            " count=" + std::to_string(count));
      }
      return index;
    }
    for (int i = 0; i < count; ++i) {
      if (selector == devices[i].uri) return i;
    }
    const std::string wanted = ToUpper(selector);
    for (int i = 0; i < count; ++i) {
      const std::string candidate = ToUpper(DescribeDevice(devices[i]));
      if (candidate.find(wanted) != std::string::npos) return i;
    }
    throw std::runtime_error("OPENNI_DEVICE_NOT_FOUND: selector=" + selector);
  }

  static std::string DescribeDevice(const OpenNIOniDeviceInfo& info) {
    std::ostringstream oss;
    oss << info.vendor << " " << info.name << " uri=" << info.uri
        << " usb_vidpid=" << std::hex << std::setw(4) << std::setfill('0')
        << info.usbVendorId << ":" << std::setw(4) << info.usbProductId << std::dec;
    return oss.str();
  }

  std::string FormatStatus(const std::string& op, int status) const {
    std::ostringstream oss;
    oss << op << " status=" << OpenNI2Api::StatusString(status);
    const std::string extended_error = api_ != nullptr ? api_->ExtendedError() : "";
    if (!extended_error.empty()) {
      oss << " extended_error=" << extended_error;
      if (extended_error.find("Access denied") != std::string::npos) {
        oss << " hint=fix_udev_permissions_or_run_with_sudo_temporarily";
      }
    }
    if (!source_description_.empty()) {
      oss << " device=" << source_description_;
    }
    return oss.str();
  }

  void RefreshModeMetadata() {
    if (stream_ == nullptr) return;
    OpenNIOniVideoMode mode{};
    int size = sizeof(mode);
    const int status =
        api_->oniStreamGetProperty(stream_, OpenNI2Api::kStreamPropertyVideoMode, &mode, &size);
    if (status != OpenNI2Api::kStatusOk) {
      width_ = 640;
      height_ = 480;
      fps_ = 30.0;
      fps_basis_ = "openni_default_fallback";
      return;
    }
    width_ = mode.resolutionX;
    height_ = mode.resolutionY;
    fps_ = mode.fps > 0 ? static_cast<double>(mode.fps) : 30.0;
    fps_basis_ = "openni_stream_mode";
    pixel_format_ = mode.pixelFormat;
  }

  cv::Mat ConvertFrameToBgr(const OpenNIOniFrame& frame) const {
    const int width = frame.width > 0 ? frame.width : width_;
    const int height = frame.height > 0 ? frame.height : height_;
    if (width <= 0 || height <= 0 || frame.data == nullptr) {
      throw std::runtime_error("OPENNI_FRAME_INVALID");
    }

    switch (frame.videoMode.pixelFormat) {
      case OpenNI2Api::kPixelFormatRgb888: {
        const cv::Mat rgb(height, width, CV_8UC3, frame.data, frame.stride);
        cv::Mat bgr;
        cv::cvtColor(rgb, bgr, cv::COLOR_RGB2BGR);
        return bgr;
      }
      case OpenNI2Api::kPixelFormatYuyv:
      case OpenNI2Api::kPixelFormatYuv422: {
        const cv::Mat yuyv(height, width, CV_8UC2, frame.data, frame.stride);
        cv::Mat bgr;
        cv::cvtColor(yuyv, bgr, cv::COLOR_YUV2BGR_YUY2);
        return bgr;
      }
      case OpenNI2Api::kPixelFormatGray8: {
        const cv::Mat gray(height, width, CV_8UC1, frame.data, frame.stride);
        cv::Mat bgr;
        cv::cvtColor(gray, bgr, cv::COLOR_GRAY2BGR);
        return bgr;
      }
      case OpenNI2Api::kPixelFormatGray16:
      case OpenNI2Api::kPixelFormatDepth1Mm:
      case OpenNI2Api::kPixelFormatDepth100Um: {
        const cv::Mat gray16(height, width, CV_16UC1, frame.data, frame.stride);
        cv::Mat gray8;
        gray16.convertTo(gray8, CV_8U, 1.0 / 256.0);
        cv::Mat bgr;
        cv::cvtColor(gray8, bgr, cv::COLOR_GRAY2BGR);
        return bgr;
      }
      default:
        throw std::runtime_error(
            "OPENNI_UNSUPPORTED_PIXEL_FORMAT: " +
            OpenNI2Api::PixelFormatString(frame.videoMode.pixelFormat));
    }
  }

  std::string source_;
  std::string source_description_;
  int wait_timeout_ms_ = 3000;
  bool initialized_ = false;
  std::unique_ptr<OpenNI2Api> api_;
  OpenNIOniDeviceHandle device_ = nullptr;
  OpenNIOniStreamHandle stream_ = nullptr;
  int width_ = 0;
  int height_ = 0;
  double fps_ = 30.0;
  int pixel_format_ = OpenNI2Api::kPixelFormatRgb888;
  std::string fps_basis_ = "openni_stream_mode";
};

class V4L2RawCamera {
 public:
  V4L2RawCamera(const std::string& source, const Args& args)
      : device_(CameraDevicePath(source)),
        requested_width_(args.v4l2_width),
        requested_height_(args.v4l2_height),
        requested_sensor_mode_(args.v4l2_sensor_mode),
        requested_fps_(args.v4l2_fps),
        width_(args.v4l2_width),
        height_(args.v4l2_height),
        bayer_pattern_(args.bayer_pattern),
        normalize_mode_(CanonicalizeV4l2NormalizeMode(args.v4l2_normalize_mode)),
        apply_white_balance_(!args.v4l2_disable_white_balance) {
    Open(args);
  }

  ~V4L2RawCamera() { Close(); }

  V4L2RawCamera(const V4L2RawCamera&) = delete;
  V4L2RawCamera& operator=(const V4L2RawCamera&) = delete;

  int width() const { return width_; }
  int height() const { return height_; }
  double fps() const { return effective_fps_ > 0.0 ? effective_fps_ : requested_fps_; }
  const std::string& fps_basis() const { return fps_basis_; }

  cv::Mat Read() {
    const auto read_started = Clock::now();
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(fd_, &fds);
    timeval tv{};
    tv.tv_sec = 3;
    const int ready = select(fd_ + 1, &fds, nullptr, nullptr, &tv);
    if (ready == -1) ThrowErrno("select failed for V4L2 raw camera");
    if (ready == 0) {
      throw std::runtime_error("timeout waiting for V4L2 raw camera frame: " + device_);
    }

    v4l2_buffer buf{};
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    if (Xioctl(fd_, VIDIOC_DQBUF, &buf) == -1) ThrowErrno("VIDIOC_DQBUF failed");
    if (buf.index >= buffers_.size()) {
      throw std::runtime_error("V4L2 returned invalid buffer index");
    }
    const auto dequeue_finished = Clock::now();

    cv::Mat frame_bgr;
    try {
      cv::Mat raw16(height_, width_, CV_16UC1, buffers_[buf.index].start, bytes_per_line_);
      RawBayerConversionProfile profile;
      frame_bgr = Raw16BayerToBgr(raw16,
                                  bayer_pattern_,
                                  normalize_mode_,
                                  apply_white_balance_,
                                  &profile,
                                  &raw8_scratch_,
                                  &normalize_samples_scratch_);
      total_read_ms_ += MsSince(read_started);
      total_wait_and_dequeue_ms_ +=
          std::chrono::duration<double, std::milli>(dequeue_finished - read_started).count();
      total_normalize_ms_ += profile.normalize_ms;
      total_debayer_ms_ += profile.debayer_ms;
      total_white_balance_ms_ += profile.white_balance_ms;
      ++profile_frames_;
    } catch (...) {
      (void)Xioctl(fd_, VIDIOC_QBUF, &buf);
      throw;
    }

    if (Xioctl(fd_, VIDIOC_QBUF, &buf) == -1) ThrowErrno("VIDIOC_QBUF failed after read");
    return frame_bgr;
  }

 private:
  struct Buffer {
    void* start = nullptr;
    size_t length = 0;
  };

  void Open(const Args& args) {
    constexpr uint32_t kCidArgusSensorMode = 0x009a2008;
    constexpr uint32_t kCidArgusGain = 0x009a2009;
    constexpr uint32_t kCidArgusExposure = 0x009a200a;
    constexpr uint32_t kCidArgusFrameRate = 0x009a200b;
    constexpr uint32_t kCidArgusBypassMode = 0x009a2064;
    constexpr uint32_t kCidArgusOverrideEnable = 0x009a2065;

    fd_ = open(device_.c_str(), O_RDWR | O_NONBLOCK, 0);
    if (fd_ == -1) ThrowErrno("failed to open V4L2 raw camera " + device_);

    v4l2_capability cap{};
    if (Xioctl(fd_, VIDIOC_QUERYCAP, &cap) == -1) ThrowErrno("VIDIOC_QUERYCAP failed");
    if ((cap.capabilities & V4L2_CAP_VIDEO_CAPTURE) == 0 ||
        (cap.capabilities & V4L2_CAP_STREAMING) == 0) {
      throw std::runtime_error("V4L2 device does not support capture+streaming: " + device_);
    }

    SetInt64Control(kCidArgusSensorMode, args.v4l2_sensor_mode, false, "sensor_mode_pre_fmt");
    SetControl(kCidArgusBypassMode, 0, false, "bypass_mode");

    v4l2_format fmt{};
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width = static_cast<uint32_t>(width_);
    fmt.fmt.pix.height = static_cast<uint32_t>(height_);
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_SRGGB10;
    fmt.fmt.pix.field = V4L2_FIELD_NONE;
    if (Xioctl(fd_, VIDIOC_S_FMT, &fmt) == -1) ThrowErrno("VIDIOC_S_FMT RG10 failed");
    width_ = static_cast<int>(fmt.fmt.pix.width);
    height_ = static_cast<int>(fmt.fmt.pix.height);
    bytes_per_line_ = static_cast<int>(fmt.fmt.pix.bytesperline);
    if (bytes_per_line_ <= 0) {
      bytes_per_line_ = width_ * static_cast<int>(sizeof(uint16_t));
    }
    if (fmt.fmt.pix.pixelformat != V4L2_PIX_FMT_SRGGB10) {
      throw std::runtime_error("V4L2 device did not accept RG10 pixel format");
    }

    SetInt64Control(kCidArgusSensorMode, args.v4l2_sensor_mode, false, "sensor_mode_post_fmt");
    // IMX219 V4L2 controls are sticky across runs. If a previous run enabled
    // manual exposure, later "default" runs can silently inherit that stale
    // state and collapse to ~2 FPS / near-black preview. Treat "unspecified"
    // as "return to non-override mode" so ordinary runs do not depend on the
    // control state left behind by an earlier experiment.
    SetControl(kCidArgusOverrideEnable, 0, false, "override_enable_reset");
    ConfigureStreamParameters(args.v4l2_fps);
    InitMmap();
    StartStreaming();
    RefreshEffectiveConfig(kCidArgusSensorMode, kCidArgusFrameRate, kCidArgusGain,
                           kCidArgusExposure, kCidArgusOverrideEnable);
  }

  void SetInt64Control(uint32_t id, int64_t value, bool required, const std::string& name) {
    v4l2_ext_control control{};
    control.id = id;
    control.value64 = value;
    v4l2_ext_controls controls{};
    controls.ctrl_class = V4L2_CTRL_ID2CLASS(id);
    controls.count = 1;
    controls.controls = &control;
    if (Xioctl(fd_, VIDIOC_S_EXT_CTRLS, &controls) == -1) {
      if (required) ThrowErrno("VIDIOC_S_EXT_CTRLS " + name + " failed");
      std::cerr << "[WARN] VIDIOC_S_EXT_CTRLS " << name << "=" << value
                << " failed: " << std::strerror(errno) << "\n";
    }
  }

  bool GetInt64Control(uint32_t id, int64_t* value, const std::string& name) {
    v4l2_ext_control control{};
    control.id = id;
    v4l2_ext_controls controls{};
    controls.ctrl_class = V4L2_CTRL_ID2CLASS(id);
    controls.count = 1;
    controls.controls = &control;
    if (Xioctl(fd_, VIDIOC_G_EXT_CTRLS, &controls) == -1) {
      std::cerr << "[WARN] VIDIOC_G_EXT_CTRLS " << name
                << " failed: " << std::strerror(errno) << "\n";
      return false;
    }
    if (value != nullptr) *value = control.value64;
    return true;
  }

  void SetControl(uint32_t id, int32_t value, bool required, const std::string& name) {
    v4l2_control control{};
    control.id = id;
    control.value = value;
    if (Xioctl(fd_, VIDIOC_S_CTRL, &control) == -1) {
      if (required) ThrowErrno("VIDIOC_S_CTRL " + name + " failed");
      std::cerr << "[WARN] VIDIOC_S_CTRL " << name << "=" << value
                << " failed: " << std::strerror(errno) << "\n";
    }
  }

  bool GetControl(uint32_t id, int32_t* value, const std::string& name) {
    v4l2_control control{};
    control.id = id;
    if (Xioctl(fd_, VIDIOC_G_CTRL, &control) == -1) {
      std::cerr << "[WARN] VIDIOC_G_CTRL " << name
                << " failed: " << std::strerror(errno) << "\n";
      return false;
    }
    if (value != nullptr) *value = control.value;
    return true;
  }

  void ConfigureStreamParameters(double requested_fps) {
    effective_fps_ = requested_fps;
    fps_basis_ = "requested_fallback";
    if (requested_fps <= 0.0) return;

    v4l2_streamparm parm{};
    parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    parm.parm.capture.timeperframe.numerator = 1;
    parm.parm.capture.timeperframe.denominator =
        static_cast<uint32_t>(std::max<int64_t>(1, std::llround(requested_fps)));
    if (Xioctl(fd_, VIDIOC_S_PARM, &parm) == -1) {
      std::cerr << "[WARN] VIDIOC_S_PARM fps=" << requested_fps
                << " failed: " << std::strerror(errno) << "\n";
    }
  }

  void RefreshEffectiveConfig(uint32_t sensor_mode_id,
                              uint32_t frame_rate_id,
                              uint32_t gain_id,
                              uint32_t exposure_id,
                              uint32_t override_enable_id) {
    v4l2_format fmt{};
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (Xioctl(fd_, VIDIOC_G_FMT, &fmt) == -1) {
      std::cerr << "[WARN] VIDIOC_G_FMT failed: " << std::strerror(errno) << "\n";
    } else {
      width_ = static_cast<int>(fmt.fmt.pix.width);
      height_ = static_cast<int>(fmt.fmt.pix.height);
      bytes_per_line_ = static_cast<int>(fmt.fmt.pix.bytesperline);
      if (bytes_per_line_ <= 0) {
        bytes_per_line_ = width_ * static_cast<int>(sizeof(uint16_t));
      }
      pixel_format_ = fmt.fmt.pix.pixelformat;
    }

    v4l2_streamparm parm{};
    parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (Xioctl(fd_, VIDIOC_G_PARM, &parm) == -1) {
      std::cerr << "[WARN] VIDIOC_G_PARM failed: " << std::strerror(errno) << "\n";
      streamparm_numerator_ = 0;
      streamparm_denominator_ = 0;
      effective_fps_ = requested_fps_;
      fps_basis_ = "requested_fallback";
    } else {
      streamparm_numerator_ = parm.parm.capture.timeperframe.numerator;
      streamparm_denominator_ = parm.parm.capture.timeperframe.denominator;
      const double readback_fps =
          FpsFromTimePerFrame(streamparm_numerator_, streamparm_denominator_);
      if (readback_fps > 0.0) {
        effective_fps_ = readback_fps;
        fps_basis_ = "v4l2_streamparm";
      } else {
        effective_fps_ = requested_fps_;
        fps_basis_ = "requested_fallback";
      }
    }

    int64_t value64 = 0;
    effective_sensor_mode_ =
        GetInt64Control(sensor_mode_id, &value64, "sensor_mode")
            ? static_cast<int>(value64)
            : -1;
    effective_frame_rate_ctrl_ =
        GetInt64Control(frame_rate_id, &value64, "frame_rate") ? value64 : -1;
    effective_gain_ = GetInt64Control(gain_id, &value64, "gain") ? value64 : -1;
    effective_exposure_ = GetInt64Control(exposure_id, &value64, "exposure") ? value64 : -1;
    int32_t value32 = -1;
    effective_override_enable_ =
        GetControl(override_enable_id, &value32, "override_enable") ? value32 : -1;
    LogEffectiveConfig();
  }

  void LogEffectiveConfig() const {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(3)
        << "V4L2_EFFECTIVE_CONFIG: device=" << device_
        << " requested=" << requested_width_ << "x" << requested_height_
        << "@" << requested_fps_
        << " actual=" << width_ << "x" << height_
        << "@" << fps()
        << " source_fps_basis=" << fps_basis_
        << " sensor_mode_requested=" << requested_sensor_mode_;
    if (effective_sensor_mode_ >= 0) {
      oss << " sensor_mode_effective=" << effective_sensor_mode_;
    } else {
      oss << " sensor_mode_effective=unavailable";
    }
    if (streamparm_numerator_ > 0 && streamparm_denominator_ > 0) {
      oss << " timeperframe=" << streamparm_numerator_ << "/" << streamparm_denominator_;
    } else {
      oss << " timeperframe=unavailable";
    }
    if (effective_frame_rate_ctrl_ >= 0) {
      oss << " frame_rate_ctrl=" << effective_frame_rate_ctrl_;
    } else {
      oss << " frame_rate_ctrl=unavailable";
    }
    oss << " override_enable_forced_reset=0";
    if (effective_override_enable_ >= 0) {
      oss << " override_enable_effective=" << effective_override_enable_;
    } else {
      oss << " override_enable_effective=unavailable";
    }
    if (effective_gain_ >= 0) {
      oss << " gain_effective=" << effective_gain_;
    } else {
      oss << " gain_effective=unavailable";
    }
    if (effective_exposure_ >= 0) {
      oss << " exposure_effective=" << effective_exposure_;
    } else {
      oss << " exposure_effective=unavailable";
    }
    oss << " pixelformat=" << FourCcToString(pixel_format_)
        << " bytesperline=" << bytes_per_line_
        << " normalize_mode=" << normalize_mode_
        << " grayworld_white_balance=" << (apply_white_balance_ ? "true" : "false");
    if (normalize_mode_ == "fixed_10bit") {
      oss << " fixed10_decode=msb_aligned_shift8";
    }
    std::cout << oss.str() << "\n";
  }

  void LogCaptureProfile() const {
    if (profile_frames_ == 0) return;
    const auto avg = [&](double total_ms) {
      return total_ms / static_cast<double>(profile_frames_);
    };
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(3)
        << "V4L2_CAPTURE_PROFILE: device=" << device_
        << " frames=" << profile_frames_
        << " avg_total_read_ms=" << avg(total_read_ms_)
        << " avg_wait_and_dequeue_ms=" << avg(total_wait_and_dequeue_ms_)
        << " avg_normalize_ms=" << avg(total_normalize_ms_)
        << " avg_debayer_ms=" << avg(total_debayer_ms_)
        << " avg_white_balance_ms=" << avg(total_white_balance_ms_)
        << " avg_convert_only_ms="
        << avg(total_normalize_ms_ + total_debayer_ms_ + total_white_balance_ms_);
    std::cout << oss.str() << "\n";
  }

  void InitMmap() {
    v4l2_requestbuffers req{};
    req.count = 4;
    req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    if (Xioctl(fd_, VIDIOC_REQBUFS, &req) == -1) ThrowErrno("VIDIOC_REQBUFS failed");
    if (req.count < 2) throw std::runtime_error("insufficient V4L2 mmap buffers");

    buffers_.resize(req.count);
    for (uint32_t index = 0; index < req.count; ++index) {
      v4l2_buffer buf{};
      buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
      buf.memory = V4L2_MEMORY_MMAP;
      buf.index = index;
      if (Xioctl(fd_, VIDIOC_QUERYBUF, &buf) == -1) ThrowErrno("VIDIOC_QUERYBUF failed");
      buffers_[index].length = buf.length;
      buffers_[index].start = mmap(nullptr, buf.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, buf.m.offset);
      if (buffers_[index].start == MAP_FAILED) {
        buffers_[index].start = nullptr;
        ThrowErrno("mmap failed for V4L2 buffer");
      }
    }
  }

  void StartStreaming() {
    for (uint32_t index = 0; index < buffers_.size(); ++index) {
      v4l2_buffer buf{};
      buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
      buf.memory = V4L2_MEMORY_MMAP;
      buf.index = index;
      if (Xioctl(fd_, VIDIOC_QBUF, &buf) == -1) ThrowErrno("VIDIOC_QBUF failed");
    }
    v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (Xioctl(fd_, VIDIOC_STREAMON, &type) == -1) ThrowErrno("VIDIOC_STREAMON failed");
    streaming_ = true;
  }

  void Close() {
    LogCaptureProfile();
    if (fd_ != -1 && streaming_) {
      v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
      (void)Xioctl(fd_, VIDIOC_STREAMOFF, &type);
      streaming_ = false;
    }
    for (Buffer& buffer : buffers_) {
      if (buffer.start != nullptr && buffer.length > 0) {
        munmap(buffer.start, buffer.length);
        buffer.start = nullptr;
        buffer.length = 0;
      }
    }
    if (fd_ != -1) {
      close(fd_);
      fd_ = -1;
    }
  }

  std::string device_;
  int fd_ = -1;
  int requested_width_ = 0;
  int requested_height_ = 0;
  int requested_sensor_mode_ = -1;
  double requested_fps_ = 0.0;
  int width_ = 0;
  int height_ = 0;
  int bytes_per_line_ = 0;
  uint32_t pixel_format_ = V4L2_PIX_FMT_SRGGB10;
  std::string bayer_pattern_;
  std::string normalize_mode_ = "percentile";
  bool apply_white_balance_ = true;
  bool streaming_ = false;
  std::vector<Buffer> buffers_;
  cv::Mat raw8_scratch_;
  std::vector<uint16_t> normalize_samples_scratch_;
  double effective_fps_ = 0.0;
  std::string fps_basis_ = "unknown";
  uint32_t streamparm_numerator_ = 0;
  uint32_t streamparm_denominator_ = 0;
  int effective_sensor_mode_ = -1;
  int64_t effective_frame_rate_ctrl_ = -1;
  int64_t effective_gain_ = -1;
  int64_t effective_exposure_ = -1;
  int effective_override_enable_ = -1;
  size_t profile_frames_ = 0;
  double total_read_ms_ = 0.0;
  double total_wait_and_dequeue_ms_ = 0.0;
  double total_normalize_ms_ = 0.0;
  double total_debayer_ms_ = 0.0;
  double total_white_balance_ms_ = 0.0;
};
#endif

#if defined(__linux__)
class SrcampyPipeCamera {
 public:
  static constexpr int kStreamFd = 3;

  SrcampyPipeCamera(const std::string& source, const Args& args)
      : source_(source.empty() ? ("srcampy://video_idx" + std::to_string(args.srcampy_video_idx))
                               : source),
        python_bin_(args.srcampy_python),
        script_path_(args.srcampy_stream_script),
        video_idx_(args.srcampy_video_idx),
        width_(args.srcampy_width),
        height_(args.srcampy_height),
        sensor_width_(args.srcampy_sensor_width),
        sensor_height_(args.srcampy_sensor_height),
        fps_(args.srcampy_fps > 0.0 ? args.srcampy_fps : 30.0),
        warmup_(std::max(0, args.srcampy_warmup)),
        startup_timeout_sec_(args.srcampy_startup_timeout_sec > 0.0
                                 ? args.srcampy_startup_timeout_sec
                                 : 8.0) {
    Open();
  }

  ~SrcampyPipeCamera() { Close(); }

  SrcampyPipeCamera(const SrcampyPipeCamera&) = delete;
  SrcampyPipeCamera& operator=(const SrcampyPipeCamera&) = delete;

  int width() const { return width_; }
  int height() const { return height_; }
  double fps() const { return fps_; }
  const std::string& fps_basis() const { return fps_basis_; }

  cv::Mat Read() {
    if (stream_ == nullptr) {
      throw std::runtime_error("SRCAMPY_STREAM_NOT_OPEN");
    }

    std::string header_line;
    if (!ReadHeaderLine(header_line)) {
      throw std::runtime_error("SRCAMPY_STREAM_EOF: " + WaitSummary());
    }

    std::istringstream iss(header_line);
    std::string frame_tag;
    int frame_id = -1;
    int width = 0;
    int height = 0;
    size_t payload_size = 0;
    iss >> frame_tag >> frame_id >> width >> height >> payload_size;
    if (frame_tag != "FRAME" || frame_id < 0 || width <= 0 || height <= 0 || payload_size == 0) {
      throw std::runtime_error("SRCAMPY_STREAM_BAD_HEADER: " + header_line);
    }

    const size_t expected = static_cast<size_t>(width) * static_cast<size_t>(height) * 3 / 2;
    if (payload_size != expected) {
      std::ostringstream oss;
      oss << "SRCAMPY_STREAM_SIZE_MISMATCH: got=" << payload_size
          << " expected=" << expected
          << " header=" << header_line;
      throw std::runtime_error(oss.str());
    }

    payload_.resize(payload_size);
    ReadExact(payload_.data(), payload_size);
    last_frame_id_ = frame_id;

    const cv::Mat nv12(height * 3 / 2, width, CV_8UC1, payload_.data());
    cv::Mat bgr;
    cv::cvtColor(nv12, bgr, cv::COLOR_YUV2BGR_NV12);
    return bgr;
  }

 private:
  void Open() {
    if (width_ <= 0 || height_ <= 0) {
      throw std::runtime_error("SRCAMPY_STREAM_INVALID_DIMENSION");
    }
    if (python_bin_.empty()) {
      throw std::runtime_error("SRCAMPY_STREAM_PYTHON_EMPTY");
    }
    if (script_path_.empty()) {
      throw std::runtime_error("SRCAMPY_STREAM_SCRIPT_EMPTY");
    }
    std::ifstream script_probe(script_path_);
    if (!script_probe.good()) {
      throw std::runtime_error("SRCAMPY_STREAM_SCRIPT_MISSING: " + script_path_);
    }

    int pipefd[2] = {-1, -1};
    if (pipe(pipefd) == -1) {
      ThrowErrno("pipe failed for srcampy helper");
    }

    child_pid_ = fork();
    if (child_pid_ == -1) {
      close(pipefd[0]);
      close(pipefd[1]);
      ThrowErrno("fork failed for srcampy helper");
    }

    if (child_pid_ == 0) {
      if (dup2(pipefd[1], kStreamFd) == -1) {
        std::perror("dup2 failed for srcampy helper stream fd");
        _exit(127);
      }
      close(pipefd[0]);
      close(pipefd[1]);

      const std::string video_idx = std::to_string(video_idx_);
      const std::string width = std::to_string(width_);
      const std::string height = std::to_string(height_);
      const std::string sensor_width = std::to_string(sensor_width_);
      const std::string sensor_height = std::to_string(sensor_height_);
      const std::string warmup = std::to_string(warmup_);
      const std::string startup_timeout = FormatFloat(startup_timeout_sec_);
      const std::string stream_fd = std::to_string(kStreamFd);

      std::vector<std::string> argv_storage = {
          python_bin_,
          script_path_,
          "--video-idx",
          video_idx,
          "--width",
          width,
          "--height",
          height,
          "--sensor-width",
          sensor_width,
          "--sensor-height",
          sensor_height,
          "--warmup",
          warmup,
          "--startup-timeout-sec",
          startup_timeout,
          "--stream-fd",
          stream_fd,
      };
      std::vector<char*> argv;
      argv.reserve(argv_storage.size() + 1);
      for (std::string& part : argv_storage) {
        argv.push_back(part.data());
      }
      argv.push_back(nullptr);
      execvp(python_bin_.c_str(), argv.data());
      std::perror("execvp failed for srcampy helper");
      _exit(127);
    }

    close(pipefd[1]);
    stream_ = fdopen(pipefd[0], "rb");
    if (stream_ == nullptr) {
      close(pipefd[0]);
      ThrowErrno("fdopen failed for srcampy helper");
    }
  }

  void Close() {
    if (stream_ != nullptr) {
      fclose(stream_);
      stream_ = nullptr;
    }
    if (child_pid_ > 0 && !child_exited_) {
      kill(child_pid_, SIGTERM);
      WaitForChildBlocking();
    }
    child_pid_ = -1;
  }

  bool ReadHeaderLine(std::string& line) {
    line.clear();
    std::array<char, 256> buffer{};
    if (std::fgets(buffer.data(), static_cast<int>(buffer.size()), stream_) == nullptr) {
      return false;
    }
    line.assign(buffer.data());
    while (!line.empty() && (line.back() == '\n' || line.back() == '\r')) {
      line.pop_back();
    }
    return !line.empty();
  }

  void ReadExact(void* dst, size_t bytes) {
    uint8_t* ptr = static_cast<uint8_t*>(dst);
    size_t offset = 0;
    while (offset < bytes) {
      const size_t n = std::fread(ptr + offset, 1, bytes - offset, stream_);
      if (n == 0) {
        if (std::feof(stream_)) {
          throw std::runtime_error("SRCAMPY_STREAM_UNEXPECTED_EOF: " + WaitSummary());
        }
        if (std::ferror(stream_)) {
          ThrowErrno("fread failed for srcampy helper");
        }
      }
      offset += n;
    }
  }

  void WaitForChildBlocking() {
    if (child_pid_ <= 0 || child_exited_) return;
    int status = 0;
    const pid_t waited = waitpid(child_pid_, &status, 0);
    if (waited > 0) {
      child_status_ = status;
      child_exited_ = true;
    }
  }

  void PollChildStatus() const {
    if (child_pid_ <= 0 || child_exited_) return;
    int status = 0;
    const pid_t waited = waitpid(child_pid_, &status, WNOHANG);
    if (waited > 0) {
      child_status_ = status;
      child_exited_ = true;
    }
  }

  std::string WaitSummary() const {
    PollChildStatus();
    std::ostringstream oss;
    oss << "source=" << source_;
    if (!child_exited_) {
      oss << " child_state=running_or_unknown";
      return oss.str();
    }
    if (WIFEXITED(child_status_)) {
      oss << " child_exit=" << WEXITSTATUS(child_status_);
    } else if (WIFSIGNALED(child_status_)) {
      oss << " child_signal=" << WTERMSIG(child_status_);
    } else {
      oss << " child_status=" << child_status_;
    }
    return oss.str();
  }

  static std::string FormatFloat(double value) {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(3) << value;
    return oss.str();
  }

  [[noreturn]] static void ThrowErrno(const std::string& message) {
    throw std::runtime_error(message + ": " + std::strerror(errno));
  }

  std::string source_;
  std::string python_bin_;
  std::string script_path_;
  int video_idx_ = 0;
  int width_ = 640;
  int height_ = 640;
  int sensor_width_ = 1920;
  int sensor_height_ = 1080;
  double fps_ = 30.0;
  int warmup_ = 10;
  double startup_timeout_sec_ = 8.0;
  std::string fps_basis_ = "srcampy_requested";
  mutable bool child_exited_ = false;
  mutable int child_status_ = 0;
  mutable pid_t child_pid_ = -1;
  FILE* stream_ = nullptr;
  int last_frame_id_ = -1;
  std::vector<uint8_t> payload_;
};
#endif

class FrameReader {
 public:
  explicit FrameReader(const Args& args)
      : args_(args),
        playlist_input_(args.input_source_type == "video_playlist" || EndsWith(args.input, ".txt") || EndsWith(args.input, ".lst")),
        file_like_input_(playlist_input_ || args.input_source_type == "video_file"),
        raw_camera_input_(args.v4l2_raw || args.input_source_type == "mipi_camera"),
        srcampy_camera_input_(args.input_source_type == "mipi_camera_hbn"),
        openni_camera_input_(args.input_source_type == "openni_camera"),
        fault_inject_disconnect_after_sec_(args.fault_inject_disconnect_after_sec) {}

  void Open() {
    if (playlist_input_) {
      playlist_paths_ = LoadPlaylistPaths(args_.input);
    }
    if (!OpenCurrentSource()) {
      throw std::runtime_error(last_error_.empty() ? ("INPUT_OPEN_FAILED: " + args_.input) : last_error_);
    }
    opened_at_ = Clock::now();
    fault_disconnect_triggered_ = false;
    initial_width_ = input_w_;
    initial_height_ = input_h_;
  }

  bool Read(cv::Mat& frame) {
    last_error_.clear();
    if (MaybeInjectDisconnect()) {
      frame.release();
      return false;
    }
    if (raw_camera_input_) {
#if defined(__linux__)
      try {
        frame = raw_camera_->Read();
        ApplyOrientationCorrection(frame);
        return !frame.empty();
      } catch (const std::exception& e) {
        last_error_ = e.what();
        return false;
      }
#else
      last_error_ = "V4L2 raw camera mode is only available on Linux";
      return false;
#endif
    }
    if (srcampy_camera_input_) {
#if defined(__linux__)
      try {
        frame = srcampy_camera_->Read();
        ApplyOrientationCorrection(frame);
        return !frame.empty();
      } catch (const std::exception& e) {
        last_error_ = e.what();
        return false;
      }
#else
      last_error_ = "srcampy camera mode is only available on Linux";
      return false;
#endif
    }
    if (openni_camera_input_) {
#if defined(__linux__)
      try {
        frame = openni_camera_->Read();
        ApplyOrientationCorrection(frame);
        return !frame.empty();
      } catch (const std::exception& e) {
        last_error_ = e.what();
        return false;
      }
#else
      last_error_ = "OpenNI camera mode is only available on Linux";
      return false;
#endif
    }
    const bool ok = cap_.read(frame);
    if (!ok) {
      frame.release();
      if (!file_like_input_) {
        std::ostringstream oss;
        oss << "INPUT_READ_FAILED: source=" << CurrentSource()
            << " input_source_type=" << args_.input_source_type;
        last_error_ = oss.str();
      }
      return false;
    }
    ApplyOrientationCorrection(frame);
    return ok;
  }

  bool ReopenLoopSource() {
    last_error_.clear();
    if (!file_like_input_ || raw_camera_input_ || srcampy_camera_input_) return false;
    if (playlist_input_) {
      if (playlist_paths_.empty()) return false;
      cap_.release();
      playlist_index_ = (playlist_index_ + 1) % playlist_paths_.size();
      if (!OpenCurrentSource()) {
        if (last_error_.empty()) last_error_ = "INPUT_OPEN_FAILED: " + CurrentSource();
        return false;
      }
      if (input_w_ != initial_width_ || input_h_ != initial_height_) {
        std::ostringstream oss;
        oss << "INPUT_DIMENSION_MISMATCH: playlist source " << CurrentSource()
            << " has " << input_w_ << "x" << input_h_
            << ", expected " << initial_width_ << "x" << initial_height_;
        last_error_ = oss.str();
        return false;
      }
      return true;
    }
    if (!cap_.isOpened()) {
      last_error_ = "INPUT_OPEN_FAILED: " + CurrentSource();
      return false;
    }
    cap_.set(cv::CAP_PROP_POS_FRAMES, 0);
    RefreshMetadata();
    ConfigureOrientationCorrection(CurrentSource());
    return true;
  }

  bool playlist_input() const { return playlist_input_; }
  size_t playlist_size() const { return playlist_paths_.size(); }
  bool file_like_input() const { return file_like_input_; }
  bool raw_camera_input() const { return raw_camera_input_; }
  bool srcampy_camera_input() const { return srcampy_camera_input_; }
  bool openni_camera_input() const { return openni_camera_input_; }
  int width() const { return input_w_; }
  int height() const { return input_h_; }
  double input_fps() const { return input_fps_; }
  const std::string& input_fps_basis() const { return input_fps_basis_; }
  double frame_interval_ms() const { return frame_interval_ms_; }
  double source_duration_ms() const { return source_duration_ms_; }
  double media_position_ms() const {
    return (raw_camera_input_ || srcampy_camera_input_ || openni_camera_input_)
               ? -1.0
               : cap_.get(cv::CAP_PROP_POS_MSEC);
  }
  const std::string& last_error() const { return last_error_; }
  std::string CurrentSource() const {
    if (playlist_input_ && playlist_index_ < playlist_paths_.size()) {
      return playlist_paths_[playlist_index_];
    }
    return (raw_camera_input_ || srcampy_camera_input_) ? CameraPath() : args_.input;
  }

 private:
  bool OpenCurrentSource() {
    if (raw_camera_input_) {
#if defined(__linux__)
      try {
        raw_camera_ = std::make_unique<V4L2RawCamera>(args_.input, args_);
      } catch (const std::exception& e) {
        last_error_ = e.what();
        return false;
      }
      input_w_ = raw_camera_->width();
      input_h_ = raw_camera_->height();
      input_fps_ = raw_camera_->fps();
      input_fps_basis_ = raw_camera_->fps_basis();
      frame_interval_ms_ = 1000.0 / std::max(1.0, input_fps_);
      source_duration_ms_ = 0.0;
      ConfigureOrientationCorrection(CameraPath());
      return true;
#else
      last_error_ = "V4L2 raw camera mode is only available on Linux";
      return false;
#endif
    }
    if (srcampy_camera_input_) {
#if defined(__linux__)
      try {
        srcampy_camera_ = std::make_unique<SrcampyPipeCamera>(args_.input, args_);
      } catch (const std::exception& e) {
        last_error_ = e.what();
        return false;
      }
      input_w_ = srcampy_camera_->width();
      input_h_ = srcampy_camera_->height();
      input_fps_ = srcampy_camera_->fps();
      input_fps_basis_ = srcampy_camera_->fps_basis();
      frame_interval_ms_ = 1000.0 / std::max(1.0, input_fps_);
      source_duration_ms_ = 0.0;
      ConfigureOrientationCorrection(CameraPath());
      return true;
#else
      last_error_ = "srcampy camera mode is only available on Linux";
      return false;
#endif
    }
    if (openni_camera_input_) {
#if defined(__linux__)
      try {
        openni_camera_ = std::make_unique<OpenNIColorCamera>(args_.input, args_);
      } catch (const std::exception& e) {
        last_error_ = e.what();
        return false;
      }
      input_w_ = openni_camera_->width();
      input_h_ = openni_camera_->height();
      input_fps_ = openni_camera_->fps();
      input_fps_basis_ = openni_camera_->fps_basis();
      frame_interval_ms_ = 1000.0 / std::max(1.0, input_fps_);
      source_duration_ms_ = 0.0;
      ConfigureOrientationCorrection(CurrentSource());
      return true;
#else
      last_error_ = "OpenNI camera mode is only available on Linux";
      return false;
#endif
    }

    const std::string source = playlist_input_ ? playlist_paths_.at(playlist_index_) : args_.input;
    if (!OpenCvCapture(cap_, source)) {
      last_error_ = "INPUT_OPEN_FAILED: " + source;
      return false;
    }
    RefreshMetadata();
    ConfigureOrientationCorrection(source);
    return true;
  }

  bool MaybeInjectDisconnect() {
    if (fault_inject_disconnect_after_sec_ < 0 || fault_disconnect_triggered_) return false;
    const auto elapsed_sec =
        std::chrono::duration_cast<std::chrono::seconds>(Clock::now() - opened_at_).count();
    if (elapsed_sec < fault_inject_disconnect_after_sec_) return false;
    fault_disconnect_triggered_ = true;
    // Do not tear down the live camera object inside the active capture loop.
    // OpenNI/V4L2 backends may still own driver/runtime state on the read path,
    // and destroying them here can turn a synthetic disconnect into a crash.
    // The capture loop will observe the injected disconnect and exit; normal
    // source teardown then releases the underlying handles on the unwind path.
    std::ostringstream oss;
    oss << "FAULT_INJECTED_DISCONNECT: elapsed_sec=" << elapsed_sec
        << " source=" << CurrentSource();
    last_error_ = oss.str();
    return true;
  }

  enum class OrientationCorrection {
    kNone,
    kClockwise,
    kCounterClockwise,
    kRotate180,
  };

  void ApplyOrientationCorrection(cv::Mat& frame) const {
    if (frame.empty()) return;
    if (orientation_correction_ == OrientationCorrection::kClockwise) {
      cv::rotate(frame, frame, cv::ROTATE_90_CLOCKWISE);
    } else if (orientation_correction_ == OrientationCorrection::kCounterClockwise) {
      cv::rotate(frame, frame, cv::ROTATE_90_COUNTERCLOCKWISE);
    } else if (orientation_correction_ == OrientationCorrection::kRotate180) {
      cv::rotate(frame, frame, cv::ROTATE_180);
    }
  }

  void ConfigureOrientationCorrection(const std::string& source) {
    orientation_correction_ = OrientationCorrection::kNone;
    if (args_.input_orientation_correction == "none") {
      return;
    } else if (args_.input_orientation_correction == "clockwise") {
      orientation_correction_ = OrientationCorrection::kClockwise;
    } else if (args_.input_orientation_correction == "counterclockwise") {
      orientation_correction_ = OrientationCorrection::kCounterClockwise;
    } else if (args_.input_orientation_correction == "rotate180" ||
               args_.input_orientation_correction == "upside_down") {
      orientation_correction_ = OrientationCorrection::kRotate180;
    } else if (args_.input_orientation_correction == "auto") {
      const bool is_rdk_x5_hbn_imx219 =
          args_.input_source_type == "mipi_camera_hbn" &&
          (args_.input_source_id == "imx219_rdkx5_hbn_001" ||
           source.rfind("srcampy://", 0) == 0);
      if (is_rdk_x5_hbn_imx219) {
        orientation_correction_ = OrientationCorrection::kRotate180;
        std::cout << "INPUT_ORIENTATION_CORRECTION: source=" << source
                  << " mode=" << args_.input_orientation_correction
                  << " effective=rotate180 normalized=" << input_w_ << "x"
                  << input_h_ << "\n";
        return;
      }
      if (source.find("bdd100k_mot_mini_v1") == std::string::npos || input_w_ >= input_h_) {
        return;
      }
      constexpr int kCapPropOrientationMeta = 48;
      int rotation = static_cast<int>(std::round(cap_.get(kCapPropOrientationMeta)));
      rotation = ((rotation % 360) + 360) % 360;
      orientation_correction_ = rotation == 270
                                    ? OrientationCorrection::kCounterClockwise
                                    : OrientationCorrection::kClockwise;
      std::swap(input_w_, input_h_);
      std::cout << "INPUT_ORIENTATION_CORRECTION: source=" << source
                << " rotation_meta=" << rotation
                << " mode=" << args_.input_orientation_correction
                << " normalized=" << input_w_ << "x" << input_h_ << "\n";
      return;
    } else {
      throw std::runtime_error(
          "CONFIG_INVALID: input orientation correction must be auto, clockwise, "
          "counterclockwise, rotate180, upside_down, or none");
    }
    if (orientation_correction_ == OrientationCorrection::kClockwise ||
        orientation_correction_ == OrientationCorrection::kCounterClockwise) {
      std::swap(input_w_, input_h_);
    }
    std::cout << "INPUT_ORIENTATION_CORRECTION: source=" << source
              << " mode=" << args_.input_orientation_correction
              << " normalized=" << input_w_ << "x" << input_h_ << "\n";
  }

  void RefreshMetadata() {
    input_w_ = static_cast<int>(std::round(cap_.get(cv::CAP_PROP_FRAME_WIDTH)));
    input_h_ = static_cast<int>(std::round(cap_.get(cv::CAP_PROP_FRAME_HEIGHT)));
    input_fps_ = cap_.get(cv::CAP_PROP_FPS);
    if (input_fps_ > 0.0) {
      input_fps_basis_ = "container_metadata";
    } else {
      input_fps_ = 30.0;
      input_fps_basis_ = "fallback_30";
    }
    frame_interval_ms_ = 1000.0 / std::max(1.0, input_fps_);
    const double frame_count = std::max(0.0, cap_.get(cv::CAP_PROP_FRAME_COUNT));
    source_duration_ms_ = frame_count > 0.0 ? frame_count * frame_interval_ms_ : 0.0;
  }

  std::string CameraPath() const {
#if defined(__linux__)
    if (srcampy_camera_input_) {
      return args_.input.empty() ? ("srcampy://video_idx" + std::to_string(args_.srcampy_video_idx))
                                 : args_.input;
    }
    return CameraDevicePath(args_.input);
#else
    return args_.input;
#endif
  }

  const Args& args_;
  bool playlist_input_ = false;
  bool file_like_input_ = false;
  bool raw_camera_input_ = false;
  bool srcampy_camera_input_ = false;
  bool openni_camera_input_ = false;
  std::vector<std::string> playlist_paths_;
  size_t playlist_index_ = 0;
  cv::VideoCapture cap_;
#if defined(__linux__)
  std::unique_ptr<V4L2RawCamera> raw_camera_;
  std::unique_ptr<SrcampyPipeCamera> srcampy_camera_;
  std::unique_ptr<OpenNIColorCamera> openni_camera_;
#endif
  int input_w_ = 0;
  int input_h_ = 0;
  int initial_width_ = 0;
  int initial_height_ = 0;
  double input_fps_ = 30.0;
  std::string input_fps_basis_ = "unknown";
  double frame_interval_ms_ = 1000.0 / 30.0;
  double source_duration_ms_ = 0.0;
  std::string last_error_;
  OrientationCorrection orientation_correction_ = OrientationCorrection::kNone;
  int fault_inject_disconnect_after_sec_ = -1;
  bool fault_disconnect_triggered_ = false;
  Clock::time_point opened_at_{};
};

Args ParseArgs(int argc, char** argv) {
  Args args;
  for (int i = 1; i < argc; ++i) {
    std::string key = argv[i];
    auto next = [&]() -> std::string {
      if (i + 1 >= argc) throw std::runtime_error("Missing value for " + key);
      return argv[++i];
    };
    if (key == "--config") args.config = next();
    else if (key == "--model-config") args.model_config = next();
    else if (key == "--backend-config") args.backend_config = next();
    else if (key == "--stream-config") args.stream_config = next();
    else if (key == "--input-source-id") args.input_source_id = next();
    else if (key == "--input-source-type") args.input_source_type = next();
    else if (key == "--input-orientation-correction") args.input_orientation_correction = next();
    else if (key == "--input") args.input = next();
    else if (key == "--duration-sec") args.duration_sec = std::stoi(next());
    else if (key == "--no-loop-video-file") args.loop_video_file = false;
    else if (key == "--loop-video-file") args.loop_video_file = true;
    else if (key == "--no-pace-video-file") args.pace_video_file_override = 0;
    else if (key == "--pace-video-file") args.pace_video_file_override = 1;
    else if (key == "--queue-policy") args.queue_policy_override = CanonicalizeQueuePolicy(next());
    else if (key == "--queue-capacity") args.queue_capacity_override = std::stoi(next());
    else if (key == "--queue-push-timeout-ms") args.queue_push_timeout_ms_override = std::stoi(next());
    else if (key == "--rknn-core-mask") args.rknn_core_mask_override = next();
    else if (key == "--inference-workers") args.inference_workers_override = std::stoi(next());
    else if (key == "--postprocess-workers") args.postprocess_workers_override = std::stoi(next());
    else if (key == "--v4l2-raw") args.v4l2_raw = true;
    else if (key == "--v4l2-width") args.v4l2_width = std::stoi(next());
    else if (key == "--v4l2-height") args.v4l2_height = std::stoi(next());
    else if (key == "--v4l2-sensor-mode") args.v4l2_sensor_mode = std::stoi(next());
    else if (key == "--v4l2-fps") args.v4l2_fps = std::stod(next());
    else if (key == "--bayer-pattern") args.bayer_pattern = next();
    else if (key == "--v4l2-normalize-mode") args.v4l2_normalize_mode = CanonicalizeV4l2NormalizeMode(next());
    else if (key == "--v4l2-disable-white-balance") args.v4l2_disable_white_balance = true;
    else if (key == "--srcampy-python") args.srcampy_python = next();
    else if (key == "--srcampy-stream-script") args.srcampy_stream_script = next();
    else if (key == "--srcampy-video-idx") args.srcampy_video_idx = std::stoi(next());
    else if (key == "--srcampy-width") args.srcampy_width = std::stoi(next());
    else if (key == "--srcampy-height") args.srcampy_height = std::stoi(next());
    else if (key == "--srcampy-sensor-width") args.srcampy_sensor_width = std::stoi(next());
    else if (key == "--srcampy-sensor-height") args.srcampy_sensor_height = std::stoi(next());
    else if (key == "--srcampy-fps") args.srcampy_fps = std::stod(next());
    else if (key == "--srcampy-warmup") args.srcampy_warmup = std::stoi(next());
    else if (key == "--srcampy-startup-timeout-sec") args.srcampy_startup_timeout_sec = std::stod(next());
    else if (key == "--fault-inject-disconnect-after-sec") {
      args.fault_inject_disconnect_after_sec = std::stoi(next());
    }
    else if (key == "--raw-output") args.raw_output = next();
    else if (key == "--output-video") args.output_video = next();
    else if (key == "--runtime-log") args.runtime_log_path = next();
    else if (key == "--monitor-log") args.monitor_log_path = next();
    else if (key == "--preview-window") args.preview_window_mode = ToLower(next());
    else throw std::runtime_error("Unknown argument: " + key);
  }
  if (args.input.empty()) throw std::runtime_error("--input is required");
  if (args.raw_output.empty()) throw std::runtime_error("--raw-output is required");
  if (args.v4l2_width <= 0 || args.v4l2_height <= 0) {
    throw std::runtime_error("--v4l2-width and --v4l2-height must be > 0");
  }
  if (args.v4l2_fps <= 0.0) {
    throw std::runtime_error("--v4l2-fps must be > 0");
  }
  if (args.srcampy_width <= 0 || args.srcampy_height <= 0) {
    throw std::runtime_error("--srcampy-width and --srcampy-height must be > 0");
  }
  if (args.srcampy_sensor_width <= 0 || args.srcampy_sensor_height <= 0) {
    throw std::runtime_error("--srcampy-sensor-width and --srcampy-sensor-height must be > 0");
  }
  if (args.srcampy_fps <= 0.0) {
    throw std::runtime_error("--srcampy-fps must be > 0");
  }
  if (args.srcampy_warmup < 0) {
    throw std::runtime_error("--srcampy-warmup must be >= 0");
  }
  if (args.srcampy_startup_timeout_sec <= 0.0) {
    throw std::runtime_error("--srcampy-startup-timeout-sec must be > 0");
  }
  if (args.v4l2_normalize_mode != "percentile" && args.v4l2_normalize_mode != "fixed_10bit") {
    throw std::runtime_error("--v4l2-normalize-mode must be percentile or fixed_10bit");
  }
  if (args.fault_inject_disconnect_after_sec < -1) {
    throw std::runtime_error("--fault-inject-disconnect-after-sec must be >= -1");
  }
  if (args.preview_window_mode != "auto" &&
      args.preview_window_mode != "on" &&
      args.preview_window_mode != "off") {
    throw std::runtime_error("--preview-window must be auto, on, or off");
  }
  return args;
}

ModelConfig LoadModelConfig(const std::string& path) {
  ModelConfig cfg;
  if (!path.empty()) {
    cfg.input_w = FindYamlInt(path, "width", cfg.input_w);
    cfg.input_h = FindYamlInt(path, "height", cfg.input_h);
    cfg.num_classes = FindYamlInt(path, "num_classes", cfg.num_classes);
    cfg.conf_thres = FindYamlFloat(path, "confidence_threshold", cfg.conf_thres);
    cfg.nms_thres = FindYamlFloat(path, "nms_iou_threshold", cfg.nms_thres);
    cfg.max_detections = FindYamlInt(path, "max_detections", cfg.max_detections);
    auto value = FindYamlScalar(path, "color_format");
    if (!value.empty()) cfg.color_format = ToUpper(value);
    value = FindYamlScalar(path, "layout");
    if (!value.empty()) cfg.layout = ToUpper(value);
    cfg.normalize_scale = FindYamlFloat(path, "scale", cfg.normalize_scale);
    cfg.pad_value = FindYamlFloat(path, "pad_value", cfg.pad_value);
    value = FindYamlScalar(path, "keep_ratio");
    if (!value.empty()) cfg.keep_ratio = ParseBool(value, cfg.keep_ratio);
    value = FindYamlScalar(path, "class_agnostic_nms");
    if (!value.empty()) cfg.class_agnostic_nms = ParseBool(value, cfg.class_agnostic_nms);
  }
  return cfg;
}

void ValidateModelConfig(const ModelConfig& cfg) {
  if (!cfg.keep_ratio) {
    throw std::runtime_error("Model config mismatch: project3 pipeline currently only supports keep_ratio=true letterbox.");
  }
  if (cfg.color_format != "RGB" && cfg.color_format != "BGR") {
    throw std::runtime_error("Model config mismatch: unsupported color_format, expected RGB or BGR.");
  }
  if (cfg.layout != "NCHW") {
    throw std::runtime_error("Model config mismatch: project3 pipeline currently only supports layout=NCHW.");
  }
  if (cfg.normalize_scale <= 0.0f) {
    throw std::runtime_error("Model config mismatch: normalize.scale must be > 0.");
  }
}

BoardConfig LoadBoardConfig(const std::string& path) {
  BoardConfig cfg;
  if (!path.empty()) {
    auto value = FindYamlScalar(path, "target");
    if (!value.empty()) cfg.target = value;
    value = FindYamlScalar(path, "board_name");
    if (!value.empty()) cfg.board = value;
    value = FindYamlScalar(path, "backend_runtime");
    if (!value.empty()) cfg.backend_runtime = value;
    value = FindYamlScalar(path, "execution_provider");
    if (!value.empty()) cfg.execution_provider = value;
    value = FindYamlScalar(path, "loader_api");
    if (!value.empty()) cfg.loader_api = value;
    value = FindYamlScalar(path, "precision_or_quantization");
    if (!value.empty()) cfg.precision = value;
    value = FindYamlScalar(path, "backend_artifact_format");
    if (!value.empty()) cfg.artifact_format = value;
    value = FindYamlScalar(path, "backend_artifact_path");
    if (!value.empty()) cfg.artifact_path = value;
    value = FindYamlScalar(path, "backend_artifact_sha256");
    if (!value.empty()) cfg.artifact_sha256 = value;
    value = FindYamlScalar(path, "rknn_core_mask");
    if (!value.empty()) cfg.rknn_core_mask = value;
    cfg.preprocess_pad_value =
        FindYamlFloat(path, "preprocess_pad_value", cfg.preprocess_pad_value);
  }
  return cfg;
}

PipelineConfig LoadPipelineConfig(const std::string& path) {
  PipelineConfig cfg;
  if (!path.empty()) {
    auto value = FindYamlScalar(path, "pipeline_mode");
    if (!value.empty()) cfg.pipeline_mode = value;
    value = FindYamlScalar(path, "mainline_policy");
    if (!value.empty()) cfg.queue_policy = CanonicalizeQueuePolicy(value);
    cfg.queue_capacity = FindYamlInt(path, "capacity", cfg.queue_capacity);
    cfg.queue_capacity = FindYamlInt(path, "queue_capacity", cfg.queue_capacity);
    cfg.queue_push_timeout_ms =
        FindYamlInt(path, "queue_push_timeout_ms", cfg.queue_push_timeout_ms);
    cfg.inference_workers = FindYamlInt(path, "inference_threads", cfg.inference_workers);
    cfg.postprocess_workers = FindYamlInt(path, "postprocess_threads", cfg.postprocess_workers);
    value = FindYamlScalar(path, "reuse");
    if (!value.empty()) cfg.buffer_reuse = (value == "true" || value == "True");
    value = FindYamlScalar(path, "pace_video_file");
    if (!value.empty()) cfg.pace_video_file = ParseBool(value, cfg.pace_video_file);
  }
  return cfg;
}

template <typename T>
class BoundedQueue {
 public:
  explicit BoundedQueue(size_t capacity) : capacity_(std::max<size_t>(1, capacity)) {}

  bool Push(T item, const std::string& policy, int timeout_ms, std::atomic<int>& dropped) {
    std::unique_lock<std::mutex> lock(mu_);
    if (closed_) return false;
    if (queue_.size() >= capacity_) {
      if (policy == "drop_newest") {
        ++dropped;
        return true;
      }
      if (policy == "block" || policy == "block_forever" || policy == "no_drop") {
        not_full_.wait(lock, [&] {
          return queue_.size() < capacity_ || closed_;
        });
        if (closed_) return false;
      } else if (policy == "block_with_timeout") {
        const bool ready = not_full_.wait_for(lock, std::chrono::milliseconds(std::max(0, timeout_ms)), [&] {
          return queue_.size() < capacity_ || closed_;
        });
        if (!ready || closed_) {
          ++dropped;
          return true;
        }
      } else {
        queue_.pop();
        ++dropped;
      }
    }
    queue_.push(std::move(item));
    not_empty_.notify_one();
    return true;
  }

  bool Pop(T& out) {
    std::unique_lock<std::mutex> lock(mu_);
    not_empty_.wait(lock, [&] { return closed_ || !queue_.empty(); });
    if (queue_.empty()) return false;
    out = std::move(queue_.front());
    queue_.pop();
    not_full_.notify_one();
    return true;
  }

  void Close() {
    std::lock_guard<std::mutex> lock(mu_);
    closed_ = true;
    not_empty_.notify_all();
    not_full_.notify_all();
  }

  int Size() const {
    std::lock_guard<std::mutex> lock(mu_);
    return static_cast<int>(queue_.size());
  }

 private:
  size_t capacity_;
  mutable std::mutex mu_;
  std::condition_variable not_empty_;
  std::condition_variable not_full_;
  std::queue<T> queue_;
  bool closed_ = false;
};

std::vector<uint8_t> BgrToNv12Bytes(const cv::Mat& bgr) {
  if (bgr.empty() || bgr.type() != CV_8UC3) return {};
  cv::Mat yuv_i420;
  cv::cvtColor(bgr, yuv_i420, cv::COLOR_BGR2YUV_I420);
  const int height = bgr.rows;
  const int width = bgr.cols;
  cv::Mat yuv = yuv_i420.reshape(1, height * 3 / 2);
  std::vector<uint8_t> nv12(static_cast<size_t>(height * width * 3 / 2));
  const uint8_t* src = yuv.ptr<uint8_t>();
  uint8_t* dst = nv12.data();
  const size_t y_bytes = static_cast<size_t>(height * width);
  std::memcpy(dst, src, y_bytes);
  const uint8_t* u_plane = src + y_bytes;
  const uint8_t* v_plane = u_plane + y_bytes / 4;
  uint8_t* uv = dst + y_bytes;
  const int chroma_h = height / 2;
  const int chroma_w = width / 2;
  for (int y = 0; y < chroma_h; ++y) {
    for (int x = 0; x < chroma_w; ++x) {
      uv[y * width + x * 2] = u_plane[y * chroma_w + x];
      uv[y * width + x * 2 + 1] = v_plane[y * chroma_w + x];
    }
  }
  return nv12;
}

std::vector<float> Preprocess(const cv::Mat& bgr,
                              const ModelConfig& cfg,
                              LetterboxInfo& info,
                              cv::Mat* letterboxed_bgr = nullptr) {
  const int src_w = bgr.cols;
  const int src_h = bgr.rows;
  const float r = std::min(static_cast<float>(cfg.input_w) / src_w,
                           static_cast<float>(cfg.input_h) / src_h);
  const int resized_w = static_cast<int>(std::round(src_w * r));
  const int resized_h = static_cast<int>(std::round(src_h * r));
  info.scale = r;
  info.pad_x = (cfg.input_w - resized_w) / 2;
  info.pad_y = (cfg.input_h - resized_h) / 2;

  cv::Mat resized;
  cv::resize(bgr, resized, cv::Size(resized_w, resized_h));
  cv::Mat canvas(cfg.input_h, cfg.input_w, CV_8UC3,
                 cv::Scalar(cfg.pad_value, cfg.pad_value, cfg.pad_value));
  resized.copyTo(canvas(cv::Rect(info.pad_x, info.pad_y, resized_w, resized_h)));
  if (letterboxed_bgr != nullptr) {
    *letterboxed_bgr = canvas.clone();
  }
  if (cfg.color_format == "RGB") {
    cv::cvtColor(canvas, canvas, cv::COLOR_BGR2RGB);
  }

  std::vector<float> chw(3 * cfg.input_w * cfg.input_h);
  const int area = cfg.input_w * cfg.input_h;
  for (int y = 0; y < cfg.input_h; ++y) {
    const auto* row = canvas.ptr<cv::Vec3b>(y);
    for (int x = 0; x < cfg.input_w; ++x) {
      const auto& px = row[x];
      const int idx = y * cfg.input_w + x;
      chw[idx] = px[0] * cfg.normalize_scale;
      chw[area + idx] = px[1] * cfg.normalize_scale;
      chw[2 * area + idx] = px[2] * cfg.normalize_scale;
    }
  }
  return chw;
}

float BoxIou(const Box& a, const Box& b) {
  const float ax1 = a.x;
  const float ay1 = a.y;
  const float ax2 = a.x + a.width;
  const float ay2 = a.y + a.height;
  const float bx1 = b.x;
  const float by1 = b.y;
  const float bx2 = b.x + b.width;
  const float by2 = b.y + b.height;

  const float ix1 = std::max(ax1, bx1);
  const float iy1 = std::max(ay1, by1);
  const float ix2 = std::min(ax2, bx2);
  const float iy2 = std::min(ay2, by2);
  const float iw = std::max(0.0f, ix2 - ix1);
  const float ih = std::max(0.0f, iy2 - iy1);
  const float inter = iw * ih;
  const float area_a = std::max(0.0f, a.width) * std::max(0.0f, a.height);
  const float area_b = std::max(0.0f, b.width) * std::max(0.0f, b.height);
  const float denom = area_a + area_b - inter;
  return denom > 0.0f ? inter / denom : 0.0f;
}

std::vector<int> NmsIndices(const std::vector<Box>& boxes,
                            const std::vector<float>& scores,
                            const std::vector<int>& class_ids,
                            float iou_threshold,
                            bool class_agnostic) {
  std::vector<int> keep;
  if (boxes.empty()) return keep;

  std::map<int, std::vector<int>> groups;
  if (class_agnostic) {
    groups[-1].reserve(boxes.size());
    for (int i = 0; i < static_cast<int>(boxes.size()); ++i) groups[-1].push_back(i);
  } else {
    for (int i = 0; i < static_cast<int>(boxes.size()); ++i) groups[class_ids[i]].push_back(i);
  }

  for (auto& entry : groups) {
    auto& indices = entry.second;
    std::sort(indices.begin(), indices.end(), [&](int lhs, int rhs) {
      return scores[lhs] > scores[rhs];
    });
    std::vector<uint8_t> suppressed(indices.size(), 0);
    for (size_t i = 0; i < indices.size(); ++i) {
      if (suppressed[i] != 0) continue;
      const int current = indices[i];
      keep.push_back(current);
      for (size_t j = i + 1; j < indices.size(); ++j) {
        if (suppressed[j] != 0) continue;
        const int candidate = indices[j];
        if (BoxIou(boxes[current], boxes[candidate]) > iou_threshold) {
          suppressed[j] = 1;
        }
      }
    }
  }

  std::sort(keep.begin(), keep.end(), [&](int lhs, int rhs) {
    return scores[lhs] > scores[rhs];
  });
  return keep;
}

std::vector<Detection> DecodeYolo(const std::vector<float>& output,
                                  const ModelConfig& cfg,
                                  const LetterboxInfo& info,
                                  const cv::Size& original_size) {
  std::vector<Detection> candidates;
  if (output.empty()) return candidates;

  const int attrs = 4 + cfg.num_classes;
  int num_boxes = 0;
  bool channel_first = false;
  if (static_cast<int>(output.size()) % attrs == 0) {
    num_boxes = static_cast<int>(output.size()) / attrs;
    channel_first = (num_boxes == 8400);
  }
  if (num_boxes <= 0) return candidates;

  auto value_at = [&](int box, int attr) -> float {
    if (channel_first) return output[attr * num_boxes + box];
    return output[box * attrs + attr];
  };

  std::vector<Box> boxes;
  std::vector<float> scores;
  std::vector<int> class_ids;
  boxes.reserve(num_boxes);
  scores.reserve(num_boxes);
  class_ids.reserve(num_boxes);

  for (int i = 0; i < num_boxes; ++i) {
    int best_class = -1;
    float best_score = 0.0f;
    for (int c = 0; c < cfg.num_classes; ++c) {
      const float score = value_at(i, 4 + c);
      if (score > best_score) {
        best_score = score;
        best_class = c;
      }
    }
    if (best_score < cfg.conf_thres) continue;

    const float cx = value_at(i, 0);
    const float cy = value_at(i, 1);
    const float w = value_at(i, 2);
    const float h = value_at(i, 3);

    float x1 = (cx - w * 0.5f - info.pad_x) / info.scale;
    float y1 = (cy - h * 0.5f - info.pad_y) / info.scale;
    float x2 = (cx + w * 0.5f - info.pad_x) / info.scale;
    float y2 = (cy + h * 0.5f - info.pad_y) / info.scale;
    x1 = std::clamp(x1, 0.0f, static_cast<float>(original_size.width));
    y1 = std::clamp(y1, 0.0f, static_cast<float>(original_size.height));
    x2 = std::clamp(x2, 0.0f, static_cast<float>(original_size.width));
    y2 = std::clamp(y2, 0.0f, static_cast<float>(original_size.height));
    const float bw = std::max(0.0f, x2 - x1);
    const float bh = std::max(0.0f, y2 - y1);
    if (bw <= 0.0f || bh <= 0.0f) continue;

    boxes.push_back({x1, y1, bw, bh});
    scores.push_back(best_score);
    class_ids.push_back(best_class);
  }

  std::vector<int> keep = NmsIndices(boxes, scores, class_ids, cfg.nms_thres, cfg.class_agnostic_nms);
  if (static_cast<int>(keep.size()) > cfg.max_detections) keep.resize(cfg.max_detections);

  candidates.reserve(keep.size());
  for (int idx : keep) {
    candidates.push_back({class_ids[idx], scores[idx], boxes[idx]});
  }
  return candidates;
}

float TensorValueNchw(const std::vector<float>& data,
                      size_t base,
                      const TensorInfo& tensor,
                      int channel,
                      int y,
                      int x) {
  if (tensor.dims.size() != 4) return 0.0f;
  const int channels = tensor.dims[1];
  const int height = tensor.dims[2];
  const int width = tensor.dims[3];
  if (channel < 0 || channel >= channels || y < 0 || y >= height || x < 0 || x >= width) return 0.0f;
  const size_t offset = base + static_cast<size_t>(channel * height * width + y * width + x);
  return offset < data.size() ? data[offset] : 0.0f;
}

float DflExpectation(const std::vector<float>& data,
                     size_t base,
                     const TensorInfo& tensor,
                     int side,
                     int y,
                     int x,
                     int reg_max) {
  float max_logit = -std::numeric_limits<float>::infinity();
  for (int bin = 0; bin < reg_max; ++bin) {
    max_logit = std::max(max_logit, TensorValueNchw(data, base, tensor, side * reg_max + bin, y, x));
  }
  float denom = 0.0f;
  float numer = 0.0f;
  for (int bin = 0; bin < reg_max; ++bin) {
    const float v = std::exp(TensorValueNchw(data, base, tensor, side * reg_max + bin, y, x) - max_logit);
    denom += v;
    numer += v * static_cast<float>(bin);
  }
  return denom > 0.0f ? numer / denom : 0.0f;
}

float Sigmoid(float x) {
  return 1.0f / (1.0f + std::exp(-x));
}

std::vector<Detection> DecodeRknnOfficialYolo11(const std::vector<float>& output,
                                                const std::vector<TensorInfo>& tensors,
                                                const ModelConfig& cfg,
                                                const LetterboxInfo& info,
                                                const cv::Size& original_size,
                                                bool apply_sigmoid_to_scores = false) {
  std::vector<Detection> candidates;
  if (tensors.size() != 6 && tensors.size() != 9) return candidates;

  std::vector<size_t> bases(tensors.size(), 0);
  size_t cursor = 0;
  for (size_t i = 0; i < tensors.size(); ++i) {
    bases[i] = cursor;
    cursor += tensors[i].elem_count;
  }
  if (cursor > output.size()) return candidates;

  std::vector<Box> boxes;
  std::vector<float> scores;
  std::vector<int> class_ids;

  const int branch_step = static_cast<int>(tensors.size() / 3);
  for (int branch = 0; branch < 3; ++branch) {
    const int box_idx = branch * branch_step;
    const int score_idx = branch * branch_step + 1;
    const TensorInfo& box_tensor = tensors[box_idx];
    const TensorInfo& score_tensor = tensors[score_idx];
    if (box_tensor.dims.size() != 4 || score_tensor.dims.size() != 4) continue;
    const int box_channels = box_tensor.dims[1];
    const int grid_h = box_tensor.dims[2];
    const int grid_w = box_tensor.dims[3];
    const int score_channels = score_tensor.dims[1];
    if (box_channels % 4 != 0 || grid_h <= 0 || grid_w <= 0 || score_channels <= 0) continue;
    const int reg_max = box_channels / 4;
    const float stride = static_cast<float>(cfg.input_h) / static_cast<float>(grid_h);
    for (int y = 0; y < grid_h; ++y) {
      for (int x = 0; x < grid_w; ++x) {
        int best_class = -1;
        float best_score = 0.0f;
        const int classes_to_scan = std::min(cfg.num_classes, score_channels);
        for (int c = 0; c < classes_to_scan; ++c) {
          float score = TensorValueNchw(output, bases[score_idx], score_tensor, c, y, x);
          if (apply_sigmoid_to_scores) {
            score = Sigmoid(score);
          }
          if (score > best_score) {
            best_score = score;
            best_class = c;
          }
        }
        if (best_score < cfg.conf_thres || best_class < 0) continue;

        const float left = DflExpectation(output, bases[box_idx], box_tensor, 0, y, x, reg_max);
        const float top = DflExpectation(output, bases[box_idx], box_tensor, 1, y, x, reg_max);
        const float right = DflExpectation(output, bases[box_idx], box_tensor, 2, y, x, reg_max);
        const float bottom = DflExpectation(output, bases[box_idx], box_tensor, 3, y, x, reg_max);

        float x1 = ((static_cast<float>(x) + 0.5f - left) * stride - info.pad_x) / info.scale;
        float y1 = ((static_cast<float>(y) + 0.5f - top) * stride - info.pad_y) / info.scale;
        float x2 = ((static_cast<float>(x) + 0.5f + right) * stride - info.pad_x) / info.scale;
        float y2 = ((static_cast<float>(y) + 0.5f + bottom) * stride - info.pad_y) / info.scale;
        x1 = std::clamp(x1, 0.0f, static_cast<float>(original_size.width));
        y1 = std::clamp(y1, 0.0f, static_cast<float>(original_size.height));
        x2 = std::clamp(x2, 0.0f, static_cast<float>(original_size.width));
        y2 = std::clamp(y2, 0.0f, static_cast<float>(original_size.height));
        const float bw = std::max(0.0f, x2 - x1);
        const float bh = std::max(0.0f, y2 - y1);
        if (bw <= 0.0f || bh <= 0.0f) continue;

        boxes.push_back({x1, y1, bw, bh});
        scores.push_back(best_score);
        class_ids.push_back(best_class);
      }
    }
  }

  std::vector<int> keep = NmsIndices(boxes, scores, class_ids, cfg.nms_thres, cfg.class_agnostic_nms);
  if (static_cast<int>(keep.size()) > cfg.max_detections) keep.resize(cfg.max_detections);
  candidates.reserve(keep.size());
  for (int idx : keep) {
    candidates.push_back({class_ids[idx], scores[idx], boxes[idx]});
  }
  return candidates;
}

class Backend {
 public:
  virtual ~Backend() = default;
  virtual bool Init(const BoardConfig& board, const ModelConfig& model, bool buffer_reuse) = 0;
  virtual bool Infer(const std::vector<float>& input,
                     const std::vector<uint8_t>* nv12_input,
                     std::vector<float>& output,
                     double& inference_ms) = 0;
  virtual const std::vector<TensorInfo>& OutputInfos() const {
    static const std::vector<TensorInfo> empty;
    return empty;
  }
};

bool WarmupBackend(Backend& backend,
                   const BoardConfig& board,
                   const ModelConfig& model,
                   int worker_index,
                   int attempts = 2) {
  if (board.backend_runtime != "tensorrt") return true;

  std::vector<float> input(3ULL * static_cast<size_t>(model.input_h) * static_cast<size_t>(model.input_w), 0.0f);
  std::vector<float> output;
  for (int attempt = 1; attempt <= attempts; ++attempt) {
    double inference_ms = 0.0;
    const bool ok = backend.Infer(input, nullptr, output, inference_ms);
    std::cout << "BACKEND_WARMUP: runtime=" << board.backend_runtime
              << " worker=" << worker_index
              << " attempt=" << attempt
              << " status=" << (ok ? "pass" : "fail")
              << " inference_ms=" << inference_ms << "\n";
    if (ok) return true;
  }
  std::cerr << "BACKEND_RUNTIME_FAILED: warmup failed runtime=" << board.backend_runtime
            << " worker=" << worker_index << "\n";
  return false;
}

class MockBackend final : public Backend {
 public:
  bool Init(const BoardConfig&, const ModelConfig&, bool) override { return true; }
  bool Infer(const std::vector<float>&,
             const std::vector<uint8_t>*,
             std::vector<float>& output,
             double& inference_ms) override {
    const auto start = Clock::now();
    output.clear();
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    inference_ms = MsSince(start);
    return true;
  }
};

#if defined(PIPELINE_BACKEND_TENSORRT)
class TrtLogger final : public nvinfer1::ILogger {
 public:
  void log(Severity severity, const char* msg) noexcept override {
    if (severity <= Severity::kWARNING) std::cerr << "[TensorRT] " << msg << "\n";
  }
};

size_t Volume(const nvinfer1::Dims& dims) {
  size_t v = 1;
  for (int i = 0; i < dims.nbDims; ++i) {
    if (dims.d[i] < 0) return 0;
    v *= static_cast<size_t>(dims.d[i]);
  }
  return v;
}

class TensorRtBackend final : public Backend {
 public:
  ~TensorRtBackend() override {
    for (void* p : device_buffers_) cudaFree(p);
  }

  bool Init(const BoardConfig& board, const ModelConfig& model, bool buffer_reuse) override {
    buffer_reuse_ = buffer_reuse;
    std::ifstream in(board.artifact_path, std::ios::binary);
    if (!in) {
      std::cerr << "Failed to open TensorRT engine: " << board.artifact_path << "\n";
      return false;
    }
    std::vector<char> engine_data((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    runtime_.reset(nvinfer1::createInferRuntime(logger_));
    if (!runtime_) return false;
    engine_.reset(runtime_->deserializeCudaEngine(engine_data.data(), engine_data.size()));
    if (!engine_) return false;
    context_.reset(engine_->createExecutionContext());
    if (!context_) return false;

    const int nb = engine_->getNbBindings();
    binding_count_ = nb;
    device_buffers_.assign(nb, nullptr);
    for (int i = 0; i < nb; ++i) {
      const bool is_input = engine_->bindingIsInput(i);
      auto dims = engine_->getBindingDimensions(i);
      if (is_input) {
        input_index_ = i;
        if (dims.nbDims == 4 && dims.d[0] < 0) {
          dims.d[0] = 1;
          dims.d[1] = 3;
          dims.d[2] = model.input_h;
          dims.d[3] = model.input_w;
          context_->setBindingDimensions(i, dims);
        }
        input_count_ = 3ULL * model.input_h * model.input_w;
        if (buffer_reuse_) cudaMalloc(&device_buffers_[i], input_count_ * sizeof(float));
      } else {
        output_index_ = i;
        auto actual_dims = context_->getBindingDimensions(i);
        output_count_ = Volume(actual_dims);
        if (output_count_ == 0) output_count_ = static_cast<size_t>(4 + model.num_classes) * 8400ULL;
        if (buffer_reuse_) cudaMalloc(&device_buffers_[i], output_count_ * sizeof(float));
      }
    }
    return input_index_ >= 0 && output_index_ >= 0 && input_count_ > 0 && output_count_ > 0;
  }

  bool Infer(const std::vector<float>& input,
             const std::vector<uint8_t>*,
             std::vector<float>& output,
             double& inference_ms) override {
    if (input.size() != input_count_) {
      std::cerr << "Input tensor size mismatch: got " << input.size() << ", expected " << input_count_ << "\n";
      return false;
    }
    const auto start = Clock::now();
    std::vector<void*> transient_buffers;
    void** bindings = device_buffers_.data();
    if (!buffer_reuse_) {
      transient_buffers.assign(static_cast<size_t>(binding_count_), nullptr);
      cudaMalloc(&transient_buffers[input_index_], input_count_ * sizeof(float));
      cudaMalloc(&transient_buffers[output_index_], output_count_ * sizeof(float));
      bindings = transient_buffers.data();
    }
    auto cleanup_transient = [&]() {
      if (!buffer_reuse_) {
        if (transient_buffers[input_index_]) cudaFree(transient_buffers[input_index_]);
        if (transient_buffers[output_index_]) cudaFree(transient_buffers[output_index_]);
      }
    };

    cudaMemcpy(bindings[input_index_], input.data(), input.size() * sizeof(float), cudaMemcpyHostToDevice);
    const bool ok = context_->executeV2(bindings);
    if (!ok) {
      cleanup_transient();
      return false;
    }
    output.resize(output_count_);
    cudaMemcpy(output.data(), bindings[output_index_], output.size() * sizeof(float), cudaMemcpyDeviceToHost);
    cudaDeviceSynchronize();
    cleanup_transient();
    inference_ms = MsSince(start);
    return true;
  }

 private:
  struct RuntimeDeleter {
    void operator()(nvinfer1::IRuntime* p) const { if (p) p->destroy(); }
  };
  struct EngineDeleter {
    void operator()(nvinfer1::ICudaEngine* p) const { if (p) p->destroy(); }
  };
  struct ContextDeleter {
    void operator()(nvinfer1::IExecutionContext* p) const { if (p) p->destroy(); }
  };

  TrtLogger logger_;
  std::unique_ptr<nvinfer1::IRuntime, RuntimeDeleter> runtime_;
  std::unique_ptr<nvinfer1::ICudaEngine, EngineDeleter> engine_;
  std::unique_ptr<nvinfer1::IExecutionContext, ContextDeleter> context_;
  std::vector<void*> device_buffers_;
  bool buffer_reuse_ = true;
  int binding_count_ = 0;
  int input_index_ = -1;
  int output_index_ = -1;
  size_t input_count_ = 0;
  size_t output_count_ = 0;
};
#endif

#if defined(PIPELINE_BACKEND_RKNN)
bool ResolveRknnCoreMask(const std::string& value, rknn_core_mask& mask) {
  const std::string normalized = ToLower(value);
  if (normalized.empty() || normalized == "auto") {
    mask = RKNN_NPU_CORE_AUTO;
  } else if (normalized == "0" || normalized == "core0") {
    mask = RKNN_NPU_CORE_0;
  } else if (normalized == "1" || normalized == "core1") {
    mask = RKNN_NPU_CORE_1;
  } else if (normalized == "2" || normalized == "core2") {
    mask = RKNN_NPU_CORE_2;
  } else if (normalized == "0_1_2" || normalized == "all") {
    mask = static_cast<rknn_core_mask>(RKNN_NPU_CORE_0 | RKNN_NPU_CORE_1 | RKNN_NPU_CORE_2);
  } else {
    return false;
  }
  return true;
}

class RknnBackend final : public Backend {
 public:
  ~RknnBackend() override {
    if (input_mem_ != nullptr && ctx_ != 0) {
      rknn_destroy_mem(ctx_, input_mem_);
      input_mem_ = nullptr;
    }
    if (ctx_ != 0) rknn_destroy(ctx_);
  }

  bool Init(const BoardConfig& board, const ModelConfig& model, bool buffer_reuse) override {
    buffer_reuse_ = buffer_reuse;
    input_io_mem_enabled_ = false;
    output_prealloc_enabled_ = false;
    input_copy_bytes_ = 0;
    output_count_ = 0;
    output_infos_.clear();
    output_float_buffers_.clear();
    prealloc_outputs_.clear();
    input_native_attrs_.clear();

    std::ifstream in(board.artifact_path, std::ios::binary);
    if (!in) {
      std::cerr << "Failed to open RKNN model: " << board.artifact_path << "\n";
      return false;
    }
    model_data_.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
    if (model_data_.empty()) {
      std::cerr << "RKNN model is empty: " << board.artifact_path << "\n";
      return false;
    }

    int ret = rknn_init(&ctx_, model_data_.data(), model_data_.size(), 0, nullptr);
    if (ret != RKNN_SUCC) {
      std::cerr << "rknn_init failed: " << ret << "\n";
      return false;
    }

    rknn_core_mask core_mask{};
    if (!ResolveRknnCoreMask(board.rknn_core_mask, core_mask)) {
      std::cerr << "Unsupported RKNN core mask: " << board.rknn_core_mask << "\n";
      return false;
    }
    ret = rknn_set_core_mask(ctx_, core_mask);
    if (ret != RKNN_SUCC) {
      std::cerr << "rknn_set_core_mask failed: mask=" << board.rknn_core_mask
                << " ret=" << ret << "\n";
      return false;
    }

    rknn_input_output_num io_num{};
    ret = rknn_query(ctx_, RKNN_QUERY_IN_OUT_NUM, &io_num, sizeof(io_num));
    if (ret != RKNN_SUCC || io_num.n_input == 0 || io_num.n_output == 0) {
      std::cerr << "rknn_query IO num failed: " << ret << "\n";
      return false;
    }
    input_attrs_.resize(io_num.n_input);
    output_attrs_.resize(io_num.n_output);
    for (uint32_t i = 0; i < io_num.n_input; ++i) {
      std::memset(&input_attrs_[i], 0, sizeof(rknn_tensor_attr));
      input_attrs_[i].index = i;
      ret = rknn_query(ctx_, RKNN_QUERY_INPUT_ATTR, &input_attrs_[i], sizeof(rknn_tensor_attr));
      if (ret != RKNN_SUCC) {
        std::cerr << "rknn_query input attr failed: " << ret << "\n";
        return false;
      }
    }
    if (buffer_reuse_) {
      input_native_attrs_.resize(io_num.n_input);
      for (uint32_t i = 0; i < io_num.n_input; ++i) {
        std::memset(&input_native_attrs_[i], 0, sizeof(rknn_tensor_attr));
        input_native_attrs_[i].index = i;
        ret = rknn_query(ctx_, RKNN_QUERY_NATIVE_INPUT_ATTR, &input_native_attrs_[i], sizeof(rknn_tensor_attr));
        if (ret != RKNN_SUCC) {
          std::cerr << "rknn_query native input attr failed: " << ret
                    << " (buffer reuse falls back to non-io-mem path)\n";
          input_native_attrs_.clear();
          break;
        }
      }
    }
    for (uint32_t i = 0; i < io_num.n_output; ++i) {
      std::memset(&output_attrs_[i], 0, sizeof(rknn_tensor_attr));
      output_attrs_[i].index = i;
      ret = rknn_query(ctx_, RKNN_QUERY_OUTPUT_ATTR, &output_attrs_[i], sizeof(rknn_tensor_attr));
      if (ret != RKNN_SUCC) {
        std::cerr << "rknn_query output attr failed: " << ret << "\n";
        return false;
      }
      output_count_ += static_cast<size_t>(output_attrs_[i].n_elems);
      TensorInfo info;
      info.elem_count = static_cast<size_t>(output_attrs_[i].n_elems);
      for (uint32_t d = 0; d < output_attrs_[i].n_dims; ++d) {
        info.dims.push_back(static_cast<int>(output_attrs_[i].dims[d]));
      }
      output_infos_.push_back(std::move(info));
    }

    input_count_ = 3ULL * model.input_h * model.input_w;
    nhwc_u8_.resize(input_count_);
    if (buffer_reuse_) {
      TryEnableReusableInput();
      EnablePreallocatedOutputs();
    }
    std::cout << "RKNN_BACKEND_INIT: model=" << board.artifact_path
              << " inputs=" << io_num.n_input
              << " outputs=" << io_num.n_output
              << " provider=RKNPU"
              << " loader_api=RKNN C API"
              << " core_mask=" << board.rknn_core_mask
              << " buffer_reuse_requested=" << (buffer_reuse_ ? "true" : "false")
              << " input_io_mem=" << (input_io_mem_enabled_ ? "true" : "false")
              << " output_prealloc=" << (output_prealloc_enabled_ ? "true" : "false")
              << "\n";
    return output_count_ > 0;
  }

  bool Infer(const std::vector<float>& input,
             const std::vector<uint8_t>*,
             std::vector<float>& output,
             double& inference_ms) override {
    if (input.size() != input_count_) {
      std::cerr << "Input tensor size mismatch: got " << input.size() << ", expected " << input_count_ << "\n";
      return false;
    }
    const auto start = Clock::now();

    const rknn_tensor_attr& input_attr = input_attrs_[0];
    int ret = RKNN_SUCC;
    if (input_io_mem_enabled_) {
      if (!CopyInputToReusableBuffer(input)) {
        return false;
      }
    } else {
      rknn_input rknn_in{};
      rknn_in.index = 0;
      rknn_in.pass_through = 0;
      if (input_attr.type == RKNN_TENSOR_FLOAT32) {
        float_input_ = input;
        rknn_in.type = RKNN_TENSOR_FLOAT32;
        rknn_in.fmt = RKNN_TENSOR_NCHW;
        rknn_in.buf = float_input_.data();
        rknn_in.size = static_cast<uint32_t>(float_input_.size() * sizeof(float));
      } else {
        const int area = static_cast<int>(input.size() / 3);
        for (int idx = 0; idx < area; ++idx) {
          for (int c = 0; c < 3; ++c) {
            const float v = std::clamp(input[c * area + idx] * 255.0f, 0.0f, 255.0f);
            nhwc_u8_[idx * 3 + c] = static_cast<uint8_t>(std::round(v));
          }
        }
        rknn_in.type = RKNN_TENSOR_UINT8;
        rknn_in.fmt = RKNN_TENSOR_NHWC;
        rknn_in.buf = nhwc_u8_.data();
        rknn_in.size = static_cast<uint32_t>(nhwc_u8_.size());
      }

      ret = rknn_inputs_set(ctx_, 1, &rknn_in);
      if (ret != RKNN_SUCC) {
        std::cerr << "rknn_inputs_set failed: " << ret << "\n";
        return false;
      }
    }

    ret = rknn_run(ctx_, nullptr);
    if (ret != RKNN_SUCC) {
      std::cerr << "rknn_run failed: " << ret << "\n";
      return false;
    }

    std::vector<rknn_output> outputs =
        output_prealloc_enabled_ ? prealloc_outputs_ : std::vector<rknn_output>(output_attrs_.size());
    if (!output_prealloc_enabled_) {
      for (size_t i = 0; i < outputs.size(); ++i) {
        outputs[i].index = static_cast<uint32_t>(i);
        outputs[i].want_float = 1;
        outputs[i].is_prealloc = 0;
      }
    }
    ret = rknn_outputs_get(ctx_, static_cast<uint32_t>(outputs.size()), outputs.data(), nullptr);
    if (ret != RKNN_SUCC) {
      std::cerr << "rknn_outputs_get failed: " << ret << "\n";
      return false;
    }

    output.clear();
    output.reserve(output_count_);
    if (output_prealloc_enabled_) {
      for (size_t i = 0; i < outputs.size(); ++i) {
        const size_t count = std::min(output_float_buffers_[i].size(), static_cast<size_t>(outputs[i].size / sizeof(float)));
        if (count > 0) {
          output.insert(output.end(), output_float_buffers_[i].data(), output_float_buffers_[i].data() + count);
        }
      }
    } else {
      for (const auto& one : outputs) {
        const size_t count = one.size / sizeof(float);
        const auto* ptr = static_cast<const float*>(one.buf);
        if (ptr && count > 0) output.insert(output.end(), ptr, ptr + count);
      }
    }
    rknn_outputs_release(ctx_, static_cast<uint32_t>(outputs.size()), outputs.data());
    inference_ms = MsSince(start);
    return !output.empty();
  }

  const std::vector<TensorInfo>& OutputInfos() const override { return output_infos_; }

 private:
  bool CopyInputToReusableBuffer(const std::vector<float>& input) {
    if (input_mem_ == nullptr || input_mem_->virt_addr == nullptr) {
      std::cerr << "RKNN reusable input buffer is not initialized\n";
      return false;
    }
    if (input_copy_bytes_ == 0 || input_copy_bytes_ > input_mem_->size) {
      std::cerr << "RKNN reusable input buffer size mismatch: copy_bytes=" << input_copy_bytes_
                << " alloc_bytes=" << (input_mem_ != nullptr ? input_mem_->size : 0) << "\n";
      return false;
    }
    if (input_mem_->size > input_copy_bytes_) {
      std::memset(input_mem_->virt_addr, 0, input_mem_->size);
    }
    if (input_io_attr_.type == RKNN_TENSOR_FLOAT32) {
      std::memcpy(input_mem_->virt_addr, input.data(), input_copy_bytes_);
      return true;
    }
    const int area = static_cast<int>(input.size() / 3);
    for (int idx = 0; idx < area; ++idx) {
      for (int c = 0; c < 3; ++c) {
        const float v = std::clamp(input[c * area + idx] * 255.0f, 0.0f, 255.0f);
        nhwc_u8_[idx * 3 + c] = static_cast<uint8_t>(std::round(v));
      }
    }
    std::memcpy(input_mem_->virt_addr, nhwc_u8_.data(), input_copy_bytes_);
    return true;
  }

  void TryEnableReusableInput() {
    if (input_native_attrs_.size() != 1 || input_attrs_.size() != 1) {
      return;
    }
    input_io_attr_ = input_native_attrs_[0];
    const bool float_input = input_attrs_[0].type == RKNN_TENSOR_FLOAT32;
    const size_t logical_bytes = float_input ? input_count_ * sizeof(float) : input_count_;
    if (input_io_attr_.size_with_stride != logical_bytes) {
      std::cout << "RKNN_BUFFER_REUSE_SKIP: input_size_with_stride=" << input_io_attr_.size_with_stride
                << " logical_bytes=" << logical_bytes
                << " reason=stride_layout_not_supported_by_current_copy_path\n";
      return;
    }
    input_io_attr_.type = float_input ? RKNN_TENSOR_FLOAT32 : RKNN_TENSOR_UINT8;
    input_io_attr_.fmt = float_input ? RKNN_TENSOR_NCHW : RKNN_TENSOR_NHWC;
    input_io_attr_.pass_through = 0;
    input_mem_ = rknn_create_mem(ctx_, input_io_attr_.size_with_stride);
    if (input_mem_ == nullptr) {
      std::cout << "RKNN_BUFFER_REUSE_SKIP: reason=create_mem_failed\n";
      return;
    }
    const int ret = rknn_set_io_mem(ctx_, input_mem_, &input_io_attr_);
    if (ret != RKNN_SUCC) {
      std::cout << "RKNN_BUFFER_REUSE_SKIP: reason=set_io_mem_failed ret=" << ret << "\n";
      rknn_destroy_mem(ctx_, input_mem_);
      input_mem_ = nullptr;
      return;
    }
    input_copy_bytes_ = logical_bytes;
    input_io_mem_enabled_ = true;
  }

  void EnablePreallocatedOutputs() {
    output_float_buffers_.resize(output_attrs_.size());
    prealloc_outputs_.resize(output_attrs_.size());
    for (size_t i = 0; i < output_attrs_.size(); ++i) {
      output_float_buffers_[i].resize(static_cast<size_t>(output_attrs_[i].n_elems));
      rknn_output out{};
      out.index = static_cast<uint32_t>(i);
      out.want_float = 1;
      out.is_prealloc = 1;
      out.buf = output_float_buffers_[i].data();
      out.size = static_cast<uint32_t>(output_float_buffers_[i].size() * sizeof(float));
      prealloc_outputs_[i] = out;
    }
    output_prealloc_enabled_ = !prealloc_outputs_.empty();
  }

  rknn_context ctx_ = 0;
  std::vector<char> model_data_;
  std::vector<rknn_tensor_attr> input_attrs_;
  std::vector<rknn_tensor_attr> input_native_attrs_;
  std::vector<rknn_tensor_attr> output_attrs_;
  std::vector<TensorInfo> output_infos_;
  std::vector<uint8_t> nhwc_u8_;
  std::vector<float> float_input_;
  std::vector<std::vector<float>> output_float_buffers_;
  std::vector<rknn_output> prealloc_outputs_;
  rknn_tensor_mem* input_mem_ = nullptr;
  rknn_tensor_attr input_io_attr_{};
  size_t input_copy_bytes_ = 0;
  size_t input_count_ = 0;
  size_t output_count_ = 0;
  bool buffer_reuse_ = false;
  bool input_io_mem_enabled_ = false;
  bool output_prealloc_enabled_ = false;
};
#endif

#if defined(PIPELINE_BACKEND_BPU)
std::vector<int> BpuShapeDims(const hbDNNTensorShape& shape) {
  std::vector<int> dims;
  dims.reserve(static_cast<size_t>(shape.numDimensions));
  for (int i = 0; i < shape.numDimensions; ++i) {
    dims.push_back(shape.dimensionSize[i]);
  }
  return dims;
}

size_t BpuElemCount(const std::vector<int>& dims) {
  size_t count = 1;
  for (int dim : dims) {
    if (dim <= 0) return 0;
    count *= static_cast<size_t>(dim);
  }
  return count;
}

size_t BpuAxisIndexFromFlat(size_t flat, const std::vector<int>& dims, int axis) {
  if (axis < 0 || axis >= static_cast<int>(dims.size()) || dims.empty()) return 0;
  std::vector<size_t> coords(dims.size(), 0);
  for (int i = static_cast<int>(dims.size()) - 1; i >= 0; --i) {
    const size_t dim = static_cast<size_t>(std::max(dims[i], 1));
    coords[static_cast<size_t>(i)] = flat % dim;
    flat /= dim;
  }
  return coords[static_cast<size_t>(axis)];
}

int BpuTensorHeight(const hbDNNTensorProperties& props) {
  const std::vector<int> dims = BpuShapeDims(props.validShape);
  if (dims.size() != 4) return 0;
  return props.tensorLayout == HB_DNN_LAYOUT_NHWC ? dims[1] : dims[2];
}

int BpuTensorWidth(const hbDNNTensorProperties& props) {
  const std::vector<int> dims = BpuShapeDims(props.validShape);
  if (dims.size() != 4) return 0;
  return props.tensorLayout == HB_DNN_LAYOUT_NHWC ? dims[2] : dims[3];
}

std::vector<int> BpuAlignedDims(const hbDNNTensorProperties& props) {
  std::vector<int> dims = BpuShapeDims(props.alignedShape);
  if (dims.size() != 4) return BpuShapeDims(props.validShape);
  bool valid = true;
  for (int dim : dims) {
    if (dim <= 0) {
      valid = false;
      break;
    }
  }
  return valid ? dims : BpuShapeDims(props.validShape);
}

float BpuApplyQuanti(double raw,
                     const hbDNNTensorProperties& props,
                     size_t flat_index,
                     const std::vector<int>& dims) {
  if (props.quantiType == NONE) return static_cast<float>(raw);
  if (props.quantiType == SHIFT) {
    if (props.shift.shiftLen <= 0 || props.shift.shiftData == nullptr) return static_cast<float>(raw);
    const size_t axis_index =
        props.shift.shiftLen == 1
            ? 0
            : std::min(
                  BpuAxisIndexFromFlat(flat_index, dims, props.quantizeAxis),
                  static_cast<size_t>(props.shift.shiftLen - 1));
    const int shift = props.shift.shiftData[axis_index];
    return static_cast<float>(std::ldexp(raw, -shift));
  }
  if (props.quantiType == SCALE) {
    double scale = 1.0;
    double zero_point = 0.0;
    if (props.scale.scaleLen > 0 && props.scale.scaleData != nullptr) {
      const size_t scale_index =
          props.scale.scaleLen == 1
              ? 0
              : std::min(
                    BpuAxisIndexFromFlat(flat_index, dims, props.quantizeAxis),
                    static_cast<size_t>(props.scale.scaleLen - 1));
      scale = props.scale.scaleData[scale_index];
    }
    if (props.scale.zeroPointLen > 0 && props.scale.zeroPointData != nullptr) {
      const size_t zp_index =
          props.scale.zeroPointLen == 1
              ? 0
              : std::min(
                    BpuAxisIndexFromFlat(flat_index, dims, props.quantizeAxis),
                    static_cast<size_t>(props.scale.zeroPointLen - 1));
      zero_point = props.scale.zeroPointData[zp_index];
    }
    return static_cast<float>((raw - zero_point) * scale);
  }
  return static_cast<float>(raw);
}

template <typename T>
void BpuAppendTensor(const T* src,
                     const hbDNNTensorProperties& props,
                     const std::vector<int>& dims,
                     std::vector<float>& output) {
  const size_t elem_count = BpuElemCount(dims);
  const std::vector<int> aligned_dims = BpuAlignedDims(props);
  if (dims.size() == 4 &&
      aligned_dims.size() == 4 &&
      (props.tensorLayout == HB_DNN_LAYOUT_NCHW || props.tensorLayout == HB_DNN_LAYOUT_NHWC)) {
    size_t flat_index = 0;
    if (props.tensorLayout == HB_DNN_LAYOUT_NCHW) {
      const size_t n_limit = static_cast<size_t>(dims[0]);
      const size_t c_limit = static_cast<size_t>(dims[1]);
      const size_t h_limit = static_cast<size_t>(dims[2]);
      const size_t w_limit = static_cast<size_t>(dims[3]);
      const size_t aligned_c = static_cast<size_t>(aligned_dims[1]);
      const size_t aligned_h = static_cast<size_t>(aligned_dims[2]);
      const size_t aligned_w = static_cast<size_t>(aligned_dims[3]);
      for (size_t n = 0; n < n_limit; ++n) {
        for (size_t c = 0; c < c_limit; ++c) {
          for (size_t h = 0; h < h_limit; ++h) {
            for (size_t w = 0; w < w_limit; ++w) {
              const size_t aligned_index =
                  ((n * aligned_c + c) * aligned_h + h) * aligned_w + w;
              output.push_back(
                  BpuApplyQuanti(static_cast<double>(src[aligned_index]), props, flat_index++, dims));
            }
          }
        }
      }
    } else {
      const size_t n_limit = static_cast<size_t>(dims[0]);
      const size_t h_limit = static_cast<size_t>(dims[1]);
      const size_t w_limit = static_cast<size_t>(dims[2]);
      const size_t c_limit = static_cast<size_t>(dims[3]);
      const size_t aligned_h = static_cast<size_t>(aligned_dims[1]);
      const size_t aligned_w = static_cast<size_t>(aligned_dims[2]);
      const size_t aligned_c = static_cast<size_t>(aligned_dims[3]);
      for (size_t n = 0; n < n_limit; ++n) {
        for (size_t h = 0; h < h_limit; ++h) {
          for (size_t w = 0; w < w_limit; ++w) {
            for (size_t c = 0; c < c_limit; ++c) {
              const size_t aligned_index =
                  ((n * aligned_h + h) * aligned_w + w) * aligned_c + c;
              output.push_back(
                  BpuApplyQuanti(static_cast<double>(src[aligned_index]), props, flat_index++, dims));
            }
          }
        }
      }
    }
    return;
  }
  for (size_t i = 0; i < elem_count; ++i) {
    output.push_back(BpuApplyQuanti(static_cast<double>(src[i]), props, i, dims));
  }
}

class BpuBackend final : public Backend {
 public:
  ~BpuBackend() override {
    for (auto& tensor : output_tensors_) {
      if (tensor.sysMem[0].virAddr != nullptr || tensor.sysMem[0].phyAddr != 0) {
        hbSysFreeMem(&tensor.sysMem[0]);
      }
    }
    if (input_tensor_.sysMem[0].virAddr != nullptr || input_tensor_.sysMem[0].phyAddr != 0) {
      hbSysFreeMem(&input_tensor_.sysMem[0]);
    }
    if (packed_dnn_handle_ != nullptr) {
      hbDNNRelease(packed_dnn_handle_);
      packed_dnn_handle_ = nullptr;
    }
  }

  bool Init(const BoardConfig& board, const ModelConfig&, bool buffer_reuse) override {
    buffer_reuse_ = buffer_reuse;
    const char* model_file_name = board.artifact_path.c_str();
    int32_t ret = hbDNNInitializeFromFiles(&packed_dnn_handle_, &model_file_name, 1);
    if (ret != 0) {
      std::cerr << "hbDNNInitializeFromFiles failed: " << ret << "\n";
      return false;
    }

    const char** model_name_list = nullptr;
    int32_t model_count = 0;
    ret = hbDNNGetModelNameList(&model_name_list, &model_count, packed_dnn_handle_);
    if (ret != 0 || model_count <= 0 || model_name_list == nullptr) {
      std::cerr << "hbDNNGetModelNameList failed: " << ret << "\n";
      return false;
    }
    ret = hbDNNGetModelHandle(&dnn_handle_, packed_dnn_handle_, model_name_list[0]);
    if (ret != 0) {
      std::cerr << "hbDNNGetModelHandle failed: " << ret << "\n";
      return false;
    }

    int32_t input_count = 0;
    ret = hbDNNGetInputCount(&input_count, dnn_handle_);
    if (ret != 0 || input_count != 1) {
      std::cerr << "hbDNNGetInputCount failed or unexpected input count: ret=" << ret
                << " count=" << input_count << "\n";
      return false;
    }

    std::memset(&input_props_, 0, sizeof(input_props_));
    ret = hbDNNGetInputTensorProperties(&input_props_, dnn_handle_, 0);
    if (ret != 0) {
      std::cerr << "hbDNNGetInputTensorProperties failed: " << ret << "\n";
      return false;
    }
    input_h_ = BpuTensorHeight(input_props_);
    input_w_ = BpuTensorWidth(input_props_);
    input_nv12_bytes_ = static_cast<size_t>(input_h_) * static_cast<size_t>(input_w_) * 3ULL / 2ULL;
    if (input_h_ <= 0 || input_w_ <= 0 || input_nv12_bytes_ == 0) {
      std::cerr << "Unsupported BPU input shape\n";
      return false;
    }

    std::memset(&input_tensor_, 0, sizeof(input_tensor_));
    input_tensor_.properties = input_props_;
    input_tensor_.properties.tensorType = HB_DNN_IMG_TYPE_NV12;
    input_tensor_.properties.alignedShape = input_tensor_.properties.validShape;
    ret = hbSysAllocCachedMem(&input_tensor_.sysMem[0], input_nv12_bytes_);
    if (ret != 0) {
      std::cerr << "hbSysAllocCachedMem input failed: " << ret << "\n";
      return false;
    }

    int32_t output_count = 0;
    ret = hbDNNGetOutputCount(&output_count, dnn_handle_);
    if (ret != 0 || output_count <= 0) {
      std::cerr << "hbDNNGetOutputCount failed: " << ret << "\n";
      return false;
    }
    output_props_.resize(static_cast<size_t>(output_count));
    output_tensors_.resize(static_cast<size_t>(output_count));
    output_infos_.clear();
    output_infos_.reserve(static_cast<size_t>(output_count));
    for (int32_t i = 0; i < output_count; ++i) {
      std::memset(&output_props_[static_cast<size_t>(i)], 0, sizeof(hbDNNTensorProperties));
      ret = hbDNNGetOutputTensorProperties(&output_props_[static_cast<size_t>(i)], dnn_handle_, i);
      if (ret != 0) {
        std::cerr << "hbDNNGetOutputTensorProperties failed: index=" << i << " ret=" << ret << "\n";
        return false;
      }
      std::memset(&output_tensors_[static_cast<size_t>(i)], 0, sizeof(hbDNNTensor));
      output_tensors_[static_cast<size_t>(i)].properties = output_props_[static_cast<size_t>(i)];
      ret = hbSysAllocCachedMem(
          &output_tensors_[static_cast<size_t>(i)].sysMem[0],
          output_props_[static_cast<size_t>(i)].alignedByteSize);
      if (ret != 0) {
        std::cerr << "hbSysAllocCachedMem output failed: index=" << i << " ret=" << ret << "\n";
        return false;
      }
      TensorInfo info;
      info.dims = BpuShapeDims(output_props_[static_cast<size_t>(i)].validShape);
      info.elem_count = BpuElemCount(info.dims);
      output_infos_.push_back(std::move(info));
    }

    std::cout << "BPU_BACKEND_INIT: model=" << board.artifact_path
              << " provider=BPU"
              << " loader_api=Horizon hbDNN C API"
              << " inputs=1"
              << " outputs=" << output_count
              << " input=" << input_w_ << "x" << input_h_
              << " buffer_reuse_requested=" << (buffer_reuse_ ? "true" : "false")
              << "\n";
    return true;
  }

  bool Infer(const std::vector<float>&,
             const std::vector<uint8_t>* nv12_input,
             std::vector<float>& output,
             double& inference_ms) override {
    if (nv12_input == nullptr || nv12_input->size() != input_nv12_bytes_) {
      std::cerr << "BPU input NV12 size mismatch: got "
                << (nv12_input != nullptr ? nv12_input->size() : 0)
                << ", expected " << input_nv12_bytes_ << "\n";
      return false;
    }
    const auto start = Clock::now();
    std::memcpy(input_tensor_.sysMem[0].virAddr, nv12_input->data(), input_nv12_bytes_);
    hbSysFlushMem(&input_tensor_.sysMem[0], HB_SYS_MEM_CACHE_CLEAN);

    hbDNNTaskHandle_t task_handle = nullptr;
    hbDNNInferCtrlParam infer_ctrl;
    HB_DNN_INITIALIZE_INFER_CTRL_PARAM(&infer_ctrl);
    hbDNNTensor* output_ptr = output_tensors_.data();
    int32_t ret = hbDNNInfer(&task_handle, &output_ptr, &input_tensor_, dnn_handle_, &infer_ctrl);
    if (ret != 0) {
      std::cerr << "hbDNNInfer failed: " << ret << "\n";
      return false;
    }
    ret = hbDNNWaitTaskDone(task_handle, 0);
    if (ret != 0) {
      std::cerr << "hbDNNWaitTaskDone failed: " << ret << "\n";
      hbDNNReleaseTask(task_handle);
      return false;
    }
    hbDNNReleaseTask(task_handle);

    output.clear();
    size_t total_output = 0;
    for (const auto& info : output_infos_) total_output += info.elem_count;
    output.reserve(total_output);

    for (size_t i = 0; i < output_tensors_.size(); ++i) {
      hbSysFlushMem(&output_tensors_[i].sysMem[0], HB_SYS_MEM_CACHE_INVALIDATE);
      const void* base = output_tensors_[i].sysMem[0].virAddr;
      const auto& props = output_props_[i];
      const auto& info = output_infos_[i];
      switch (props.tensorType) {
        case HB_DNN_TENSOR_TYPE_F32:
          BpuAppendTensor(static_cast<const float*>(base), props, info.dims, output);
          break;
        case HB_DNN_TENSOR_TYPE_S32:
          BpuAppendTensor(static_cast<const int32_t*>(base), props, info.dims, output);
          break;
        case HB_DNN_TENSOR_TYPE_S8:
          BpuAppendTensor(static_cast<const int8_t*>(base), props, info.dims, output);
          break;
        case HB_DNN_TENSOR_TYPE_U8:
          BpuAppendTensor(static_cast<const uint8_t*>(base), props, info.dims, output);
          break;
        default:
          std::cerr << "Unsupported BPU output tensor type: " << props.tensorType << "\n";
          return false;
      }
    }
    inference_ms = MsSince(start);
    return !output.empty();
  }

  const std::vector<TensorInfo>& OutputInfos() const override { return output_infos_; }

 private:
  hbPackedDNNHandle_t packed_dnn_handle_ = nullptr;
  hbDNNHandle_t dnn_handle_ = nullptr;
  hbDNNTensorProperties input_props_{};
  hbDNNTensor input_tensor_{};
  std::vector<hbDNNTensorProperties> output_props_;
  std::vector<hbDNNTensor> output_tensors_;
  std::vector<TensorInfo> output_infos_;
  size_t input_nv12_bytes_ = 0;
  int input_w_ = 0;
  int input_h_ = 0;
  bool buffer_reuse_ = false;
};
#endif

std::unique_ptr<Backend> CreateBackend(const BoardConfig& board) {
#if defined(PIPELINE_BACKEND_TENSORRT)
  if (board.backend_runtime == "tensorrt") return std::make_unique<TensorRtBackend>();
#endif
#if defined(PIPELINE_BACKEND_RKNN)
  if (board.backend_runtime == "rknn") return std::make_unique<RknnBackend>();
#endif
#if defined(PIPELINE_BACKEND_BPU)
  if (board.backend_runtime == "bpu") return std::make_unique<BpuBackend>();
#endif
  return std::make_unique<MockBackend>();
}

void DrawDetections(cv::Mat& frame, const std::vector<Detection>& detections) {
  for (const auto& det : detections) {
    const cv::Rect box(static_cast<int>(std::round(det.box.x)),
                       static_cast<int>(std::round(det.box.y)),
                       static_cast<int>(std::round(det.box.width)),
                       static_cast<int>(std::round(det.box.height)));
    cv::rectangle(frame, box, cv::Scalar(0, 255, 0), 2);
    const std::string label = FormatDetectionLabel(det);
    int baseline = 0;
    const cv::Size text_size =
        cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, 0.55, 1, &baseline);
    const int box_x = std::max(0, box.x);
    int label_top = box.y - text_size.height - 10;
    if (label_top < 0) label_top = std::min(std::max(0, box.y + 4), std::max(0, frame.rows - text_size.height - 8));
    int label_width = std::min(frame.cols - box_x, text_size.width + 10);
    if (label_width <= 0) continue;
    cv::Rect label_bg(box_x, label_top, label_width, text_size.height + 8);
    label_bg &= cv::Rect(0, 0, frame.cols, frame.rows);
    cv::rectangle(frame, label_bg, cv::Scalar(0, 255, 0), cv::FILLED);
    const int text_x = label_bg.x + 5;
    const int text_y = std::min(label_bg.y + text_size.height + 2, frame.rows - 2);
    cv::putText(frame, label, cv::Point(text_x, text_y),
                cv::FONT_HERSHEY_SIMPLEX, 0.55, cv::Scalar(0, 0, 0), 1, cv::LINE_AA);
  }
}

std::vector<Detection> DecodeOutputTensor(const BoardConfig& board,
                                          const Backend& backend,
                                          const std::vector<float>& output_tensor,
                                          const ModelConfig& model,
                                          const LetterboxInfo& letterbox,
                                          const cv::Size& frame_size) {
  if (board.backend_runtime == "rknn") {
    std::vector<Detection> detections =
        DecodeRknnOfficialYolo11(output_tensor, backend.OutputInfos(), model, letterbox, frame_size);
    if (detections.empty()) {
      detections = DecodeYolo(output_tensor, model, letterbox, frame_size);
    }
    return detections;
  }
  if (board.backend_runtime == "bpu") {
    return DecodeRknnOfficialYolo11(
        output_tensor, backend.OutputInfos(), model, letterbox, frame_size, true);
  }
  return DecodeYolo(output_tensor, model, letterbox, frame_size);
}

void WriteRaw(std::ofstream& out,
              const Args& args,
              const BoardConfig& board,
              const ModelConfig& model,
              const PipelineConfig& pipeline,
              const ResultPacket& packet,
              int input_w,
              int input_h,
              int queue_capture_size,
              int queue_preprocess_size,
              int queue_infer_size,
              int queue_postprocess_size,
              int dropped_count) {
  const char* env_id = std::getenv("ENVIRONMENT_BASELINE_ID");
  const std::string environment_baseline_id =
      env_id ? env_id
             : (board.backend_runtime == "bpu"
                    ? "20260612_rdk_x5_8gb_env_baseline"
                    : "pending_project3_jetson_env_baseline");
  const std::string input_sha = std::getenv("INPUT_SOURCE_SHA256") ? std::getenv("INPUT_SOURCE_SHA256") : "";
  const char* power_mode_env = std::getenv("POWER_MODE");
  const std::string power_mode = power_mode_env ? power_mode_env : "not_recorded";
  const std::string utilization_source =
      board.backend_runtime == "rknn"
          ? "rknpu_monitor"
          : (board.backend_runtime == "tensorrt"
                 ? "tegrastats"
                 : (board.backend_runtime == "bpu" ? "rdk_x5_bpu_monitor" : "runtime_monitor"));
  const double drop_frame_rate =
      dropped_count > 0 ? static_cast<double>(dropped_count) / static_cast<double>(dropped_count + packet.frame_id + 1) : 0.0;

  out << "{";
  out << "\"run_id\":\"" << JsonEscape(std::getenv("RUN_ID") ? std::getenv("RUN_ID") : "unknown_run") << "\",";
  out << "\"timestamp\":\"" << NowIso() << "\",";
  out << "\"schema_version\":1,";
  out << "\"project\":\"03_video_pipeline\",";
  out << "\"measurement_scope\":\"frame\",";
  out << "\"board\":\"" << JsonEscape(board.board) << "\",";
  out << "\"target\":\"" << JsonEscape(board.target) << "\",";
  out << "\"environment_baseline_id\":\"" << JsonEscape(environment_baseline_id) << "\",";
  out << "\"backend_runtime\":\"" << JsonEscape(board.backend_runtime) << "\",";
  out << "\"execution_provider\":\"" << JsonEscape(board.execution_provider) << "\",";
  out << "\"loader_api\":\"" << JsonEscape(board.loader_api) << "\",";
  out << "\"model\":\"yolo11n\",";
  out << "\"model_file_hash\":\"" << JsonEscape(board.artifact_sha256) << "\",";
  out << "\"precision_or_quantization\":\"" << JsonEscape(board.precision) << "\",";
  out << "\"backend_artifact_format\":\"" << JsonEscape(board.artifact_format) << "\",";
  out << "\"backend_artifact_path\":\"" << JsonEscape(board.artifact_path) << "\",";
  out << "\"backend_artifact_sha256\":\"" << JsonEscape(board.artifact_sha256) << "\",";
  out << "\"input_source_id\":\"" << JsonEscape(args.input_source_id) << "\",";
  out << "\"input_source_type\":\"" << JsonEscape(args.input_source_type) << "\",";
  out << "\"input_source_sha256\":" << JsonStringOrNull(input_sha) << ",";
  out << "\"input_width\":" << input_w << ",";
  out << "\"input_height\":" << input_h << ",";
  out << "\"input_fps\":" << packet.input_fps << ",";
  out << "\"pipeline_mode\":\"" << JsonEscape(pipeline.pipeline_mode) << "\",";
  out << "\"queue_policy\":\"" << JsonEscape(pipeline.queue_policy) << "\",";
  out << "\"queue_capacity\":" << pipeline.queue_capacity << ",";
  out << "\"queue_push_timeout_ms\":" << pipeline.queue_push_timeout_ms << ",";
  out << "\"inference_workers\":" << pipeline.inference_workers << ",";
  out << "\"postprocess_workers\":" << pipeline.postprocess_workers << ",";
  const std::string core_binding =
      board.backend_runtime == "rknn" && pipeline.inference_workers > 1
          ? "core0,core1,core2"
          : board.rknn_core_mask;
  out << "\"rknn_core_binding\":\"" << JsonEscape(core_binding) << "\",";
  out << "\"buffer_reuse\":" << (pipeline.buffer_reuse ? "true" : "false") << ",";
  out << "\"frame_id\":" << packet.frame_id << ",";
  out << "\"capture_ts\":\"" << JsonEscape(packet.trace.capture_ts) << "\",";
  out << "\"decode_ts\":" << JsonStringOrNull(packet.trace.decode_ts) << ",";
  out << "\"preprocess_ts\":" << JsonStringOrNull(packet.trace.preprocess_ts) << ",";
  out << "\"infer_start_ts\":" << JsonStringOrNull(packet.trace.infer_start_ts) << ",";
  out << "\"infer_end_ts\":" << JsonStringOrNull(packet.trace.infer_end_ts) << ",";
  out << "\"postprocess_ts\":" << JsonStringOrNull(packet.trace.postprocess_ts) << ",";
  out << "\"output_ts\":" << JsonStringOrNull(packet.trace.output_ts) << ",";
  out << "\"capture_ms\":" << packet.trace.capture_ms << ",";
  out << "\"decode_ms\":" << packet.trace.decode_ms << ",";
  out << "\"preprocess_ms\":" << packet.trace.preprocess_ms << ",";
  out << "\"inference_ms\":" << packet.trace.inference_ms << ",";
  out << "\"postprocess_ms\":" << packet.trace.postprocess_ms << ",";
  out << "\"output_ms\":" << packet.trace.output_ms << ",";
  out << "\"end_to_end_latency_ms\":"
      << (packet.trace.capture_ms + packet.trace.decode_ms + packet.trace.preprocess_ms +
          packet.trace.inference_ms + packet.trace.postprocess_ms + packet.trace.output_ms) << ",";
  out << "\"queue_capture_size\":" << queue_capture_size << ",";
  out << "\"queue_preprocess_size\":" << queue_preprocess_size << ",";
  out << "\"queue_infer_size\":" << queue_infer_size << ",";
  out << "\"queue_postprocess_size\":" << queue_postprocess_size << ",";
  out << "\"drop_frame_count\":" << dropped_count << ",";
  out << "\"drop_frame_rate\":" << drop_frame_rate << ",";
  out << "\"dropped_frame_reason\":" << (dropped_count > 0 ? "\"queue_full\"" : "null") << ",";
  out << "\"output_valid\":" << (packet.ok ? "true" : "false") << ",";
  out << "\"detection_count\":" << packet.detections.size() << ",";
  out << "\"detections\":[";
  for (size_t i = 0; i < packet.detections.size(); ++i) {
    const auto& det = packet.detections[i];
    if (i > 0) out << ",";
    out << "{";
    out << "\"class_id\":" << det.class_id << ",";
    out << "\"confidence\":" << det.confidence << ",";
    out << "\"bbox_xywh\":["
        << det.box.x << ","
        << det.box.y << ","
        << det.box.width << ","
        << det.box.height << "]";
    out << "}";
  }
  out << "],";
  out << "\"detection_quality_status\":\"not_checked\",";
  out << "\"runtime_evidence_path\":\"" << JsonEscape(args.runtime_log_path) << "\",";
  out << "\"accelerator_evidence_path\":" << JsonStringOrNull(args.monitor_log_path) << ",";
  out << "\"cpu_fallback\":false,";
  out << "\"fallback_reason\":null,";
  out << "\"memory_mb\":null,";
  out << "\"temperature_c\":null,";
  out << "\"power_w\":null,";
  out << "\"power_mode\":\"" << JsonEscape(power_mode) << "\",";
  out << "\"cpu_gpu_npu_bpu_utilization\":{\"source\":\"" << JsonEscape(utilization_source) << "\",\"log_path\":"
      << JsonStringOrNull(args.monitor_log_path) << "},";
  out << "\"status\":\"" << (packet.ok ? "pass" : "fail") << "\",";
  out << "\"error_code\":\"" << JsonEscape(packet.error_code) << "\",";
  out << "\"runtime_log_path\":\"" << JsonEscape(args.runtime_log_path) << "\",";
  out << "\"monitor_log_path\":" << JsonStringOrNull(args.monitor_log_path) << ",";
  out << "\"failure_log_path\":null,";
  out << "\"related_troubleshooting_id\":null";
  out << "}\n";
}

int RunSingleThreadPipeline(const Args& args,
                            const ModelConfig& model,
                            const BoardConfig& board,
                            const PipelineConfig& pipeline) {
  auto backend = CreateBackend(board);
  if (!backend->Init(board, model, pipeline.buffer_reuse)) {
    std::cerr << "BACKEND_RUNTIME_FAILED: failed to initialize " << board.backend_runtime << "\n";
    return 21;
  }
  if (!WarmupBackend(*backend, board, model, 0)) {
    return 21;
  }

  FrameReader source(args);
  try {
    source.Open();
  } catch (const std::exception& e) {
    std::cerr << e.what() << "\n";
    return 10;
  }

  std::ofstream raw(args.raw_output);
  if (!raw) {
    std::cerr << "OUTPUT_FAILED: cannot open raw output " << args.raw_output << "\n";
    return 40;
  }

  const int input_w = source.width();
  const int input_h = source.height();
  const bool file_like_input = source.file_like_input();
  const bool pace_video_file = file_like_input && pipeline.pace_video_file;

  std::cout << "INPUT_PACING: input_source_type=" << args.input_source_type
            << " source_fps=" << source.input_fps()
            << " source_fps_basis=" << source.input_fps_basis()
            << " pace_video_file=" << (pace_video_file ? "true" : "false")
            << " pacing_mode=" << (pace_video_file ? "source_timestamps_with_fps_fallback" : "unpaced")
            << " source_duration_ms=" << source.source_duration_ms()
            << " playlist_input=" << (source.playlist_input() ? "true" : "false")
            << " playlist_items=" << source.playlist_size() << "\n";

  cv::VideoWriter writer;
  if (!args.output_video.empty()) {
    writer.open(args.output_video, cv::VideoWriter::fourcc('m', 'p', '4', 'v'), source.input_fps(),
                cv::Size(input_w, input_h));
  }
  PreviewWindow preview(args, board.target);

  const auto started = Clock::now();
  const bool endless = args.duration_sec <= 0;
  int exit_code = 0;
  int frame_id = 0;
  auto pacing_started = Clock::now();
  auto next_frame_due = pacing_started;
  double loop_offset_ms = 0.0;
  double loop_media_base_ms = -1.0;
  double last_media_ms = -1.0;
  double current_input_fps = source.input_fps();
  double current_frame_interval_ms = source.frame_interval_ms();
  double current_source_duration_ms = source.source_duration_ms();

  while (endless || std::chrono::duration_cast<std::chrono::seconds>(Clock::now() - started).count() < args.duration_sec) {
    const auto capture_started = Clock::now();
    cv::Mat frame;
    if (!source.Read(frame)) {
      if (file_like_input && args.loop_video_file) {
        if (current_source_duration_ms > 0.0) {
          loop_offset_ms += current_source_duration_ms;
        } else if (loop_media_base_ms >= 0.0 && last_media_ms >= loop_media_base_ms) {
          loop_offset_ms += std::max(current_frame_interval_ms, last_media_ms - loop_media_base_ms + current_frame_interval_ms);
        }
        loop_media_base_ms = -1.0;
        last_media_ms = -1.0;
        if (!source.ReopenLoopSource()) {
          if (!source.last_error().empty()) {
            std::cerr << source.last_error() << "\n";
            exit_code = source.last_error().rfind("INPUT_DIMENSION_MISMATCH:", 0) == 0 ? 11 : 10;
          }
          break;
        }
        current_input_fps = source.input_fps();
        current_frame_interval_ms = source.frame_interval_ms();
        current_source_duration_ms = source.source_duration_ms();
        if (!source.Read(frame)) {
          if (!source.last_error().empty()) {
            std::cerr << source.last_error() << "\n";
            exit_code = 11;
          }
          break;
        }
      } else {
        if (!source.last_error().empty()) {
          std::cerr << "INPUT_DISCONNECTED: " << source.last_error() << "\n";
          exit_code = 11;
        }
        break;
      }
    }

    if (pace_video_file) {
      const double media_ms = source.media_position_ms();
      bool paced_with_source_timestamps = false;
      if (media_ms >= 0.0) {
        if (loop_media_base_ms < 0.0) loop_media_base_ms = media_ms;
        if (media_ms >= loop_media_base_ms) {
          const double target_ms = loop_offset_ms + (media_ms - loop_media_base_ms);
          std::this_thread::sleep_until(
              pacing_started +
              std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double, std::milli>(target_ms)));
          paced_with_source_timestamps = true;
          last_media_ms = media_ms;
        }
      }
      if (!paced_with_source_timestamps) {
        std::this_thread::sleep_until(next_frame_due);
        next_frame_due += std::chrono::duration_cast<Clock::duration>(
            std::chrono::duration<double, std::milli>(current_frame_interval_ms));
      } else {
        next_frame_due =
            Clock::now() +
            std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double, std::milli>(current_frame_interval_ms));
      }
    }

    ResultPacket packet;
    packet.frame_id = frame_id++;
    packet.input_fps = current_input_fps;
    packet.frame = frame;
    packet.trace.capture_ts = NowIso();
    packet.trace.capture_ms = MsSince(capture_started);
    packet.trace.decode_ts = packet.trace.capture_ts;
    packet.trace.decode_ms = 0.0;

    const auto preprocess_started = Clock::now();
    packet.trace.preprocess_ts = NowIso();
    LetterboxInfo letterbox;
    cv::Mat letterboxed_bgr;
    std::vector<float> input_tensor = Preprocess(frame, model, letterbox, &letterboxed_bgr);
    std::vector<uint8_t> nv12_input;
    if (board.backend_runtime == "bpu") {
      nv12_input = BgrToNv12Bytes(letterboxed_bgr);
    }
    packet.trace.preprocess_ms = MsSince(preprocess_started);

    const auto infer_started = Clock::now();
    packet.trace.infer_start_ts = NowIso();
    std::vector<float> output_tensor;
    packet.ok = backend->Infer(
        input_tensor,
        board.backend_runtime == "bpu" ? &nv12_input : nullptr,
        output_tensor,
        packet.trace.inference_ms);
    packet.trace.infer_end_ts = NowIso();
    if (!packet.ok) {
      packet.error_code = "BACKEND_RUNTIME_FAILED";
      exit_code = 21;
    }

    const auto postprocess_started = Clock::now();
    packet.trace.postprocess_ts = NowIso();
    if (packet.ok) {
      packet.detections =
          DecodeOutputTensor(board, *backend, output_tensor, model, letterbox, frame.size());
    }
    packet.trace.postprocess_ms = MsSince(postprocess_started);

    const auto output_started = Clock::now();
    packet.trace.output_ts = NowIso();
    if (!packet.frame.empty() && (writer.isOpened() || preview.enabled())) {
      DrawDetections(packet.frame, packet.detections);
      if (writer.isOpened()) writer.write(packet.frame);
      if (preview.enabled()) preview.Show(packet.frame, packet.detections.size());
    }
    packet.trace.output_ms = MsSince(output_started);
    WriteRaw(raw, args, board, model, pipeline, packet, input_w, input_h, 0, 0, 0, 0, 0);
  }

  return exit_code;
}

int RunPipeline(const Args& args,
                const ModelConfig& model,
                const BoardConfig& board,
                const PipelineConfig& pipeline) {
  if (pipeline.pipeline_mode == "single_thread") {
    return RunSingleThreadPipeline(args, model, board, pipeline);
  }

  std::vector<std::unique_ptr<Backend>> backends;
  backends.reserve(static_cast<size_t>(pipeline.inference_workers));
  for (int worker = 0; worker < pipeline.inference_workers; ++worker) {
    BoardConfig worker_board = board;
    if (board.backend_runtime == "rknn" && pipeline.inference_workers > 1) {
      worker_board.rknn_core_mask = "core" + std::to_string(worker % 3);
    }
    auto backend = CreateBackend(worker_board);
    if (!backend->Init(worker_board, model, pipeline.buffer_reuse)) {
      std::cerr << "BACKEND_RUNTIME_FAILED: failed to initialize " << board.backend_runtime
                << " worker=" << worker << " core_mask=" << worker_board.rknn_core_mask << "\n";
      return 21;
    }
    std::cout << (board.backend_runtime == "rknn" ? "RKNN_WORKER_INIT" : "BACKEND_WORKER_INIT")
              << ": worker=" << worker
              << " core_mask=" << worker_board.rknn_core_mask << "\n";
    backends.push_back(std::move(backend));
  }
  for (int worker = 0; worker < static_cast<int>(backends.size()); ++worker) {
    if (!WarmupBackend(*backends[worker], board, model, worker)) {
      return 21;
    }
  }
  std::cout << "INFERENCE_WORKERS: count=" << pipeline.inference_workers << "\n";
  std::cout << "POSTPROCESS_WORKERS: count=" << pipeline.postprocess_workers << "\n";

  FrameReader source(args);
  try {
    source.Open();
  } catch (const std::exception& e) {
    std::cerr << e.what() << "\n";
    return 10;
  }

  std::ofstream raw(args.raw_output);
  if (!raw) {
    std::cerr << "OUTPUT_FAILED: cannot open raw output " << args.raw_output << "\n";
    return 40;
  }

  const int input_w = source.width();
  const int input_h = source.height();
  double input_fps = source.input_fps();
  const bool file_like_input = source.file_like_input();
  const bool pace_video_file = file_like_input && pipeline.pace_video_file;
  const double frame_interval_ms = source.frame_interval_ms();
  const double source_duration_ms = source.source_duration_ms();

  std::cout << "INPUT_PACING: input_source_type=" << args.input_source_type
            << " source_fps=" << input_fps
            << " source_fps_basis=" << source.input_fps_basis()
            << " pace_video_file=" << (pace_video_file ? "true" : "false")
            << " pacing_mode=" << (pace_video_file ? "source_timestamps_with_fps_fallback" : "unpaced")
            << " source_duration_ms=" << source_duration_ms
            << " playlist_input=" << (source.playlist_input() ? "true" : "false")
            << " playlist_items=" << source.playlist_size() << "\n";

  cv::VideoWriter writer;
  if (!args.output_video.empty()) {
    writer.open(args.output_video, cv::VideoWriter::fourcc('m', 'p', '4', 'v'), input_fps,
                cv::Size(input_w, input_h));
  }
  PreviewWindow preview(args, board.target);

  BoundedQueue<FramePacket> q_capture(pipeline.queue_capacity);
  BoundedQueue<TensorPacket> q_preprocess(pipeline.queue_capacity);
  BoundedQueue<InferPacket> q_infer(pipeline.queue_capacity);
  BoundedQueue<ResultPacket> q_result(pipeline.queue_capacity);
  std::atomic<int> dropped{0};
  std::atomic<int> exit_code{0};

  const auto started = Clock::now();
  const bool endless = args.duration_sec <= 0;

  std::thread capture_thread([&] {
    int frame_id = 0;
    auto pacing_started = Clock::now();
    auto next_frame_due = pacing_started;
    double loop_offset_ms = 0.0;
    double loop_media_base_ms = -1.0;
    double last_media_ms = -1.0;
    double current_input_fps = input_fps;
    double current_frame_interval_ms = frame_interval_ms;
    double current_source_duration_ms = source_duration_ms;
    while (endless || std::chrono::duration_cast<std::chrono::seconds>(Clock::now() - started).count() < args.duration_sec) {
      const auto t0 = Clock::now();
      cv::Mat frame;
      if (!source.Read(frame)) {
        if (file_like_input && args.loop_video_file) {
          if (current_source_duration_ms > 0.0) {
            loop_offset_ms += current_source_duration_ms;
          } else if (loop_media_base_ms >= 0.0 && last_media_ms >= loop_media_base_ms) {
            loop_offset_ms += std::max(current_frame_interval_ms, last_media_ms - loop_media_base_ms + current_frame_interval_ms);
          }
          loop_media_base_ms = -1.0;
          last_media_ms = -1.0;
          if (!source.ReopenLoopSource()) {
            if (!source.last_error().empty()) {
              std::cerr << source.last_error() << "\n";
              exit_code = source.last_error().rfind("INPUT_DIMENSION_MISMATCH:", 0) == 0 ? 11 : 10;
            }
            break;
          }
          current_input_fps = source.input_fps();
          current_frame_interval_ms = source.frame_interval_ms();
          current_source_duration_ms = source.source_duration_ms();
          if (!source.Read(frame)) {
            if (!source.last_error().empty()) {
              std::cerr << "INPUT_DISCONNECTED: " << source.last_error() << "\n";
              exit_code = 11;
            }
            break;
          }
        } else {
          if (!source.last_error().empty()) {
            std::cerr << "INPUT_DISCONNECTED: " << source.last_error() << "\n";
            exit_code = 11;
          }
          break;
        }
      }
      if (pace_video_file) {
        const double media_ms = source.media_position_ms();
        bool paced_with_source_timestamps = false;
        if (media_ms >= 0.0) {
          if (loop_media_base_ms < 0.0) loop_media_base_ms = media_ms;
          if (media_ms >= loop_media_base_ms) {
            const double target_ms = loop_offset_ms + (media_ms - loop_media_base_ms);
            std::this_thread::sleep_until(
                pacing_started +
                std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double, std::milli>(target_ms)));
            paced_with_source_timestamps = true;
            last_media_ms = media_ms;
          }
        }
        if (!paced_with_source_timestamps) {
          std::this_thread::sleep_until(next_frame_due);
          next_frame_due += std::chrono::duration_cast<Clock::duration>(
              std::chrono::duration<double, std::milli>(current_frame_interval_ms));
        } else {
          next_frame_due =
              Clock::now() + std::chrono::duration_cast<Clock::duration>(
                                 std::chrono::duration<double, std::milli>(current_frame_interval_ms));
        }
      }
      FramePacket packet;
      packet.frame_id = frame_id++;
      packet.input_fps = current_input_fps;
      packet.frame = frame;
      packet.trace.capture_ts = NowIso();
      packet.trace.capture_ms = MsSince(t0);
      packet.trace.decode_ts = packet.trace.capture_ts;
      packet.trace.decode_ms = 0.0;
      q_capture.Push(std::move(packet), pipeline.queue_policy, pipeline.queue_push_timeout_ms, dropped);
    }
    q_capture.Close();
  });

  std::thread preprocess_thread([&] {
    FramePacket input;
    while (q_capture.Pop(input)) {
      const auto t0 = Clock::now();
      TensorPacket packet;
      packet.frame_id = input.frame_id;
      packet.input_fps = input.input_fps;
      packet.frame = input.frame;
      packet.trace = input.trace;
      packet.trace.preprocess_ts = NowIso();
      cv::Mat letterboxed_bgr;
      packet.input_tensor = Preprocess(input.frame, model, packet.letterbox, &letterboxed_bgr);
      if (board.backend_runtime == "bpu") {
        packet.nv12_input = BgrToNv12Bytes(letterboxed_bgr);
      }
      packet.trace.preprocess_ms = MsSince(t0);
      q_preprocess.Push(std::move(packet), pipeline.queue_policy, pipeline.queue_push_timeout_ms, dropped);
    }
    q_preprocess.Close();
  });

  std::mutex infer_pop_mu;
  int next_inference_sequence = 0;
  std::atomic<int> inference_workers_remaining{pipeline.inference_workers};
  std::vector<std::thread> infer_threads;
  infer_threads.reserve(static_cast<size_t>(pipeline.inference_workers));
  for (int worker = 0; worker < pipeline.inference_workers; ++worker) {
    infer_threads.emplace_back([&, worker] {
      while (true) {
        TensorPacket input;
        int sequence = 0;
        {
          std::lock_guard<std::mutex> lock(infer_pop_mu);
          if (!q_preprocess.Pop(input)) break;
          sequence = next_inference_sequence++;
        }
        InferPacket packet;
        packet.inference_sequence = sequence;
        packet.frame_id = input.frame_id;
        packet.input_fps = input.input_fps;
        packet.frame = input.frame;
        packet.trace = input.trace;
        packet.letterbox = input.letterbox;
        packet.trace.infer_start_ts = NowIso();
        double infer_ms = 0.0;
        const std::vector<uint8_t>* nv12_input =
            input.nv12_input.empty() ? nullptr : &input.nv12_input;
        packet.ok = backends[worker]->Infer(
            input.input_tensor, nv12_input, packet.output_tensor, infer_ms);
        packet.trace.infer_end_ts = NowIso();
        packet.trace.inference_ms = infer_ms;
        if (!packet.ok) {
          packet.error_code = "BACKEND_RUNTIME_FAILED";
          exit_code = 21;
        }
        q_infer.Push(std::move(packet), "block", pipeline.queue_push_timeout_ms, dropped);
      }
      if (inference_workers_remaining.fetch_sub(1) == 1) q_infer.Close();
    });
  }

  std::atomic<int> postprocess_workers_remaining{pipeline.postprocess_workers};
  std::vector<std::thread> postprocess_threads;
  postprocess_threads.reserve(static_cast<size_t>(pipeline.postprocess_workers));
  for (int worker = 0; worker < pipeline.postprocess_workers; ++worker) {
    postprocess_threads.emplace_back([&, worker] {
      (void)worker;
      InferPacket input;
      while (q_infer.Pop(input)) {
        const auto t0 = Clock::now();
        ResultPacket packet;
        packet.inference_sequence = input.inference_sequence;
        packet.frame_id = input.frame_id;
        packet.input_fps = input.input_fps;
        packet.frame = input.frame;
        packet.trace = input.trace;
        packet.ok = input.ok;
        packet.error_code = input.error_code;
        packet.trace.postprocess_ts = NowIso();
        if (input.ok) {
          packet.detections =
              DecodeOutputTensor(board, *backends.front(), input.output_tensor, model, input.letterbox, input.frame.size());
        }
        packet.trace.postprocess_ms = MsSince(t0);
        // Frames that already consumed NPU time must not be dropped downstream.
        q_result.Push(std::move(packet), "block", pipeline.queue_push_timeout_ms, dropped);
      }
      if (postprocess_workers_remaining.fetch_sub(1) == 1) q_result.Close();
    });
  }

  std::map<int, ResultPacket> pending_results;
  int next_result_sequence = 0;
  auto emit_result = [&](ResultPacket& packet) {
    const auto t0 = Clock::now();
    packet.trace.output_ts = NowIso();
    if (!packet.frame.empty() && (writer.isOpened() || preview.enabled())) {
      DrawDetections(packet.frame, packet.detections);
      if (writer.isOpened()) writer.write(packet.frame);
      if (preview.enabled()) preview.Show(packet.frame, packet.detections.size());
    }
    packet.trace.output_ms = MsSince(t0);
    WriteRaw(raw, args, board, model, pipeline, packet, input_w, input_h,
             q_capture.Size(), q_preprocess.Size(), q_infer.Size(), q_result.Size(), dropped.load());
  };

  ResultPacket packet;
  while (q_result.Pop(packet)) {
    pending_results.emplace(packet.inference_sequence, std::move(packet));
    while (true) {
      auto ready = pending_results.find(next_result_sequence);
      if (ready == pending_results.end()) break;
      ResultPacket ordered = std::move(ready->second);
      pending_results.erase(ready);
      emit_result(ordered);
      ++next_result_sequence;
    }
  }
  for (auto& item : pending_results) {
    emit_result(item.second);
  }

  capture_thread.join();
  preprocess_thread.join();
  for (auto& thread : infer_threads) thread.join();
  for (auto& thread : postprocess_threads) thread.join();

  return exit_code.load();
}

}  // namespace

int main(int argc, char** argv) {
  try {
    Args args = ParseArgs(argc, argv);
    ModelConfig model = LoadModelConfig(args.model_config);
    BoardConfig board = LoadBoardConfig(args.backend_config);
    if (std::isfinite(board.preprocess_pad_value)) {
      model.pad_value = board.preprocess_pad_value;
      std::cout << "PREPROCESS_OVERRIDE: pad_value=" << model.pad_value
                << " source=board_config\n";
    }
    ValidateModelConfig(model);
    PipelineConfig pipeline = LoadPipelineConfig(args.config);
    if (args.pace_video_file_override != -1) {
      pipeline.pace_video_file = args.pace_video_file_override == 1;
    }
    if (!args.queue_policy_override.empty()) {
      pipeline.queue_policy = args.queue_policy_override;
    }
    if (args.queue_capacity_override > 0) {
      pipeline.queue_capacity = args.queue_capacity_override;
    }
    if (args.queue_push_timeout_ms_override >= 0) {
      pipeline.queue_push_timeout_ms = args.queue_push_timeout_ms_override;
    }
    if (args.inference_workers_override > 0) {
      pipeline.inference_workers = args.inference_workers_override;
    }
    if (args.postprocess_workers_override > 0) {
      pipeline.postprocess_workers = args.postprocess_workers_override;
    }
    if (pipeline.inference_workers <= 0 || pipeline.inference_workers > 3) {
      throw std::runtime_error("inference_workers must be between 1 and 3");
    }
    if (pipeline.postprocess_workers <= 0 || pipeline.postprocess_workers > 8) {
      throw std::runtime_error("postprocess_workers must be between 1 and 8");
    }
    if (!args.rknn_core_mask_override.empty()) {
      board.rknn_core_mask = args.rknn_core_mask_override;
    }

#if !defined(PIPELINE_BACKEND_TENSORRT)
    if (board.backend_runtime == "tensorrt") {
      std::cerr << "This binary was not built with PIPELINE_BACKEND=tensorrt.\n";
      return 21;
    }
#endif
#if !defined(PIPELINE_BACKEND_RKNN)
    if (board.backend_runtime == "rknn") {
      std::cerr << "This binary was not built with PIPELINE_BACKEND=rknn.\n";
      return 21;
    }
#endif
#if !defined(PIPELINE_BACKEND_BPU)
    if (board.backend_runtime == "bpu") {
      std::cerr << "This binary was not built with PIPELINE_BACKEND=bpu.\n";
      return 21;
    }
#endif

    return RunPipeline(args, model, board, pipeline);
  } catch (const std::exception& e) {
    std::cerr << "CONFIG_INVALID: " << e.what() << "\n";
    return 30;
  }
}
