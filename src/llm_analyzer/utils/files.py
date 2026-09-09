import json
import os
import tempfile
from pathlib import Path
from typing import Any

MAX_JSON_BYTES = 10 * 1024 * 1024


def read_json(path: Path) -> Any:
    with path.open("rb") as stream:
        data = stream.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("JSON input exceeds the 10 MiB limit")
    return json.loads(data.decode("utf-8-sig"))


def atomic_write(path: Path, content: str, force: bool = False) -> Path:
    path = path.expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".llm-analyzer-", dir=path.parent)
    temporary = Path(temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if force:
            os.replace(temporary, path)
        else:
            # Hard-link publication is atomic and fails if the target already exists.
            # On filesystems without hard links, exclusive creation still prevents overwrite.
            try:
                os.link(temporary, path)
            except FileExistsError:
                raise
            except OSError:
                with path.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(content)
        return path
    finally:
        temporary.unlink(missing_ok=True)
