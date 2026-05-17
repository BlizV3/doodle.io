import random
import os


class WordManager:
    # Resolve the word list file path and load all non-empty words from it.
    def __init__(self, words_file: str = None):
        if words_file is None:
            root = os.path.join(os.path.dirname(__file__), "..")
            words_file = os.path.join(root, "words.txt")

        with open(words_file, encoding="utf-8") as f:
            self.words = [w.strip() for w in f if w.strip()]

    def pick_words(self, n: int = 3) -> list[str]:
        return random.sample(self.words, min(n, len(self.words)))

    @staticmethod
    def make_hint(word: str, revealed: set[int]) -> list[str]:
        """Return list of chars: visible letter, '_', or ' ' for spaces."""
        return [
            c if (c == " " or i in revealed) else "_"
            for i, c in enumerate(word)
        ]

    @staticmethod
    def reveal_random_letter(word: str, revealed: set[int]) -> set[int]:
        """Add one random unrevealed non-space index to revealed; return updated set."""
        candidates = [i for i, c in enumerate(word) if c != " " and i not in revealed]
        if candidates:
            revealed = revealed | {random.choice(candidates)}
        return revealed
