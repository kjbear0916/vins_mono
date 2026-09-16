#!/usr/bin/env bash
echo "--- find gz config yaml ---"
find /etc/gz /usr/share/gz /usr/share/gz-tools* "$HOME/.gz" /opt/gz -maxdepth 3 -name '*.yaml*' 2>/dev/null | head -30
echo "--- ruby env usage in dispatcher ---"
grep -n 'ENV\[' /usr/bin/gz | head
echo "--- version sort logic ---"
grep -n 'sort\|max_by\|version' /usr/bin/gz | head -30