#!/usr/bin/env python3
import argparse
import ctypes
import json
import sys
from ctypes import POINTER, byref, c_char, c_char_p, c_int, c_uint16, c_uint64, c_void_p
from pathlib import Path


ONI_STATUS = {
    0: "OK",
    1: "ERROR",
    2: "NOT_IMPLEMENTED",
    3: "NOT_SUPPORTED",
    4: "BAD_PARAMETER",
    5: "OUT_OF_FLOW",
    6: "NO_DEVICE",
    102: "TIME_OUT",
}

ONI_SENSOR = {
    1: "ir",
    2: "color",
    3: "depth",
}

ONI_PIXEL_FORMAT = {
    100: "DEPTH_1_MM",
    101: "DEPTH_100_UM",
    102: "SHIFT_9_2",
    103: "SHIFT_9_3",
    200: "RGB888",
    201: "YUV422",
    202: "GRAY8",
    203: "GRAY16",
    204: "JPEG",
    205: "YUYV",
}

STREAM_PROPERTY_VIDEO_MODE = 3


class OniVersion(ctypes.Structure):
    _fields_ = [
        ("major", c_int),
        ("minor", c_int),
        ("maintenance", c_int),
        ("build", c_int),
    ]


class OniVideoMode(ctypes.Structure):
    _fields_ = [
        ("pixelFormat", c_int),
        ("resolutionX", c_int),
        ("resolutionY", c_int),
        ("fps", c_int),
    ]


class OniSensorInfo(ctypes.Structure):
    _fields_ = [
        ("sensorType", c_int),
        ("numSupportedVideoModes", c_int),
        ("pSupportedVideoModes", POINTER(OniVideoMode)),
    ]


class OniDeviceInfo(ctypes.Structure):
    _fields_ = [
        ("uri", c_char * 256),
        ("vendor", c_char * 256),
        ("name", c_char * 256),
        ("usbVendorId", c_uint16),
        ("usbProductId", c_uint16),
    ]


class OniFrame(ctypes.Structure):
    _fields_ = [
        ("dataSize", c_int),
        ("data", c_void_p),
        ("sensorType", c_int),
        ("timestamp", c_uint64),
        ("frameIndex", c_int),
        ("width", c_int),
        ("height", c_int),
        ("videoMode", OniVideoMode),
        ("croppingEnabled", c_int),
        ("cropOriginX", c_int),
        ("cropOriginY", c_int),
        ("stride", c_int),
    ]


def decode_fixed_string(raw):
    return bytes(raw).split(b"\x00", 1)[0].decode("utf-8", errors="replace")


def status_string(code):
    return ONI_STATUS.get(code, f"UNKNOWN_{code}")


def sensor_name(sensor_type):
    return ONI_SENSOR.get(sensor_type, f"sensor_{sensor_type}")


def pixel_format_name(pixel_format):
    return ONI_PIXEL_FORMAT.get(pixel_format, f"PIXEL_{pixel_format}")


def frame_to_dict(frame):
    return {
        "sensor_type": sensor_name(frame.sensorType),
        "frame_index": int(frame.frameIndex),
        "timestamp": int(frame.timestamp),
        "width": int(frame.width),
        "height": int(frame.height),
        "stride": int(frame.stride),
        "data_size": int(frame.dataSize),
        "pixel_format": pixel_format_name(frame.videoMode.pixelFormat),
        "fps": int(frame.videoMode.fps),
    }


def video_mode_to_dict(mode):
    return {
        "pixel_format": pixel_format_name(mode.pixelFormat),
        "pixel_format_id": int(mode.pixelFormat),
        "width": int(mode.resolutionX),
        "height": int(mode.resolutionY),
        "fps": int(mode.fps),
    }


