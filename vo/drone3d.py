"""Custom minimal-OpenGL 3D quadcopter renderer for the indoor-GPS UAV demo.

pyrender 0.1.45 renders an empty frame on this machine, while raw PyOpenGL
works, so this module draws the 3D scene with a small hand-rolled GL
pipeline inside a hidden pyglet window.

The drone body defaults to a real STL model (D:\Things\vo\models\jdrone.stl,
z-up, converted to world y-up on load); if the file is missing it falls back
to the procedural frame.

Public API used by nav_demo_drone.py:
    handle = drone3d.init(size=(w, h))
    drone3d.use_model(path=None)      # load an STL/OBJ/glTF body mesh
    drone3d.draw_panel(handle, img, x, y, w, h,
                       yaw_deg, pitch_deg, roll_deg, phase,
                       shadow_alpha=0.45, t=0.0)
    # t>0 orbits the camera slowly (recommended: t = frame_index / fps)
"""
import ctypes
import math
import os

import cv2
import numpy as np
import pyglet
from pyglet.window import Window
from pyglet.gl import Config

from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BGRA, GL_BLEND, GL_CLAMP_TO_EDGE, GL_COLOR_ATTACHMENT0,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_DEPTH_COMPONENT24,
    GL_DEPTH_ATTACHMENT, GL_DEPTH_TEST, GL_DYNAMIC_DRAW, GL_ELEMENT_ARRAY_BUFFER, GL_FALSE,
    GL_FLOAT, GL_FRAMEBUFFER, GL_FRAGMENT_SHADER, GL_LESS, GL_LINEAR,
    GL_ONE_MINUS_SRC_ALPHA, GL_RENDERBUFFER, GL_RGBA, GL_RGBA8,
    GL_SRC_ALPHA, GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_TRIANGLES, GL_TRUE,
    GL_UNSIGNED_INT, GL_UNSIGNED_BYTE, GL_VERTEX_SHADER, glBindBuffer,
    glBindFramebuffer, glBindRenderbuffer, glBindTexture, glBindVertexArray,
    glBlendFunc, glBufferData, glCheckFramebufferStatus, glClear,
    glClearColor, glClearDepth, glColorMask, glDeleteBuffers,
    glDeleteFramebuffers, glDeleteRenderbuffers, glDeleteTextures,
    glDepthMask, glDepthFunc, glDisable, glDrawElements, glEnable,
    glEnableVertexAttribArray, glFramebufferRenderbuffer,
    glFramebufferTexture2D, glGenBuffers, glGenFramebuffers,
    glGenRenderbuffers, glGenTextures, glGenVertexArrays, glReadBuffer,
    glReadPixels, glRenderbufferStorage, glTexImage2D, glTexParameteri,
    glUniform1f, glUniform3f, glUniform2f, glUniformMatrix3fv,
    glUniformMatrix4fv,
    glUseProgram,
    glVertexAttribPointer, glViewport)
from OpenGL.GL import shaders as _sh

ARM_LEN = 0.48
BODY_W = 0.30
BODY_H = 0.22
MOTOR_R = 0.045
MOTOR_H = 0.14
HUB_Z = 0.19
BLADE_L = 0.36
BLADE_W = 0.028
BLADE_H = 0.005
HOVER_Z = 0.86

_MODEL = None
_MODEL_WARNED = False
_DEFAULT_MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "models", "jdrone.stl")

_VSH = """
#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNor;
uniform mat4 uMvp;
uniform mat3 uNor;
out vec3 vNor;
out vec3 vPos;
void main(){
    gl_Position = uMvp * vec4(aPos, 1.0);
    vNor = uNor * aNor;
    vPos = aPos;
}
"""

