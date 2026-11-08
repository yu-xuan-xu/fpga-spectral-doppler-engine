# Real-Time FPGA Spectral Doppler Engine — MVP v1 Specification

**Status:** Hardware-independent MVP approved; physical-board validation deferred until an UPduino is available  
**Version:** 1.3
**Date:** 2026-08-13  
**Scope:** Educational, synthetic-signal FPGA test platform. This system is not a medical device and makes no diagnostic or clinical-accuracy claim.

## 1. MVP acceptance boundary

The v1 MVP processes pre-generated complex Doppler I/Q frames on one FPGA and returns one signed peak-velocity estimate per frame. It includes Python floating- and bit-accurate fixed-point models, synthesizable RTL around a 256-point FFT, automated self-checking simulation, implementation reports, and one on-board BRAM-to-UART demonstration.

The MVP does **not** include an ultrasound analog front end, ADC, live probe data, physical-flow phantom, custom PCB, GUI, overlapping FFT frames, multi-peak spectral-envelope tracking, or medical validation.

The project is released in two explicitly named milestones:

- **M1 — Hardware-independent implementation:** Python models, bit-accurate vectors, RTL, self-checking regression, and target-device synthesis/place-and-route reports.
- **M2 — Board-validated implementation:** programming, BRAM playback, result-link comparison, and repeatability evidence on a physical board.

M1 may be completed without owning the board. The full project is complete only after M2 passes. Passing Python, simulation, or synthesis must never be described as “deployed on FPGA hardware.”

## 2. Day-1 hardware freeze gate

The target family is an iCE40 UltraPlus on an UPduino board. The linked UPduino v3.x documentation identifies an `iCE40UP5K-SG48` device, but the physical board revision must still be checked from its silkscreen or USB identity. No physical board is currently available. The host audit below was performed on 2026-08-13.

| Item | Current finding | Freeze rule |
|---|---|---|
| Board | UPduino, revision not yet confirmed | Read the board silkscreen; v3.0/v3.1 may be recorded as `UPduino v3.x` after confirmation |
| FPGA | `iCE40UP5K-SG48` if the board is UPduino v3.x | Confirm against the physical board before publishing |
| Host OS | macOS 15.3.1 (24D70), Apple Silicon arm64 | Confirmed on this host |
| Installed flow | IceStorm 1.1, Icarus Verilog 13.0, Yosys 0.68+post, and nextpnr-ice40 0.11.1 are installed and tested | Preserve versions in generated reports |
| FFT implementation | Project RTL, resource-shared radix-2 iterative 256-point FFT | Keep the implementation isolated behind the FFT interface |
| Board clock | UPduino v3.x exposes a 12 MHz oscillator when the documented R16 jumper is shorted; UP5K also has an internal 48 MHz oscillator | Start with 12 or 24 MHz processing; raise only after timing evidence |
| Programmer | `iceprog` from IceStorm 1.1 is installed | Verify detection and a blink design with the physical board attached |
| Result link | No UPduino or USB serial device was attached during the audit | Verify the board-created serial device; otherwise use an external 3.3 V USB-UART adapter |
| Python | Project-local Python 3.11 environment is ready in `.venv`; numerical, plotting, test, cocotb, and serial smoke checks pass | Use `requirements.txt`/`requirements-dev.txt`; do not use the system Python for project runs |
| Prior course flow | WashU course environment used an FPGA Programmer Server plus Chrome/Edge WebUSB | Treat it as historical programming experience, not evidence of a complete local synthesis installation |

**M1 stop/go test:** install/restore the local build flow, synthesize a minimal `iCE40UP5K-SG48` design, and synthesize a stand-alone 256-point resource-shared FFT configuration. If it does not fit, revise the target before implementing the surrounding RTL. Do not spend the sprint building a large fully parallel FFT merely to rescue an undersized device.

**M2 stop/go test:** once a board is available, identify its revision, verify its USB identity, program a minimal blink image, and determine the result-link path before attempting the complete image.

Except for target-specific wrappers and timing/resource numbers, the remainder of this specification is frozen.

## 3. Signal and physical model

| Parameter | v1 value |
|---|---:|
| Input type | Complex baseband I/Q |
| Sample rate, `Fs` | 20,000 complex samples/s |
| Frame length | 256 samples |
| Frame overlap | 0 samples |
| Frame duration | 12.8 ms |
| Nominal frame rate | 78.125 frames/s |
| FFT-bin spacing | 78.125 Hz |
| Nominal ultrasound carrier, `f0` | 5.000 MHz |
| Assumed sound speed, `c` | 1540 m/s |
| Assumed probe angle, `theta` | 0 degrees |
| Unaliased Doppler interval | `[-10,000, +9,921.875] Hz` under signed-bin mapping |
| Nominal velocity interval | approximately `[-1.540, +1.528] m/s` |
| Velocity resolution | 0.01203125 m/s per FFT bin |

