# coding=utf-8
page = """

<section class="slide level1">
<p><img src="{image}"></p>
<p>{text}</p>
<audio> <source src="{audio}" </audio>
<center>
<strong>{page}</strong>
</center>
</section>

"""

trailer = """
<section class="slide level1">
<h2 id="en-veldig-høy-mann-1">{title}</h2>
<strong>Text:</strong> {author}<br>
<strong>Illustration:</strong> {artist}<br>
<strong>Translated by:</strong> {translator}<br>
<strong>Read by:</strong> {narrator}<br>
<strong>Language:</strong> {language}<br>
<p>

This story comes from the Global African Storybook Project, which is working on translating the stories from <a href = 'http://africanstorybook.org/'>The African Storybook Project</a> for all world languages.
<p>

<img src = "https://global-asp.github.io/logo.png" alt = "Global ASP logo" border = "0" />
</section>
"""

class Carousel(object):
    def __init__(self, data):
        self.data = data
        self.pages = self.pagehtml()
        self.title = data.title
        self.cover = data.cover
        self.coveraudio = data.coveraudio
        self.trailer = self.trailerhtml()

    def html(self):
        with open("template.html") as f:
            html = f.read()
        for item in ["title", "pages", "cover", "trailer", "coveraudio"]:
            assert "**"+item+"**" in html, item
            html = html.replace("**{}**".format(item), getattr(self, item))
        return html

    def pagehtml(self):
        html =  []
        for i, (text, img, audio) in enumerate(zip(self.data.texts, self.data.imgs, self.data.audios)):
            fields = {"text": text,
                      "image": img,
                      "audio": audio,
                      "page": i}
            html.append(page.format(**fields))
        return '\n\n'.join(html)

    def trailerhtml(self):
        return trailer.format(title = getattr(self.data, 'title', ''),
                              author = getattr(self.data, 'author', ''),
                              artist = getattr(self.data, 'artist', ''),
                              narrator = getattr(self.data, 'narrator', ''),
                              language = getattr(self.data, 'language', ''),
                              translator = getattr(self.data, 'translator', ''))



