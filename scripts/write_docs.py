"""Generate README.md, docs/script.md and docs/dataflow.md from the computed tables.

Rule 2 of this build: regenerate from code, never type. That applies to the
documentation as much as to the screens, because a README is where a stale
number survives longest. Every figure below is an f-string over `tables`, and
`checks.py` asserts the files on disk match what this script produces.

Prose is written as one line per paragraph rather than hard wrapped. Wrapping
around an interpolated value splits a sentence at whatever column the number
happens to end on, which reads badly in the source and shifts every time the
data moves. Markdown renders both forms identically.

Run `python -m scripts.write_docs` from the project root after any change to
the data or the metrics.
"""

from core.paths import PROJECT_ROOT

from core import metrics
from core import prep

ROOT = PROJECT_ROOT

MONTHS = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
    "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
}


def pretty_date(iso_date):
    year, month, day = iso_date.split("-")
    return f"{int(day)} {MONTHS[month]} {year}"


def percent(fraction, places=1):
    return f"{fraction * 100:.{places}f}%"


def build_readme(tables):
    """The front door: what this is, how to run it, what it is built on.

    Deliberately short. The reasoning lives in docs/script.md so that someone
    who just wants to start the app is not reading an essay first.
    """
    facts = tables["dataset_facts"]
    funnel = tables["shortlist"]["funnel"]

    return f"""# Dev Color Hackathon Assessment 2026

**Trending TikTok Creator Opportunity Brief**

Which creators and which content look most promising in a batch of {facts['rows']:,} trending TikTok videos from {facts['creators']:,} creators, and a plain English way to ask follow up questions about them.

The data covers {pretty_date(facts['date_min'])} to {pretty_date(facts['date_max'])}. There are no follower counts in it, so reach is views and nothing else.

## What it does

Two screens, selected from the sidebar.

**Where to focus.** One screen, no scrolling. A shortlist of {funnel['qualifying']} creators who clear three bars, split into those with a three video record and those resting on two. Beside it, what to brief them to make: video length and sound, the two content signals that separate high engagement trending posts from the rest.

**Ask a question.** Type a question in plain English and get an answer drawn from the same prepared tables behind the first screen. Every answer arrives with the table it came from and a panel naming the function that produced it. Questions the data cannot answer are declined with a reason rather than guessed at.

## Running it

```
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

`requirements.txt` holds two pinned packages, both for the app layer. The metrics core in `core/` is standard library only, so the test suite runs under a bare interpreter.

Then run the test suite before any demo:

```
python -m tests
```

That is one command and an obvious exit code. It asserts the dataset invariants, the tool contract, the provenance guard, that the generated documents still match the data, and that all ten golden questions answer correctly offline. Add the live model path with `python -m tests.golden anthropic`, which needs a key.

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

**Plain assertions as the test suite.** `tests/` is a list of asserts and an exit code, no pytest. Each module owns one concern, and the golden set pins ten questions to the tool each should reach, the sample size it should report, and a hand checked fact that must appear.

**GitHub Actions** runs the whole suite on every push and pull request, including a headless boot of the app. No API key is needed, because the offline answer path is what CI exercises.

**Generated documentation.** This file, the script and the data flow sketch are written by `scripts/write_docs.py` from the computed tables. The suite fails if any of the three drifts from the data, so a number cannot go stale in prose.

## Layout

```
.
├── app.py                  Streamlit entry point, both screens
├── requirements.txt        two pinned packages, app layer only
├── core/                   everything that produces a number. No Streamlit, no pandas
│   ├── paths.py            project paths, resolved once
│   ├── prep.py             load the export, derive per video rates and scores
│   ├── metrics.py          aggregate into the five tables
│   ├── tools.py            five typed functions over those tables
│   ├── llm.py              route a question to one tool, narrate the result
│   └── provenance.py       check every figure in an answer against its source
├── tests/                  the suite. Run with python -m tests
│   ├── expectations.py     the numbers the code is held to
│   ├── runner.py           the check helper and the reporting
│   ├── source_data.py      the export: counts, dates, uniqueness
│   ├── percentiles.py      the ranking, recomputed value by value
│   ├── aggregates.py       scores, buckets, creators, the funnel
│   ├── tool_payloads.py    the envelope every tool must return
│   ├── provenance.py       the guard that catches an invented figure
│   ├── documentation.py    the generated docs still match the data
│   └── golden.py           ten questions end to end
├── scripts/
│   └── write_docs.py       regenerates the three documents
├── docs/
│   ├── script.md           the reasoning behind the brief
│   └── dataflow.md         how a question becomes an answer
├── data/                   the export
└── .github/workflows/      continuous integration
```

The dependency direction runs one way. `core` imports nothing above it, `tests` and `scripts` import `core`, and `app.py` imports `core` and nothing else in the project. `provenance.py` lives in `core` rather than in `tests` because it runs on every answer the app renders, so it is production code that the suite happens to test.

## Further reading

* `docs/script.md` covers what "promising" means here, why the metric is built this way, what the content findings are, and what this cannot tell you.
* `docs/dataflow.md` covers how a question becomes an answer.
"""


