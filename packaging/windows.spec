from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

root = Path(SPECPATH).parent
sys.path.insert(0, str(root / "src"))
from llm_analyzer import __version__

version_tuple = tuple(int(part) for part in __version__.split(".")[:3]) + (0,)
metadata = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple, mask=0x3F, flags=0,
                      OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[StringFileInfo([StringTable("040904B0", [StringStruct("FileDescription", "Local LLM Analyzer"),
                                                StringStruct("FileVersion", __version__), StringStruct("ProductVersion", __version__),
                                                StringStruct("ProductName", "Local LLM Analyzer"),
                                                StringStruct("OriginalFilename", "llm-analyzer-windows-x64.exe")])]),
          VarFileInfo([VarStruct("Translation", [1033, 1200])])],
)

a = Analysis([str(root / "packaging/windows-entry.py")], pathex=[str(root / "src")],
             binaries=[], datas=collect_data_files("llm_analyzer") + [(str(root / "LICENSE"), ".")],
             hiddenimports=["cpuinfo", "cpuinfo.cpuinfo"], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=["torch", "tensorflow", "numpy", "pandas", "matplotlib", "tkinter"], noarchive=False)
pyz = PYZ(a.pure)
if os.environ.get("LLM_ANALYZER_BUILD_MODE") == "onedir":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="llm-analyzer-windows-x64",
              debug=False, strip=False, upx=False, console=True, version=metadata, uac_admin=False)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="llm-analyzer-windows-x64")
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="llm-analyzer-windows-x64",
              debug=False, strip=False, upx=False, console=True, version=metadata, uac_admin=False)
