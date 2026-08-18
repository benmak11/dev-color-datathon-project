"""Generate README.md and docs/dataflow.md from the computed tables.

Rule 2 of this build: regenerate from code, never type. That applies to the
documentation as much as to the screens, because a README is where a stale
number survives longest. Every figure below is an f-string over `tables`, and
`checks.py` asserts the files on disk match what this script produces.

Run `python write_docs.py` after any change to the data or the metrics.
"""

from pathlib import Path

import metrics
import prep

ROOT = Path(__file__).parent

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
    facts = tables["dataset_facts"]
    shortlist = tables["shortlist"]
    funnel = shortlist["funnel"]
    gates = shortlist["gates"]
    duration = tables["duration_table"]
    verified, unverified = tables["segment_tables"]["verified"]
    original, licensed = tables["segment_tables"]["music_is_original"]
    longest = duration[-1]
    emerging = len(shortlist["emerging"])

    return f"""# Trending TikTok: Creator Opportunity Brief

Which creators and which content look most promising in a batch of
{facts['rows']:,} trending TikTok videos, and a plain English way to ask
follow up questions about them.

Two screens:

1. **Where to focus.** One screen, no scrolling. Who to talk to and what to
   brief them to make.
2. **Ask a question.** Type a question in plain English and get an answer drawn
   from the same prepared tables behind the first screen.

## Running it

```
uv venv --python 3.12 .venv
uv pip install streamlit anthropic
.venv/bin/streamlit run app.py
```

The Q&A screen works with no API key. It routes by keyword and answers from
templates. To use the language model instead, put `ANTHROPIC_API_KEY` in a
`.env` file at the project root. Both paths call the same functions and show
the same figures; only the wording and the routing differ. Answers take roughly
five to eight seconds through the model, because each question makes two calls.

## What "promising" means here

There is no follower count in this data, so reach is views and nothing else.
Every row is already a trending video, which means views measure what the
recommendation algorithm did rather than what a creator is worth. Views and
engagement rate are essentially unrelated here, so a views leaderboard and an
engagement leaderboard are two different lists.

The honest question is therefore not who is big, but who converts the attention
they were given. A promising creator earns above median engagement across more
than one trending video, at a reach level worth a conversation. Three bars:

1. **Posted at least {gates['min_videos']} videos in this batch.**
   {funnel['creators'] - funnel['with_2plus']:,} of the {funnel['creators']:,}
   creators appear exactly once. Appearing twice is the least luck driven fact
   available.
2. **Median views of at least {gates['min_median_views']:,}.** This is a
   business relevance filter, not a correction for anything. Engagement rate is
   flat across view quintiles, so small accounts are not inflating the ranking.
3. **Engagement above the batch middle.** A video's rank against all
   {facts['rows']:,} on likes, comments and shares per view, with the three
   ranks averaged.

That narrows {funnel['creators']:,} creators to {funnel['with_2plus']} with
repeat appearances, then {funnel['clearing_reach_floor']} clearing the reach
bar, then **{funnel['qualifying']} who clear all three**.

### Why the three ranks are averaged

Raw engagement in this batch is {percent(facts['likes_share_of_engagement'], 0)}
likes. Adding the three rates together produces a like rate wearing a costume.
Ranking each separately and averaging them is what makes the score respond to
comments and shares at all. It changes the answer: creators who collect likes
and nothing else drop out.

### Evidence tiers

The shortlist is split. **Proven** creators have three or more videos
({shortlist['proven_count']} of them). **Emerging** creators have exactly two
({emerging} of them). The split matters because the top of the raw ranking is
dominated by two video creators, and two videos is real signal but thin
evidence. Treat Emerging as a cheap test rather than a headline deal.

## What the content looks like

Longer videos engage harder, and views stay flat across the length buckets, so
this is not a reach effect:

* {duration[0]['bucket']}: {percent(duration[0]['median_engagement_rate'])} median engagement, {duration[0]['n_videos']} videos
* {duration[1]['bucket']}: {percent(duration[1]['median_engagement_rate'])} median engagement, {duration[1]['n_videos']} videos
* {duration[2]['bucket']}: {percent(duration[2]['median_engagement_rate'])} median engagement, {duration[2]['n_videos']} videos
* {duration[3]['bucket']}: {percent(duration[3]['median_engagement_rate'])} median engagement, {duration[3]['n_videos']} videos

Only {longest['n_videos']} of {facts['rows']:,} videos run
{longest['bucket']}, so the format is under supplied.

Videos on original sound engage better, at
{percent(original['median_engagement_rate'])} against
{percent(licensed['median_engagement_rate'])}, and
{percent(original['share_of_videos'], 0)} of the batch already uses it.
Trending sounds buy reach. Original sound buys engagement.

Verified accounts are worth stating plainly, because the finding cuts both
ways. Verified videos take {verified['ratios']['median_views']['text']} the
median views of unverified ones
({int(verified['median_views']):,} against {int(unverified['median_views']):,}),
but they score {verified['ratios']['median_score']['text']} on the blended
engagement metric, which is lower. Verified buys scale. Unverified buys
engagement per view.

## How the answers are kept accurate and honest

**The model never calculates anything.** It chooses which prepared question to
run and explains the result. Every number comes from a Python function.

**Every figure is checked before you see it.** After the model writes an
answer, each number in it is matched against the data it was given. If a figure
cannot be traced, the sentence is withheld and the table is shown instead. This
is not a precaution on paper: during testing the model invented three figures
on four of five runs, with values close enough to the real ones to read as
correct. An instruction not to invent numbers did not prevent invention.

**Sample size travels with every claim.** "9 creators" and "9 of
{funnel['qualifying']}" read very differently, so the sample the rows came from
is attached to every result and shown in the panel under each answer.

**Questions the data cannot answer are refused, with a reason.** There are no
follower counts, no audience demographics, no fees, no data after
{pretty_date(facts['date_max'])}, and no content topic labels. Refusal is one
of the options the model can pick, so it declines rather than guesses.

## What this cannot tell you

* **Every row already trended.** This describes who engages best among winners.
  It says nothing about creators who did not make the export, and it cannot
  estimate the odds that any of these creators trend again.
* **Two videos is thin.** Most of the shortlist qualifies on exactly two
  videos. {shortlist['proven_count']} creators have three or more if you want a
  stricter cut.
* **No follower counts.** Engagement rate cannot be separated from audience
  size. A creator with 100,000 followers and one with a million, at the same
  engagement rate, are not equivalent signings.
* **The data is from {facts['date_max'][:4]}.** Formats, sounds and the
  algorithm have all moved on.
* **No cost, availability or brand safety data.** This narrows the field to
  {funnel['qualifying']} creators worth researching. It does not decide
  anything, and the handles need a human read before they go in front of a
  client.

## Files

* `prep.py` loads the export and derives the per video rates and scores
* `metrics.py` aggregates everything into five tables
* `tools.py` exposes five typed functions over those tables
* `llm.py` routes a question to one tool and narrates the result
* `checks.py` asserts the invariants and verifies figures in answers
* `golden.py` runs ten hand checked questions through both answer paths
* `app.py` renders the two screens
* `write_docs.py` regenerates this file and the data flow sketch

Run `python checks.py` and `python golden.py` before any demo.

See `docs/dataflow.md` for how a question becomes an answer.
"""


