import random
import pytest
from typingapp.engine.markov import build_chain, MarkovChain


CORPUS = [
    "the quick brown fox jumps over the lazy dog",
    "the lazy dog sleeps in the warm sun",
    "a quick fox runs through the green forest",
    "the brown dog and the quick fox are friends",
]


def test_build_chain_returns_markov_chain():
    chain = build_chain(CORPUS)
    assert isinstance(chain, MarkovChain)


def test_generate_respects_approximate_word_count():
    random.seed(42)
    chain = build_chain(CORPUS)
    result = chain.generate(word_count=10)
    words = result.split()
    # allow some slack since generation rounds out to sentence end
    assert 5 <= len(words) <= 20


def test_generate_produces_nonempty_text():
    random.seed(1)
    chain = build_chain(CORPUS)
    result = chain.generate(word_count=8)
    assert len(result.strip()) > 0


def test_generate_words_come_from_corpus_vocabulary():
    random.seed(7)
    chain = build_chain(CORPUS)
    result = chain.generate(word_count=12)
    corpus_vocab = set(" ".join(CORPUS).lower().split())
    for word in result.lower().split():
        assert word.strip(".,!?") in corpus_vocab


def test_empty_corpus_raises_no_exception_and_returns_empty():
    chain = build_chain([])
    result = chain.generate(word_count=10)
    assert result == ""


def test_tiny_corpus_still_generates():
    chain = build_chain(["hello world"])
    result = chain.generate(word_count=5)
    assert len(result) > 0
