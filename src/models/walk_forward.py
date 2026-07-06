"""Walk-forward validation with purging/embargo. Never random splits.

Timeline per fold (dates are unique sorted trading days):

    [------------- train -------------][ embargo ][ test ]

The embargo removes the last `embargo` trading days before the test window
from training, because 5-day forward labels computed there overlap the test
period (label leakage otherwise).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Fold:
    fold_id: int
    train_dates: np.ndarray
    test_dates: np.ndarray


def walk_forward_splits(
    dates: np.ndarray | pd.Series,
    min_train: int = 252,
    test_size: int = 21,
    step: int = 21,
    embargo: int = 5,
) -> Iterator[Fold]:
    dates = np.sort(pd.unique(pd.Series(dates)))
    n = len(dates)
    fold_id = 0
    cursor = min_train
    while cursor + test_size <= n:
        train = dates[: cursor - embargo]
        test = dates[cursor : cursor + test_size]
        if len(train) > 0:
            yield Fold(fold_id, train, test)
            fold_id += 1
        cursor += step


def split_frame(df: pd.DataFrame, fold: Fold) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"].isin(fold.train_dates)]
    test = df[df["date"].isin(fold.test_dates)]
    return train, test
