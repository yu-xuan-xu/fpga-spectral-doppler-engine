# v1 numerical-model erratum

The frozen `v1.0-ice40` tag is unchanged. Its RTL Hann-window output is a signed 16-bit value, but the Python fixed-point oracle in `python/doppler/fixed.py` saturated that intermediate to 18 bits.

A test-first boundary case using alternating full-scale positive and negative samples exposed the mismatch: the old oracle produced -32993, outside the RTL range, instead of saturating to -32768. New tests also cover positive and negative full scale, overflow/underflow, positive and negative rounding boundaries, and exact half-way rounding. The v2 branch corrects only the oracle saturation width to 16 bits.

Canonical vectors did not trigger the issue because their Hann-windowed intermediate values stayed within the signed 16-bit range. Re-running the complete 1,800-configuration Python matrix produced unchanged published summary metrics: 100% high-SNR direction accuracy, 100% high-SNR fixed/float agreement within one bin, and zero reported saturation events. The fix therefore corrects the boundary contract without changing the reported ordinary-configuration results.
