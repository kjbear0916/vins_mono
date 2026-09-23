#!/usr/bin/env python3
"""Try to connect to PX4 nsh console via TCP. PX4 SITL usually has
a console on some TCP port. Check common ports."""
import socket, time

for port in [4500, 4501, 4502, 4503, 4504, 4505]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect(("127.0.0.1", port))
        print("Connected to TCP port %d!" % port, flush=True)
        time.sleep(1)
        data = b""
        s.settimeout(2)
        try:
            data = s.recv(4096)
        except:
            pass
        print("Initial data (%d bytes): %s" % (len(data), repr(data[:200])), flush=True)
        # Try sending nsh command
        s.sendall(b"mavlink status\r\n")
        time.sleep(2)
        try:
            resp = s.recv(8192)
            print("Response:\n%s" % resp.decode("utf-8", errors="replace"), flush=True)
        except:
            print("No response to mavlink status", flush=True)
        s.close()
        break
    except (ConnectionRefusedError, OSError):
        pass
    finally:
        s.close()
else:
    print("No PX4 console found on common ports", flush=True)
