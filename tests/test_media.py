import numpy as np
import pytest

from decision_lab.media import CHANNELS, MediaFit, adstock, build_media, fit_media, generate_weekly, hill, optimize_budget, steady_state_revenue
from decision_lab.metrics import regression_metrics


def test_seed_reproducibility_and_week_boundary():
    first = generate_weekly()
    assert first.equals(generate_weekly())
    assert not first.equals(generate_weekly(99))
    assert len(first) == 156
    data = build_media()
    assert data["synthetic"] is True
    assert data["currency"] == "GBP"
    assert [r["split"] for r in data["weekly"]] == ["train"] * 130 + ["test"] * 26
    assert data["metrics"]["model_mae"] > 0
    assert data["metrics"]["model_mae"] < data["metrics"]["baseline_mae"]


def test_adstock_hill_and_causal_prefix():
    np.testing.assert_allclose(adstock([10, 0, 0], 0.5), [10, 5, 2.5])
    np.testing.assert_allclose(hill([0, 10, 30], 10), [0, 0.5, 0.75])
    np.testing.assert_array_equal(adstock([10, 0, 0, 90000], 0.5)[:3], adstock([10, 0, 0], 0.5))


@pytest.mark.parametrize("decay", [-0.1, 1, np.inf, np.nan])
def test_invalid_adstock_decay(decay):
    with pytest.raises(ValueError):
        adstock([1, 2], decay)


@pytest.mark.parametrize("spend,half", [([-1], 1), ([np.nan], 1), ([1], 0), ([1], -1)])
def test_invalid_hill(spend, half):
    with pytest.raises(ValueError):
        hill(spend, half)


def test_media_fit_and_predictions_have_no_lookahead():
    frame = generate_weekly()
    fit = fit_media(frame)
    altered = frame.copy()
    altered.loc[130:, "revenue"] = 1e12
    altered.loc[140:, list(CHANNELS)] = 1e9
    changed = fit_media(altered)
    np.testing.assert_array_equal(fit.coefficients, changed.coefficients)
    np.testing.assert_array_equal(fit.predict(frame[list(CHANNELS)])[:140], changed.predict(altered[list(CHANNELS)])[:140])
    assert (fit.coefficients[-3:] >= 0).all()


def test_media_rejects_bad_order_and_missing_fields():
    frame = generate_weekly()
    with pytest.raises(ValueError, match="chronological"):
        fit_media(frame.iloc[::-1])
    with pytest.raises(ValueError, match="Missing synthetic"):
        fit_media(frame.drop(columns="video"))
    with pytest.raises(ValueError):
        fit_media(frame, decay=[1, 0.3, 0.5])


def test_steady_state_and_budget_grid_match_frontend_formula():
    data = build_media()
    fit = fit_media(generate_weekly())
    assert steady_state_revenue([0, 0, 0], fit) == 0
    assert len(data["plans"]) == 19
    for plan in data["plans"]:
        assert abs(sum(plan["shares"].values()) - 1) < 1e-8
        assert all(0.1 - 1e-8 <= v <= 0.6 + 1e-8 for v in plan["shares"].values())
        browser = equal = 0
        for channel in data["channels"]:
            assert channel["steady_state_multiplier"] == 1 / (1 - channel["decay"])
            x = plan["budget"] * plan["shares"][channel["id"]] * channel["steady_state_multiplier"]
            browser += channel["coefficient"] * (x / (channel["half_saturation"] + x))
            x_equal = plan["budget"] / 3 * channel["steady_state_multiplier"]
            equal += channel["coefficient"] * (x_equal / (channel["half_saturation"] + x_equal))
        assert plan["incremental_revenue"] == pytest.approx(browser, abs=1e-8)
        assert plan["balanced_revenue"] == pytest.approx(equal, abs=1e-8)
        assert browser >= equal - 1e-6


def test_optimizer_hits_bounds_when_only_one_channel_responds():
    fit = MediaFit(np.r_[np.zeros(6), 20000, 0, 0], np.array([0.3, 0.4, 0.5]), np.full(3, 10000), 130)
    assert optimize_budget(10000, fit)["shares"]["search"] == pytest.approx(0.6)
    assert all(0.1 - 1e-8 <= v <= 0.6 + 1e-8 for v in optimize_budget(10000, fit)["shares"].values())


@pytest.mark.parametrize("budget,minimum,maximum", [(0, 0.1, 0.6), (-1, 0.1, 0.6), (np.nan, 0.1, 0.6), (10000, 0.4, 0.6), (10000, 0.1, 0.2)])
def test_infeasible_budgets_fail(budget, minimum, maximum):
    with pytest.raises(ValueError):
        optimize_budget(budget, fit_media(generate_weekly()), minimum, maximum)


def test_metrics_are_ratios_and_zero_denominator_is_unknown():
    assert regression_metrics([100, 100], [90, 110]) == {"mae": 10.0, "rmse": 10.0, "wape": 0.1}
    assert regression_metrics([0], [1])["wape"] is None
    with pytest.raises(ValueError):
        regression_metrics([1], [np.nan])
