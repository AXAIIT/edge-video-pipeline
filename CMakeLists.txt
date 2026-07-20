cmake_minimum_required(VERSION 3.16)

project(edge_video_pipeline LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT DEFINED PIPELINE_BACKEND)
  set(PIPELINE_BACKEND "mock")
endif()

find_package(Threads REQUIRED)
find_package(OpenCV REQUIRED COMPONENTS core imgproc videoio highgui dnn)

add_executable(video_pipeline_app
  src/video_pipeline_app.cpp
)

target_include_directories(video_pipeline_app PRIVATE ${OpenCV_INCLUDE_DIRS})
target_link_libraries(video_pipeline_app PRIVATE ${OpenCV_LIBS} Threads::Threads)
if(CMAKE_DL_LIBS)
  target_link_libraries(video_pipeline_app PRIVATE ${CMAKE_DL_LIBS})
endif()

if(PIPELINE_BACKEND STREQUAL "tensorrt")
  find_path(TENSORRT_INCLUDE_DIR NvInfer.h
    PATHS /usr/include/aarch64-linux-gnu /usr/include /usr/local/include
  )
  find_path(CUDA_INCLUDE_DIR cuda_runtime_api.h
    PATHS /usr/local/cuda/include /usr/include
  )
  find_library(NVINFER_LIBRARY nvinfer
    PATHS /usr/lib/aarch64-linux-gnu /usr/lib /usr/local/lib
    REQUIRED
  )
  find_library(CUDART_LIBRARY cudart
    PATHS /usr/local/cuda/lib64 /usr/lib/aarch64-linux-gnu /usr/lib
    REQUIRED
  )
  if(TENSORRT_INCLUDE_DIR)
    target_include_directories(video_pipeline_app PRIVATE ${TENSORRT_INCLUDE_DIR})
  endif()
  if(CUDA_INCLUDE_DIR)
    target_include_directories(video_pipeline_app PRIVATE ${CUDA_INCLUDE_DIR})
  endif()
  target_compile_definitions(video_pipeline_app PRIVATE PIPELINE_BACKEND_TENSORRT=1)
  target_link_libraries(video_pipeline_app PRIVATE ${NVINFER_LIBRARY} ${CUDART_LIBRARY})
endif()

if(PIPELINE_BACKEND STREQUAL "rknn")
  find_path(RKNN_INCLUDE_DIR rknn_api.h
    PATHS
      /usr/include
      /usr/local/include
      /usr/include/rknn
      /usr/local/include/rknn
      /usr/include/rknpu2
      /usr/local/include/rknpu2
      /usr/local/rknn/include
      $ENV{RKNN_SDK_ROOT}/include
      $ENV{RKNN_SDK_ROOT}/runtime/RK3588/Linux/librknn_api/include
  )
  if(NOT RKNN_INCLUDE_DIR)
    message(FATAL_ERROR "rknn_api.h not found. Install RKNN runtime headers or set RKNN_SDK_ROOT to the RKNN Toolkit2 SDK root.")
  endif()
  find_library(RKNNRT_LIBRARY rknnrt
    PATHS
      /usr/lib
      /usr/local/lib
      /usr/lib/aarch64-linux-gnu
      /usr/local/lib/aarch64-linux-gnu
      /usr/local/rknn/lib
      $ENV{RKNN_SDK_ROOT}/lib
      $ENV{RKNN_SDK_ROOT}/runtime/RK3588/Linux/librknn_api/aarch64
      $ENV{RKNN_SDK_ROOT}/runtime/RK3588/Linux/librknn_api/aarch64/lib
    REQUIRED
  )
  if(RKNN_INCLUDE_DIR)
    target_include_directories(video_pipeline_app PRIVATE ${RKNN_INCLUDE_DIR})
  endif()
  target_compile_definitions(video_pipeline_app PRIVATE PIPELINE_BACKEND_RKNN=1)
  target_link_libraries(video_pipeline_app PRIVATE ${RKNNRT_LIBRARY})
endif()

if(PIPELINE_BACKEND STREQUAL "bpu")
  if(NOT HB_DNN_INCLUDE_DIR)
    find_path(HB_DNN_INCLUDE_DIR dnn/hb_dnn.h
      PATHS
        /usr/include
        /usr/local/include
        /opt/hobot/include
        ${HOBOT_DNN_ROOT}/include
        ${HORIZON_DNN_ROOT}/include
        $ENV{HOBOT_DNN_ROOT}/include
        $ENV{HORIZON_DNN_ROOT}/include
        $ENV{HOME}/.horizon/ddk/x5_aarch64/dnn/include
        $ENV{HOME}/.horizon/ddk/j5_aarch64/dnn/include
    )
  endif()
  if(NOT HB_DNN_INCLUDE_DIR)
    message(FATAL_ERROR "dnn/hb_dnn.h not found. Set HB_DNN_INCLUDE_DIR or HOBOT_DNN_ROOT/HORIZON_DNN_ROOT.")
  endif()

  if(NOT HB_DNN_LIBRARY)
    find_library(HB_DNN_LIBRARY dnn
      PATHS
        /usr/lib
        /usr/local/lib
        /usr/lib/aarch64-linux-gnu
        /usr/local/lib/aarch64-linux-gnu
        /opt/hobot/lib
        ${HOBOT_DNN_ROOT}/lib
        ${HORIZON_DNN_ROOT}/lib
        $ENV{HOBOT_DNN_ROOT}/lib
        $ENV{HORIZON_DNN_ROOT}/lib
        $ENV{HOME}/.horizon/ddk/x5_aarch64/dnn/lib
        $ENV{HOME}/.horizon/ddk/j5_aarch64/dnn/lib
      REQUIRED
    )
  endif()

  if(NOT HB_HBRT_LIBRARY)
    find_library(HB_HBRT_LIBRARY NAMES hbrt_bayes_aarch64 hbrt_bayes
      PATHS
        /usr/lib
        /usr/local/lib
        /usr/lib/aarch64-linux-gnu
        /usr/local/lib/aarch64-linux-gnu
        /opt/hobot/lib
        ${HOBOT_DNN_ROOT}/lib
        ${HORIZON_DNN_ROOT}/lib
        $ENV{HOBOT_DNN_ROOT}/lib
        $ENV{HORIZON_DNN_ROOT}/lib
        $ENV{HOME}/.horizon/ddk/x5_aarch64/dnn/lib
        $ENV{HOME}/.horizon/ddk/j5_aarch64/dnn/lib
    )
  endif()

  target_include_directories(video_pipeline_app PRIVATE ${HB_DNN_INCLUDE_DIR})
  target_compile_definitions(video_pipeline_app PRIVATE PIPELINE_BACKEND_BPU=1)
  target_link_libraries(video_pipeline_app PRIVATE ${HB_DNN_LIBRARY} rt)
  if(HB_HBRT_LIBRARY)
    target_link_libraries(video_pipeline_app PRIVATE ${HB_HBRT_LIBRARY})
  endif()
  if(UNIX)
    target_link_options(video_pipeline_app PRIVATE "-Wl,-unresolved-symbols=ignore-in-shared-libs")
  endif()
endif()
