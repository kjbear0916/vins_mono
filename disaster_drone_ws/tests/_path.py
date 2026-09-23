#!/usr/bin/env python3
"""Shared sys.path bootstrap so tests import the source tree directly
(no colcon install needed). Exposes the src root as SRC_ROOT."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_ROOT = os.path.abspath(os.path.join(TESTS_DIR, os.pardir, "src"))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)