_FSH = """
#version 330 core
in vec3 vNor;
in vec3 vPos;
uniform vec3 uColor;
uniform vec3 uLightDir;
uniform vec3 uFillDir;
uniform vec3 uCamPos;
uniform vec3 uFog;
uniform vec2 uFogRange;
uniform float uMetallic;
uniform float uAlpha;
out vec4 fragColor;
void main(){
    vec3 n = normalize(vNor);
    vec3 L1 = normalize(uLightDir);
    vec3 L2 = normalize(uFillDir);
    vec3 V = normalize(uCamPos - vPos);
    vec3 H = normalize(L1 + V);
    float ndl1 = max(dot(n, L1), 0.0);
    float ndl2 = max(dot(n, L2), 0.0);
    float spec = pow(max(dot(n, H), 0.0), 48.0);
    float rsp = spec * mix(0.25, 1.0, uMetallic);
    vec3 col = uColor * (0.28 + 0.72 * ndl1 + 0.28 * ndl2) + vec3(rsp) * 0.5;
    float d = length(vPos.xy);
    float fog = smoothstep(uFogRange.x, uFogRange.y, d);
    col = mix(col, uFog, fog * 0.9);
    fragColor = vec4(col, uAlpha);
}
"""


def _rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0],
                     [0, 0, 0, 1]], np.float64)


def _rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0],
                     [0, 0, 0, 1]], np.float64)


def _rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0],
                     [0, 0, 0, 1]], np.float64)


def _rot_about(axis, a):
    axis = np.asarray(axis, np.float64)
    axis = axis / (np.linalg.norm(axis) + 1e-12)
    x, y, z = axis
    c, s = math.cos(a), math.sin(a)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s, 0],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s, 0],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C, 0],
                     [0, 0, 0, 1]], np.float64)


def _trans(x, y, z):
    m = np.eye(4, dtype=np.float64)
    m[:3, 3] = [x, y, z]
    return m


def _look_at(eye, ctr, up=np.array([0.0, 0.0, 1.0])):
    f = np.asarray(ctr, np.float64) - np.asarray(eye, np.float64)
    f = f / (np.linalg.norm(f) + 1e-12)
    r = np.cross(f, np.asarray(up, np.float64))
    r = r / (np.linalg.norm(r) + 1e-12)
    u = np.cross(r, f)
    m = np.eye(4)
    m[:3, 0] = r
    m[:3, 1] = u
    m[:3, 2] = -f
    m[:3, 3] = np.asarray(eye, np.float64)
    return np.linalg.inv(m)


def _box(cx, cy, cz, sx, sy, sz):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    c = np.array([[-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz],
                  [-hx, hy, -hz], [-hx, -hy, hz], [hx, -hy, hz],
                  [hx, hy, hz], [-hx, hy, hz]])
    face_norm = [(0, -1, 0), (0, 1, 0), (-1, 0, 0), (1, 0, 0),
                 (0, 0, 1), (0, 0, -1)]
    face_idx = [(0, 1, 2, 3), (5, 4, 7, 6), (0, 4, 1, 5), (3, 7, 2, 6),
                (1, 5, 6, 2), (0, 3, 7, 4)]
    pos, nor, idx = [], [], []
    for fn, qi in zip(face_norm, face_idx):
        q = c[list(qi)] + np.array([cx, cy, cz])
        ids = len(pos)
        pos.extend(q)
        nor.extend([fn] * 4)
        idx += [ids, ids + 1, ids + 2, ids, ids + 2, ids + 3]
    return (np.asarray(pos, np.float32), np.asarray(nor, np.float32),
            np.asarray(idx, np.int32))


