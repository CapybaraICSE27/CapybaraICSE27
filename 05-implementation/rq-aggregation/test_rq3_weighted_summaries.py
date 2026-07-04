import unittest
from collections import Counter

from rq3_weighted_summaries import (
    build_event_weighted_summary,
    build_repo_weighted_summary,
    build_test_weighted_summary,
)


class _Agg:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestWeightedSummaries(unittest.TestCase):
    def test_event_weighted_shares(self):
        rows = build_event_weighted_summary(
            locator_events=10,
            locator_composition=Counter({"direct_chain": 7, "standalone_locator_query": 3}),
            locator_strategy=Counter(),
            sync_events=0,
            sync_pattern=Counter(),
            workflow_events=0,
            abstraction_kind=Counter(),
        )
        direct = [r for r in rows if r["label"] == "direct_chain"][0]
        self.assertAlmostEqual(direct["share"], 0.7)

    def test_test_weighted_prevalence(self):
        aggs = [
            _Agg(
                locator_event_count=2,
                locator_composition_counts=Counter({"direct_chain": 2}),
                sync_pattern_counts=Counter(),
                abstraction_kind_counts=Counter(),
            ),
            _Agg(
                locator_event_count=0,
                locator_composition_counts=Counter(),
                sync_pattern_counts=Counter(),
                abstraction_kind_counts=Counter(),
            ),
        ]
        rows = build_test_weighted_summary(aggs)
        direct = [r for r in rows if r["label"] == "direct_chain"][0]
        self.assertEqual(direct["count"], 1)
        self.assertAlmostEqual(direct["share"], 0.5)

    def test_repo_mean_weighting(self):
        aggs = [
            _Agg(
                repo="a",
                locator_event_count=1,
                locator_composition_counts=Counter({"direct_chain": 1}),
                sync_pattern_counts=Counter(),
                abstraction_kind_counts=Counter(),
            ),
            _Agg(
                repo="b",
                locator_event_count=1,
                locator_composition_counts=Counter({"standalone_locator_query": 1}),
                sync_pattern_counts=Counter(),
                abstraction_kind_counts=Counter(),
            ),
        ]
        rows = build_repo_weighted_summary(aggs)
        labels = {r["label"]: r["mean_test_prevalence_per_repo"] for r in rows}
        self.assertAlmostEqual(labels["direct_chain"], 0.5)
        self.assertAlmostEqual(labels["standalone_locator_query"], 0.5)


if __name__ == "__main__":
    unittest.main()
