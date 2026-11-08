"""Reference models for the FPGA spectral Doppler engine."""

from .classification import FrameLabels, classify_frame
from .config import DopplerConfig, FlowProfile
from .fixed import FixedFrameResult, process_fixed_frame
from .floating import FloatFrameResult, process_float_frame
from .generator import SyntheticSignal, generate_signal
from .protocol import ResultPacket, crc16_ccitt

__all__ = [
    "DopplerConfig",
    "FixedFrameResult",
    "FloatFrameResult",
    "FlowProfile",
    "FrameLabels",
    "ResultPacket",
    "SyntheticSignal",
    "classify_frame",
    "crc16_ccitt",
    "generate_signal",
    "process_fixed_frame",
    "process_float_frame",
]