def configure_api(lib):
    lib.oniGetVersion.restype = OniVersion

    lib.oniInitialize.argtypes = [c_int]
    lib.oniInitialize.restype = c_int

    lib.oniShutdown.argtypes = []
    lib.oniShutdown.restype = None

    lib.oniGetExtendedError.argtypes = []
    lib.oniGetExtendedError.restype = c_char_p

    lib.oniGetDeviceList.argtypes = [POINTER(POINTER(OniDeviceInfo)), POINTER(c_int)]
    lib.oniGetDeviceList.restype = c_int

    lib.oniReleaseDeviceList.argtypes = [POINTER(OniDeviceInfo)]
    lib.oniReleaseDeviceList.restype = c_int

    lib.oniDeviceOpen.argtypes = [c_char_p, POINTER(c_void_p)]
    lib.oniDeviceOpen.restype = c_int

    lib.oniDeviceClose.argtypes = [c_void_p]
    lib.oniDeviceClose.restype = c_int

    lib.oniDeviceGetSensorInfo.argtypes = [c_void_p, c_int]
    lib.oniDeviceGetSensorInfo.restype = POINTER(OniSensorInfo)

    lib.oniDeviceCreateStream.argtypes = [c_void_p, c_int, POINTER(c_void_p)]
    lib.oniDeviceCreateStream.restype = c_int

    lib.oniStreamDestroy.argtypes = [c_void_p]
    lib.oniStreamDestroy.restype = None

    lib.oniStreamStart.argtypes = [c_void_p]
    lib.oniStreamStart.restype = c_int

    lib.oniStreamStop.argtypes = [c_void_p]
    lib.oniStreamStop.restype = None

    lib.oniWaitForAnyStream.argtypes = [POINTER(c_void_p), c_int, POINTER(c_int), c_int]
    lib.oniWaitForAnyStream.restype = c_int

    lib.oniStreamReadFrame.argtypes = [c_void_p, POINTER(POINTER(OniFrame))]
    lib.oniStreamReadFrame.restype = c_int

    lib.oniFrameRelease.argtypes = [POINTER(OniFrame)]
    lib.oniFrameRelease.restype = None

    lib.oniStreamGetProperty.argtypes = [c_void_p, c_int, c_void_p, POINTER(c_int)]
    lib.oniStreamGetProperty.restype = c_int


class OpenNIProbeError(RuntimeError):
    pass


class OpenNIProbe:
    def __init__(self, lib_path):
        self.lib = ctypes.CDLL(lib_path)
        configure_api(self.lib)
        self.initialized = False

    def init(self):
        version = self.lib.oniGetVersion()
        api_version = version.major * 1000 + version.minor
        status = self.lib.oniInitialize(api_version)
        if status != 0:
            raise OpenNIProbeError(
                f"oniInitialize failed: status={status_string(status)} extended_error={self.extended_error()}"
            )
        self.initialized = True
        return {
            "version": {
                "major": int(version.major),
                "minor": int(version.minor),
                "maintenance": int(version.maintenance),
                "build": int(version.build),
            },
            "api_version": int(api_version),
        }

    def shutdown(self):
        if self.initialized:
            self.lib.oniShutdown()
            self.initialized = False

    def extended_error(self):
        raw = self.lib.oniGetExtendedError()
        if not raw:
            return ""
        return raw.decode("utf-8", errors="replace")

    def get_devices(self):
        devices_ptr = POINTER(OniDeviceInfo)()
        count = c_int(0)
        status = self.lib.oniGetDeviceList(byref(devices_ptr), byref(count))
        if status != 0:
            raise OpenNIProbeError(
                f"oniGetDeviceList failed: status={status_string(status)} extended_error={self.extended_error()}"
            )
        try:
            devices = []
            for i in range(count.value):
                info = devices_ptr[i]
                devices.append(
                    {
                        "index": i,
                        "uri": decode_fixed_string(info.uri),
                        "vendor": decode_fixed_string(info.vendor),
                        "name": decode_fixed_string(info.name),
                        "usb_vendor_id": int(info.usbVendorId),
                        "usb_product_id": int(info.usbProductId),
                    }
                )
            return devices
        finally:
            self.lib.oniReleaseDeviceList(devices_ptr)

    def open_device(self, uri):
        handle = c_void_p()
        status = self.lib.oniDeviceOpen(uri.encode("utf-8"), byref(handle))
        if status != 0:
            raise OpenNIProbeError(
                f"oniDeviceOpen failed: status={status_string(status)} uri={uri} extended_error={self.extended_error()}"
            )
        return handle

    def close_device(self, handle):
        self.lib.oniDeviceClose(handle)

    def get_sensor_info(self, device, sensor_type):
        info_ptr = self.lib.oniDeviceGetSensorInfo(device, sensor_type)
        if not info_ptr:
            return None
        info = info_ptr.contents
        modes = [video_mode_to_dict(info.pSupportedVideoModes[i]) for i in range(info.numSupportedVideoModes)]
        return {
            "sensor_type": sensor_name(sensor_type),
            "supported_mode_count": int(info.numSupportedVideoModes),
            "supported_modes": modes,
        }

    def open_stream(self, device, sensor_type):
        stream = c_void_p()
        status = self.lib.oniDeviceCreateStream(device, sensor_type, byref(stream))
        if status != 0:
            raise OpenNIProbeError(
                f"oniDeviceCreateStream failed: status={status_string(status)} sensor={sensor_name(sensor_type)} "
                f"extended_error={self.extended_error()}"
            )
        return stream

    def close_stream(self, stream):
        if stream:
            self.lib.oniStreamStop(stream)
            self.lib.oniStreamDestroy(stream)

    def get_stream_video_mode(self, stream):
        mode = OniVideoMode()
        size = c_int(ctypes.sizeof(mode))
        status = self.lib.oniStreamGetProperty(stream, STREAM_PROPERTY_VIDEO_MODE, byref(mode), byref(size))
        if status != 0:
            return {
                "status": status_string(status),
                "extended_error": self.extended_error(),
            }
        return {
            "status": "OK",
            "mode": video_mode_to_dict(mode),
        }

    def read_frames(self, stream, frame_count, timeout_ms):
        status = self.lib.oniStreamStart(stream)
        if status != 0:
            raise OpenNIProbeError(
                f"oniStreamStart failed: status={status_string(status)} extended_error={self.extended_error()}"
            )

        handles = (c_void_p * 1)()
        handles[0] = stream
        frames = []
        for _ in range(frame_count):
            ready_index = c_int(-1)
            wait_status = self.lib.oniWaitForAnyStream(handles, 1, byref(ready_index), timeout_ms)
            if wait_status != 0:
                raise OpenNIProbeError(
                    f"oniWaitForAnyStream failed: status={status_string(wait_status)} extended_error={self.extended_error()}"
                )
            frame_ptr = POINTER(OniFrame)()
            read_status = self.lib.oniStreamReadFrame(stream, byref(frame_ptr))
            if read_status != 0:
                raise OpenNIProbeError(
                    f"oniStreamReadFrame failed: status={status_string(read_status)} extended_error={self.extended_error()}"
                )
            try:
                frames.append(frame_to_dict(frame_ptr.contents))
            finally:
                self.lib.oniFrameRelease(frame_ptr)
        return frames


