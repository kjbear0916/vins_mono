python3 -c "import gz.transport13; print('gz.transport13 OK')" 2>&1
python3 -c "import gz.msgs10; print('gz.msgs10 OK')" 2>&1
python3 -c "import px4_msgs; print('px4_msgs OK')" 2>&1
dpkg -l 2>/dev/null | grep -iE 'python3-gz|python3-px4' | awk '{print $2}'