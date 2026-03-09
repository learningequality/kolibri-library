import jsonlines
import re

MEANINGLESS = ["(c)", "copyright", "all", "rights", "reserved", "not", "by", "listed", "the", "out", "of", "for", "a"]
DELETIONS = ["&copy;", "©", "<p>", "</p>", ".", "�", "—"]

def has_copyright(s):
    if not s: return False
    if not s.strip(): return False
    words = s.split(" ")
    for word in words:
        word = word.lower()
        for d in DELETIONS:
            word = word.replace(d, "")
        if word in MEANINGLESS:
            continue
        elif re.search("\d\d\d\d", word):
            continue
        else:
            return word
    return False

if __name__ == "__main__":
    seen = set()
    with jsonlines.open("full.uniq.jsonlines") as records:
        for i, record in enumerate(records):
            c = record['detail'].get('copyright', "")
            word = has_copyright(c)
            if word:
                if word not in seen:
                    print (word, c)
                    seen.add(word)
            if i>10000: exit()

        