# Dev Color Hackathon Assessment 2026

**Trending TikTok Creator Opportunity Brief**

Which creators and which content look most promising in a batch of 1,000 trending TikTok videos from 802 creators, and a plain English way to ask follow up questions about them.

The data covers 22 Sep 2020 to 21 Dec 2020. There are no follower counts in it, so reach is views and nothing else.

## What it does

Two screens, selected from the sidebar.

**Where to focus.** One screen, no scrolling. A shortlist of 45 creators who clear three bars, split into those with a three video record and those resting on two. Beside it, what to brief them to make: video length and sound, the two content signals that separate high engagement trending posts from the rest.

**Ask a question.** Type a question in plain English and get an answer drawn from the same prepared tables behind the first screen. Every answer arrives with the table it came from and a panel naming the function that produced it. Questions the data cannot answer are declined with a reason rather than guessed at.

## Running it

```
uv venv --python 3.12 .venv
uv pip install streamlit anthropic
.venv/bin/streamlit run app.py
```

Then `python checks.py` and `python golden.py` before any demo. The first asserts the dataset invariants, the second runs ten hand checked questions through both answer paths.

## Using the language model

The Q&A screen works with no API key. It routes by keyword and answers from templates, so a fresh clone is a working demo with nothing to configure.

To answer through Claude instead, create a file named `.env` in the project root:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

That is the whole setup. Notes on it:

* `.env` is gitignored and never leaves the machine. The key is not printed, logged or shown in the app.
* `llm.py` reads the file at import with the standard library, so there is no `python-dotenv` dependency. A real exported environment variable takes priority over the file.
* The model is `claude-opus-5`. Set `ANTHROPIC_MODEL` in the same file to change it.
* Restart Streamlit after creating the file.

Both paths call the same five functions and show the same figures. Only the routing and the wording differ. Answers take roughly five to eight seconds through the model, because each question makes two calls: one to choose the function, one to write the sentence.

If the key is missing, malformed or a call fails, the screen falls back to the keyword path and a banner says which path answered.

## The tech behind it

**Python 3.12 and the standard library** for everything that produces a number. `csv`, `statistics`, `difflib` and `re`. pandas arrives as a Streamlit dependency but is never imported, so the whole correctness path runs in about a second with any interpreter on the machine and is immune to dataframe API drift.

**Streamlit** for the two screens, with one Altair bar chart for the single figure that earns a chart.

**The Anthropic Messages API** for routing and narration, through tool use. The model is handed five typed function schemas and must call one of them. Declining is one of the five, so refusal is a routing outcome rather than a keyword filter sitting in front of the model.

**Plain assertions as the test suite.** `checks.py` is a list of asserts and an exit code, no pytest. `golden.py` pins ten questions to the tool each should reach, the sample size it should report, and a hand checked fact that must appear.

**Generated documentation.** This file, the script and the data flow sketch are written by `write_docs.py` from the computed tables. `checks.py` fails if any of the three drifts from the data, so a number cannot go stale in prose.

## Files

* `prep.py` loads the export and derives the per video rates and scores
* `metrics.py` aggregates everything into five tables
* `tools.py` exposes five typed functions over those tables
* `llm.py` routes a question to one tool and narrates the result
* `checks.py` asserts the invariants and verifies figures in answers
* `golden.py` runs ten hand checked questions through both answer paths
* `app.py` renders the two screens
* `write_docs.py` regenerates the three documents

## Further reading

* `docs/script.md` covers what "promising" means here, why the metric is built this way, what the content findings are, and what this cannot tell you.
* `docs/dataflow.md` covers how a question becomes an answer.
