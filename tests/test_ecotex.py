import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.pop("GROQ_API_KEY", None)  # tests must never call the network

from ecotex import SCORE_PARTS, get_dataset, parse_query, recommend  # noqa: E402
from ecotex import process  # noqa: E402
from ecotex.charts import score_breakdown_figure  # noqa: E402
from ecotex.render import options_markdown, options_table, status_markdown  # noqa: E402


@pytest.fixture(scope="module")
def df():
    return get_dataset()


# ---------------------------------------------------------------- dataset
def test_dataset_shape(df):
    assert len(df) == 120
    assert set(df["Fiber"]) == {"Cotton", "Polyester", "Viscose", "Linen", "Blended"}


def test_eco_score_is_sum_of_parts(df):
    parts = [c for c, _label, _max in SCORE_PARTS]
    diff = (df[parts].sum(axis=1) - df["Eco Score"]).abs()
    assert (diff < 0.2).all()


# ---------------------------------------------------------------- parser
def test_parses_fiber_and_color():
    p = parse_query("eco friendly dye for red cotton")
    assert p.fibers == ["Cotton"] and p.colors == ["Red"] and p.on_topic


@pytest.mark.parametrize("text", ["what is the weather today", "I required a carpet", "tell me a joke", "red"])
def test_off_topic_is_rejected(text):
    assert not parse_query(text).on_topic


def test_word_boundaries():
    p = parse_query("fabric dye as required for the carpet")
    assert p.colors == [] and p.fibers == []


def test_blend_detection():
    assert parse_query("cotton polyester blend").fibers == ["Blended"]
    assert parse_query("poly-cotton black").fibers == ["Blended"]
    assert parse_query("polyester navy").fibers == ["Polyester"]


def test_unsupported_fibers_and_colors():
    p = parse_query("purple wool dye")
    assert p.unsupported_fibers == ["Wool"] and p.unsupported_colors == ["Purple"]


def test_navy_blue_is_one_color():
    assert parse_query("navy blue cotton").colors == ["Navy"]


def test_shade_method_and_preferences():
    p = parse_query("dark cotton semi-continuous salt free low temperature epa compliant")
    assert p.shade == "Dark" and p.method == "Semi-continuous"
    assert p.salt_free and p.low_temp and p.epa_only
    assert parse_query("continuous polyester dye").method == "Continuous"


# ---------------------------------------------------------------- engine
def test_basic_recommendation_sorted_by_eco_score():
    rec = recommend("eco-friendly dye for red cotton")
    assert rec.ok and len(rec.options) == 3
    scores = [o["Eco Score"] for o in rec.options]
    assert scores == sorted(scores, reverse=True)
    assert rec.options[0]["DyeType"] == "Vat" and rec.options[0]["Eco Score"] == 86.2
    assert all(o["Fiber"] == "Cotton" and o["Color"] == "Red" for o in rec.options)


def test_off_topic_message():
    rec = recommend("write me a poem about the sea")
    assert rec.status == "off_topic" and "EcoTex AI" in rec.message


def test_empty_query():
    assert recommend("   ").status == "empty"


def test_unsupported_fiber_does_not_return_wrong_fabric():
    rec = recommend("best dye for wool")
    assert rec.status == "no_data" and "Wool" in rec.message and not rec.options


def test_unsupported_color_does_not_return_other_colors():
    rec = recommend("purple cotton dye")
    assert rec.status == "no_data" and "Purple" in rec.message


def test_mixed_supported_and_unsupported_adds_note():
    rec = recommend("cotton or wool dye in red")
    assert rec.ok and any("Wool" in n for n in rec.notes)
    assert all(o["Fiber"] == "Cotton" for o in rec.options)


def test_impossible_combo_is_relaxed_with_a_note():
    rec = recommend("linen disperse dye")
    assert rec.ok and any("dye class" in n for n in rec.notes)
    assert all(o["Fiber"] == "Linen" for o in rec.options)


def test_salt_free_preference_is_applied():
    rec = recommend("salt-free dye for black linen")
    assert rec.ok and all(o["NaCl Required"] == 0 for o in rec.options)


def test_unsatisfiable_preference_is_ignored_with_a_note():
    rec = recommend("salt-free dye for blue viscose")  # no salt-free blue viscose exists
    assert rec.ok and any("salt-free" in n for n in rec.notes)


def test_low_temperature_filter():
    rec = recommend("cotton low temperature dye")
    assert rec.ok and all(o["Temperature"] <= 60 for o in rec.options)


def test_exact_filter_combination():
    rec = recommend("dark navy polyester continuous")
    assert rec.ok and rec.matches == 1
    top = rec.options[0]
    assert (top["DyeType"], top["ShadeLevel"], top["Dye Method"]) == ("Acid", "Dark", "Continuous")


def test_top_three_prefers_different_dye_classes():
    rec = recommend("cotton dye")
    assert len({o["DyeType"] for o in rec.options}) == 3


# ---------------------------------------------------------------- output
def test_process_steps_use_dataset_values():
    row = recommend("eco-friendly dye for red cotton").options[0]  # Vat, 50 C, 1:12, pH 11.3
    text = " ".join(process.process_steps(row))
    assert "50 °C" in text and "1:12" in text and "pH 11.3" in text
    assert "No salt" in text
    for invented in ("soda ash", "caustic", "minutes", "hours"):
        assert invented not in text.lower()


def test_builtin_explanation_mentions_score():
    row = recommend("eco-friendly dye for red cotton").options[0]
    text = process.builtin_explanation(row)
    assert "86.2/100" in text and "Strongest factor" in text


def test_model_failure_falls_back(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")

    def boom(_facts):
        raise RuntimeError("network down")

    monkeypatch.setattr(process, "_llm_call", boom)
    row = recommend("red cotton").options[0]
    text, by_model = process.explain(row)
    assert not by_model and "Eco Score" in text


def test_model_text_is_used_when_available(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setattr(process, "_llm_call", lambda _facts: "Model summary.")
    row = recommend("red cotton").options[0]
    assert process.explain(row) == ("Model summary.", True)


def test_chart_and_render():
    rec = recommend("black polyester")
    fig = score_breakdown_figure(rec.options)
    assert len(fig.axes) == 1
    table = options_table(rec)
    assert list(table["Rank"]) == [1, 2, 3]
    md = options_markdown(rec)
    assert md.count("### Option") == 3 and "Process outline" in md
    assert "Found" in status_markdown(rec)