def build_dataflow(tables):
    facts = tables["dataset_facts"]
    return f"""# How a question becomes an answer

```
  "which creators get the most engagement?"
       |
       v
  1. ROUTE                                   (language model)
       Picks one of five prepared questions, or picks the option
       that says this data cannot answer that. Choosing is all it
       does here. It sees no rows and does no arithmetic.
       |
       v
  2. COMPUTE                                 (pure Python)
       The chosen function reads the prepared tables and returns a
       result carrying its own sample size, the filters that
       produced it, and any warnings the code attaches.
       |
       v
  3. NARRATE                                 (language model)
       Writes plain English about the result it was handed. It is
       given the figures already formatted for reading, because it
       is not allowed to convert anything.
       |
       v
  4. VERIFY                                  (pure Python)
       Every number in the sentence is matched against the result.
       Anything that cannot be traced means the sentence is
       withheld and the table is shown on its own.
       |
       v
  5. RENDER
       The answer, the table it came from, and a panel naming the
       function that ran, its arguments and the sample size.
```

Two things are worth noticing about the shape.

**The model appears twice and computes at neither point.** It picks a question
at step 1 and explains an answer at step 3. Steps 2 and 4 are ordinary Python.
A wrong choice at step 1 is visible and recoverable, since the panel names the
function that ran. An invented number would be neither, which is why step 4
exists.

**Refusal is a routing outcome, not a filter.** The option to decline sits
alongside the five real questions, so the model selects it the same way it
selects anything else. A keyword filter in front of the model would have
refused legitimate questions, which is a worse failure than it sounds: asking
what content to make is answerable here, through video length and sound.

The same five functions serve both answer paths. With no API key, steps 1 and 3
are handled by keyword rules and templates instead, and steps 2, 4 and 5 are
unchanged. The figures are identical either way.

Scope on every answer: {facts['rows']:,} trending videos from
{facts['creators']:,} creators, {facts['date_min']} to {facts['date_max']}.
"""


def main():
    tables = metrics.build_tables(prep.load_rows())

    readme = ROOT / "README.md"
    dataflow = ROOT / "docs" / "dataflow.md"
    dataflow.parent.mkdir(exist_ok=True)

    readme.write_text(build_readme(tables))
    dataflow.write_text(build_dataflow(tables))

    print(f"wrote {readme.name} ({len(readme.read_text().splitlines())} lines)")
    print(f"wrote docs/{dataflow.name} ({len(dataflow.read_text().splitlines())} lines)")


if __name__ == "__main__":
    main()