def parse_args():
    parser = argparse.ArgumentParser(
        description="Probe Orbbec Astra/OpenNI2 device availability, supported sensors, and frame read viability."
    )
    parser.add_argument("--lib", default="/usr/lib/libOpenNI2.so", help="Path to libOpenNI2.so")
    parser.add_argument("--device-index", type=int, default=0, help="Which OpenNI device to probe")
    parser.add_argument(
        "--device",
        default="",
        help="Optional device selector. Supports exact URI, USB vid/pid substring like 2bc5/0402, or any substring of vendor/name/uri.",
    )
    parser.add_argument(
        "--sensors",
        default="color,depth,ir",
        help="Comma-separated sensors to inspect/read. Valid values: color,depth,ir",
    )
    parser.add_argument("--frames", type=int, default=3, help="Number of frames to read per available sensor")
    parser.add_argument("--timeout-ms", type=int, default=3000, help="Frame wait timeout in milliseconds")
    parser.add_argument("--json-output", default="", help="Optional path to write JSON result")
    return parser.parse_args()


def select_device_index(devices, device_index, device_selector):
    selector = (device_selector or "").strip()
    if not selector:
        if device_index < 0 or device_index >= len(devices):
            raise OpenNIProbeError(
                f"device_index {device_index} out of range; device_count={len(devices)}"
            )
        return device_index

    for idx, device in enumerate(devices):
        if selector == device["uri"]:
            return idx

    wanted = selector.lower()
    for idx, device in enumerate(devices):
        candidate_fields = [
            device["uri"],
            device["vendor"],
            device["name"],
            f"{device['usb_vendor_id']:04x}:{device['usb_product_id']:04x}",
            f"{device['usb_vendor_id']:04x}/{device['usb_product_id']:04x}",
        ]
        haystack = " ".join(part for part in candidate_fields if part).lower()
        if wanted in haystack:
            return idx

    raise OpenNIProbeError(
        f"device selector not found: selector={selector} device_count={len(devices)}"
    )


