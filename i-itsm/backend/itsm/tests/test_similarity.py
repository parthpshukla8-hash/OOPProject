"""Cosine-similarity engine. Pure Python, so these run without a database."""
import unittest

from itsm.similarity import CentroidClassifier, SimilarityIndex, SparseVector, TfidfModel, tokenize


class TextNormalisationTests(unittest.TestCase):
    def test_synonyms_and_plurals_collapse_to_one_term(self):
        self.assertEqual(tokenize("Payments unavailable")[:2], tokenize("payment outage")[:2])

    def test_stopwords_are_ignored(self):
        self.assertEqual(tokenize("the app is not working"), ["app", "down"])


class CosineSimilarityTests(unittest.TestCase):
    def setUp(self):
        self.model = TfidfModel([
            "payment application unavailable", "unable to make payment", "vpn keeps disconnecting",
            "laptop battery not charging", "database query timeouts"])

    def test_identical_text_scores_one(self):
        vector = self.model.vectorize("payment application unavailable")
        self.assertAlmostEqual(vector.cosine_similarity(vector), 1.0)

    def test_unrelated_text_scores_zero(self):
        first = self.model.vectorize("vpn keeps disconnecting")
        second = self.model.vectorize("laptop battery not charging")
        self.assertEqual(first.cosine_similarity(second), 0.0)

    def test_empty_text_scores_zero_instead_of_failing(self):
        self.assertEqual(self.model.vectorize("").cosine_similarity(self.model.vectorize("payment")), 0.0)

    def test_score_is_symmetric_and_bounded(self):
        a, b = self.model.vectorize("payment is down"), self.model.vectorize("payment application unavailable")
        self.assertAlmostEqual(a.cosine_similarity(b), b.cosine_similarity(a))
        self.assertTrue(0.0 <= a.cosine_similarity(b) <= 1.0)

    def test_reworded_report_matches_original_best(self):
        docs = [("pay", "Payment application unavailable, users unable to complete transactions"),
                ("vpn", "VPN keeps disconnecting from home network"),
                ("db", "Database query timeouts on reporting server")]
        results = SimilarityIndex(docs).search("transactions failing in the payment app")
        self.assertEqual(results[0].item, "pay")
        self.assertIn("payment", results[0].shared_terms)


class ClassifierTests(unittest.TestCase):
    def test_suggests_label_with_closest_centroid(self):
        classifier = CentroidClassifier({
            "Network": ["network wifi vpn internet router"], "Hardware": ["laptop battery screen keyboard"]})
        self.assertEqual(classifier.rank("my wifi and vpn are down")[0][0], "Network")

    def test_centroid_of_nothing_is_empty(self):
        self.assertTrue(SparseVector.centroid([]).is_empty)


if __name__ == "__main__":
    unittest.main()
