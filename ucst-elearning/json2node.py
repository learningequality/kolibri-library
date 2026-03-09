import json
from collections import OrderedDict
from abc import ABC, abstractmethod
from le_utils.constants import content_kinds


class Node:
    def __init__(self, title=None, source_id=None, lang="en", author=None, license=None):
        self.title = title
        self.source_id = source_id
        self.tree_nodes = OrderedDict()
        self.lang = lang
        self.description = None
        self.author = author
        self.license = license

    def add_node(self, obj):
        node = obj.to_dict()
        if node is not None:
            self.tree_nodes[node["source_id"]] = node

    def to_dict(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.source_id,
            title=self.title,
            description=self.description,
            language=self.lang,
            author=self.author,
            license=self.license,
            children=list(self.tree_nodes.values())
        )


class GradeJsonTree:
    def __init__(self, *args, subject_node=None, **kwargs):
        self.grades = []
        self.subject_node = subject_node

    def load(self, filename, auto_parse=False, author=None, license=None, 
            save_url_to=None, load_video_list=False):
        with open(filename, "r") as f:
            grades = json.load(f)
            for grade in grades:
                grade_obj = GradeNode(title=grade["title"], 
                                      source_id=grade["source_id"],
                                      author=author,
                                      license=license)
                if "subjects" in grade:
                    for subject in grade["subjects"]:
                        subject_obj = self.subject_node(title=subject["title"],
                                              source_id=subject["source_id"],
                                              lang=subject["lang"],
                                              author=author,
                                              license=license)
                        subject_obj.auto_generate_lessons(subject["lessons"], 
                            save_url_to=save_url_to, load_video_list=load_video_list)
                        grade_obj.add_subject(subject_obj)
                    self.grades.append(grade_obj)
                elif "lessons" in grade:
                    for lesson in grade["lessons"]:
                        lesson_obj = self.subject_node(title=lesson,
                                              source_id=lesson,
                                              lang=grade["lang"],
                                              author=author,
                                              license=license)
                        lesson_obj.auto_generate_lessons(lesson, 
                            save_url_to=save_url_to, load_video_list=load_video_list)
                        grade_obj.add_subject(lesson_obj)
                    self.grades.append(grade_obj)

    def __iter__(self):
        return iter(self.grades)


class GradeNode(Node):
    def __init__(self, *args, **kwargs):
        super(GradeNode, self).__init__(*args, **kwargs)
        self.subjects = []

    def add_subject(self, subject):
        self.subjects.append(subject)


class ABCSubjectNode(ABC, Node):
    def __init__(self, *args, **kwargs):
        Node.__init__(self, *args, **kwargs)
        self.lessons = []

    @abstractmethod
    def auto_generate_lessons(self, urls):
        raise NotImplementedError


class ABCLessonNode(ABC, Node):

    def __init__(self, *args, **kwargs):
        Node.__init__(self, *args, **kwargs)
        self.item = None

    @abstractmethod
    def download(self, download=True, base_path=None):
        raise NotImplementedError

    def to_dict(self):
        children = list(self.tree_nodes.values())
        if len(children) == 1:
            return children[0]
        else:
            return dict(
                kind=content_kinds.TOPIC,
                source_id=self.source_id,
                title=self.title,
                description=self.description,
                language=self.lang,
                author=self.author,
                license=self.license,
                children=children
            )
