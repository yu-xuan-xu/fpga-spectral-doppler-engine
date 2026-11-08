import json

import numpy as np
import pytest
from doppler.classification import classify_frame
from doppler.common import peak_metrics, raw_to_signed_bin, select_peak
from doppler.config import DopplerConfig, FlowProfile
from doppler.fixed import hann_q15, process_fixed_frame, quantize_q15, round_shift, saturate
from doppler.floating import process_float_frame
from doppler.generator import generate_signal


@pytest.mark.parametrize("profile", list(FlowProfile))
def test_all_profiles_are_deterministic(profile):
    config = DopplerConfig(profile=profile, seed=23)
    first = generate_signal(config)
    second = generate_signal(config)
    np.testing.assert_array_equal(first.iq, second.iq)
    assert first.iq.shape == (1024,)


def test_positive_and_reverse_sign():
    positive = generate_signal(DopplerConfig(profile=FlowProfile.STEADY, snr_db=None))
    reverse = generate_signal(DopplerConfig(profile=FlowProfile.REVERSE, snr_db=None))
    assert np.all(positive.doppler_hz > 0)
    assert np.all(reverse.doppler_hz < 0)


@pytest.mark.parametrize(
    "profile", [FlowProfile.PULSATILE, FlowProfile.ACCELERATED, FlowProfile.IRREGULAR]
)
def test_time_varying_profiles_honor_programmed_direction(profile):
    signal = generate_signal(DopplerConfig(profile=profile, velocity_m_s=-0.1))
    assert np.all(signal.velocity_m_s < 0)


def test_snr_definition_statistically():
    config = DopplerConfig(frame_count=128, snr_db=20, clutter_ratio=0)
    signal = generate_signal(config)
    measured = 10 * np.log10(np.mean(abs(signal.clean_iq) ** 2) / np.mean(abs(signal.noise) ** 2))
    assert measured == pytest.approx(20, abs=0.2)


@pytest.mark.parametrize("signed_bin", [2, 3, 16, 64, 127, -2, -3, -16, -64, -127])
def test_float_and_fixed_recover_bin_centered_tones(signed_bin):
    config = DopplerConfig(
        velocity_m_s=signed_bin * 0.01203125,
        profile=FlowProfile.STEADY if signed_bin > 0 else FlowProfile.REVERSE,
        snr_db=None,
        clutter_ratio=0,
        initial_phase_rad=0.37,
    )
    signal = generate_signal(config)
    frame = signal.iq[256:512]
    float_result = process_float_frame(frame, config)
    fixed_result = process_fixed_frame(frame, config)
    assert float_result.peak_bin == signed_bin
    assert fixed_result.peak_bin == signed_bin
    assert fixed_result.frequency_q8_hz == signed_bin * 20_000
    assert fixed_result.velocity_q8_mm_s == signed_bin * 3080


def test_fixed_arithmetic_edges():
    assert saturate(200_000, 18) == 131071
    assert saturate(-200_000, 18) == -131072
    assert round_shift(3, 1) == 2
    assert round_shift(-3, 1) == -2
    assert quantize_q15([1, -1, 0.5, -0.5]).tolist() == [32767, -32768, 16384, -16384]
    coeff = hann_q15()
    assert coeff[0] == coeff[-1] == 0
    assert coeff.max() <= 32767


@pytest.mark.parametrize("level", [32767 / 32768, -1.0])
def test_window_full_scale_constant_stays_in_signed_16_bits(level):
    config = DopplerConfig(snr_db=None, clutter_ratio=0)
    samples = np.full(256, level, dtype=np.complex128)
    result = process_fixed_frame(samples, config)
    assert np.all(result.window_i >= -32768)
    assert np.all(result.window_i <= 32767)


def test_window_alternating_full_scale_saturates_to_signed_16_bits():
    config = DopplerConfig(snr_db=None, clutter_ratio=0)
    levels = np.where(np.arange(256) % 2, 32767 / 32768, -1.0)
    result = process_fixed_frame(levels.astype(np.complex128), config)
    assert result.window_i.min() == -32768
    assert result.window_i.max() == 32767


@pytest.mark.parametrize(
    ("value", "shift", "expected"),
    [(1, 1, 1), (-1, 1, -1), (3, 1, 2), (-3, 1, -2), (5, 1, 3), (-5, 1, -3)],
)
def test_round_shift_exact_half_away_from_zero(value, shift, expected):
    assert round_shift(value, shift) == expected


def test_signed_mapping_and_tie_rule():
    assert raw_to_signed_bin(255) == -1
    assert raw_to_signed_bin(128) == -128
    power = np.zeros(256, dtype=np.int64)
    power[2] = power[254] = 10
    assert select_peak(power) == (254, -2)


def test_confidence_rule_and_zero_spectrum():
    power = np.zeros(256, dtype=np.int64)
    assert peak_metrics(power)[-1]
    power[2], power[3] = 30, 10
    assert not peak_metrics(power)[-1]
    power[3] = 11
    assert peak_metrics(power)[-1]


def test_frame_labels_are_explicit():
    config = DopplerConfig()
    stable = np.full(256, 1000.0)
    assert classify_frame(0, stable, config, False).warmup
    assert classify_frame(1, stable, config, False).scored
    transition = np.linspace(0.0, 2 * config.bin_hz, 256)
    assert classify_frame(1, transition, config, False).transition
    aliased = np.full(256, config.sample_rate_hz / 2)
    assert classify_frame(1, aliased, config, False).alias


def test_config_json_roundtrip(tmp_path):
    config = DopplerConfig(profile=FlowProfile.IRREGULAR, seed=99)
    path = tmp_path / "config.json"
    config.to_json(path)
    assert json.loads(path.read_text())["seed"] == 99
    assert DopplerConfig.from_json(path) == config
