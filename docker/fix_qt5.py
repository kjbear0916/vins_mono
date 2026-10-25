import pathlib
f = pathlib.Path('/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/CMakeLists.txt')
t = f.read_text()
old = 'endif()\n\npkg_check_modules(OGRE OGRE)'
new = '''endif()

if(APPLE)
  execute_process(COMMAND brew --prefix qt5
                  ERROR_QUIET
                  OUTPUT_VARIABLE QT5_PREFIX_PATH
                  OUTPUT_STRIP_TRAILING_WHITESPACE
                 )
  list(APPEND CMAKE_PREFIX_PATH "${QT5_PREFIX_PATH}/lib/cmake")
endif()
find_package(Qt5 COMPONENTS Core Widgets REQUIRED)

pkg_check_modules(OGRE OGRE)'''
assert old in t, 'pattern not found'
t = t.replace(old, new, 1)
f.write_text(t)
print('OK')