def _cylinder_between(a, b, r, seg=10):
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    diff = b - a
    h = np.linalg.norm(diff)
    if h < 1e-9:
        return (np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32),
                np.zeros((0,), np.int32))
    uz = diff / h
    pos, nor, idx = [], [], []
    n = seg
    pts = np.array([[math.cos(2 * math.pi * i / n),
                     math.sin(2 * math.pi * i / n)] for i in range(n + 1)])
    for i in range(n + 1):
        x, y = pts[i]
        pos.append([x * r, y * r, -h / 2])
        pos.append([x * r, y * r, h / 2])
        nor.append([x, y, 0])
        nor.append([x, y, 0])
    for i in range(n):
        b0 = i * 2
        idx += [b0, b0 + 1, b0 + 2, b0 + 2, b0 + 1, b0 + 3]
    base = len(pos)
    pos.append([0, 0, -h / 2])
    nor.append([0, 0, -1])
    for i in range(n):
        x, y = pts[i]
        pos.append([x * r, y * r, -h / 2])
        nor.append([0, 0, -1])
        if i < n - 1:
            idx += [base, base + 1 + i, base + 2 + i]
    base = len(pos)
    pos.append([0, 0, h / 2])
    nor.append([0, 0, 1])
    for i in range(n):
        x, y = pts[i]
        pos.append([x * r, y * r, h / 2])
        nor.append([0, 0, 1])
        if i < n - 1:
            idx += [base, base + 2 + i, base + 1 + i]
    pos = np.asarray(pos, np.float32)
    nor = np.asarray(nor, np.float32)
    up = np.array([0.0, 0.0, 1.0])
    axis = np.cross(up, uz)
    an = np.linalg.norm(axis)
    if an > 1e-7:
        R = _rot_about(axis / an, math.acos(np.clip(float(np.dot(up, uz)), -1, 1)))
    else:
        R = np.eye(4) if float(np.dot(up, uz)) > 0 else _rot_about([1, 0, 0],
                                                                   math.pi)
    pos4 = np.hstack([pos, np.ones((pos.shape[0], 1), np.float32)])
    M = _trans(*a) @ R
    pos = (M @ pos4.T).T[:, :3].astype(np.float32)
    nor4 = np.hstack([nor, np.zeros((nor.shape[0], 1), np.float32)])
    nor = ((R @ nor4.T).T[:, :3]).astype(np.float32)
    return pos, nor, np.asarray(idx, np.int32)


def _uv_sphere(cx, cy, cz, r, nlat=8, nlon=10):
    pos, nor, idx = [], [], []
    grid = []
    for i in range(nlat + 1):
        row = []
        lat = math.pi / 2 - math.pi * i / nlat
        for j in range(nlon + 1):
            lon = 2 * math.pi * j / nlon
            v = np.array([math.cos(lat) * math.cos(lon),
                          math.cos(lat) * math.sin(lon), math.sin(lat)])
            pos.append(v * r + np.array([cx, cy, cz]))
            nor.append(v)
        grid.append(row)
    def rd(i, j):
        return i * (nlon + 1) + j
    for i in range(nlat):
        for j in range(nlon):
            a0, a1, a2, a3 = rd(i, j), rd(i, j + 1), rd(i + 1, j + 1), rd(i + 1, j)
            idx += [a0, a1, a3, a1, a2, a3]
    return (np.asarray(pos, np.float32), np.asarray(nor, np.float32),
            np.asarray(idx, np.int32))


def _plane(cx, cy, cz, w, d):
    pos = np.array([[-w / 2, -d / 2, 0], [w / 2, -d / 2, 0],
                    [w / 2, d / 2, 0], [-w / 2, d / 2, 0]], np.float32)
    pos += np.array([cx, cy, cz], np.float32)
    nor = np.tile([0.0, 0.0, 1.0], (4, 1)).astype(np.float32)
    idx = np.array([0, 1, 2, 0, 2, 3], np.int32)
    return pos, nor, idx


def _part(pos, nor, idx, color, alpha=1.0):
    return dict(pos=pos, nor=nor, idx=idx,
                color=np.asarray(color, np.float32), alpha=alpha,
                n=int(idx.shape[0]))


