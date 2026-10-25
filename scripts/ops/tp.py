#!/usr/bin/env python3
import sys, time
sys.path.insert(0, '/usr/lib/x86_64-linux-gnu/gazebo-11')
import gz.msgs
import gazebo.transport as transport

node = transport.Node()
got = {'imu': 0, 'mag': 0, 'gt': 0}

def on_imu(msg, ident):
    got['imu'] += 1
def on_mag(msg, ident):
    got['mag'] += 1
def on_gt(msg, ident):
    got['gt'] += 1

node.Subscribe('/gazebo/iris/irisimu', gz.msgs.ImageStamped, on_imu) if False else node.Subscribe('/gazebo/iris/irisimu', gz.msgs.Imu, on_imu)
node.Subscribe('/gazebo/iris/irismag', gz.msgs.Magnetometer, on_mag)
node.Subscribe('/gazebo/iris/iris/groundtruth', gz.msgs.Groundtruth, on_gt)

t0 = time.time()
while time.time() - t0 < 6:
    time.sleep(0.1)
print('IMU msgs:', got['imu'])
print('MAG msgs:', got['mag'])
print('GT msgs:', got['gt'])