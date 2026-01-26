"""
ComfyUI 3D查看器插件
用于在ComfyUI中打开3D模型查看器
"""

import os
import webbrowser
import subprocess
import sys
from pathlib import Path
import base64
import tempfile
import threading
import time
import urllib.parse
import uuid
import json
import functools
import io
try:
    from PIL import Image
    import numpy as np
except Exception:
    Image = None
    np = None
try:
    # Optional extra imaging helper used by the image-loading node
    from PIL import ImageOps
except Exception:
    ImageOps = None
import comfy
import re
import logging
try:
    import torch as _torch
    TORCH_AVAILABLE = True
except Exception:
    _torch = None
    TORCH_AVAILABLE = False
# expose a name `torch` for compatibility with imported node code
torch = _torch

# 轻量包装器（当没有 torch 时，提供 .cpu()/.numpy() 接口以兼容 ComfyUI 预览）
class _NumpyTensorWrapper:
    def __init__(self, arr):
        # Ensure we store a numpy array copy to avoid unexpected views
        try:
            import numpy as _np_local
            self._arr = _np_local.array(arr)
        except Exception:
            # Fallback: store as-is
            self._arr = arr
        self.shape = getattr(self._arr, 'shape', None)
    def cpu(self):
        return self
    def numpy(self):
        """
        Return a numpy array in CHW float32 format (channels, height, width)
        normalized to 0..1 to mimic torch.Tensor.cpu().numpy() behavior.
        This is the format ComfyUI preview expects when a tensor-like object
        is provided.
        """
        arr = self._arr
        try:
            import numpy as _np_local
        except Exception:
            return arr

        if arr is None:
            return arr

        # If HWC color, convert to CHW float32 in 0..1
        if getattr(arr, 'ndim', None) == 3 and arr.shape[2] >= 3:
            ch = arr[..., :3].astype(_np_local.float32)
            # Normalize if integer
            if arr.dtype.kind in ('u', 'i'):
                ch = ch / 255.0
            return _np_local.transpose(ch, (2, 0, 1)).copy()

        # Grayscale HxW -> 1xHxW float32 normalized
        if getattr(arr, 'ndim', None) == 2:
            a = arr.astype(_np_local.float32)
            if arr.dtype.kind in ('u', 'i'):
                a = a / 255.0
            return a[np.newaxis, ...].copy()

        # Fallback: attempt to coerce
        try:
            coerced = _np_local.array(arr, dtype=_np_local.float32)
            if coerced.ndim == 3:
                if coerced.shape[2] == 3:
                    if coerced.dtype.kind in ('u', 'i'):
                        coerced = coerced.astype(_np_local.float32) / 255.0
                    return _np_local.transpose(coerced, (2, 0, 1)).copy()
            if coerced.ndim == 2:
                if coerced.dtype.kind in ('u', 'i'):
                    coerced = coerced.astype(_np_local.float32) / 255.0
                return coerced[np.newaxis, ...].copy()
            return coerced
        except Exception:
            return arr
    def to(self, *args, **kwargs):
        return self

# 获取当前插件目录的路径
PLUGIN_DIR = Path(__file__).parent

# 全局截图注册表：token -> {'event': threading.Event, 'path': str}
_screenshot_registry = {}
_screenshot_lock = threading.Lock()
# 命令队列（短轮询使用）
_pending_commands = []
_pending_commands_lock = threading.Lock()