def _build_static(large=False):
    if large:
        parts = [_part(*_plane(0, 0, 0.0, 44.0, 44.0), (0.88, 0.90, 0.88))]
        g = (0.62, 0.62, 0.62)
        for v in np.arange(-9.0, 9.05, 0.5):
            parts.append(_part(*_box(v, 0, 0.002, 0.016, 18.0, 0.006), g))
        for v in np.arange(-9.0, 9.05, 0.5):
            parts.append(_part(*_box(0, v, 0.002, 18.0, 0.016, 0.006), g))
        ring = [(3.5, 0.0), (0.0, 3.5), (-3.5, 0.0), (0.0, -3.5),
                (2.5, 2.5), (-2.5, 2.5), (2.5, -2.5), (-2.5, -2.5)]
        for i, (cx, cy) in enumerate(ring):
            col = (0.25, 0.72, 0.30) if i % 2 == 0 else (0.25, 0.40, 0.85)
            parts.append(_part(*_box(cx, cy, 0.006, 0.5, 0.5, 0.010), col))
        for cx, cy in [(-0.8, -0.8), (0.8, 0.8), (0.8, -0.8), (-0.8, 0.8)]:
            col = (0.25, 0.72, 0.30) if (cx + cy) > 0 else (0.25, 0.40, 0.85)
            parts.append(_part(*_box(cx, cy, 0.006, 0.16, 0.16, 0.010), col))
        return parts
    parts = [_part(*_plane(0, 0, 0.0, 8.0, 8.0), (0.90, 0.90, 0.88))]
    g = (0.62, 0.62, 0.62)
    for v in np.arange(-2.0, 2.05, 0.4):
        parts.append(_part(*_box(v, 0, 0.002, 0.008, 4.0, 0.004), g))
    for v in np.arange(-2.0, 2.05, 0.4):
        parts.append(_part(*_box(0, v, 0.002, 4.0, 0.008, 0.004), g))
    for cx, cy in [(-0.8, -0.8), (0.8, 0.8), (0.8, -0.8), (-0.8, 0.8)]:
        col = (0.25, 0.72, 0.30) if (cx + cy) > 0 else (0.25, 0.40, 0.85)
        parts.append(_part(*_box(cx, cy, 0.004, 0.16, 0.16, 0.006), col))
    return parts


def _apply_T(parts, T, R_att):
    for p in parts:
        pos, nor, idx = p["pos"], p["nor"], p["idx"]
        pos4 = np.hstack([pos, np.ones((pos.shape[0], 1), np.float32)])
        nor4 = np.hstack([nor, np.zeros((nor.shape[0], 1), np.float32)])
        p["pos"] = (T @ pos4.T).T[:, :3].astype(np.float32)
        p["nor"] = (R_att @ nor4.T).T[:, :3].astype(np.float32)
    return parts


def _load_model(path):
    import trimesh
    s = trimesh.load(path, force="mesh")
    v = np.asarray(s.vertices, np.float32)
    f = np.asarray(s.faces, np.int32)
    if v.shape[0] == 0 or f.shape[0] == 0:
        raise ValueError("model has no geometry")
    R = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], np.float32)
    v = np.asarray(v @ R.T, np.float32)
    n = np.asarray(s.vertex_normals, np.float32)
    n = np.asarray(n @ R.T, np.float32)
    v[:, 0] -= (v[:, 0].min() + v[:, 0].max()) / 2.0
    v[:, 2] -= (v[:, 2].min() + v[:, 2].max()) / 2.0
    lo, hi = float(v[:, 1].min()), float(v[:, 1].max())
    anchors = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            q = np.where((v[:, 0] * sx > 0) & (v[:, 1] * sy > 0))[0]
            if q.size == 0:
                continue
            i = q[int(np.argmax(v[q, 0] ** 2 + v[q, 1] ** 2))]
            r = np.hypot(v[i, 0], v[i, 1])
            if r < 1e-6:
                continue
            anchors.append((float(v[i, 0] * (r + 0.004) / r),
                            float(v[i, 1] * (r + 0.004) / r)))
    prop_r = 0.16
    if anchors:
        prop_r = min(0.20, max(np.hypot(a[0], a[1]) for a in anchors) * 0.92)
    return dict(v=v, n=n, f=f, lo=lo, hi=hi, mid=(lo + hi) / 2.0,
                top=hi, anchors=anchors, prop_r=max(prop_r, 0.05),
                hub_z=hi + 0.015)


