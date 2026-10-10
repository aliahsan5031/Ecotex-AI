---
title: EcoTex AI
emoji: 🌿
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 6.14.0
python_version: '3.13'
app_file: app.py
pinned: false
license: mit
short_description: AI Powered Eco Friendly Dye Recipe Advisor For Textiles
---

# 🌿 EcoTex AI

EcoTex AI is an eco-friendly dye recipe advisor for textiles. Describe the fabric you want to dye in plain
English and it returns the three best dye recipes from its dataset, ranked by **Eco Score**, together with a
chart that shows what makes up each score and a process outline for every option.

> **Live demo:** https://huggingface.co/spaces/AliAhsan5031/EcoTex_AI

## Example questions

- `Eco-friendly dye for red cotton`
- `Navy polyester, dark shade, continuous method`
- `Salt-free dye for black linen`
- `Cotton polyester blend, black, low temperature`
- `Best EPA compliant dye for yellow viscose`

## What it does

- **Understands your question.** It picks out the fiber, color, shade level (light / medium / dark), dyeing
  method (batch / continuous / semi-continuous), dye class and preferences such as *salt-free*, *low
  temperature* or *EPA compliant*. Words are matched as whole words, so "required" is not read as the color red.
- **Stays on topic.** Questions that have nothing to do with textile dyeing get a polite explanation instead of an error.
- **Is honest about gaps.** If you ask for a fiber or color that is not in the dataset (wool, silk, purple, ...),
  it says so and lists what is available, rather than quietly showing a different fabric. If no recipe fits
  every criterion, it tells you which criteria it relaxed.
- **Ranks by Eco Score.** The score is the sum of six parts (EPA compliance, dye tenacity, dye residues, salt use,
  temperature, dye class), and the chart shows each part so you can see why an option wins.
- **Builds the process outline from the data only.** Every number in the outline comes from the dataset; nothing is invented.
- **Optional AI summary.** With a [Groq](https://console.groq.com) API key, the "Why" sentence for each option is written
  by `llama-3.3-70b-versatile`. Without a key (or if the call fails) the app falls back to a built-in explanation, so it always works.

## Quick start

```bash
git clone https://github.com/<your-username>/ecotex-ai.git
cd ecotex-ai
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open the local URL that Gradio prints (usually http://127.0.0.1:7860).

### Optional: AI summaries

```bash
cp .env.example .env      # then put your key in GROQ_API_KEY=
```

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | _(empty)_ | Enables the AI-written summaries |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `ECOTEX_USE_LLM` | `1` | Set to `0` to turn the AI summary off even if a key is present |
| `ECOTEX_DATA` | `data/ecotex_dataset.csv` | Use a different dataset file |

On Hugging Face Spaces, add `GROQ_API_KEY` under **Settings → Variables and secrets** (as a secret).

## Project structure

```
ecotex-ai/
├── app.py                  # Gradio interface (entry point)
├── ecotex/
│   ├── data.py             # loads and validates the CSV
│   ├── query.py            # question -> fiber, color, shade, method, preferences
│   ├── engine.py           # filtering, relaxing, ranking, top-3 selection
│   ├── process.py          # process outline + (optional) Groq explanation
│   ├── charts.py           # Eco Score breakdown chart
│   └── render.py           # Markdown / table output for the UI
├── data/ecotex_dataset.csv # 120 dye recipes
├── tests/test_ecotex.py    # pytest suite
├── requirements.txt
└── .github/workflows/      # runs the tests on every push
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests never call the network.

## Deploying to Hugging Face Spaces

The block of settings at the top of this README is the Space configuration (GitHub shows it as a small table). To publish:

```bash
git remote add space https://huggingface.co/spaces/AliAhsan5031/EcoTex_AI
git push space main --force     # replaces the old files with this version
```

The old Chroma files (`chroma.sqlite3`, `data_level0.bin`, `header.bin`, `length.bin`, `link_lists.bin`) and
`readme.txt` are no longer needed. Pushing this version removes them.

## Data and limitations

- The dataset has **120 recipes**: 5 fibers (cotton, polyester, viscose, linen, blended) × 8 colors × 3 dye classes each.
  It contains no wool, silk, nylon or acrylic, and no purple, pink, grey or brown.
- It looks **illustrative rather than measured**, so treat the Eco Scores as a ranking aid, not as certified life-cycle data.
  Some pairings (for example acid dyes on polyester) are unusual in practice and should be checked by a textile specialist.
- The CSV does not state units. The app shows temperature in °C and leaves every other value as stored.
- The process outline lists dataset values only. Times, auxiliaries and after-treatments are not included.
  **Validate any recipe in a lab before production use.**

## License

[MIT](LICENSE)
