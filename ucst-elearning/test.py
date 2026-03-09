from json2node import GradeJsonTree, ABCLessonNode, ABCSubjectNode


LICENSE = "TEST"
AUTHOR = "TEST"


class SubjectNode(ABCSubjectNode):
    
    def auto_generate_lessons(self, urls, save_url_to=None, load_video_list=False):
        for url in urls:
            lesson = LessonNode(title=url, source_id=url, 
                                lang=self.lang, author=self.author, 
                                license=self.license)
            self.lessons.append(lesson)


class LessonNode(ABCLessonNode):

    def download(self, download=True, base_path=None):
        return self.source_id


def check_json_resources_01():
    grades = GradeJsonTree(subject_node=SubjectNode)
    grades.load("resources_test.json", auto_parse=True, author=AUTHOR, 
        license=LICENSE, save_url_to="", load_video_list="")
    for i, grade in enumerate(grades, 1):
        assert grade.title == "Category Title 0" + str(i)
        assert grade.source_id == "Category Source Id 0" + str(i)
        for i, subject in enumerate(grade.subjects, 1):
            assert subject.title == "Subject Title 0" + str(i)
            assert subject.source_id == "Subject Source Id 0" + str(i)
            for lesson in subject.lessons:
                video = lesson.download()
                assert video == lesson.source_id
                subject.add_node(lesson)
            grade.add_node(subject)
    assert isinstance(grade.to_dict(), dict) == True


def check_json_resources_02():
    grades = GradeJsonTree(subject_node=SubjectNode)
    grades.load("resources_test_wo_subject.json", auto_parse=True, author=AUTHOR, 
        license=LICENSE, save_url_to="", load_video_list="")
    for i, grade in enumerate(grades, 1):
        assert grade.title == "Category Title 0" + str(i)
        assert grade.source_id == "Category Source Id 0" + str(i)
        for subject in grade.subjects:
            grade.add_node(subject)
    assert isinstance(grade.to_dict(), dict) == True


if __name__ == '__main__':
    check_json_resources_01()
    check_json_resources_02()
