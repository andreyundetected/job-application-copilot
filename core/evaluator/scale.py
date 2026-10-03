PREP_LABELS = {
    10: "< 1 day",
    9: "~4 days",
    8: "~1 week",
    7: "1-2 weeks",
    6: "3-4 weeks",
    5: "~2 months",
    4: "3-4 months",
    3: "~6 months",
    2: "~1 year",
    1: "1+ year",
}


def prep_label(score):
    if score is None:
        return None
    return PREP_LABELS.get(score)