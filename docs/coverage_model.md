# Phase 4 functional coverage model

## Implementation

Icarus Verilog does not provide SystemVerilog covergroups, so Phase 4 implements functional
coverage in `tb/cocotb/coverage_model.py`. Each bin stores hit count, first seed, first cycle,
and first scenario. Coverage fragments from the 100-seed regression and targeted closure
test are merged by `scripts/archive_phase4_verification.py`.

Credit is based on observed events:

- Input and output transfers require actual `TVALID && TREADY`.
- Gap and stall lengths are measured from sampled interface cycles.
- AXI-Lite address/order/strobe/response bins are credited after the real response returns.
- Frame type uses accepted samples and accepted TLAST, not source intent.
- Reset location is inferred from accepted frame state, public stream state, and outstanding
  AXI channel handshakes; soft-reset credit also requires the internal generated reset pulse.
- Algorithm conditions are credited only after a transferred RTL result passes the
  bit-accurate scoreboard. Low-SNR accuracy is not assumed from coverage.

## Coverage points

The model defines 149 required functional bins and 114 required risk-driven cross bins.
They cover input gaps/stalls, output stalls and context, five frame types, result behavior,
AW/W ordering/delay, B/R stalls, six address types, response type, all 16 WSTRB values,
register side effects, ten global-reset locations, six soft-reset locations, post-reset
state, nine IRQ behaviors, direction, seven peak ranges, five SNR ranges, four clutter
ranges, three amplitudes, six special signals, and the meaningful system crosses listed in
the verification plan.

Crosses deliberately avoid a full Cartesian product. For example, address type crosses
only its legal response, and AW/W order crosses representative zero, 2–3 and 16+ B-stall
risk classes.

## Scoreboard separation

The random regression keeps generated stimulus, accepted stream beats, expected algorithm
results, transferred results, register transactions, and reset-aborted work as distinct
objects. A reset may remove untransferred work under the documented contract without being
reported as loss. Result count, snapshot, sequence, enable and IRQ state are read back and
compared after observed output transfers.

On failure, the runner records the failing seed, scenario, Q1.15 input vectors, expected and
actual traces, first mismatch cycle, and automatically reruns that seed with an Icarus FST
waveform. `scripts/run_seeded_regression.py --seed <seed> --waves` is the manual reproducer.

## Waived defined bins

Four bins remain defined but waived outside the required denominator:

- Natural 32-bit sequence wrap in the controlled top would require 2^32 results. Phase 2
  separately tests the same wrapper from `0xfffffffe` through wrap.
- The three `amplitude × saturated` outcomes are unreachable for legal Q1.15 samples with
  the frozen 18-bit wall filter and per-stage scaled FFT. The 1,800-case matrix also observes
  zero saturation. Their corresponding non-saturated crosses are required and hit.

These bins were not deleted to manufacture a perfect headline. The supported claim is
“100% of defined required functional coverage bins,” not code, toggle, or universal
coverage.