The educational conversion is:

```text
velocity_m_s = doppler_frequency_hz * c / (2 * f0 * cos(theta))
             = doppler_frequency_hz * 0.000154
```

Positive complex rotation means positive velocity; negative rotation means reverse flow. This sign convention must be used by the generator, reference models, RTL, plots, and documentation.

### 3.1 Synthetic scenarios

The generator must deterministically support these five profiles:

1. `steady`: constant signed velocity.
2. `pulsatile`: positive baseline plus a periodic pulse component.
3. `accelerated`: a repeatable ramp to a higher peak, described only as “stenosis-like” in synthetic tests.
4. `reverse`: negative signed velocity.
5. `irregular`: pulse timing and amplitude varied from a saved pseudo-random seed.

Signal construction must permit independent settings for initial phase, additive complex white Gaussian noise, and low-frequency complex wall clutter. Every generated case saves all physical parameters, amplitude/SNR convention, clutter settings, and random seed in machine-readable JSON.

## 4. Numeric representation and deterministic arithmetic

### 4.1 Stage formats

| Stage | Format | Rule |
|---|---|---|
| Input I and Q | signed 16-bit Q1.15 | range `[-1, 1)`; saturating quantization |
| Wall-filter state/output | signed 18-bit Q3.15 | saturate after feedback addition |
| Hann coefficients | unsigned 16-bit Q1.15 | `round(32767*w[n])`, endpoints zero |
| Window output | signed 16-bit | round-to-nearest, ties away from zero, then saturate |
| FFT logical output | signed 16-bit I/Q, sign-extended to 18-bit interface | block normalized by exactly `1/256`; saturate to 16 bits after each stage |
| Power | unsigned 37-bit minimum | exact `Re^2 + Im^2`; no square root |
| Peak bin | signed 9-bit integer | `[-128, 127]` |
| Frequency result | signed 24-bit Q16.8 Hz | `peak_bin * 20000` |
| Velocity result | signed 20-bit Q11.8 mm/s | `peak_bin * 3080` |

The Q11.8 velocity mapping is exact for the frozen constants because one bin is 12.03125 mm/s and `12.03125 * 256 = 3080`. Host software converts it to m/s by dividing by `256000`.

All additions, shifts, rounding, saturation, and tie-breaking behavior must be implemented identically in the Python fixed-point model and RTL. Wraparound is forbidden at externally observable stage boundaries. Any vendor FFT scaling schedule must be adapted in `fft_wrapper` so its logical output is equivalent to a `1/256` normalized FFT.

### 4.2 Wall-clutter filter

Apply the following first-order complex high-pass filter independently to I and Q, continuously across frames:

```text
y[n] = sat18(x[n] - x[n-1] + round((63 * y[n-1]) / 64))
```

Filter state is cleared only by reset, not by frame boundaries. A case begins with at least one discarded warm-up frame before scored frames. This shift/add coefficient avoids a general multiplier and yields a repeatable RTL contract.

### 4.3 Window

Use the symmetric 256-point Hann definition:

```text
w[n] = 0.5 - 0.5*cos(2*pi*n/255), n = 0..255
```

Coefficient generation is performed once by Python and checked into the repository as a ROM initialization file. RTL must not calculate trigonometric functions.

## 5. Spectrum and peak rules

1. Compute a forward 256-point complex FFT.
2. Map raw FFT index `k` to signed bin `b`: `b=k` for `k<=127`; otherwise `b=k-256`.
3. Compute power as `Re^2 + Im^2` without logarithms or square root.
4. Exclude signed bins `-1, 0, +1` from the peak search to suppress residual wall/DC energy.
5. Select the remaining bin with greatest power.
6. On an exact power tie, select the candidate with smaller absolute signed-bin value; if still tied, select the negative bin.
7. Find the greatest allowed non-peak power. Set `low_confidence` when the peak is zero or is less than three times that runner-up. Equality at exactly three times is confident. The flag does not suppress the numeric result.

No sub-bin interpolation, spectral smoothing, harmonic selection, or multi-bin envelope estimate is permitted in v1. Accordingly, the nominal quantization floor is half a bin, or about 6.016 mm/s, before noise and leakage effects.

## 6. Streaming and module contracts

### 6.1 Input stream

The reusable processing core uses one clock domain and an AXI-Stream-like interface (not a claim of full AXI compliance):

```text
clk, rst_n
s_valid, s_ready
s_i[15:0], s_q[15:0]
s_last
```

A sample transfers only when `s_valid && s_ready`. `s_last` must be asserted on sample 255. Once asserted, `s_valid`, sample data, and `s_last` remain stable until accepted. Input gaps are legal. The core may deassert `s_ready`; BRAM playback must honor it.

