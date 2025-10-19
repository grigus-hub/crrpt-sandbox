import ctypes
import os
import urllib.request
import tempfile
from pathlib import Path

LIB_URLS = {
    "corruptjpeg": "https://github.com/grigus-hub/crrpt-sandbox-wrapper/releases/download/latest/corruptjpeg_latest.dll",
    "jpeg": "https://github.com/grigus-hub/crrpt-sandbox-wrapper/releases/download/latest/jpeg62.dll",
}

CACHE_DIR = Path(tempfile.gettempdir()) / "corruptme_libs"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_library(name: str):
    url = LIB_URLS.get(name)
    if not url:
        raise ValueError(f"No URL registered for library '{name}'")

    filename = Path(url).name
    local_path = CACHE_DIR / filename

    print(f"[CorruptMe] Downloading {name} library from {url}...")
    urllib.request.urlretrieve(url, local_path)
    print(f"[CorruptMe] Cached at {local_path}")

    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(local_path.parent))
    else:
        # fallback: update PATH
        os.environ["PATH"] = str(local_path.parent) + \
            os.pathsep + os.environ.get("PATH", "")

    try:
        return ctypes.CDLL(str(local_path))
    except OSError as e:
        raise RuntimeError(f"Failed to load {local_path} library: {e}")


class JPEGCore:
    def __init__(self, path: str):
        self.jpeg_lib = load_library("jpeg")
        self.core_lib = load_library("corruptjpeg")

        self._bind_functions()

        self.handle = self.core_lib.jpeg_open(path.encode("utf-8"))
        if not self.handle:
            raise RuntimeError(f"Failed to open JPEG file: {path}")

        self.path = path

    def _bind_functions(self):
        # jpeg_open
        self.core_lib.jpeg_open.argtypes = [ctypes.c_char_p]
        self.core_lib.jpeg_open.restype = ctypes.c_void_p

        # jpeg_close
        self.core_lib.jpeg_close.argtypes = [ctypes.c_void_p]
        self.core_lib.jpeg_close.restype = None

    def close(self):
        if self.handle:
            self.core_lib.jpeg_close(self.handle)
            self.handle = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


if __name__ == "__main__":
    image = 'examples/sample.jpg'

    jc = JPEGCore(image)
    print(f"Opened: {image}")
    jc.close()
    print(f"Closed: {image}")
