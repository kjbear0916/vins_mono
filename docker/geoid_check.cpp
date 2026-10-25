#include <GeographicLib/Geoid.hpp>
#include <cstdio>

int main(int argc, char** argv) {
  try {
    GeographicLib::Geoid geoid("egm96-5", "/tmp", true, false);
    double pts[][2] = {{48.14, 11.58}, {40.7, -73.9}, {0.0, 0.0}, {60.0, 100.0},
                       {89.0, -179.0}, {-89.0, 179.0}, {35.0, 140.0}};
    for (auto& p : pts) {
      double h = geoid(p[0], p[1]);
      printf("%8.4f %8.4f -> %.4f\n", p[0], p[1], h);
    }
  } catch (const std::exception& e) {
    fprintf(stderr, "ERROR: %s\n", e.what());
    return 1;
  }
  return 0;
}