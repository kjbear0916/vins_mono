"""Phase 0 acceptance test: takeoff to 1 m, hover 10 s, land.

Requires PX4 SITL running with Gazebo (``make px4_sitl gz_x500``).
Connects over UDP using MAVSDK.
"""
import asyncio
import shutil
import subprocess
import sys
import time

from mavsdk import System


def log(msg: str) -> None:
    print(msg, flush=True)


def gz_true_z() -> float | None:
    """Query Gazebo for the x500 model's true world Z position."""
    exe = shutil.which("gz")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "model", "-m", "x500", "--info"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Pose:") and "[" in line:
            try:
                inner = line.split("[", 1)[1].split("]", 1)[0]
                return float(inner.split(",")[2].strip())
            except Exception:
                return None
    return None


async def run() -> None:
    drone = System()
    log("connecting to PX4 SITL, listening on udpin://0.0.0.0:14540 ...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    log("waiting for vehicle ...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("connected")
            break

    print("waiting for health checks ...")
    t_h = time.time()
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_armable:
            print("health OK")
            break
        if time.time() - t_h > 90.0:
            print(f"FAIL: health not OK after 90.0 s: "
                  f"local={health.is_local_position_ok} "
                  f"global={health.is_global_position_ok} "
                  f"home={health.is_home_position_ok} "
                  f"armable={health.is_armable}")
            print(f"  health obj fields: {[a for a in dir(health) if not a.startswith('_')]}")
            return

    print("waiting until arming allowed (GPS + home pos)")
    t_p = time.time()
    async for pos in drone.telemetry.position():
        if pos.relative_altitude_m is not None:
            print(f"position stream alive, rel_alt={pos.relative_altitude_m:.2f} m")
            break
        if time.time() - t_p > 20.0:
            print("FAIL: position stream never delivered data")
            return

    altitude = 2.0
    print(f"arming + takeoff to {altitude} m")
    await asyncio.sleep(2)
    await drone.action.arm()
    await asyncio.sleep(1)
    await drone.action.takeoff()

    print("climbing ...")
    reached = False
    t_climb = time.time()
    while time.time() - t_climb < 45.0:
        async for pos in drone.telemetry.position():
            rel = pos.relative_altitude_m
            gz_z = gz_true_z()
            print(f"  climb t={time.time()-t_climb:5.1f}s est_rel={rel:6.2f} gz_true={gz_z}")
            if rel >= altitude - 0.2:
                print(f"reached {rel:.2f} m (gz_true_z={gz_z})")
                reached = True
                break
            break
        if reached:
            break
        await asyncio.sleep(1.0)

    if not reached:
        print(f"FAIL: did not reach {altitude} m within 45 s")
        await drone.action.land()
        await asyncio.sleep(4)
        return

    print("hovering 10 s ...")
    t0 = time.time()
    hover_err = []
    rows = []
    while time.time() - t0 < 10.0:
        gz_z = gz_true_z()
        async for pos in drone.telemetry.position():
            rel = pos.relative_altitude_m
            hover_err.append(abs(rel - altitude))
            rows.append((round(time.time() - t0, 1), round(rel, 2),
                         round(gz_z, 2) if gz_z is not None else None))
            break
        await asyncio.sleep(0.8)

    if hover_err:
        print(f"hover err mean={sum(hover_err)/len(hover_err):.3f} m "
              f"max={max(hover_err):.3f} m over {len(hover_err)} samples")
    for t_s, rel, gz in rows:
        print(f"  t={t_s:4.1f}s est_rel_alt={rel:6.2f} gz_true_z={gz}")

    ok = hover_err and max(hover_err) < 0.5
    print("PASS" if ok else "FAIL")
    print("landing ...")
    await drone.action.land()
    await asyncio.sleep(6)
    print("done")


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()