#!/usr/bin/env python3
import sys, time
import gazebo as pip
from gazebo import transport
import gazebo.msgs

node = transport.Node()
got = {'imu': 0, 'mag': 0, 'gt': 0}

def on_imu(msg):
    got['imu'] += 1
def on_mag(msg):
    got['mag'] += 1
def on_gt(msg):
    got['gt'] += 1

node.Subscribe('/gazebo/iris/irisimu', gazebo.msgs.Imu, on_imu)
node.Subscribe('/gazebo/iris/irismag', gazebo.msgs.Magnetometer, on_mag)
node.Subscribe('/gazebo/iris/iris/groundtruth', gazebo.msgs.Groundtruth, on_gt)

t0 = time.time()
while time.time() - t0 < 6:
    time.sleep(0.1)
print('IMU msgs:', got['imu'])
print('MAG msgs:', got['mag'])
print('GT msgs:', got['gt'])