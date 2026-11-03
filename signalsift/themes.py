"""Unsupervised theme discovery: TF-IDF -> LSA -> K-Means.

No one labels the feedback up front. The model groups reviews that use similar
words and names each theme after its most distinctive terms so a PM can read
it at a glance.

How many themes to show is a product decision as much as a statistical one:
statistical scores such as silhouette keep rising as themes get more granular,
but a brief with 20 micro-themes is not actionable. The default of 8 fits on one
page; the app exposes a slider and the silhouette curve so the trade-off is visible.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import Normalizer

DEFAULT_THEMES = 8

# Mood words appear in every theme ("terrible", "love"). Removing them makes
# clusters form around *what* users talk about, not *how they feel*; sentiment
# is measured separately.
GENERIC_WORDS = {
    "app", "freshkart", "please", "really", "just", "time", "times", "fix", "team",
    "worst", "experience", "absolutely", "terrible", "pathetic", "service", "disappointed",
    "happy", "frustrating", "disappointing", "okay", "average", "mixed", "feelings",
    "good", "overall", "mostly", "pretty", "love", "excellent", "amazing", "uninstalling",
    "ordering", "week", "hope", "looks", "expected", "better", "fine", "improving",
    "stars", "thank", "keep", "otherwise", "possible", "great", "best", "highly", "recommend",
}
STOP_WORDS = sorted(ENGLISH_STOP_WORDS | GENERIC_WORDS)


@dataclass
class ThemeModel:
    vectorizer: TfidfVectorizer
    svd: TruncatedSVD
    normalizer: Normalizer
    kmeans: KMeans
    labels: np.ndarray
    names: dict[int, str]
    top_terms: dict[int, list[str]]
    silhouette_by_k: dict[int, float] = field(default_factory=dict)

    @property
    def k(self) -> int:
        return int(self.kmeans.n_clusters)

    def embed(self, clean_texts):
        return self.normalizer.transform(self.svd.transform(self.vectorizer.transform(list(clean_texts))))

    def assign(self, clean_texts) -> list[str]:
        """Map new feedback onto the discovered themes."""
        return [self.names[i] for i in self.kmeans.predict(self.embed(clean_texts))]


def _readable_name(terms: list[str], max_terms: int = 3) -> str:
    """Join the top terms, skipping ones whose words are already covered."""
    chosen: list[str] = []
    covered: set[str] = set()
    for term in terms:
        words = set(term.split())
        if words <= covered:
            continue
        chosen.append(term)
        covered |= words
        if len(chosen) == max_terms:
            break
    return " / ".join(chosen)


def fit_themes(clean_texts, k: int = DEFAULT_THEMES, random_state: int = 42,
               diagnostics_k_range=None) -> ThemeModel:
    """Discover ``k`` themes.

    Pass ``diagnostics_k_range`` (e.g. ``range(5, 13)``) to also record the
    silhouette score for each candidate k, which the app plots.
    """
    texts = list(clean_texts)
    if len(texts) < 50:
        raise ValueError("Need at least 50 pieces of feedback to discover themes.")
    if not 2 <= k < len(texts):
        raise ValueError(f"Number of themes must be between 2 and {len(texts) - 1}.")

    vectorizer = TfidfVectorizer(
        stop_words=STOP_WORDS, token_pattern=r"(?u)\b[a-z][a-z]+\b",
        ngram_range=(1, 2), min_df=3, max_df=0.4, sublinear_tf=True,
    )
    tfidf = vectorizer.fit_transform(texts)
    # A compact LSA space (a little larger than k) keeps short reviews from
    # being split on incidental words; tested against labelled data.
    svd = TruncatedSVD(n_components=min(max(10, k + 2), tfidf.shape[1] - 1), random_state=random_state)
    normalizer = Normalizer(copy=False)
    embedded = normalizer.fit_transform(svd.fit_transform(tfidf))

    silhouette_by_k: dict[int, float] = {}
    for candidate in diagnostics_k_range or []:
        if 2 <= candidate < len(texts):
            labels = KMeans(n_clusters=candidate, n_init=10, random_state=random_state).fit_predict(embedded)
            silhouette_by_k[candidate] = round(float(silhouette_score(
                embedded, labels, sample_size=min(3000, len(texts)), random_state=random_state)), 4)

    kmeans = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(embedded)
    labels = kmeans.labels_

    vocabulary = np.array(vectorizer.get_feature_names_out())
    top_terms: dict[int, list[str]] = {}
    names: dict[int, str] = {}
    for cluster in range(k):
        mean_weights = np.asarray(tfidf[labels == cluster].mean(axis=0)).ravel()
        top_terms[cluster] = vocabulary[mean_weights.argsort()[::-1][:8]].tolist()
        names[cluster] = _readable_name(top_terms[cluster])

    # Two clusters can share top terms; suffix duplicates so names stay unique.
    seen: dict[str, int] = {}
    for cluster, name in names.items():
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            names[cluster] = f"{name} ({seen[name]})"

    return ThemeModel(vectorizer, svd, normalizer, kmeans, labels, names, top_terms, silhouette_by_k)


def clustering_quality(gold_labels, predicted_labels) -> float:
    """Adjusted Rand Index vs. a labelled sample: 1.0 is perfect, 0.0 is random."""
    return round(float(adjusted_rand_score(list(gold_labels), list(predicted_labels))), 3)
