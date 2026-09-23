#!/bin/bash
set -u
echo "== gz-physics engine plugins =="
find /usr/lib/x86_64-linux-gnu -maxdepth 1 -name 'libgz-physics*engine*' 2>/dev/null | sort
find /usr/lib/x86_64-linux-gnu -maxdepth 1 -name 'libgz-physics*-plugin.so' 2>/dev/null | sort
echo "== GZ_PHYSICS_ENGINE_PATH in default env =="
printenv GZ_PHYSICS_ENGINE_PATH || echo "(unset)"
echo "== Physics system plugin listing =="
ls -la /usr/lib/x86_64-linux-gnu/gz-sim-8/plugins/ | grep -E 'physics|user-commands|scene-broadcaster|sensors|contact'
echo "== verbose tail of last default trial =="
grep -aE 'Physics|physics' /tmp/trial.log | head -15