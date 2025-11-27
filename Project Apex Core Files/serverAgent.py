from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import socket
import time
from functools import lru_cache
import re
import mimetypes
from urllib.parse import unquote

# ===== 配置 =====
PORT = 8000
FILE_NAME = "PROJECT_APEX_V2.html"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PATH = os.path.join(SCRIPT_DIR, FILE_NAME)

# ===== 更可靠的IP获取方法 =====
def get_local_ip():
    """获取本机局域网IP"""
    try:
        # 方法1：通过连接外部服务器获取IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            # 方法2：通过主机名获取IP
            return socket.gethostbyname(socket.gethostname())
        except:
            # 方法3：回退到本地IP
            return "127.0.0.1"

# ===== 预加载文件 =====
try:
    with open(FILE_PATH, "rb") as f:
        FILE_CONTENT = f.read()
    print(f"预加载完成，文件大小: {len(FILE_CONTENT)/1024:.2f} KB")
except Exception as e:
    print(f"预加载失败: {e}")
    FILE_CONTENT = b"<h1>File Not Loaded</h1>"

# ===== 预缓存图片 =====
IMAGE_CACHE = {}  # key: url path (e.g. /Images/img.jpg) -> (bytes, mime)

def preload_images_from_html(html_bytes):
    try:
        html = html_bytes.decode('utf-8', errors='ignore')
    except:
        html = ''
    # 匹配 src/href 引用，常见图片目录 Images/ 或 images/
    paths = set(re.findall(r'src=["\']([^"\']+)["\']', html))
    paths.update(re.findall(r'href=["\']([^"\']+)["\']', html))
    cached = 0
    for p in paths:
        # 只处理看起来是图片的相对路径或 Images/ 子路径
        lp = p.split('?')[0].split('#')[0]
        if not lp:
            continue
        ext = os.path.splitext(lp)[1].lower()
        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico'):
            # 构造文件系统路径
            # 支持绝对 /Images/... 与相对 Images/...
            request_path = lp if lp.startswith('/') else '/' + lp
            fs_path = os.path.join(SCRIPT_DIR, lp.lstrip('/'))
            fs_path = os.path.normpath(fs_path)
            if os.path.exists(fs_path) and os.path.isfile(fs_path):
                try:
                    with open(fs_path, 'rb') as imgf:
                        data = imgf.read()
                    mime, _ = mimetypes.guess_type(fs_path)
                    if not mime:
                        mime = 'application/octet-stream'
                    IMAGE_CACHE[request_path] = (data, mime)
                    cached += 1
                except Exception as e:
                    print(f"预缓存图片失败: {fs_path} -> {e}")
    print(f"图片预缓存完成: {cached} 张已缓存")

# 执行预缓存
preload_images_from_html(FILE_CONTENT)

# ===== 请求处理 =====
class FastRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # 统一解码路径（处理空格与编码）
        path = unquote(self.path)
        if path in ('/', f'/{FILE_NAME}', f'/{os.path.basename(FILE_NAME)}'):
            # 当请求根或指定文件时，返回预加载的 HTML
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            # 缓存策略：客户端可以缓存一会儿
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(FILE_CONTENT)
            print(f"已处理请求: {path} -> served {FILE_NAME}")
            return

        # 如果在图片缓存中，直接返回缓存内容
        if path in IMAGE_CACHE:
            data, mime = IMAGE_CACHE[path]
            self.send_response(200)
            self.send_header("Content-type", mime)
            # 长一点的缓存（浏览器端），若需要强制更新可修改为 no-cache
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
            print(f"已处理请求: {path} -> served cached image ({len(data)} bytes)")
            return

        # 若不是已知缓存资源，尝试从磁盘提供（保留 SimpleHTTPRequestHandler 的静态文件处理）
        # 注意：SimpleHTTPRequestHandler 使用当前工作目录作为根目录
        # 若需要从 SCRIPT_DIR 提供，请先 chdir 或实现自定义文件读取
        return super().do_GET()

# ===== 服务器启动 =====
def run_server():
    # 切换工作目录到脚本目录，这样 SimpleHTTPRequestHandler 能正确提供同目录下的资源
    os.chdir(SCRIPT_DIR)
    server = ThreadingHTTPServer(('0.0.0.0', PORT), FastRequestHandler)
    local_ip = get_local_ip()
    
    print(f"\n⚡ 代理服务器已启动")
    print(f"├─ 本机访问: http://localhost:{PORT}/{FILE_NAME}")
    if local_ip != "127.0.0.1":
        print(f"└─ 局域网访问: http://{local_ip}:{PORT}/{FILE_NAME}")
    else:
        print("└─ 警告: 无法获取局域网IP，只能本机访问")
    
    print("\n按 Ctrl+C 停止服务器...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")

if __name__ == "__main__":
    if not os.path.exists(FILE_PATH):
        print(f"错误: {FILE_PATH} 不存在")
        exit(1)
    
    run_server()