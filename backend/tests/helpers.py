from apps.assessment.models import Exam, Mark, MarkSheet
from apps.curriculum.models import Subject


def ple_subjects(school):
    return {s.short_name: s for s in Subject.objects.filter(school=school, level="primary")}


def exam(term, school_class, kind="eot", weight=100, name=None):
    e = Exam.objects.create(
        school=term.school, term=term, name=name or kind.upper(), kind=kind, weight=weight
    )
    e.classes.add(school_class)
    return e


def approved_marks(exam_obj, school_class, subject, scores):
    """scores = {learner: score}; creates an approved sheet."""
    sheet = MarkSheet.objects.create(
        school=exam_obj.school, exam=exam_obj, subject=subject, school_class=school_class
    )
    for learner, score in scores.items():
        Mark.objects.create(school=exam_obj.school, mark_sheet=sheet, learner=learner, score=score)
    sheet.status = MarkSheet.Status.APPROVED
    sheet.save()
    return sheet


def approve_all_offered(exam_obj, school_class, learners, score_for):
    """Approved sheets for every subject offered in the class; score_for(learner, subject) -> score."""
    from apps.assessment.grading import subjects_offered

    for subject in subjects_offered(school_class):
        approved_marks(exam_obj, school_class, subject, {l: score_for(l, subject) for l in learners})
