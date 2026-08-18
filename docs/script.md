# Script: the reasoning behind the brief

The thinking behind the two screens. Every figure here is generated from the same tables the app reads, so this document and the screens cannot disagree.

## What "promising" means here

There is no follower count in this data, so reach is views and nothing else. Every row is already a trending video, which means views measure what the recommendation algorithm did rather than what a creator is worth. Views and engagement rate are essentially unrelated here, so a views leaderboard and an engagement leaderboard are two different lists.

The honest question is therefore not who is big, but who converts the attention they were given. A promising creator earns above median engagement across more than one trending video, at a reach level worth a conversation. Three bars:

1. **Posted at least 2 videos in this batch.** 711 of the 802 creators appear exactly once. Appearing twice is the least luck driven fact available.
2. **Median views of at least 50,000.** This is a business relevance filter, not a correction for anything. Engagement rate is flat across view quintiles, so small accounts are not inflating the ranking.
3. **Engagement above the batch middle.** A video's rank against all 1,000 on likes, comments and shares per view, with the three ranks averaged.

That narrows 802 creators to 91 with repeat appearances, then 74 clearing the reach bar, then **45 who clear all three**.

### Why the three ranks are averaged

Raw engagement in this batch is 97% likes. Adding the three rates together produces a like rate wearing a costume. Ranking each separately and averaging them is what makes the score respond to comments and shares at all. It changes the answer: creators who collect likes and nothing else drop out.

### Evidence tiers

The shortlist is split. **Proven** creators have three or more videos (14 of them). **Emerging** creators have exactly two (31 of them). The split matters because the top of the raw ranking is dominated by two video creators, and two videos is real signal but thin evidence. Treat Emerging as a cheap test rather than a headline deal.

## What the content looks like

Longer videos engage harder, and views stay flat across the length buckets, so this is not a reach effect:

* 4-9s: 7.3% median engagement, 203 videos
* 10-19s: 8.7% median engagement, 517 videos
* 20-29s: 9.4% median engagement, 111 videos
* 30-60s: 10.9% median engagement, 169 videos

Only 169 of 1,000 videos run 30-60s, so the format is under supplied.

Videos on original sound engage better, at 9.1% against 8.0%, and 75% of the batch already uses it. Trending sounds buy reach. Original sound buys engagement.

Verified accounts are worth stating plainly, because the finding cuts both ways. Verified videos take 7.6x the median views of unverified ones (598,300 against 78,750), but they score 0.96x on the blended engagement metric, which is lower. Verified buys scale. Unverified buys engagement per view.

## How the answers are kept accurate and honest

**The model never calculates anything.** It chooses which prepared question to run and explains the result. Every number comes from a Python function.

**Every figure is checked before you see it.** After the model writes an answer, each number in it is matched against the data it was given. If a figure cannot be traced, the sentence is withheld and the table is shown instead. This is not a precaution on paper: during testing the model invented three figures on four of five runs, with values close enough to the real ones to read as correct. An instruction not to invent numbers did not prevent invention.

**Sample size travels with every claim.** "9 creators" and "9 of 45" read very differently, so the sample the rows came from is attached to every result and shown in the panel under each answer.

**Questions the data cannot answer are refused, with a reason.** There are no follower counts, no audience demographics, no fees, no data after 21 Dec 2020, and no content topic labels. Refusal is one of the options the model can pick, so it declines rather than guesses.

## What this cannot tell you

* **Every row already trended.** This describes who engages best among winners. It says nothing about creators who did not make the export, and it cannot estimate the odds that any of these creators trend again.
* **Two videos is thin.** Most of the shortlist qualifies on exactly two videos. 14 creators have three or more if you want a stricter cut.
* **No follower counts.** Engagement rate cannot be separated from audience size. A creator with 100,000 followers and one with a million, at the same engagement rate, are not equivalent signings.
* **The data is from 2020.** Formats, sounds and the algorithm have all moved on.
* **No cost, availability or brand safety data.** This narrows the field to 45 creators worth researching. It does not decide anything, and the handles need a human read before they go in front of a client.

See `docs/dataflow.md` for how a question becomes an answer.
