#!/usr/bin/env bash
echo "--- which gz ---"
command -v gz
echo "--- file type ---"
file "$(command -v gz)"
echo "--- head of dispatcher ---"
head -40 "$(command -v gz)"
echo "--- search env override in ruby dispatcher ---"
RUBY=$(command -v gz)
grep -rn 'GZ_VERSION\|ENV\[' /usr/lib/ruby/vendor_ruby/gz/ 2>/dev/null | head -20