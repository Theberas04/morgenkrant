"""Taalherkenning: houd de krant Nederlandstalig, ook als een feed Engels meelevert."""
import re

NL = {"de", "het", "een", "van", "en", "is", "dat", "niet", "op", "te", "voor", "met",
      "zijn", "ook", "maar", "aan", "bij", "door", "over", "wordt", "worden", "heeft",
      "hebben", "kan", "kunnen", "nog", "wel", "geen", "dit", "deze", "als", "dan",
      "om", "naar", "uit", "tot", "meer", "al", "zo", "wat", "hoe", "wij", "we", "ik",
      "hij", "zij", "ze", "je", "jij", "mijn", "ons", "onze", "er", "was", "waren",
      "zal", "zou", "moet", "mag", "wil", "wil", "per", "jaar", "nieuwe", "tussen",
      "volgens", "onder", "tijdens", "sinds", "tegen", "zonder", "binnen", "buiten",
      "eerste", "laatste", "miljoen", "mensen", "nederland", "nederlandse"}
EN = {"the", "and", "of", "to", "in", "is", "that", "for", "with", "was", "has", "have",
      "will", "it", "this", "from", "but", "not", "are", "were", "been", "they", "their",
      "there", "which", "who", "what", "when", "how", "more", "than", "also", "would",
      "could", "should", "his", "her", "its", "our", "your", "about", "into", "after",
      "before", "over", "such", "only", "just", "because", "through", "these", "those",
      "week", "years", "first", "last", "million", "people", "government", "country"}


def _words(text):
    return re.findall(r"[a-zA-Zà-ÿ]+", (text or "").lower())


def scores(text):
    woorden = _words(text)[:800]
    nl = sum(1 for w in woorden if w in NL)
    en = sum(1 for w in woorden if w in EN and w not in NL)
    return nl, en


def is_dutch(text, minimum=6):
    """True als de tekst overtuigend Nederlands is (en niet Engels)."""
    nl, en = scores(text)
    if nl < minimum:
        return False
    return nl >= en * 1.3