Malformed early/late `s_last` sets `frame_error`, discards the current frame, and resynchronizes at the next accepted `s_last`. Reset immediately invalidates partial frames and clears filter state.

### 6.2 Result stream

```text
m_valid, m_ready
m_peak_bin[8:0]
m_frequency_q8_hz[23:0]
m_velocity_q8_mm_s[19:0]
m_peak_power[36:0]
m_status[3:0]   // {reserved, overflow, low_confidence, frame_error}
```

A result transfers only on `m_valid && m_ready`; all result fields remain stable during output backpressure. Exactly one result is emitted for every valid accepted frame and none for a discarded frame.

### 6.3 Required hierarchy

```text
doppler_core
├── dc_wall_filter
├── window_multiplier + coefficient_rom
├── fft_wrapper
├── power_calculator
├── peak_bin_detector
└── velocity_mapper

board_top
├── bram_sample_source
├── doppler_core
├── result_buffer
└── uart_tx / command control
```

Target-specific FFT and clock-generation details are isolated in wrappers. Core modules must not contain board pin names or UART behavior.

## 7. Clock, throughput, and latency targets

The UPduino baseline processing clock is 12 MHz from the board oscillator, subject to the documented R16 jumper and physical-board confirmation. A 24 MHz internal-clock option may be generated by PLL or selected from the UP5K oscillator only after a minimal timing test. A 100 MHz target is removed for this small device. The external nominal source rate is only 20 kS/s, so a resource-shared, multi-cycle FFT is acceptable.

Targets:

- No dropped samples under a protocol-compliant source.
- The filter/window front end accepts one sample per cycle while ready; the complete core may deassert `s_ready` while an iterative FFT is active.
- Result latency: no more than 120,000 processing-clock cycles from acceptance of input `s_last` to assertion of `m_valid`.
- Nominal acquisition-to-result time: no more than 12.8 ms acquisition plus 10 ms processing at 12 MHz, for less than 22.8 ms total.
- Minimum sustained frame rate: 43 frames/s; stretch target: the source frame rate of 78.125 frames/s.
- Timing closure: non-negative worst slack at the frozen processing clock.

Report measured cycle latency, sustained throughput, Fmax or achieved clock, worst slack, LUT, FF, DSP, and BRAM usage. Do not substitute targets for measured results.

## 8. Reference-model and file contract

Each test case directory must contain:

```text
config.json                 # parameters, seed, model/version hash
metadata.json               # model/spec versions and arithmetic convention
input_iq_q15.mem            # 256 or more packed I/Q samples
expected_frames.csv         # bin, frequency Q8, velocity Q8, peak power, flags
float_results.csv           # floating estimate and programmed ground truth
intermediate/frame_NNN/      # filter, window, FFT, and power oracle memories
```

The floating model defines algorithmic behavior. The fixed-point model is the bit-accurate RTL oracle. The comparison report must always distinguish:

- programmed/theoretical velocity;
- floating-point Python estimate;
- fixed-point Python estimate;
- RTL simulation estimate;
- physical FPGA estimate.

## 9. Verification plan and pass criteria

### 9.1 Directed tests

- Reset while idle, between frames, and mid-frame.
- Correct, early, missing, and late `s_last`.
- Input gaps and randomized input/output backpressure.
- Output stability while stalled.
- Positive bins `2, 3, 16, 64, 127` and negative bins `-2, -3, -16, -64, -127`.
- Near-Nyquist and intentional aliasing cases.
- Zero input, full-scale input, saturation, and exact peak-power tie.
- Filter warm-up and state continuity across frame boundaries.

### 9.2 Regression matrix

Run at minimum:

- 5 waveform families;
- 10 signed velocity levels, including both directions;
- SNR levels `{infinite, 30, 20, 10}` dB;
- clutter-to-signal amplitude ratios `{0, 0.5, 2.0}`;
- 3 seeds for randomized profiles.

This is at least 1,800 parameterized cases before protocol-specific directed tests. A reduced smoke suite may run per commit; the full matrix runs before results are published.

### 9.3 Assertions and scoreboard

Assertions must cover handshake stability, legal frame length, one result per valid frame, no result after aborted/reset frames, counter bounds, and no unknown values on accepted transfers. The ordered scoreboard compares every output field against the bit-accurate Python oracle and records case configuration and seed on failure.

### 9.4 Release thresholds

| Metric | Required threshold |
|---|---:|
| Protocol/output mismatches vs fixed-point oracle | 0 |
| Assertions failed | 0 |
| Direction accuracy for accepted non-aliasing cases at SNR >= 20 dB | 100% |
| RTL peak-bin difference vs fixed-point oracle | 0 bins |
| Fixed-point vs floating peak-bin difference at SNR >= 20 dB | <= 1 bin for >= 99% of scored frames |
| Mean absolute FPGA-vs-programmed velocity error at SNR >= 20 dB | <= 1 FFT bin (12.03125 mm/s), excluding documented transition/alias frames |
| Timing | WNS >= 0 at frozen clock |
| On-board repeatability | 100 consecutive demo runs with 0 result mismatches |

