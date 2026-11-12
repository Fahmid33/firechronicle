"""Basic sanity test to verify that the environment and core packages are ready."""

import pytest


def test_imports():
    """Verify core data science dependencies can be imported."""
    import numpy as np
    import pandas as pd
    import scipy
    import statsmodels
    import sklearn
    import pyarrow
    import joblib

    assert np.__version__ is not None
    assert pd.__version__ is not None
