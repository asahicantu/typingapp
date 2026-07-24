from typingapp.engine.charts import horizontal_bar, ranked_bars


def test_horizontal_bar_full_ratio():
    result = horizontal_bar("Accuracy", 100, 100, width=10, value_fmt="{:.0f}%")
    assert "██████████" in result
    assert "100%" in result


def test_horizontal_bar_zero_value():
    result = horizontal_bar("Errors", 0, 10, width=10)
    assert "░" * 10 in result


def test_horizontal_bar_clamps_over_max():
    result = horizontal_bar("Time", 999, 60, width=10, value_fmt="{:.0f}")
    assert "█" * 10 in result


def test_horizontal_bar_callable_fmt():
    result = horizontal_bar("Time", 65, 100, width=5, value_fmt=lambda v: f"{int(v)}s")
    assert "65s" in result


def test_ranked_bars_empty():
    assert ranked_bars([]) == "(no data)"


def test_ranked_bars_orders_by_count_desc():
    result = ranked_bars([("th", 5), ("er", 2)])
    lines = result.splitlines()
    assert "th" in lines[0]
    assert "er" in lines[1]
