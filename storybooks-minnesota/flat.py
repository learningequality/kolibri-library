import detail

class Page(object):
    def page(self, offset=0):
        return "0"+str(self.number+offset)
    def __init__(self, i, text, audio, foreign, img):
        self.number = i
        self.img = img
        self.lang = [text, text, foreign]  # TODO confirm correct behaviour
        self.audio = audio

def make_pages_from_book(book):
    for i, raw_page in enumerate(zip(book.texts, book.audios, book.foreigns, book.imgs)):
        yield Page(i+2, *raw_page)

def effify(s):
    return eval(f'f"""{s}"""')

book = detail.MyFoundry(detail.url).book
with open("html/page.template.html") as f:
    p_template = f.read()

page_list = []
for page in make_pages_from_book(book):
    page_list.append(effify(p_template))
pages = "\n".join(page_list)

with open("html/index.template.html") as f:
    template = f.read()
    f_template = effify(template)
with open("html/index.out.html", "w") as f:
    f.write(f_template)

