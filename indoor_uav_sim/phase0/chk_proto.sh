python3 -c 'import google.protobuf; print("protobuf pip version:", google.protobuf.__version__)' 2>&1
dpkg -l 2>/dev/null | grep python3-protobuf | awk '{print "apt python3-protobuf:", $3}'
GZ_PY_IMPL_TEST=1 PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 -c 'from gz.msgs10 import pose_pb2, clock_pb2, imu_pb2, battery_pb2; print("gz.msgs10 py_impl import OK")' 2>&1