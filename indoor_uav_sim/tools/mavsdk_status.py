#!/usr/bin/env python3
import asyncio
from mavsdk import System

async def main():
    drone = System()
    await drone.connect(system_address="udp://0.0.0.0:14540")
    async for state in drone.core.connection_state():
        if state.is_connected:
            break
    print("=== Connection ===")
    async for health in drone.telemetry.health():
        print(f"armable={health.is_armable} local_pos_ok={health.is_local_position_ok} "
              f"global_pos_ok={health.is_global_position_ok} "
              f"home_ok={health.is_home_position_ok}")
        break
    print("=== Position ===")
    pos = await drone.telemetry.position().__anext__()
    print(f"abs_lat={pos.latitude_deg:.6f} abs_lon={pos.longitude_deg:.6f} "
          f"rel_alt={pos.relative_altitude_m:.3f}")
    print("=== Attitude euler ===")
    att = await drone.telemetry.attitude_euler().__anext__()
    print(f"roll={att.roll_deg:.1f} pitch={att.pitch_deg:.1f} yaw={att.yaw_deg:.1f}")
    print("=== GPS info ===")
    gps = await drone.telemetry.gps_info().__anext__()
    print(f"fix={gps.fix_type} sats={gps.num_satellites}")
    print("=== Velocity ===")
    vel = await drone.telemetry.velocity_ned().__anext__()
    print(f"vN={vel.north_m_s:.2f} vE={vel.east_m_s:.2f} vD={vel.down_m_s:.2f}")

asyncio.run(main())