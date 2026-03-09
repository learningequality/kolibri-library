import csv
import lxml.html
import login

session = login.session

class Page():
    def __init__(self, url):
        self.url = url
        self.response = session.get(url)
        self.root = lxml.html.fromstring(self.response.content)


def top_index():
    """Have manually checked: this is complete for categorynames in course_index"""
    page = Page("https://www.aldarayn.com/course/index.php?categoryid=17")
    options = page.root.xpath("//option")
    option_ids = [x.get("value") for x in options]
    option_names = [x.text for x in options]
    return zip(option_ids, option_names)

def course_index(course_id):
    page = Page("https://www.aldarayn.com/course/index.php?categoryid={}&perpage=99999999".format(course_id))
    course_tags = page.root.xpath("//*[@class='coursename']/a")
    course_names = [x.text for x in course_tags]
    course_urls = [x.get('href') for x in course_tags]
    return zip(course_names, course_urls)

def all_courses():
    for top_id, top_name in top_index():
        for course_name, course_url in course_index(top_id):
            yield [top_id, top_name, course_name, course_url]

def csv_output():
    with open('sample.csv', 'w', newline='', encoding='utf-8') as csvfile:
        csvout = csv.writer(csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        # spamwriter.writerow("")
        i = 0
        for top_id, top_name in top_index():
            for course_name, course_url in course_index(top_id):
                i = i + 1
                csvout.writerow([top_id,
                                top_name, '=GOOGLETRANSLATE(B{}, "ar", "en")'.format(i),
                                course_name, '=GOOGLETRANSLATE(D{}, "ar", "en")'.format(i),
                                course_url])

# csv_output()
