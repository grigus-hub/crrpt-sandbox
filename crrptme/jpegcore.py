import ctypes
import os
import urllib.request
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image

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
        
        self.width = self.core_lib.jpeg_get_width(self.handle)
        self.height = self.core_lib.jpeg_get_height(self.handle)
        self.num_components = self.core_lib.jpeg_get_num_components(self.handle)

        self.path = path

    def _bind_functions(self):
        self.core_lib.jpeg_open.argtypes = [ctypes.c_char_p]
        self.core_lib.jpeg_open.restype = ctypes.c_void_p

        self.core_lib.jpeg_close.argtypes = [ctypes.c_void_p]
        self.core_lib.jpeg_close.restype = None

        self.core_lib.jpeg_get_width.argtypes = [ctypes.c_void_p]
        self.core_lib.jpeg_get_width.restype = ctypes.c_int

        self.core_lib.jpeg_get_height.argtypes = [ctypes.c_void_p]
        self.core_lib.jpeg_get_height.restype = ctypes.c_int

        self.core_lib.jpeg_get_num_components.argtypes = [ctypes.c_void_p]
        self.core_lib.jpeg_get_num_components.restype = ctypes.c_int

        self.core_lib.jpeg_get_num_blocks_x.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.core_lib.jpeg_get_num_blocks_x.restype = ctypes.c_int

        self.core_lib.jpeg_get_num_blocks_y.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.core_lib.jpeg_get_num_blocks_y.restype = ctypes.c_int

        self.core_lib.jpeg_get_dct_block.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, 
                                                     ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.c_int]
        self.core_lib.jpeg_get_dct_block.restype = ctypes.c_int

        self.core_lib.jpeg_set_dct_block.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, 
                                                     ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.c_int]
        self.core_lib.jpeg_set_dct_block.restype = ctypes.c_int

    def get_num_blocks_x(self, component: int) -> int:
        return self.core_lib.jpeg_get_num_blocks_x(self.handle, component)

    def get_num_blocks_y(self, component: int) -> int:
        return self.core_lib.jpeg_get_num_blocks_y(self.handle, component)

    def get_dct_block(self, channel: int, bx: int, by: int) -> np.ndarray:
        buf = (ctypes.c_float * 64)()
        res = self.core_lib.jpeg_get_dct_block(self.handle, channel, bx, by, buf, 64)
        if res < 0:
            raise RuntimeError(f"jpeg_get_dct_block failed: {res}")
        arr = np.ctypeslib.as_array(buf)
        return arr.reshape((8, 8)).astype(np.float32)

    def set_dct_block(self, channel: int, bx: int, by: int, block: np.ndarray):
        if block.shape != (8, 8):
            raise ValueError("block must be (8,8)")
        flat = block.astype(np.float32).ravel()
        buf = (ctypes.c_float * 64)(*flat.tolist())
        res = self.core_lib.jpeg_set_dct_block(self.handle, channel, bx, by, buf, 64)
        if res < 0:
            raise RuntimeError(f"jpeg_set_dct_block failed: {res}")
        return res

    def close(self):
        if self.handle:
            self.core_lib.jpeg_close(self.handle)
            self.handle = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
