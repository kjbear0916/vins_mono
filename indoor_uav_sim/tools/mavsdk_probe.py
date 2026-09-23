#!/usr/bin/env python3
import asyncio, logging
logging.basicConfig(level=logging.DEBUG)
from mavsdk import System

async def main():
    print("creating system")
    drone = System()
    print("connecting", flush=True)
    await drone.connect(system_address="udpin://0.0.0.0:14540")
    print("connected", flush=True)
    try:
        async for state in drone.core.connection_state():
            print("conn_state is_connected=", state.is_connected, flush=True)
            if state.is_connected:
                break
    except Exception as e:
        print("conn_state err", repr(e), flush=True)
    async for health in drone.telemetry.health():
        print("health armable=%s localpos=%s" % (health.is_armable, health.is_local_position_ok), flush=True)
        if health.is_armable:
            break

asyncio.run(main())
print("done", flush=True)