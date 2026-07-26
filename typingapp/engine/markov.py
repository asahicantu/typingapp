from __future__ import annotations
import random
from collections import defaultdict

SENTENCE_END_CHARS = ".!?"


class MarkovChain:
    def __init__(self, transitions: dict[tuple[str, ...], list[str]], order: int) -> None:
        self._transitions = transitions
        self._order = order
        self._starts = list(transitions.keys())

    def generate(self, word_count: int) -> str:
        if not self._starts:
            return ""
        state = random.choice(self._starts)
        words = list(state)
        while len(words) < word_count:
            next_words = self._transitions.get(state)
            if not next_words:
                state = random.choice(self._starts)
                words.extend(state)
                continue
            next_word = random.choice(next_words)
            words.append(next_word)
            state = tuple(words[-self._order:])
            if len(words) >= word_count and next_word[-1:] in SENTENCE_END_CHARS:
                break
        return " ".join(words)


def build_chain(corpus_sentences: list[str], order: int = 2) -> MarkovChain:
    transitions: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for sentence in corpus_sentences:
        words = sentence.split()
        if len(words) < order:
            continue
        for i in range(len(words) - order):
            state = tuple(words[i:i + order])
            next_word = words[i + order]
            transitions[state].append(next_word)
        # For sentences with exactly `order` words, add the final state as a start with no transitions
        if len(words) == order:
            state = tuple(words)
            if state not in transitions:
                transitions[state] = []
    return MarkovChain(dict(transitions), order)