def main():
    args = parse_args()
    lib_path = Path(args.lib)
    if not lib_path.exists():
        print(f"OPENNI_LIB_MISSING: {lib_path}", file=sys.stderr)
        return 2

    sensor_map = {"ir": 1, "color": 2, "depth": 3}
    selected_sensors = []
    for part in args.sensors.split(","):
        key = part.strip().lower()
        if not key:
            continue
        if key not in sensor_map:
            print(f"UNKNOWN_SENSOR: {key}", file=sys.stderr)
            return 2
        selected_sensors.append((key, sensor_map[key]))
    if not selected_sensors:
        print("NO_SENSOR_SELECTED", file=sys.stderr)
        return 2

    result = {
        "lib_path": str(lib_path),
        "devices": [],
        "probe_status": "fail",
    }

    probe = OpenNIProbe(str(lib_path))
    try:
        init_info = probe.init()
        result["openni_version"] = init_info["version"]
        result["api_version"] = init_info["api_version"]

        devices = probe.get_devices()
        result["devices"] = devices
        if not devices:
            result["probe_status"] = "no_device"
            print("OPENNI_DEVICE_COUNT: 0")
            return 1

        selected_index = select_device_index(devices, args.device_index, args.device)
        device_info = devices[selected_index]
        result["selected_device"] = device_info
        print(
            "OPENNI_DEVICE_SELECTED:",
            f"index={device_info['index']}",
            f"vendor={device_info['vendor']}",
            f"name={device_info['name']}",
            f"uri={device_info['uri']}",
            f"usb_vidpid={device_info['usb_vendor_id']:04x}:{device_info['usb_product_id']:04x}",
        )

        device = probe.open_device(device_info["uri"])
        try:
            sensor_results = {}
            readable_sensors = []
            for sensor_key, sensor_type in selected_sensors:
                info = probe.get_sensor_info(device, sensor_type)
                if info is None:
                    sensor_results[sensor_key] = {"available": False}
                    print(f"OPENNI_SENSOR: sensor={sensor_key} available=false")
                    continue

                sensor_result = {"available": True, **info}
                print(
                    f"OPENNI_SENSOR: sensor={sensor_key} available=true supported_modes={info['supported_mode_count']}"
                )

                stream = None
                try:
                    stream = probe.open_stream(device, sensor_type)
                    sensor_result["stream_video_mode"] = probe.get_stream_video_mode(stream)
                    frames = probe.read_frames(stream, args.frames, args.timeout_ms)
                    sensor_result["read_status"] = "pass"
                    sensor_result["frames"] = frames
                    readable_sensors.append(sensor_key)
                    if frames:
                        first = frames[0]
                        print(
                            "OPENNI_FRAME_OK:",
                            f"sensor={sensor_key}",
                            f"width={first['width']}",
                            f"height={first['height']}",
                            f"pixel_format={first['pixel_format']}",
                            f"fps={first['fps']}",
                            f"stride={first['stride']}",
                        )
                except OpenNIProbeError as exc:
                    sensor_result["read_status"] = "fail"
                    sensor_result["read_error"] = str(exc)
                    print(f"OPENNI_FRAME_FAIL: sensor={sensor_key} error={exc}")
                finally:
                    if stream is not None:
                        probe.close_stream(stream)

                sensor_results[sensor_key] = sensor_result

            result["sensor_results"] = sensor_results
            result["readable_sensors"] = readable_sensors
            result["probe_status"] = "pass" if readable_sensors else "no_readable_sensor"
            result["color_stream_readable"] = "color" in readable_sensors
        finally:
            probe.close_device(device)

    except OpenNIProbeError as exc:
        result["probe_error"] = str(exc)
        print(f"OPENNI_PROBE_ERROR: {exc}", file=sys.stderr)
        return_code = 1
    else:
        return_code = 0 if result["probe_status"] == "pass" else 1
    finally:
        probe.shutdown()

    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"json_output={output_path}")

    if return_code == 0:
        print(
            "OPENNI_PROBE_SUMMARY:",
            f"probe_status={result['probe_status']}",
            f"color_stream_readable={result.get('color_stream_readable', False)}",
            f"readable_sensors={','.join(result.get('readable_sensors', []))}",
        )

    return return_code


if __name__ == "__main__":
    sys.exit(main())