def use_model(path=None):
    global _MODEL, _MODEL_WARNED
    path = path or _DEFAULT_MODEL
    if not os.path.isfile(path):
        if not _MODEL_WARNED:
            print("drone3d: model not found (%s) - using procedural frame"
                  % path)
            _MODEL_WARNED = True
        _MODEL = None
        return False
    try:
        _MODEL = _load_model(path)
        print("drone3d: model %s  verts=%d tris=%d prop_r=%.3f anchors=%d"
              % (os.path.basename(path), _MODEL["v"].shape[0],
                 _MODEL["f"].shape[0], _MODEL["prop_r"],
                 len(_MODEL["anchors"])))
        return True
    except ImportError:
        if not _MODEL_WARNED:
            print("drone3d: trimesh missing - using procedural frame")
            _MODEL_WARNED = True
        _MODEL = None
        return False
    except Exception as e:  # noqa: BLE001
        if not _MODEL_WARNED:
            print("drone3d: model load failed (%s) - using procedural frame" % e)
            _MODEL_WARNED = True
        _MODEL = None
        return False


def _procedural_parts(yaw_deg, pitch_deg, roll_deg, phase, hover_z):
    yaw, pitch, roll = map(math.radians, (yaw_deg, pitch_deg, roll_deg))
    R_att = _rot_z(yaw) @ _rot_x(pitch) @ _rot_y(roll)
    T = _trans(0, 0, hover_z) @ R_att
    parts = []
    parts.append(_part(*_box(0, 0, 0.11, BODY_W, BODY_W, BODY_H),
                       (0.30, 0.32, 0.36)))
    parts.append(_part(*_box(0, 0, 0.30, 0.26, 0.26, 0.05),
                       (0.22, 0.24, 0.28)))
    parts.append(_part(*_cylinder_between([0.15, 0, 0.09], [0.24, 0, 0.09], 0.028),
                       (0.55, 0.95, 0.95)))
    parts.append(_part(*_uv_sphere(0.255, 0, 0.09, 0.028), (0.70, 0.30, 0.85)))
    parts.append(_part(*_uv_sphere(0.13, 0, 0.25, 0.028), (0.95, 0.20, 0.20)))
    parts.append(_part(*_uv_sphere(-0.13, 0, 0.25, 0.028), (0.25, 0.90, 0.25)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            mx, my = sx * ARM_LEN, sy * ARM_LEN
            parts.append(_part(
                *_cylinder_between([sx * BODY_W / 3, sy * BODY_W / 3, 0.09],
                                   [mx, my, 0.13], 0.016),
                (0.18, 0.19, 0.22)))
            parts.append(_part(
                *_cylinder_between([mx, my, 0.10], [mx, my, 0.17], MOTOR_R),
                (0.12, 0.13, 0.15)))
            bc = (0.40, 0.42, 0.44)
            pa, na, ia = _box(0, 0, 0, BLADE_L * 2, BLADE_W, BLADE_H)
            for j in (0, 1):
                sp = phase * 3.2 + (0 if j == 0 else math.pi / 2) + \
                     (math.pi / 2 if sy < 0 else 0)
                Tspin = _rot_z(sp)
                Tm = _trans(mx, my, HUB_Z)
                full = T @ Tspin @ Tm
                pa4 = np.hstack([pa, np.ones((pa.shape[0], 1), np.float32)])
                pw = (full @ pa4.T).T[:, :3].astype(np.float32)
                na4 = np.hstack([na, np.zeros((na.shape[0], 1), np.float32)])
                nw = ((Tspin @ na4.T).T[:, :3]).astype(np.float32)
                parts.append(_part(pw, nw, ia, bc, alpha=0.62))
    return _apply_T([p for p in parts if p["alpha"] >= 1.0], T, R_att) + \
        [p for p in parts if p["alpha"] < 1.0]


def _model_parts(yaw_deg, pitch_deg, roll_deg, phase, hover_z):
    M = _MODEL
    yaw, pitch, roll = map(math.radians, (yaw_deg, pitch_deg, roll_deg))
    R_att = _rot_z(yaw) @ _rot_x(pitch) @ _rot_y(roll)
    T = _trans(0, 0, hover_z) @ R_att

    v, n = M["v"], M["n"]
    v4 = np.hstack([v, np.ones((v.shape[0], 1), np.float32)])
    wv = (T @ v4.T).T[:, :3].astype(np.float32)
    n4 = np.hstack([n, np.zeros((n.shape[0], 1), np.float32)])
    wn = (R_att @ n4.T).T[:, :3].astype(np.float32)

    cy = v[M["f"]].mean(axis=1)
    up_f = M["f"][cy >= M["mid"]].reshape(-1).astype(np.int32)
    dn_f = M["f"][cy < M["mid"]].reshape(-1).astype(np.int32)
    ncol = 0.0
    up_col = (0.345, 0.355, 0.385)
    dn_col = (0.24, 0.25, 0.28)
    parts = [_part(wv, wn, up_f, up_col), _part(wv, wn, dn_f, dn_col)]

    pr, hz = M["prop_r"], M["hub_z"]
    blade_len = pr
    bc = (0.42, 0.43, 0.46)
    pa, na, ia = _box(0, 0, 0, blade_len * 2, 0.02, 0.006)
    for (mx, my) in M["anchors"]:
        parts.append(_part(
            *_cylinder_between([mx, my, hz - 0.008], [mx, my, hz + 0.004],
                               max(0.008, pr * 0.10)),
            (0.14, 0.15, 0.18)))
        for j in (0, 1):
            sp = phase * 3.2 + (0 if j == 0 else math.pi / 2) + \
                 (math.pi / 2 if (mx * my) < 0 else 0)
            Tspin = _rot_z(sp)
            Tm = _trans(mx, my, hz + 0.004)
            full = T @ Tspin @ Tm
            pa4 = np.hstack([pa, np.ones((pa.shape[0], 1), np.float32)])
            pw = (full @ pa4.T).T[:, :3].astype(np.float32)
            na4 = np.hstack([na, np.zeros((na.shape[0], 1), np.float32)])
            nw = ((Tspin @ na4.T).T[:, :3]).astype(np.float32)
            parts.append(_part(pw, nw, ia, bc, alpha=0.55))

    top = M["top"]
    parts.append(_part(*_uv_sphere(0.16, 0, ncol + 0.01, 0.018),
                       (0.60, 0.98, 0.99), alpha=1.0))
    parts.append(_part(*_uv_sphere(0.07, 0.05, top + 0.015, 0.012),
                       (0.95, 0.20, 0.20)))
    parts.append(_part(*_uv_sphere(-0.07, -0.05, top + 0.015, 0.012),
                       (0.25, 0.90, 0.25)))
    return _apply_T([p for p in parts if p["alpha"] >= 1.0], T, R_att) + \
        [p for p in parts if p["alpha"] < 1.0]


def _dynamic_parts(yaw_deg, pitch_deg, roll_deg, phase, hover_z):
    if _MODEL is not None:
        return _model_parts(yaw_deg, pitch_deg, roll_deg, phase, hover_z)
    return _procedural_parts(yaw_deg, pitch_deg, roll_deg, phase, hover_z)


def _orbit_eye(t):
    base = np.array([-0.9, -1.8, 1.45], np.float64)
    target = np.array([0.0, 0.0, 0.62], np.float64)
    if not t:
        return base
    d0 = base - target
    rad = float(np.linalg.norm(d0[:2]))
    az0 = math.atan2(d0[1], d0[0])
    el = math.atan2(d0[2], rad)
    az = az0 + float(t) * 0.28
    return target + np.array([rad * math.cos(el) * math.cos(az),
                              rad * math.cos(el) * math.sin(az),
                              rad * math.sin(el)], np.float64)


def _render_frame(cfg, w, h, yaw_deg, pitch_deg, roll_deg, phase,
                  t=0.0, eye=None, target=None):
    if (cfg["w"], cfg["h"]) != (w, h):
        _resize_fbo(cfg, w, h)
    glBindFramebuffer(GL_FRAMEBUFFER, cfg["fbo"])
    glViewport(0, 0, w, h)
    sky = cfg["sky"]
    glClearColor(sky[0], sky[1], sky[2], 1.0)
    glClearDepth(1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LESS)

    if eye is None:
        eye = _orbit_eye(t)
    if target is None:
        target = np.array([0, 0, 0.62], np.float64)
    V = _look_at(np.asarray(eye, np.float64),
                 np.asarray(target, np.float64))
    near, far = 0.05, 20.0
    f = 1.0 / math.tan(math.radians(42) / 2)
    a = w / max(h, 1)
    P = np.array([[f / a, 0, 0, 0],
                  [0, f, 0, 0],
                  [0, 0, (far + near) / (near - far),
                   2 * far * near / (near - far)],
                  [0, 0, -1, 0]], np.float64)
    MVP = P @ V
    I3 = np.eye(3, dtype=np.float32)

    glUseProgram(cfg["prog"])
    glUniformMatrix4fv(cfg["u_mvp"], 1, GL_TRUE, np.ascontiguousarray(MVP.T, np.float32))
    glUniformMatrix3fv(cfg["u_nor"], 1, GL_TRUE,
                      np.ascontiguousarray(I3))
    glUniform3f(cfg["u_light"], 0.40, -0.55, 0.65)
    glUniform3f(cfg["u_fill"], -0.42, 0.42, -0.30)
    glUniform3f(cfg["u_fog"], *map(float, sky))
    fr = cfg["fog"]
    glUniform2f(cfg["u_fogrange"], float(fr[0]), float(fr[1]))
    glUniform3f(cfg["u_cam"], *map(float, eye))
    glUniform1f(cfg["u_metallic"], 0.0)

    vbo, ebo = cfg["vbo"], cfg["ebo"]
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)

    def draw(part, alpha):
        inter = np.concatenate([part["pos"], part["nor"]], axis=1)
        glBufferData(GL_ARRAY_BUFFER, inter.nbytes, inter, GL_DYNAMIC_DRAW)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, part["idx"].nbytes,
                     part["idx"], GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, None)
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, _VEC_OFF)
        glUniform3f(cfg["u_color"], *map(float, part["color"]))
        glUniform1f(cfg["u_alpha"], alpha)
        glUniform1f(cfg["u_metallic"], 0.35 if alpha < 1.0 else 0.0)
        glDrawElements(GL_TRIANGLES, part["n"], GL_UNSIGNED_INT, None)

    for p in cfg["static"]:
        draw(p, 1.0)

    dyn_parts = _dynamic_parts(yaw_deg, pitch_deg, roll_deg, phase, HOVER_Z)
    opaque = [p for p in dyn_parts if p["alpha"] >= 1.0]
    for p in opaque:
        draw(p, 1.0)
    blend = [p for p in dyn_parts if p["alpha"] < 1.0]
    if blend:
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(GL_FALSE)
        for p in blend:
            draw(p, p["alpha"])
        glDepthMask(GL_TRUE)
        glDisable(GL_BLEND)
    glColorMask(True, True, True, True)

    glReadBuffer(GL_COLOR_ATTACHMENT0)
    raw = glReadPixels(0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE)
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4)[:, :, :3]
    return np.ascontiguousarray(arr[::-1, :, :])


