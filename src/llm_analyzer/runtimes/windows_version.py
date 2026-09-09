import ctypes as ct


def file_version(path: str) -> str | None:
    """Read local PE version metadata without launching Ollama or contacting its daemon."""
    try:
        dll = ct.WinDLL("version.dll", winmode=0x800)  # type: ignore[attr-defined]
        dll.GetFileVersionInfoSizeW.argtypes = [ct.c_wchar_p, ct.POINTER(ct.c_uint32)]
        dll.GetFileVersionInfoSizeW.restype = ct.c_uint32
        dll.GetFileVersionInfoW.argtypes = [ct.c_wchar_p, ct.c_uint32, ct.c_uint32, ct.c_void_p]
        dll.GetFileVersionInfoW.restype = ct.c_int
        dll.VerQueryValueW.argtypes = [
            ct.c_void_p,
            ct.c_wchar_p,
            ct.POINTER(ct.c_void_p),
            ct.POINTER(ct.c_uint32),
        ]
        dll.VerQueryValueW.restype = ct.c_int
        handle = ct.c_uint32()
        size = dll.GetFileVersionInfoSizeW(path, ct.byref(handle))
        if not size or size > 1024 * 1024:
            return None
        buffer = ct.create_string_buffer(size)
        if not dll.GetFileVersionInfoW(path, 0, size, buffer):
            return None
        pointer, length = ct.c_void_p(), ct.c_uint32()
        if (
            not dll.VerQueryValueW(buffer, "\\", ct.byref(pointer), ct.byref(length))
            or length.value < 52
        ):
            return None
        fields = ct.cast(pointer, ct.POINTER(ct.c_uint32 * 13)).contents
        if fields[0] != 0xFEEF04BD:
            return None
        return f"{fields[2] >> 16}.{fields[2] & 65535}.{fields[3] >> 16}"
    except OSError:
        return None
