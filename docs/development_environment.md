# Development environment

## Python

The project uses an isolated Python 3.11 environment at `.venv`. Activate it from the repository root:

```sh
source .venv/bin/activate
```

Recreate the environment when needed with:

```sh
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Runtime and verification dependencies are declared in `requirements.txt`; developer-only tooling is in `requirements-dev.txt`. The local environment itself is excluded from version control.

## Verified package set

Environment smoke-tested on 2026-08-13 with:

- Python 3.11.1
- NumPy 2.4.6
- SciPy 1.17.1
- pandas 3.0.5
- Matplotlib 3.11.1
- pytest 9.1.1
- cocotb 2.0.1
- pyserial 3.5
- Ruff 0.16.2

The smoke check recovered a 1,250 Hz complex tone at bin 16 of a 256-point FFT sampled at 20 kS/s, generated a SciPy spectrogram and PNG plot, and reported no broken Python requirements.

On restricted or headless systems, point plotting caches at a writable location:

```sh
XDG_CACHE_HOME=/tmp/doppler-cache MPLCONFIGDIR=/tmp/doppler-mpl \
  .venv/bin/python your_script.py
```
