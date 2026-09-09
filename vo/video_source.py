import threading
import time

import cv2
import numpy as np


class VideoSource:
    def read(self):
        raise NotImplementedError

    def release(self):
        raise NotImplementedError


class WebcamSource(VideoSource):
    def __init__(self, device=0, width=None, height=None, fps=None):
        self.cap = cv2.VideoCapture(device)
        if width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if fps:
            self.cap.set(cv2.CAP_PROP_FPS, fps)

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()


class VideoFileSource(VideoSource):
    def __init__(self, path):
        self.cap = cv2.VideoCapture(path)

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()


class HTTPMJPEGSource(VideoSource):
    """MJPEG stream reader that bypasses cv2's MJPEG demuxer.

    OpenCV's ffmpeg demuxer is slow and assert-prone on the ESP32's
    multipart/x-mixed-replace stream (measured ~1 fps). This source opens a
    plain HTTP stream, splits JPEG frames on the multipart boundary and
    decodes each with cv2.imdecode -- then keeps only the latest decoded frame
    in a lock-protected slot, which a background thread refreshes at the
    stream's native rate.
    """

    def __init__(self, url, timeout=10.0):
        self.url = url
        self.timeout = timeout
        self.lock = threading.Lock()
        self.frame = None
        self.ok = False
        self.alive = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        t0 = time.time()
        while time.time() - t0 < 10.0:
            with self.lock:
                if self.frame is not None:
                    return
            time.sleep(0.02)
        print("HTTPMJPEGSource: no frame within 10s")

    def _run(self):
        import re
        import requests
        while self.alive:
            try:
                r = requests.get(self.url, stream=True, timeout=self.timeout)
                buf = b""
                for chunk in r.iter_content(chunk_size=8192):
                    if not self.alive:
                        return
                    buf += chunk
                    while True:
                        m = re.search(br"\r\nContent-Length:\s*(\d+)\r\n",
                                      buf)
                        if not m:
                            if len(buf) > 65536:
                                buf = b""
                            break
                        n_bytes = int(m.group(1))
                        j_start = buf.find(b"\r\n\r\n", m.end())
                        if j_start < 0:
                            if len(buf) > 65536:
                                buf = b""
                            break
                        j_start += 4
                        j_end = j_start + n_bytes
                        if len(buf) < j_end:
                            break
                        jpeg = buf[j_start:j_end]
                        buf = buf[j_end:]
                        if jpeg:
                            img = cv2.imdecode(
                                np.frombuffer(jpeg, np.uint8),
                                cv2.IMREAD_COLOR)
                            if img is not None:
                                with self.lock:
                                    self.frame = img
                                    self.ok = True
            except Exception:
                if self.alive:
                    time.sleep(0.5)

    def read(self):
        with self.lock:
            f = self.frame
            ok = self.ok
        return ok, f

    def release(self):
        self.alive = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)


class ThreadedMJPEGSource(VideoSource):
    """Continuous MJPEG collector on a dedicated thread.

    cv2.VideoCapture on an MJPEG URL blocks inside `read()` for one JPEG
    decode + network round trip. When the consumer is slow, that latency
    stacks frame-to-frame and the pipeline falls to a few fps. This source
    decodes in the background, keeps only the most recent complete frame in a
    lock-protected slot, and `read()` returns it instantly (dropping frames if
    the consumer is slower than the feed -- which is exactly what a VO front
    end wants: every processed frame is the newest, none aging in a queue).
    """

    def __init__(self, url, buffer_slots=1):
        self.url = url
        self.cap = cv2.VideoCapture(url)
        self.lock = threading.Lock()
        self.frame = None
        self.ok = False
        self.alive = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        # wait for first decoded frame
        t0 = time.time()
        while time.time() - t0 < 8.0:
            with self.lock:
                if self.frame is not None:
                    return
            time.sleep(0.02)

    def _run(self):
        while self.alive:
            ok, fr = self.cap.read()
            if ok and fr is not None:
                with self.lock:
                    self.frame = fr
                    self.ok = True
            else:
                time.sleep(0.05)

    def read(self):
        with self.lock:
            f = self.frame
            ok = self.ok
        return ok, f

    def fps(self):
        n, t0 = 0, time.time()
        while time.time() - t0 < 1.0:
            if self.read()[0]:
                n += 1
        return n

    def release(self):
        self.alive = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.cap.release()


class Esp32MJPEGSource(VideoSource):
    def __init__(self, url):
        self.cap = cv2.VideoCapture(url)

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()


def create_source(kind, **kwargs):
    if kind == "webcam":
        return WebcamSource(**kwargs)
    if kind == "file":
        return VideoFileSource(**kwargs)
    if kind == "esp32":
        return HTTPMJPEGSource(**kwargs)
    raise ValueError("unknown source kind: %s" % kind)