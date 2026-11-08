import csv

from doppler.config import DopplerConfig
from doppler.export import export_case


def test_export_contract(tmp_path):
    summary = export_case(DopplerConfig(snr_db=None), tmp_path / "case")
    assert summary.scored_frames == 3
    assert summary.fixed_float_bin_mismatches == 0
    assert (summary.directory / "config.json").is_file()
    assert (summary.directory / "metadata.json").is_file()
    assert len((summary.directory / "input_iq_q15.mem").read_text().splitlines()) == 1024
    frame = summary.directory / "intermediate" / "frame_001"
    assert len((frame / "fft_i_s16.mem").read_text().splitlines()) == 256
    assert len((frame / "power_u37.mem").read_text().splitlines()) == 256
    with (summary.directory / "expected_frames.csv").open() as stream:
        rows = list(csv.DictReader(stream))
        assert len(rows) == 3
        assert {"low_confidence", "transition", "alias", "scored"} <= rows[0].keys()
