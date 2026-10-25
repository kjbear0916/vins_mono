import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", 14540))
s.settimeout(1)
t0 = time.time()
n = 0
out = open("/tmp/udp_out.txt", "w")
def log(x):
    out.write(x + "\n")
    out.flush()
while time.time() - t0 < 6:
    try:
        d, a = s.recvfrom(65535)
        n += 1
        if n <= 5:
            log(f"pkt#{n} {a} len={len(d)}")
    except Exception:
        pass
log(f"TOTAL={n} IN {time.time()-t0:.1f}s")
out.close()