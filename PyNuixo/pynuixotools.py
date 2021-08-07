from datetime import datetime

class PyNuixoTools:
    def __init__(self, subjectScores):
        self.subjectScores = subjectScores

    def get_this_month_subjectScores(self):
        today = datetime.today()
        this_month = today.month
        this_month_subjectScores = []
        for ss in self.subjectScores:
            if f"{this_month}/15" in ss.limit:
                this_month_subjectScores.append(ss)
        return this_month_subjectScores

    def to_csv(self):
        csv = "教科名, 締め切り, 進捗率, 点数"
        for ss in self.subjectScores:
            csv += f"\n{ss.subject}, {ss.limit}, {ss.percentage}, {ss.score}"
        return csv

    def get_subjects(self):
        all_duplicate_subjects = []
        for subjectScore in self.subjectScores:
            all_duplicate_subjects.append(subjectScore.subject)
        return list(set(all_duplicate_subjects))