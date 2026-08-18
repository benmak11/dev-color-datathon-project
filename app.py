"""Streamlit app: the at-a-glance brief, plus the Q&A flow arriving next phase.

Screen 1 is the artifact she sees first. It must fit one screen without
scrolling. Every number rendered here is an f-string over `tables`. Nothing is
typed by hand, because the source architecture doc's hand-copied funnel was
wrong by two creators in both directions.
"""

import altair as alt
import pandas as pd
import streamlit as st

import checks
import llm
import metrics
import prep

SHORTLIST_ROWS_PER_TIER = 6
RECOMMENDED_BUCKET = "30-60s"

# One per tool, and the first four items of the golden set. The demo script and
# the regression test are the same list, so neither gets skipped.
QUESTION_CHIPS = [
    "Which creators get the most engagement?",
    "Does video length matter?",
    "Are verified creators worth more?",
    "Tell me about papaswolio",
]

SHORTLIST_ROW_HEIGHT = 30
SHORTLIST_TABLE_HEIGHT = SHORTLIST_ROW_HEIGHT * (SHORTLIST_ROWS_PER_TIER * 2 + 1) + 6

MONTH_ABBREVIATIONS = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
    "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
}

# Blue ramp, one hue. The recommended bucket takes the accent step and the rest
# take a recessive step. Both were validated against their surface. The
# recessive step sits below 3:1, which is why every bar carries a value label.
CHART_COLORS = {
    "light": {"accent": "#2a78d6", "context": "#86b6ef", "ink": "#52514e"},
    "dark": {"accent": "#3987e5", "context": "#184f95", "ink": "#c3c2b7"},
}

# Streamlit ships 96px of top padding, 160px of bottom padding, and a 16px gap
# between every element. On a one-screen brief that is 368px of nothing, which
# is more than a third of the viewport. These are the only style overrides.
COMPACT_LAYOUT_CSS = """
<style>
  /* 4rem clears Streamlit's fixed header. Anything less slides the headline
     underneath it. The saving comes from the 160px bottom padding. */
  [data-testid="stMainBlockContainer"] {
    padding-top: 4rem;
    padding-bottom: 0.5rem;
  }
  [data-testid="stVerticalBlock"] { gap: 0.6rem; }
  [data-testid="stCaptionContainer"] { line-height: 1.35; }
</style>
"""


@st.cache_data
def load_tables():
    return metrics.build_tables()


def is_dark_theme():
    """Read the theme the app renders in, not the viewer's OS setting.

    `st.context.theme` reports the browser preference. That disagrees with the
    pinned base in .streamlit/config.toml. Following it painted the light-mode
    page with the dark ramp, so the recommended bar came out paler than the
    bars it was supposed to stand out from.
    """
    return st.get_option("theme.base") == "dark"


def format_date(iso_date, include_year=False):
    year, month, day = iso_date.split("-")
    formatted = f"{int(day)} {MONTH_ABBREVIATIONS[month]}"
    return f"{formatted} {year}" if include_year else formatted


def format_date_span(facts):
    return (
        f"{format_date(facts['date_min'])} to "
        f"{format_date(facts['date_max'], include_year=True)}"
    )


def format_percent(fraction, decimals=0):
    return f"{fraction * 100:.{decimals}f}%"


def format_bucket_as_words(bucket):
    """'30-60s' reads as '30 to 60 seconds' in a sentence."""
    low, high = bucket.rstrip("s").split("-")
    return f"{low} to {high} seconds"


def score_out_of_100(score):
    return round(score * 100)


def render_headline(tables):
    """Block A. The recommendation, not the funnel."""
    facts = tables["dataset_facts"]
    shortlist = tables["shortlist"]
    proven_count = shortlist["proven_count"]
    emerging_count = len(shortlist["emerging"])

    st.markdown(
        f"#### Focus on {proven_count} creators and one format.\n"
        f"Of **{facts['creators']:,}** creators across **{facts['rows']:,}** trending "
        f"videos ({format_date_span(facts)}), **{shortlist['total_qualifying']}** "
        f"clear all three bars. **{proven_count}** of those did it across 3 or more "
        f"videos. Start with those {proven_count}. The other {emerging_count} are "
        "your research list. Whoever you sign, brief them for "
        f"**{format_bucket_as_words(RECOMMENDED_BUCKET)} with original sound**. "
        "Those are the two content signals that separate high-engagement trending "
        "posts from the rest."
    )


def shortlist_frame(tables):
    """Block B's rows. Proven tier first, then Emerging, each by score descending."""
    shortlist = tables["shortlist"]
    rows = []
    for tier, label in (("proven", "Proven"), ("emerging", "Emerging")):
        for creator in shortlist[tier][:SHORTLIST_ROWS_PER_TIER]:
            rows.append(
                {
                    "Tier": label,
                    "Creator": creator["handle"],
                    "Videos": creator["n_videos"],
                    "Median views": creator["median_views"],
                    "Engagement score": score_out_of_100(creator["median_score"]),
                    "Verified": "✓" if creator["verified"] else "",
                }
            )
    return pd.DataFrame(rows)


