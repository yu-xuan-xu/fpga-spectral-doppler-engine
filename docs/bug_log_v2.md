# Phase 4 bug log

No RTL defects were found during the Phase 4 100-seed randomized regression or targeted
coverage closure. No design RTL was modified.

Test-infrastructure issues found while building coverage were corrected before release:

- Coverage classification was refined to use the prior observed IRQ state when a soft-reset
  pulse clears the sticky bit on the preceding edge.
- Output-stall context sampling was extended to observe a next-frame source becoming active
  after the stall had already begun.

These were coverage-observer issues, not DUT failures, and produced no protocol, register,
algorithm, loss, duplication, or ordering mismatch.