def _resize_fbo(cfg, w, h):
    if cfg["fbo"] is not None:
        glDeleteFramebuffers(1, [cfg["fbo"]])
        glDeleteRenderbuffers(1, [cfg["rbo"]])
        glDeleteTextures(1, [cfg["tex"]])
    fbo = glGenFramebuffers(1)
    tex = glGenTextures(1)
    rbo = glGenRenderbuffers(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA,
                 GL_UNSIGNED_BYTE, None)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glBindFramebuffer(GL_FRAMEBUFFER, fbo)
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,
                           tex, 0)
    glBindRenderbuffer(GL_RENDERBUFFER, rbo)
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, w, h)
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                              GL_RENDERBUFFER, rbo)
    cfg["fbo"], cfg["tex"], cfg["rbo"] = fbo, tex, rbo
    cfg["w"], cfg["h"] = w, h


def init(size=(370, 248)):
    if not hasattr(init, "_window"):
        init._window = Window(width=1, height=1, visible=False, resizable=True,
                              config=Config(depth_size=24))
        init._window.switch_to()
    prog = _sh.compileProgram(
        _sh.compileShader(_VSH, GL_VERTEX_SHADER),
        _sh.compileShader(_FSH, GL_FRAGMENT_SHADER))
    glUseProgram(prog)
    vao = glGenVertexArrays(1)
    glBindVertexArray(vao)
    handle = dict(prog=prog, vao=vao, vbo=glGenBuffers(1), ebo=glGenBuffers(1),
                  fbo=None, tex=None, rbo=None, w=0, h=0,
                  static=_build_static(), sky=(0.925, 0.925, 0.91),
                  fog=(3.0, 4.4))
    handle["u_mvp"] = _glGetUniformLocation(prog, "uMvp")
    handle["u_nor"] = _glGetUniformLocation(prog, "uNor")
    handle["u_color"] = _glGetUniformLocation(prog, "uColor")
    handle["u_light"] = _glGetUniformLocation(prog, "uLightDir")
    handle["u_fill"] = _glGetUniformLocation(prog, "uFillDir")
    handle["u_fog"] = _glGetUniformLocation(prog, "uFog")
    handle["u_fogrange"] = _glGetUniformLocation(prog, "uFogRange")
    handle["u_cam"] = _glGetUniformLocation(prog, "uCamPos")
    handle["u_metallic"] = _glGetUniformLocation(prog, "uMetallic")
    handle["u_alpha"] = _glGetUniformLocation(prog, "uAlpha")
    return handle


