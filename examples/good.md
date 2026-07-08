# Example: claims backed by evidence (this file passes the gate)

- Fixed the off-by-one in pagination.
  Evidence: `src/pagination.py:88`, and the suite is green:
  ```
  $ pytest -q
  47 passed in 1.2s
  ```

- Login flow is verified end-to-end — see https://ci.example.com/runs/4821
  (exit code 0, 0 failures).

- Shipped the docs update. Result: build 12.4 s, 0 warnings.

- Performance work: p95 latency dropped to 180 ms (measured over 10k requests).
