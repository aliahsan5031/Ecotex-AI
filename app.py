"""EcoTex AI - Gradio app.

Run locally:   python app.py
Hugging Face:  this file is the Space entry point (app_file: app.py).
"""

from __future__ import annotations

import logging

import gradio as gr

try:  # optional: load GROQ_API_KEY etc. from a local .env file
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from ecotex import get_dataset, recommend
from ecotex.charts import score_breakdown_figure
from ecotex.render import (
    DISCLAIMER,
    best_score_label,
    empty_table,
    options_markdown,
    options_table,
    status_markdown,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ecotex.app")

EXAMPLES = [
    ["Eco-friendly dye for red cotton"],
    ["Navy polyester, dark shade, continuous method"],
    ["Salt-free dye for black linen"],
    ["Cotton polyester blend, black, low temperature"],
    ["Best EPA compliant dye for yellow viscose"],
]

INTRO = (
    "Describe the fabric you want to dye. EcoTex AI ranks the dye recipes in its dataset by "
    "**Eco Score** and shows the top 3 options, what makes up their scores, and a process outline. "
    "You can mention the **fiber** (cotton, polyester, viscose, linen, blend), the **color**, "
    "the **shade** (light, medium, dark), the **method** (batch, continuous, semi-continuous) "
    "or preferences such as *salt-free*, *low temperature* or *EPA compliant*."
)

THEME = gr.themes.Soft(primary_hue="green", secondary_hue="emerald")


def run(query: str):
    """Gradio handler. Returns: status, best score, table, chart, details."""
    try:
        rec = recommend(query)
        status = status_markdown(rec)
        if not rec.ok:
            return status, "", empty_table(), None, ""
        return (
            status,
            best_score_label(rec),
            options_table(rec),
            score_breakdown_figure(rec.options),
            options_markdown(rec),
        )
    except Exception:  # never show a stack trace to users
        logger.exception("Request failed for query %r", query)
        return (
            "❌ Something went wrong while building your recommendation. Please try again.",
            "",
            empty_table(),
            None,
            "",
        )


def build_demo() -> gr.Blocks:
    data = get_dataset()
    dataset_line = (
        f"Dataset: {len(data)} recipes · {data['Fiber'].nunique()} fibers · "
        f"{data['DyeType'].nunique()} dye classes · {data['Color'].nunique()} colors"
    )

    with gr.Blocks(title="EcoTex AI - Eco-friendly dye recipe advisor") as demo:
        gr.Markdown("# 🌿 EcoTex AI\n*AI-powered eco-friendly dye recipe advisor for textiles*")
        gr.Markdown(INTRO)

        with gr.Row():
            query = gr.Textbox(
                label="What do you want to dye?",
                placeholder="e.g. Eco-friendly dye for red cotton",
                lines=1,
                scale=4,
                autofocus=True,
            )
            with gr.Column(scale=1, min_width=160):
                submit = gr.Button("Generate", variant="primary")
                clear = gr.Button("Clear")

        gr.Examples(examples=EXAMPLES, inputs=query, label="Try an example", cache_examples=False)

        status = gr.Markdown()

        with gr.Row():
            best_score = gr.Label(label="Best eco score", scale=1)
            table = gr.Dataframe(
                label="Top options",
                value=empty_table(),
                interactive=False,
                wrap=True,
                scale=3,
            )

        chart = gr.Plot(label="Eco score breakdown")
        details = gr.Markdown()

        gr.Markdown(f"<small>{dataset_line}. {DISCLAIMER}</small>")

        outputs = [status, best_score, table, chart, details]
        submit.click(run, inputs=query, outputs=outputs, api_name="recommend")
        query.submit(run, inputs=query, outputs=outputs, api_visibility="private")
        clear.click(
            lambda: ("", "", "", empty_table(), None, ""),
            inputs=None,
            outputs=[query, *outputs],
            api_visibility="private",
        )

    demo.queue(default_concurrency_limit=4)
    return demo


demo = build_demo()

if __name__ == "__main__":
    demo.launch(theme=THEME)
