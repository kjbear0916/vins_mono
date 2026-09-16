#!/usr/bin/env bash
awk 'NR>=14 && NR<=70' /tmp/px4gzdiag.log | cat -A