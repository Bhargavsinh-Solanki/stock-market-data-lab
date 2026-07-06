"""Walk-forward split integrity: chronology, embargo, no overlap."""
import numpy as np
import pandas as pd

from src.models.walk_forward import walk_forward_splits


def _dates(n: int = 400) -> pd.Series:
    return pd.Series(pd.bdate_range("2024-01-02", periods=n))


def test_train_strictly_before_test():
    for fold in walk_forward_splits(_dates(), min_train=252, test_size=21, embargo=5):
        assert fold.train_dates.max() < fold.test_dates.min()


def test_embargo_gap_enforced():
    dates = np.sort(pd.unique(_dates()))
    for fold in walk_forward_splits(dates, min_train=252, test_size=21, embargo=5):
        gap_start = np.searchsorted(dates, fold.train_dates.max()) + 1
        gap_end = np.searchsorted(dates, fold.test_dates.min())
        assert gap_end - gap_start >= 4  # ~5 trading days purged


def test_no_test_window_overlap_with_step_equal_test_size():
    seen: set = set()
    for fold in walk_forward_splits(_dates(), min_train=252, test_size=21, step=21, embargo=5):
        current = set(pd.to_datetime(fold.test_dates))
        assert not (seen & current)
        seen |= current


def test_folds_advance_chronologically():
    starts = [fold.test_dates.min() for fold in
              walk_forward_splits(_dates(), min_train=252, test_size=21, embargo=5)]
    assert all(a < b for a, b in zip(starts, starts[1:]))


def test_shuffled_input_dates_are_sorted_internally():
    shuffled = _dates().sample(frac=1.0, random_state=0)
    folds = list(walk_forward_splits(shuffled, min_train=252, test_size=21, embargo=5))
    assert folds and all(f.train_dates.max() < f.test_dates.min() for f in folds)