def build_script(tables):
    """The reasoning behind the numbers, for talking through the work.

    This is the content that used to sit in the README. It is separated
    because the two documents answer different questions: the README answers
    "how do I run this", and this one answers "why should I believe it".
    """
    facts = tables["dataset_facts"]
    shortlist = tables["shortlist"]
    funnel = shortlist["funnel"]
    gates = shortlist["gates"]
    duration = tables["duration_table"]
    verified, unverified = tables["segment_tables"]["verified"]
    original, licensed = tables["segment_tables"]["music_is_original"]
    longest = duration[-1]
    emerging = len(shortlist["emerging"])

    return f"""# Script: the reasoning behind the brief

The thinking behind the two screens. Every figure here is generated from the same tables the app reads, so this document and the screens cannot disagree.

## What "promising" means here

There is no follower count in this data, so reach is views and nothing else. Every row is already a trending video, which means views measure what the recommendation algorithm did rather than what a creator is worth. Views and engagement rate are essentially unrelated here, so a views leaderboard and an engagement leaderboard are two different lists.

The honest question is therefore not who is big, but who converts the attention they were given. A promising creator earns above median engagement across more than one trending video, at a reach level worth a conversation. Three bars:

1. **Posted at least {gates['min_videos']} videos in this batch.** {funnel['creators'] - funnel['with_2plus']:,} of the {funnel['creators']:,} creators appear exactly once. Appearing twice is the least luck driven fact available.
2. **Median views of at least {gates['min_median_views']:,}.** This is a business relevance filter, not a correction for anything. Engagement rate is flat across view quintiles, so small accounts are not inflating the ranking.
3. **Engagement above the batch middle.** A video's rank against all {facts['rows']:,} on likes, comments and shares per view, with the three ranks averaged.

That narrows {funnel['creators']:,} creators to {funnel['with_2plus']} with repeat appearances, then {funnel['clearing_reach_floor']} clearing the reach bar, then **{funnel['qualifying']} who clear all three**.

### Why the three ranks are averaged

Raw engagement in this batch is {percent(facts['likes_share_of_engagement'], 0)} likes. Adding the three rates together produces a like rate wearing a costume. Ranking each separately and averaging them is what makes the score respond to comments and shares at all. It changes the answer: creators who collect likes and nothing else drop out.

### Evidence tiers

The shortlist is split. **Proven** creators have three or more videos ({shortlist['proven_count']} of them). **Emerging** creators have exactly two ({emerging} of them). The split matters because the top of the raw ranking is dominated by two video creators, and two videos is real signal but thin evidence. Treat Emerging as a cheap test rather than a headline deal.

## What the content looks like

Longer videos engage harder, and views stay flat across the length buckets, so this is not a reach effect:

* {duration[0]['bucket']}: {percent(duration[0]['median_engagement_rate'])} median engagement, {duration[0]['n_videos']} videos
* {duration[1]['bucket']}: {percent(duration[1]['median_engagement_rate'])} median engagement, {duration[1]['n_videos']} videos
* {duration[2]['bucket']}: {percent(duration[2]['median_engagement_rate'])} median engagement, {duration[2]['n_videos']} videos
* {duration[3]['bucket']}: {percent(duration[3]['median_engagement_rate'])} median engagement, {duration[3]['n_videos']} videos

Only {longest['n_videos']} of {facts['rows']:,} videos run {longest['bucket']}, so the format is under supplied.

Videos on original sound engage better, at {percent(original['median_engagement_rate'])} against {percent(licensed['median_engagement_rate'])}, and {percent(original['share_of_videos'], 0)} of the batch already uses it. Trending sounds buy reach. Original sound buys engagement.

Verified accounts are worth stating plainly, because the finding cuts both ways. Verified videos take {verified['ratios']['median_views']['text']} the median views of unverified ones ({int(verified['median_views']):,} against {int(unverified['median_views']):,}), but they score {verified['ratios']['median_score']['text']} on the blended engagement metric, which is lower. Verified buys scale. Unverified buys engagement per view.

## How the answers are kept accurate and honest

**The model never calculates anything.** It chooses which prepared question to run and explains the result. Every number comes from a Python function.

**Every figure is checked before you see it.** After the model writes an answer, each number in it is matched against the data it was given. If a figure cannot be traced, the sentence is withheld and the table is shown instead. This is not a precaution on paper: during testing the model invented three figures on four of five runs, with values close enough to the real ones to read as correct. An instruction not to invent numbers did not prevent invention.

**Sample size travels with every claim.** "9 creators" and "9 of {funnel['qualifying']}" read very differently, so the sample the rows came from is attached to every result and shown in the panel under each answer.

**Questions the data cannot answer are refused, with a reason.** There are no follower counts, no audience demographics, no fees, no data after {pretty_date(facts['date_max'])}, and no content topic labels. Refusal is one of the options the model can pick, so it declines rather than guesses.

## What this cannot tell you

* **Every row already trended.** This describes who engages best among winners. It says nothing about creators who did not make the export, and it cannot estimate the odds that any of these creators trend again.
* **Two videos is thin.** Most of the shortlist qualifies on exactly two videos. {shortlist['proven_count']} creators have three or more if you want a stricter cut.
* **No follower counts.** Engagement rate cannot be separated from audience size. A creator with 100,000 followers and one with a million, at the same engagement rate, are not equivalent signings.
* **The data is from {facts['date_max'][:4]}.** Formats, sounds and the algorithm have all moved on.
* **No cost, availability or brand safety data.** This narrows the field to {funnel['qualifying']} creators worth researching. It does not decide anything, and the handles need a human read before they go in front of a client.

See `docs/dataflow.md` for how a question becomes an answer.
"""


