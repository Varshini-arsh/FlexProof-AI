"""Paired significance tests for common held-out scenario outcomes."""
from __future__ import annotations
from scipy.stats import binomtest


def exact_mcnemar(first: list[bool], second: list[bool]) -> dict:
    """Two-sided exact McNemar test; paired observations must share scenario order."""
    if len(first)!=len(second) or not first:
        raise ValueError("paired outcome arrays must have equal nonzero length")
    first_only=sum(bool(a) and not bool(b) for a,b in zip(first,second))
    second_only=sum(not bool(a) and bool(b) for a,b in zip(first,second))
    discordant=first_only+second_only
    pvalue=1.0 if discordant==0 else float(
        binomtest(min(first_only,second_only),discordant,0.5,alternative="two-sided").pvalue)
    return {"method":"exact two-sided McNemar test","sample_count":len(first),
        "first_only_successes":first_only,"second_only_successes":second_only,
        "discordant_pairs":discordant,"p_value":pvalue}
