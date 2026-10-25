#!/usr/bin/env python3
import socket, struct, time
import pymavlink.dialects.v20.ardupilotmega as ac
from pymavlink.mavutil import mavlink_parse_char

# Show first parsed HIL_SENSOR (id 107) & HIL_GPS (113) from TCP 4560 stream
# (the conversation is PX4<->gazebo; we attach as an extra TCP client is NOT
#  allowed - server accepts one conn.  Instead sniff via loopback capture is
#  out of scope here; this tool reads from a pcap-less live socket is not
#  possible on the server side.  So we instead SUBSCRIBE gz topics live.)

import subprocess

def gzecho(topic, lines=2):
    try:
        p = subprocess.Popen(["gz", "topic", "-e", topic],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=8)
        out = p.stdout
        n = 0
        for line in out:
            print(topic, "::", line.decode("utf-8", "replace")[:160], flush=True)
            n += 1
            if n >= lines:
                p.kill()
                break
    except Exception as e:
        print(topic, "ERR", e, flush=True)

gzecho("/gazebo/default/iris_fpv_cam/imu")
gzecho("/gazebo/default/iris_fpv_cam/world_wind/velocity", 1)