def build_dataflow(tables):
    facts = tables["dataset_facts"]
    return f"""# How a question becomes an answer

```mermaid
flowchart TD
    Q(["a question in plain English"]) --> ROUTE
    ROUTE["<b>1. ROUTE</b><br/>pick one of five functions"] --> COMPUTE
    COMPUTE["<b>2. COMPUTE</b><br/>run it over the prepared tables"] --> NARRATE
    NARRATE["<b>3. NARRATE</b><br/>write plain English about the result"] --> VERIFY
    VERIFY{{"<b>4. VERIFY</b><br/>is every number traceable?"}}
    VERIFY -->|yes| RENDER["<b>5. RENDER</b><br/>answer, source table, audit panel"]
    VERIFY -->|no| WITHHELD["<b>5. RENDER</b><br/>answer withheld, table shown alone"]

    classDef model fill:#dbeafe,stroke:#2a78d6,color:#10243d;
    classDef python fill:#e4efdf,stroke:#4b7c3f,color:#16240f;
    classDef plain fill:#f2f2f4,stroke:#8d8d96,color:#1f1f23;
    class ROUTE,NARRATE model;
    class COMPUTE,VERIFY python;
    class Q,RENDER,WITHHELD plain;
```

Blue is the language model. Green is pure Python.

1. **Route.** Picks one of five prepared questions, or picks the option that says this data cannot answer that. Choosing is all it does here. It sees no rows and does no arithmetic.
2. **Compute.** The chosen function reads the prepared tables and returns a result carrying its own sample size, the filters that produced it, and any warnings the code attaches.
3. **Narrate.** Writes plain English about the result it was handed. It is given the figures already formatted for reading, because it is not allowed to convert anything.
4. **Verify.** Every number in the sentence is matched against the result. Anything that cannot be traced means the sentence is withheld and the table is shown on its own.
5. **Render.** The answer, the table it came from, and a panel naming the function that ran, its arguments and the sample size.

Two things are worth noticing about the shape.

**The model appears twice and computes at neither point.** It picks a question at step 1 and explains an answer at step 3. Steps 2 and 4 are ordinary Python. A wrong choice at step 1 is visible and recoverable, since the panel names the function that ran. An invented number would be neither, which is why step 4 exists.

**Refusal is a routing outcome, not a filter.** The option to decline sits alongside the five real questions, so the model selects it the same way it selects anything else. A keyword filter in front of the model would have refused legitimate questions, which is a worse failure than it sounds: asking what content to make is answerable here, through video length and sound.

The same five functions serve both answer paths. With no API key, steps 1 and 3 are handled by keyword rules and templates instead, and steps 2, 4 and 5 are unchanged. The figures are identical either way.

Scope on every answer: {facts['rows']:,} trending videos from {facts['creators']:,} creators, {facts['date_min']} to {facts['date_max']}.
"""


DOCUMENTS = (
    ("README.md", build_readme),
    ("docs/script.md", build_script),
    ("docs/dataflow.md", build_dataflow),
)


def main():
    tables = metrics.build_tables(prep.load_rows())

    for relative_path, builder in DOCUMENTS:
        path = ROOT / relative_path
        path.parent.mkdir(exist_ok=True)
        path.write_text(builder(tables))
        print(f"wrote {relative_path} ({len(path.read_text().splitlines())} lines)")


if __name__ == "__main__":
    main()