def render_shortlist(tables):
    shortlist = tables["shortlist"]
    st.markdown("**Who to talk to**")
    st.dataframe(
        shortlist_frame(tables),
        hide_index=True,
        height=SHORTLIST_TABLE_HEIGHT,
        row_height=SHORTLIST_ROW_HEIGHT,
        column_config={
            "Median views": st.column_config.NumberColumn(format="localized"),
            "Engagement score": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%d"
            ),
        },
    )
    st.caption(
        f"{shortlist['total_qualifying']} creators qualify. "
        f"{shortlist['proven_count']} have a 3+ video record. \"Emerging\" means the "
        "signal is real but rests on two videos. Treat those as a cheap test, not a "
        "headline deal."
    )
    st.caption(
        "Handles appear exactly as in the data. Brand-safety review is a human "
        "step before outreach."
    )


def duration_chart(tables):
    palette = CHART_COLORS["dark" if is_dark_theme() else "light"]
    frame = pd.DataFrame(
        {
            "Length": row["bucket"],
            "Engagement score": score_out_of_100(row["median_score"]),
            "Videos": row["n_videos"],
            "Median views": row["median_views"],
            "Engagement rate": format_percent(row["median_engagement_rate"], 1),
        }
        for row in tables["duration_table"]
    )

    base = alt.Chart(frame).encode(
        y=alt.Y("Length:N", sort=list(prep.BUCKET_ORDER), title=None),
        x=alt.X("Engagement score:Q", title=None, axis=None),
    )
    bars = base.mark_bar(
        height=20, cornerRadiusTopRight=4, cornerRadiusBottomRight=4
    ).encode(
        color=alt.condition(
            alt.datum.Length == RECOMMENDED_BUCKET,
            alt.value(palette["accent"]),
            alt.value(palette["context"]),
        ),
        tooltip=["Length", "Engagement score", "Videos", "Median views", "Engagement rate"],
    )
    labels = base.mark_text(align="left", dx=6, fontSize=12, color=palette["ink"]).encode(
        text=alt.Text("Engagement score:Q", format=".0f")
    )
    return (
        (bars + labels)
        .properties(height=170)
        .configure_view(strokeWidth=0)
        .configure_axis(domain=False, ticks=False, labelColor=palette["ink"], grid=False)
    )


def render_content_brief(tables):
    """Block C. The content half of the question, readable on its own."""
    duration_rows = tables["duration_table"]
    original_sound, licensed_sound = tables["segment_tables"]["music_is_original"]
    longest = duration_rows[-1]
    view_medians = [row["median_views"] for row in duration_rows]
    score_ladder = " → ".join(
        str(score_out_of_100(row["median_score"])) for row in duration_rows
    )

    st.markdown("**What to brief them to make**")
    st.altair_chart(duration_chart(tables), use_container_width=True)
    st.markdown(
        f"**Length.** Longer trending videos engage harder. Median engagement score "
        f"climbs {score_ladder} from {duration_rows[0]['bucket']} to "
        f"{longest['bucket']}. Median views stay flat across those buckets "
        f"({int(min(view_medians)):,} to {int(max(view_medians)):,}). Only "
        f"**{longest['n_videos']} of {tables['dataset_facts']['rows']:,}** videos run "
        f"{longest['bucket']}. The format is under-supplied."
    )
    st.markdown(
        f"**Sound.** Videos on original sound engage better. Median rate is "
        f"{format_percent(original_sound['median_engagement_rate'], 1)} against "
        f"{format_percent(licensed_sound['median_engagement_rate'], 1)}. Median views "
        f"are slightly *lower* ({int(original_sound['median_views']):,} against "
        f"{int(licensed_sound['median_views']):,}). "
        f"{format_percent(original_sound['share_of_videos'])} of the batch already "
        "uses it. Trending sounds buy reach. Original sound buys engagement."
    )


def render_scope(tables):
    """Block D. What this is, and what it cannot tell her."""
    facts = tables["dataset_facts"]
    gates = tables["shortlist"]["gates"]
    hashtags = ", ".join(f"`{tag}` {count}" for tag, count in facts["top_hashtags"])

    # Two columns rather than four stacked lines. The scope strip has to be on
    # screen, and stacking it is what pushed the page past one viewport.
    left, right = st.columns(2, gap="large")
    with left:
        st.caption(
            f"{facts['rows']:,} trending videos, {facts['creators']:,} creators, "
            f"{format_date_span(facts)}. Every row already trended. This says who "
            "engages best *among winners*. It does not say who will win."
        )
        st.caption(
            f"Engagement score = where a video ranks against all {facts['rows']:,} on "
            "likes, comments and shares per view, with the three ranks averaged. Raw "
            f"engagement is {format_percent(facts['likes_share_of_engagement'])} "
            "likes. Ranking each separately stops this being a like rate in disguise."
        )
    with right:
        st.caption(
            f"The three bars: posted {gates['min_videos']}+ videos here · median "
            f"views ≥ {gates['min_median_views']:,} (business relevance, not a size "
            "handicap) · engagement above the batch middle."
        )
        st.caption(
            "Views are the only reach signal here. There are no follower counts. "
            f"`primary_hashtag` is mostly generic discovery tags ({hashtags}; "
            f"{facts['distinct_hashtags']} values, {facts['blank_hashtags']} blank). "
            "We do not segment by content topic."
        )


