# Monotonic request timer

`k6/x/monotonic` exposes `now()` in milliseconds since module initialization. Go keeps the monotonic component of `time.Now()`; `time.Since(epoch)` is independent of later wall-clock corrections. Request events keep UTC time separately for timeline alignment.

Build with `python -B bench/build_k6.py`. The pinned versions are k6 2.2.0, xk6 1.5.1 and Go 1.26.5. `go.mod` and `go.sum` retain module dependencies. The build needs network access on its first use. The generated binary and its hash record stay in `.bench-runtime/`; each run records that hash and copies these timer sources to `inputs/monotonic/`.

The timer protects elapsed latency. It does not repair Windows/WSL clock synchronization or change the clock-skew acceptance rule.
