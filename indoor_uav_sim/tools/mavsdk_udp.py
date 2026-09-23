#!/usr/bin/env python3
import asyncio, time, sys
url = sys.argv[1] if len(sys.argv) > 1 else "udp://:14540"
from mavsdk import System

async def main():
    print("connecting %s..." % url, flush=True)
    drone = System()
    t0 = time.time()
    try:
        await asyncio.wait_for(drone.connect(system_address=url), 15)
        print(f"connect returned after {time.time()-t0:.1f}s", flush=True)
    except Exception as e:
        print(f"connect err: {type(e).__name__}: {e}", flush=True)
        return
    async for state in drone.core.connection_state():
        print("is_connected=", state.is_connected, flush=True)
        if state.is_connected:
            break

asyncio.run(main())
print("done", flush=True)