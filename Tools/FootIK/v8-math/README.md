# V8 math compatibility for the native Foot IK runtime

`src/base/ieee754.cc` and `ieee754.h` are unmodified from V8 tag
`13.6.233.17`, matching the canonical Node 24.19 runtime
(`13.6.233.17-node.51`). They are the fdlibm-derived implementation, not
the newer LLVM-libc implementation on V8's main branch.

Source: https://chromium.googlesource.com/v8/v8/+/refs/tags/13.6.233.17/src/base/

The other four headers in `src/base/` supply the small standalone type,
bit-cast, overflow and export adapters needed to compile these two files.
They contain no solver logic. `LICENSE` retains V8's license; the original
Sun/fdlibm notice remains in `ieee754.cc`.

Compile with precise IEEE arithmetic (`/fp:strict` on MSVC), without
reassociation or fused multiply-add. This code is intended only to match
the native runtime's arithmetic to the unchanged canonical lab. It is not
installed into the browser or Node reference implementation.

The adjacent `deterministic-math.js` reproduces the separate V8
`Math.hypot` operation order from the matching `src/builtins/math.tq`.

`Math.pow` must use the matching `src/numbers/ieee754.cc` default
`use_std_math_pow` wrapper, including its `exponent == 2` and `0.5`
special cases. The legacy fdlibm `pow` function in this source is not the
canonical Node implementation and must not be registered as `Math.pow`.

`parity-math.cjs` compares native results against Node before solver tests.
The native test probe is built by `Tools/FootIK/CMakeLists.txt` into a
directory under `Saved/`; it does not alter Unreal or the running lab.