Frames whose programmed frequency changes materially within the 12.8 ms analysis window must be tagged `transition`; report them separately rather than silently removing them. Low-confidence and intentional-alias cases are also reported separately.

## 10. Hardware-independent two-week deliverables

| Day | Deliverable and exit criterion |
|---:|---|
| 1 | Restore the local toolchain; synthesize a minimal UP5K target and size the FFT; publish block diagram and this signed-off specification. Physical programming is deferred. |
| 2 | Deterministic generator for steady, reverse, noise, and clutter; JSON metadata and saved seeds. |
| 3 | Floating pipeline, all five profiles, required plots, and bin-centered recovery tests. |
| 4 | Bit-accurate Q-format model, coefficient ROM, overflow sweep, and float-vs-fixed quantization report. |
| 5 | Streaming shell, frame checker, filter RTL, unit tests, and handshake assertions. |
| 6 | Window RTL/ROM, arithmetic edge-case tests, and comparison against fixed model. |
| 7 | FFT wrapper integrated; one positive and one negative steady case pass end to end. |
| 8 | Power, signed peak selection, velocity mapper, and exact tie/guard-bin tests pass. |
| 9 | Full ordered scoreboard; reset, malformed frame, input-gap, and backpressure tests pass. |
| 10 | Smoke regression passes with zero mismatches; top-level and UART packet format frozen. |
| 11 | Synthesis/place-and-route; timing closure; archived timing and utilization reports. No new features. |
| 12 | Complete the synthesizable BRAM source, result packetizer, UART RTL, and self-checking loopback simulation; archive the generated bitstream as **unverified on hardware**. |
| 13 | Full experiment matrix; accuracy/SNR/direction/simulated-latency/resource plots and raw CSV results. |
| 14 | README, architecture graphic, limitations, simulation demo, and M1 résumé bullets using only verified simulation/synthesis values. Create an M2 board-validation checklist. |

If the M1 synthesis gate fails because the design cannot fit UP5K, change the target before continuing RTL integration. Lack of a physical board does not pause M1. If later work slips, remove optional plots/demo polish before reducing self-checking verification or timing closure.

### 10.1 Deferred M2 board-validation day

When a board becomes available, reserve one focused day to:

1. confirm board revision, FPGA marking, oscillator selection, and USB identity;
2. program a known blink image;
3. program the Doppler bitstream and run the BRAM-resident cases;
4. compare at least 100 returned result packets with the fixed-point oracle;
5. archive programmer logs, board photo/video, failures, and measured repeatability;
6. update README and résumé language from “targeted/synthesized for” to “deployed on” only after passing.

## 11. Host-link demonstration contract

The board demo uses BRAM-resident input. The preferred result link is 115200-8-N-1 UART when the connected UPduino exposes a usable serial path; otherwise an external 3.3 V USB-UART adapter is the v1 fallback. A host command starts one named case; the board returns a fixed binary result packet containing a sync word, case ID, signed peak bin, Q8 frequency, Q8 velocity, peak power, status, and CRC-16. Python validates the CRC and compares the decoded payload to the same case’s fixed-point expected result.

Live PC-to-FPGA sample streaming is explicitly optional and cannot block M2 completion.

## 12. Change control

After Day 1, changes to sample rate, frame length, Q formats, filter coefficient, window definition, FFT normalization, bin-sign convention, guard bins, or output units require:

1. a dated specification revision;
2. regenerated vectors and coefficients;
3. rerunning all unit and regression tests;
4. an explanation in the results report.

Board-specific pin assignments, FFT wrapper wiring, and measured implementation numbers may be completed without changing the algorithmic baseline.

## 13. Information still required from the owner

To close M1, record:

- working Yosys and nextpnr-ice40 versions after installation/restoration;
- stand-alone FFT and complete-core fit/timing reports for `iCE40UP5K-SG48`;
- realistic hours available per day and résumé deadline;
- any reusable, publishable code or Doppler data constraints.

To close M2 later, record:

- physical UPduino revision and confirmation of the `iCE40UP5K-SG48` marking;
- whether R16 is shorted or the internal oscillator will be used;
- USB identity and serial-device path with the board connected;
- whether the UPduino link can carry the result protocol or an external 3.3 V USB-UART is required;
- the blink and 100-run Doppler validation evidence.

The integrated processing core has synthesized and placed for the UP5K target at 12 MHz; preserve the exact report and tool versions with any such claim. Until M2 passes, do not claim the board revision, host result link, or on-board operation has been demonstrated.
