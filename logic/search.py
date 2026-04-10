class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.words = []


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        normalized = word.lower()
        current = self.root

        for char in normalized:
            if char not in current.children:
                current.children[char] = TrieNode()
            current = current.children[char]

        current.is_end_of_word = True
        current.words.append(word)

    def _find_node(self, prefix):
        normalized = prefix.lower()
        current = self.root

        for char in normalized:
            if char not in current.children:
                return None
            current = current.children[char]

        return current

    def get_suggestions(self, prefix, limit=5):
        node = self._find_node(prefix)
        if node is None:
            return []

        suggestions = []
        self._collect_words(node, suggestions, limit)
        return suggestions

    def _collect_words(self, node, suggestions, limit):
        if len(suggestions) >= limit:
            return

        if node.is_end_of_word:
            for word in node.words:
                suggestions.append(word)
                if len(suggestions) >= limit:
                    return

        for child in node.children.values():
            self._collect_words(child, suggestions, limit)