def render_summary_screen(tables):
    render_headline(tables)
    shortlist_column, content_column = st.columns([3, 2], gap="large")
    with shortlist_column:
        render_shortlist(tables)
    with content_column:
        render_content_brief(tables)
    render_scope(tables)


def set_pending_question(question):
    st.session_state.question_input = question


def answer_table(payload):
    """The source rows, with the raw and display forms of each figure merged."""
    frame = pd.DataFrame(payload["rows"])
    # Display columns exist for the model's benefit. Beside the raw column they
    # are duplicates, so prefer them and drop the raw twin.
    for column in [c for c in frame.columns if c.endswith("_display")]:
        frame[column[: -len("_display")]] = frame[column]
        frame = frame.drop(columns=[column])
    frame = frame.drop(columns=[c for c in ("requested_metric",) if c in frame])
    frame.columns = [c.replace("_", " ").capitalize() for c in frame.columns]
    return frame


def render_answer(question):
    result = llm.answer(question)
    payload = result.payload
    verified, unbacked = checks.provenance_check(result.prose, payload)

    # Fail closed. During live testing the model invented figures that read as
    # correct, so an unverifiable sentence is withheld rather than shown with a
    # caveat nobody would notice.
    if verified:
        st.markdown(f"**{result.prose}**")
    else:
        st.warning(
            "I can't verify one of the figures in that answer, so here's the "
            "data instead."
        )

    if payload["rows"]:
        st.dataframe(answer_table(payload), hide_index=True)

    with st.expander("Where this answer came from"):
        if verified:
            st.markdown("✅ Every figure above was read straight from this table.")
        else:
            st.markdown(
                "⚠️ Withheld the summary: "
                f"{', '.join(f'`{token}`' for token in unbacked)} "
                "did not appear in the data behind it."
            )
        st.markdown(
            f"Question routed to `{result.call.name}` "
            f"with `{result.call.arguments or 'no arguments'}`. "
            f"Sample size: "
            f"**{payload['n'] if payload['n'] is not None else 'not applicable'}** "
            f"{payload['unit']}."
        )
        for note in payload["notes"]:
            st.caption(note)

    return result.mode


def render_question_screen():
    """Screen 2. Same tables as the summary, reached by asking."""
    st.markdown("#### Ask a follow-up")
    st.caption(
        "Answers come from the same prepared tables behind the summary. The "
        "question picks which table to read. Nothing is calculated on the fly."
    )

    # Chips, not a bare text box. She has 20 minutes and will not invent prompts.
    for column, chip in zip(st.columns(len(QUESTION_CHIPS)), QUESTION_CHIPS):
        column.button(
            chip,
            use_container_width=True,
            on_click=set_pending_question,
            args=(chip,),
        )

    question = st.text_input(
        "Or ask your own", key="question_input", placeholder="Type a question"
    )

    if question:
        render_mode_banner(render_answer(question))
    else:
        st.caption("Pick a question above, or type your own.")


def render_mode_banner(mode):
    """Say which path actually answered. Never guess it.

    The first version inferred the mode from whether a fallback had been
    recorded, and told the reader it was in offline mode while the model was
    answering. A banner about trustworthiness has to be right about itself.
    """
    if mode == "anthropic":
        st.caption(
            "Answered by the language model: it chose which prepared question "
            "to run and explained the result. The figures come from the table "
            "above, and each one was checked against it."
        )
        return

    reason = llm.last_fallback_reason()
    if reason:
        st.warning(
            "Answered offline: routing by keyword, narrating from templates. "
            "The language model was unavailable, so the same tools ran without "
            f"it. Reason: {reason}"
        )
    else:
        st.info(
            "Offline mode: routing by keyword, narrating from templates. Set "
            "ANTHROPIC_API_KEY to use the language model. Both modes call the "
            "same tools and show the same figures."
        )


def main():
    st.set_page_config(
        page_title="Trending TikTok, Creator Opportunity Brief", layout="wide"
    )
    st.markdown(COMPACT_LAYOUT_CSS, unsafe_allow_html=True)
    tables = load_tables()

    screen = st.sidebar.radio(
        "View", ["Where to focus", "Ask a question"], label_visibility="collapsed"
    )
    st.sidebar.caption(
        f"Generated {tables['dataset_facts']['generated_at'].replace('T', ' ')} "
        "from the trending export. Historical data, not live trends."
    )

    if screen == "Where to focus":
        render_summary_screen(tables)
    else:
        render_question_screen()


if __name__ == "__main__":
    main()
