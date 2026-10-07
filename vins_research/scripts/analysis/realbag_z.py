#!/usr/bin/env python3
import sys
import rosbag
import statistics

bag_path = sys.argv[1]
ts = []
zs = []
with rosbag.Bag(bag_path, 'r') as bag:
    for topic, msg, t in bag.read_messages(topics=['/gazebo/model_states']):
        for i, name in enumerate(msg.name):
            if 'iris' in name:
                x = msg.pose[i].position
                ts.append(t.to_sec())
                zs.append(x.z)
if not zs:
    print('GT_Z none')
    sys.exit(0)
print('GT_Z n=%d t0=%.1f t1=%.1f z: min=%.3f max=%.3f mean=%.3f' % (
    len(zs), ts[0], ts[-1], min(zs), max(zs), statistics.mean(zs)))
step = max(1, len(zs) // 20)
for i in range(0, len(zs), step):
    print('  t=%6.1f z=%7.3f' % (ts[i] - ts[0], zs[i]))