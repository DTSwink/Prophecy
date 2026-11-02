#pragma once
#include <cstdint>
#include <type_traits>
#include "src/base/macros.h"
namespace v8 { namespace base {
template<class T> inline T NegateWithWraparound(T value) {
  using U=typename std::make_unsigned<T>::type;
  return bit_cast<T>(U(0)-static_cast<U>(value));
}
inline int32_t SubWithWraparound(int32_t a, int32_t b) {
  return bit_cast<int32_t>(static_cast<uint32_t>(a) - static_cast<uint32_t>(b));
}
}}
