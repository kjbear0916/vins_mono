#!/usr/bin/env python3
import asyncio, logging, sys, time
logging.basicConfig(level=logging.DEBUG)
from mavsdk import System

async def main():
    print("creating system", flush=True)
    drone = System()
    print("connecting...", flush=True)
    t0 = time.time()
    try:
        await asyncio.wait_for(drone.connect(system_address="udpin://0.0.0.0:14540"), 20)
        print(f"connect returned after {time.time()-t0:.1f}s", flush=True)
    except Exception as e:
        print(f"connect err after {time.time()-t0:.1f}s: {type(e).__name__}: {e}", flush=True)
        return
    print("waiting for connection_state...", flush=True)
    try:
        async for state in drone.core.connection_state():
            print("is_connected=", state.is_connected, flush=True)
            if state.is_connected:
                break
            if time.time() - t0 > 20:
                break
    except Exception as e:
        print("conn_state err:", type(e).__name__, e, flush=True)

asyncio.run(main())
print("done", flush=True)