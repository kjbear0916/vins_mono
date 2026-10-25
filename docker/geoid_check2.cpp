#include <GeographicLib/Geoid.hpp>
#include <cstdio>
int main() {
  try {
    GeographicLib::Geoid g("egm96-5");
    printf("default-path 48.14,11.58 -> %.4f\n", g(48.14, 11.58));
  } catch (const std::exception& e) {
    fprintf(stderr, "ERR: %s\n", e.what());
    return 1;
  }
  return 0;
}