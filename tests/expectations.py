"""The numbers this suite holds the code to.

These are hardcoded on purpose. This is the file that catches a figure
drifting, so if an expectation here disagrees with the code, one of them is
wrong and the disagreement is the signal. The rule against hardcoded numbers
applies to anything displayed to the user, not to the file whose job is to
check the display.

The source architecture doc claimed a funnel of 802 -> 91 -> 76 -> 47. The real
answer is 74 and 45. That transcription error is why this suite exists.
"""

ROWS = 1_000
CREATORS = 802
TOTAL_VIEWS = 1_029_212_935
DATE_RANGE = ("2020-09-22", "2020-12-21")
FUNNEL = (802, 91, 74, 45)
DURATION_COUNTS = (203, 517, 111, 169)
BATCH_MEDIAN_SCORE = 0.4977
PROVEN_COUNT = 14
VERIFIED_QUALIFYING = 4
VERIFIED_VIEWS_RATIO = "7.6x"

PERCENTILE_COLUMNS = ("p_like", "p_comment", "p_share")