class Open3DViewer:
    """
    打开3D查看器的节点
    """
    def __init__(self):
        self.viewer_path = None

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "viewer_file": ("STRING", {"default": "ve2.html"}),
            },
            "optional": {
                "viewer_path": ("STRING", {"default": ""}),
                "auto_open": ("BOOLEAN", {"default": True}),
                "port": ("INT", {"default": 8001, "min": 1000, "max": 9999}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "open_viewer"
    CATEGORY = "🔵BB 3D查看器"

    def open_viewer(self, viewer_file, viewer_path="", auto_open=True, port=8001):
        """
        打开3D查看器

        Args:
            viewer_file: HTML查看器文件名
            viewer_path: 查看器文件的完整路径（可选，如果为空则自动查找）
            auto_open: 是否自动打开浏览器
            port: HTTP服务器端口

        Returns:
            status: 操作状态信息
        """
        try:
            # 确定查看器文件的完整路径
            if viewer_path and Path(viewer_path).exists():
                # 如果提供了完整路径且文件存在，直接使用
                viewer_full_path = Path(viewer_path)
            else:
                # 自动查找文件路径（按优先级查找）
                viewer_full_path = None

                # 1. 先在插件目录内部查找
                plugin_internal_path = PLUGIN_DIR / viewer_file
                if plugin_internal_path.exists():
                    viewer_full_path = plugin_internal_path
                else:
                    # 2. 在插件目录的父目录（custom_nodes）查找
                    custom_nodes_path = PLUGIN_DIR.parent / viewer_file
                    if custom_nodes_path.exists():
                        viewer_full_path = custom_nodes_path
                    else:
                        # 3. 在ComfyUI根目录查找
                        comfyui_root_path = PLUGIN_DIR.parent.parent / viewer_file
                        if comfyui_root_path.exists():
                            viewer_full_path = comfyui_root_path
                        else:
                            # 4. 在ComfyUI根目录的上一级查找
                            comfyui_parent_path = PLUGIN_DIR.parent.parent.parent / viewer_file
                            if comfyui_parent_path.exists():
                                viewer_full_path = comfyui_parent_path

                if not viewer_full_path or not viewer_full_path.exists():
                    # 列出所有可能的路径用于调试
                    possible_paths = [
                        str(PLUGIN_DIR / viewer_file),
                        str(PLUGIN_DIR.parent / viewer_file),
                        str(PLUGIN_DIR.parent.parent / viewer_file),
                        str(PLUGIN_DIR.parent.parent.parent / viewer_file)
                    ]
                    return (f"错误：找不到文件 {viewer_file}。尝试的路径：{' | '.join(possible_paths)}",)

            # 启动本地HTTP服务器
            import http.server
            import socketserver
            import threading
            import json as _json
            import base64 as _base64
            import tempfile as _tempfile
            import urllib.parse as _urllib_parse

            class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
                def log_message(self, format, *args):
                    pass  # 静默日志
                def do_GET(self):
                    # 支持 /next_command 用于前端轮询获取下一个 token
                    parsed = _urllib_parse.urlparse(self.path)
                    if parsed.path != '/next_command':
                        return super().do_GET()
                    qs = _urllib_parse.parse_qs(parsed.query)
                    # 可以基于 viewer 参数做更复杂的路由，目前简单 FIFO
                    token = None
                    with _pending_commands_lock:
                        if _pending_commands:
                            token = _pending_commands.pop(0)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    if token:
                        self.wfile.write(_json.dumps({'token': token}).encode('utf-8'))
                    else:
                        self.wfile.write(_json.dumps({}).encode('utf-8'))
                    return
                def do_POST(self):
                    # 仅处理 /upload_screenshot
                    parsed = _urllib_parse.urlparse(self.path)
                    if parsed.path != '/upload_screenshot':
                        self.send_response(404)
                        self.end_headers()
                        return
                    qs = _urllib_parse.parse_qs(parsed.query)
                    token = qs.get('token', [''])[0]
                    try:
                        length = int(self.headers.get('Content-Length', 0))
                    except Exception:
                        length = 0
                    body = self.rfile.read(length).decode('utf-8', errors='ignore')
                    dataurl = None
                    try:
                        j = _json.loads(body)
                        dataurl = j.get('dataUrl') or j.get('dataurl') or j.get('data')
                    except Exception:
                        dataurl = body.strip()
                    if not dataurl:
                        self.send_response(400)
                        self.end_headers()
                        return
                    # data:image/png;base64,...
                    if dataurl.startswith('data:image'):
                        try:
                            _, b64 = dataurl.split(',', 1)
                            data = _base64.b64decode(b64)
                            # 将上传保存为固定文件 image.png（先写临时文件再原子替换）
                            tmpf = _tempfile.NamedTemporaryFile(delete=False, suffix='.png', dir=str(PLUGIN_DIR))
                            try:
                                tmpf.write(data)
                                tmpf.flush()
                                tmpf.close()
                                target_path = PLUGIN_DIR / 'image.png'
                                try:
                                    # 原子替换（Windows/Unix 都支持）
                                    os.replace(tmpf.name, str(target_path))
                                except Exception:
                                    # 备用方案
                                    try:
                                        import shutil as _shutil
                                        _shutil.move(tmpf.name, str(target_path))
                                    except Exception:
                                        # 如果移动失败，尽量清理并报错
                                        try:
                                            os.unlink(tmpf.name)
                                        except Exception:
                                            pass
                                        raise
                                path = str(target_path)
                            except Exception as _write_err:
                                # 清理临时文件（如果存在）并返回错误
                                try:
                                    if tmpf and hasattr(tmpf, 'name') and os.path.exists(tmpf.name):
                                        os.unlink(tmpf.name)
                                except Exception:
                                    pass
                                try:
                                    self.send_response(500)
                                    self.end_headers()
                                    self.wfile.write(str(_write_err).encode('utf-8', errors='ignore'))
                                except Exception:
                                    pass
                                return
                            # 注册结果并触发等待事件（如果存在）
                            with _screenshot_lock:
                                entry = _screenshot_registry.get(token)
                                if not entry:
                                    entry = {}
                                    _screenshot_registry[token] = entry
                                entry['path'] = path
                                ev = entry.get('event')
                                if ev:
                                    ev.set()
                            try:
                                self.send_response(200)
                                self.end_headers()
                                self.wfile.write(b'OK')
                            except Exception:
                                pass
                            print(f"[3DViewer DEBUG] Saved uploaded screenshot to {path}")
                            return
                        except Exception as e:
                            try:
                                self.send_response(500)
                                self.end_headers()
                                self.wfile.write(str(e).encode('utf-8', errors='ignore'))
                            except Exception:
                                pass
                            return
                    else:
                        self.send_response(400)
                        self.end_headers()
                        return

            # 切换到文件所在目录
            os.chdir(viewer_full_path.parent)

            # 创建HTTP服务器并在后台线程中持续运行
            try:
                httpd = socketserver.TCPServer(("", port), QuietHTTPRequestHandler)
            except OSError as e:
                return (f"错误：无法绑定端口 {port}（可能被占用）：{e}",)

            server_url = f"http://localhost:{port}/{viewer_full_path.name}"

            # 在新线程中打开浏览器，避免阻塞（延迟以确保服务器已启动）
            if auto_open:
                def open_browser():
                    import time
                    time.sleep(0.5)
                    try:
                        webbrowser.open(server_url)
                    except Exception:
                        pass
                threading.Thread(target=open_browser, daemon=True).start()

            # 启动服务器的后台线程（守护线程，随进程退出）
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()

            # 保存引用以便将来可能需要停止服务器
            try:
                self._viewer_httpd = httpd
                self._viewer_thread = server_thread
            except Exception:
                # 如果没有 self（极小概率），忽略
                pass

            print(f"3D查看器已启动: {server_url}")
            return (f"3D查看器已启动: {server_url}",)

        except Exception as e:
            error_msg = f"打开3D查看器失败: {str(e)}"
            print(error_msg)
            return (error_msg,)

#
# 以下为从原始 `imaaaa.py` 合并过来的图像读取节点（Read images from directory）
#
def extract_first_number(s):
    match = re.search(r'\d+', s)
    return int(match.group()) if match else float('inf')


sort_methods = [
    "None",
    "Alphabetical (ASC)",
    "Alphabetical (DESC)",
    "Numerical (ASC)",
    "Numerical (DESC)",
    "Datetime (ASC)",
    "Datetime (DESC)"
]


def sort_by(items, base_path='.', method=None):
    def fullpath(x): return os.path.join(base_path, x)

    def get_timestamp(path):
        try:
            return os.path.getmtime(path)
        except FileNotFoundError:
            return float('-inf')

    if method == "Alphabetical (ASC)":
        return sorted(items)
    elif method == "Alphabetical (DESC)":
        return sorted(items, reverse=True)
    elif method == "Numerical (ASC)":
        return sorted(items, key=lambda x: extract_first_number(os.path.splitext(x)[0]))
    elif method == "Numerical (DESC)":
        return sorted(items, key=lambda x: extract_first_number(os.path.splitext(x)[0]), reverse=True)
    elif method == "Datetime (ASC)":
        return sorted(items, key=lambda x: get_timestamp(fullpath(x)))
    elif method == "Datetime (DESC)":
        return sorted(items, key=lambda x: get_timestamp(fullpath(x)), reverse=True)
    else:
        return items


try:
    import pillow_jxl  # noqa: F401
    jxl = True
except Exception:
    jxl = False


class imaaaa:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "directory": ("STRING", {"default": str(PLUGIN_DIR)}),
            },
            "optional": {
                "image_load_cap": ("INT", {"default": 0, "min": 0, "step": 1}),
                "start_index": ("INT", {"default": 0, "min": -1, "max": 0xffffffffffffffff, "step": 1}),
                "load_always": ("BOOLEAN", {"default": False, "label_on": "enabled", "label_off": "disabled"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "load_images"
    CATEGORY = "🔵BB 3D查看器"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        if 'load_always' in kwargs and kwargs['load_always']:
            return float("NaN")
        else:
            return hash(frozenset(kwargs))

    def load_images(self, directory: str, image_load_cap: int = 0, start_index: int = 0, load_always=False):
        if not os.path.isdir(directory):
            raise FileNotFoundError(f"Directory '{directory} cannot be found.'")
        dir_files = os.listdir(directory)
        if len(dir_files) == 0:
            raise FileNotFoundError(f"No files in directory '{directory}'.")

        # Filter files by extension
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        if jxl:
            valid_extensions.extend('.jxl')
        dir_files = [f for f in dir_files if any(f.lower().endswith(ext) for ext in valid_extensions)]

        dir_files = sort_by(dir_files, directory)
        dir_files = [os.path.join(directory, x) for x in dir_files]

        # start at start_index
        dir_files = dir_files[start_index:]

        images = []
        masks = []

        limit_images = False
        if image_load_cap > 0:
            limit_images = True
        image_count = 0

        has_non_empty_mask = False

        for image_path in dir_files:
            if os.path.isdir(image_path) and os.path.ex:
                continue
            if limit_images and image_count >= image_load_cap:
                break
            i = Image.open(image_path)
            # Ensure orientation is correct if available
            if ImageOps is not None:
                try:
                    i = ImageOps.exif_transpose(i)
                except Exception:
                    pass
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            # If torch is available use it, otherwise wrap numpy to keep compatibility
            if torch is not None:
                image = torch.from_numpy(image)[None,]
            else:
                image = _NumpyTensorWrapper(image)
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                if torch is not None:
                    mask = 1. - torch.from_numpy(mask)
                else:
                    mask = 1. - mask
                has_non_empty_mask = True
            else:
                if torch is not None:
                    mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
                else:
                    mask = np.zeros((64, 64), dtype=np.float32)
            images.append(image)
            masks.append(mask)
            image_count += 1

        if len(images) == 1:
            return (images[0],)

        elif len(images) > 1:
            image1 = images[0]
            mask1 = None

            for image2 in images[1:]:
                # If torch is available, ensure tensors have compatible shapes and use comfy upscale
                try:
                    if hasattr(image1, 'shape') and hasattr(image2, 'shape') and image1.shape[1:] != image2.shape[1:]:
                        image2 = comfy.utils.common_upscale(image2.movedim(-1, 1), image1.shape[2], image1.shape[1], "bilinear", "center").movedim(1, -1)
                except Exception:
                    pass
                # Concatenate along batch dimension if torch available
                if torch is not None:
                    image1 = torch.cat((image1, image2), dim=0)
                else:
                    # Fallback: stack numpy arrays
                    image1 = np.concatenate((image1, image2), axis=0)

            for mask2 in masks:
                if has_non_empty_mask:
                    try:
                        if torch is not None:
                            if image1.shape[1:3] != mask2.shape:
                                mask2 = torch.nn.functional.interpolate(mask2.unsqueeze(0).unsqueeze(0), size=(image1.shape[1], image1.shape[2]), mode='bilinear', align_corners=False)
                                mask2 = mask2.squeeze(0)
                            else:
                                mask2 = mask2.unsqueeze(0)
                        else:
                            # numpy fallback: expand dims
                            mask2 = np.expand_dims(mask2, 0)
                    except Exception:
                        mask2 = np.expand_dims(mask2, 0)
                else:
                    if torch is not None:
                        mask2 = mask2.unsqueeze(0)
                    else:
                        mask2 = np.expand_dims(mask2, 0)

                if mask1 is None:
                    mask1 = mask2
                else:
                    if torch is not None:
                        mask1 = torch.cat((mask1, mask2), dim=0)
                    else:
                        mask1 = np.concatenate((mask1, mask2), axis=0)

            return (image1,)


# 注册节点（包含已有的 Open3DViewer 与新合并的 imaaaa 读取节点）
NODE_CLASS_MAPPINGS = {
    "Open3DViewer": Open3DViewer,
    "🔵BB 读取图像 //Inspire": imaaaa,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Open3DViewer": "🔵BB 打开3D查看器",
    "🔵BB 读取图像 //Inspire": "🔵BB 读取图像",
}

# 插件信息
__version__ = "1.1.0"
__description__ = "ComfyUI 3D模型查看器插件（含图像目录读取节点）"


 
 
