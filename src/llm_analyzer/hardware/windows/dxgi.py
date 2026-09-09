"""Read-only DXGI 1.1 enumeration; no persistent adapter identifiers are exported."""

import ctypes as ct
import uuid
from typing import Any

from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import GPUInfo


def enumerate_dxgi() -> list[GPUInfo]:
    class GUID(ct.Structure):
        _fields_ = [("data", ct.c_ubyte * 16)]

    class LUID(ct.Structure):
        _fields_ = [("low", ct.c_uint32), ("high", ct.c_int32)]

    class Desc(ct.Structure):
        _fields_ = [
            ("description", ct.c_wchar * 128),
            ("vendor", ct.c_uint32),
            ("device", ct.c_uint32),
            ("subsys", ct.c_uint32),
            ("revision", ct.c_uint32),
            ("dedicated_video", ct.c_size_t),
            ("dedicated_system", ct.c_size_t),
            ("shared", ct.c_size_t),
            ("luid", LUID),
            ("flags", ct.c_uint32),
        ]

    def method(pointer: ct.c_void_p, index: int, result: Any, *args: Any) -> Any:
        table = ct.cast(pointer, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
        return ct.WINFUNCTYPE(result, ct.c_void_p, *args)(table[index])  # type: ignore[attr-defined]

    dll = ct.WinDLL("dxgi.dll", winmode=0x800)  # type: ignore[attr-defined]
    factory = ct.c_void_p()
    iid = GUID.from_buffer_copy(uuid.UUID("770aae78-f26f-4dba-a829-253c83d1b387").bytes_le)
    create = dll.CreateDXGIFactory1
    create.argtypes = [ct.POINTER(GUID), ct.POINTER(ct.c_void_p)]
    create.restype = ct.c_int32
    if create(ct.byref(iid), ct.byref(factory)) < 0:
        raise OSError("DXGI factory unavailable")
    gpus: list[GPUInfo] = []
    try:
        for index in range(32):
            adapter = ct.c_void_p()
            hr = method(factory, 12, ct.c_int32, ct.c_uint32, ct.POINTER(ct.c_void_p))(
                factory, index, ct.byref(adapter)
            )
            if hr & 0xFFFFFFFF == 0x887A0002:
                break
            if hr < 0:
                raise OSError("DXGI adapter enumeration failed")
            try:
                desc = Desc()
                if method(adapter, 10, ct.c_int32, ct.POINTER(Desc))(adapter, ct.byref(desc)) < 0:
                    raise OSError("DXGI adapter description unavailable")
                evidence = Evidence(
                    source="DXGI GetDesc1", confidence=Confidence.HIGH, status=Status.AVAILABLE
                )
                gpus.append(
                    GPUInfo(
                        index=index,
                        name=desc.description,
                        vendor={
                            0x10DE: "NVIDIA",
                            0x1002: "AMD",
                            0x8086: "Intel",
                            0x1414: "Microsoft",
                        }.get(desc.vendor, "other"),
                        dedicated_vram_bytes=desc.dedicated_video,
                        shared_memory_bytes=desc.shared,
                        gpu_type="software" if desc.flags & 2 else "unknown",
                        evidence={
                            "identity": evidence,
                            "dedicated_vram_bytes": evidence,
                            "shared_memory_bytes": evidence,
                        },
                    )
                )
            finally:
                method(adapter, 2, ct.c_uint32)(adapter)
    finally:
        method(factory, 2, ct.c_uint32)(factory)
    return gpus
