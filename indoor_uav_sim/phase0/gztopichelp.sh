#!/usr/bin/env bash
timeout 10 gz topic --help 2>&1 | grep -A2 -E '^\s+-i|--info' | head -12