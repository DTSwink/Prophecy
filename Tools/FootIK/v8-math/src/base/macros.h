#pragma once
#include <cstdint>
#include <cstring>
#define V8_WARN_UNUSED_RESULT
#define V8_INLINE inline
namespace v8 { namespace base {
template<class To, class From> inline To bit_cast(const From& source) {
  static_assert(sizeof(To) == sizeof(From));
  To result;
  std::memcpy(&result, &source, sizeof(result));
  return result;
}
inline double Divide(double a, double b) { return a / b; }
}}
