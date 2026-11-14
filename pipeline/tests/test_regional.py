import numpy as np
import pytest

from firecal.regional import Candidate, fit_ratios


def test_baseline_shrinkage_and_sparse_fallback():
    observed = np.array([[100, 2], [50, 1]])
    viirs = np.array([[300, 10], [200, 5]])
    k = fit_ratios(observed, viirs, np.array(["a", "a"]), Candidate())
    prior = 153 / 515
    assert k[0] == pytest.approx((150 + 100 * prior) / 600)
    assert k[1] == pytest.approx(prior)


def test_balancing_preserves_training_totals_in_each_supported_region():
    m = np.array([[100, 1, 50, 0], [50, 2, 25, 0]])
    v = np.array([[100, 100, 100, 100], [50, 100, 200, 0]])
    groups = np.array(["a", "a", "b", "b"])
    k = fit_ratios(m, v, groups, Candidate(balance=True), min_region=100)
    for group in ("a", "b"):
        mask = groups == group
        assert (v[:, mask] * k[mask]).sum() == pytest.approx(m[:, mask].sum())


def test_unseen_group_borrows_global_training_prior():
    m, v = np.array([[30, 0]]), np.array([[100, 0]])
    k = fit_ratios(m, v, np.array(["seen", "unseen"]), Candidate(balance=True))
    assert k[1] == pytest.approx(0.3)
    assert np.isfinite(k).all()


@pytest.mark.parametrize("bad", [np.nan, np.inf, -1])
def test_invalid_counts_are_rejected(bad):
    with pytest.raises(ValueError, match="finite and nonnegative"):
        fit_ratios(np.array([[bad]]), np.ones((1, 1)), np.array(["a"]), Candidate())


def test_no_training_viirs_is_rejected():
    with pytest.raises(ValueError, match="No training VIIRS"):
        fit_ratios(np.ones((1, 1)), np.zeros((1, 1)), np.array(["a"]), Candidate())