def use_large_ground(handle, sky=(0.63, 0.74, 0.85), fog=(4.5, 9.5)):
    handle["static"] = _build_static(large=True)
    handle["sky"] = sky
    handle["fog"] = fog


def render_frame(h, w, hh, yaw_deg, pitch_deg, roll_deg, phase,
                 eye=None, target=None, t=0.0):
    """Render the GL scene directly (no cv2 overlays) and return a BGR image.

    Pass eye/target to follow the drone with a camera; otherwise the default
    orbit camera (t seconds of azimuth) is used.
    """
    return _render_frame(h, w, hh, yaw_deg, pitch_deg, roll_deg, phase,
                         t, eye, target)


def draw_panel(h, img, x, y, pw, ph, yaw_deg, pitch_deg, roll_deg,
               phase, shadow_alpha=0.45, t=0.0):
    arr = _render_frame(h, pw, ph, yaw_deg, pitch_deg, roll_deg, phase, t)
    img[y:y + ph, x:x + pw] = arr
    overlay = img.copy()
    center = (x + int(pw * 0.5), y + int(ph * 0.80))
    axes = (max(10, int(pw * 0.16)), max(4, int(ph * 0.07)))
    cv2.ellipse(overlay, center, axes, 0, 0, 360, (70, 70, 70), -1)
    cv2.addWeighted(overlay, shadow_alpha, img, 1.0 - shadow_alpha, 0, img)
    cv2.rectangle(img, (x, y), (x + pw, y + ph), (140, 140, 140), 1)
    cv2.putText(img, "3D UAV VIEW", (x + 6, y + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 40), 1, cv2.LINE_AA)


_VEC_OFF = ctypes.c_void_p(12)
_glGetUniformLocation = None


def _bind_uniform_loc():
    global _glGetUniformLocation
    from OpenGL.GL import glGetUniformLocation
    _glGetUniformLocation = glGetUniformLocation


_bind_uniform_loc()