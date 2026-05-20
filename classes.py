def create_course_object(config, pub):
    courseObject = Course(config[pub]['coursecode'],
                            config[pub]['coursesize'],
                            int(config[pub]['lectures']),
                            config[pub]['coursename'],
                            config[pub]['filename_prefix'],
                            config[pub]['lectureterm'],
                            config[pub]['publish_dir'], 
                            config[pub]['course_slides_dir'])
    try:
        for x in range(1, courseObject.lectures+1):  
            lecturelist = config[pub][str(x)].split(";")
            lecture_name = lecturelist.pop(0).strip()
            courseObject.add_lecture(lecture_name, x, [topic.strip() for topic in lecturelist])
    except KeyError:
        print(f"Lectures should be added as <lecturenumber = name, topic1, topic2 ... topicN> under publication {courseObject.name} in settings.ini")
    return courseObject

class Course:
    def __init__(self, coursecode: str, coursesize: str, lectures: int, name: str, filename_prefix: str, lectureterm: str, publication_dir: str, course_slides_dir: str):
        self.name = name
        self.coursecode = coursecode
        self.coursesize = coursesize
        self.lectures = lectures
        self.filename_prefix = filename_prefix
        self.lectureterm = lectureterm
        self.publication_dir = publication_dir
        self.course_slides_dir = course_slides_dir
        self.lecture_list = list()

    def add_lecture(self, name, lectureNumber, topic_list):
        clean_topic_list = [item for item in topic_list if item and str(item).strip()]
        self.lecture_list.append(
            Lecture(name, lectureNumber, clean_topic_list)
        )

class Lecture():
    def __init__(self, name: str, lectureNumber: int, topic_list: list):
        self.name = name
        self.lectureNumber = lectureNumber
        self.topic_list = topic_list

    def add_topic(self, topic):
        self.topics.append(topic)
