"""Real-signal comparison uses synthetic arrays only; never implies real data were checked."""
import numpy as np
import pytest

from scripts.qa_bearing_recording_duplicates import identical_raw_signals, SourceQualityError


def test_identical_vibration_and_current_is_duplicate():
    source = [np.arange(80.), np.arange(80.) * 0.25]
    other = [source[0].copy(), source[1].copy()]
    assert identical_raw_signals(source, other)


def test_one_channel_different_is_not_duplicate():
    source = [np.arange(80.), np.arange(80.)]
    other = [source[0].copy(), source[1].copy()]
    other[1][0] = 999.
    assert not identical_raw_signals(source, other)


def test_shape_difference_is_not_duplicate():
    assert not identical_raw_signals([np.arange(80.), np.arange(80.)], [np.arange(81.), np.arange(80.)])


def test_missing_channel_blocks_duplicate_test():
    with pytest.raises(SourceQualityError, match='two_matched_channels'):
        identical_raw_signals([np.arange(20.)], [np.arange(20.), np.arange(20.)])
