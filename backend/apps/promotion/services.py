from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.assessment.models import ReportCard, ResultSummary
from apps.attendance.services import learner_stats
from apps.core.exceptions import BusinessRuleError
from apps.learners.models import Enrolment, Learner, LearnerExit
from apps.learners.services import learners_in

from .models import PromotionBatch, PromotionDecision, PromotionRule

O = PromotionDecision.Outcome
B = PromotionBatch.Status
DEFAULT_PASS_MARK = Decimal("50")


def rule_for(school_class):
    return (
        PromotionRule.objects.filter(school=school_class.school, school_class=school_class).first()
        or PromotionRule.objects.filter(
            school=school_class.school, section=school_class.section, school_class__isnull=True
        ).first()
    )


def measure(rule, learner, term):
    """The learner's value for the rule's measure, or None when marks are missing."""
    if rule.measure == PromotionRule.Measure.ATTENDANCE:
        return learner_stats(learner, term)["rate"]
    term_result = ResultSummary.objects.filter(learner=learner, term=term).first()
    if term_result is None or not term_result.is_complete:
        return None
    if rule.measure == PromotionRule.Measure.TERM3_AVERAGE:
        return term_result.average
    if rule.measure == PromotionRule.Measure.PLE_AGGREGATE:
        return term_result.aggregate
    if rule.measure == PromotionRule.Measure.SUBJECTS_FAILED:
        return sum(
            1
            for r in term_result.subjects
            if r["score"] is not None and Decimal(str(r["score"])) < rule.fail_below
        )
    if rule.measure == PromotionRule.Measure.ANNUAL_AVERAGE:
        results = ResultSummary.objects.filter(learner=learner, term__academic_year=term.academic_year)
        averages = [r.average for r in results if r.average is not None]
        if len(averages) < term.academic_year.terms.count():
            return None
        return sum(averages) / len(averages)
    return None


def decide(rule, value, attendance_rate=None):
    if value is None:
        return O.REVIEW
    value = Decimal(str(value))
    if rule.lower_is_better:
        outcome = (
            O.PROMOTE
            if value <= rule.pass_mark
            else (
                O.PROBATION if rule.probation_mark is not None and value <= rule.probation_mark else O.REPEAT
            )
        )
    else:
        outcome = (
            O.PROMOTE
            if value >= rule.pass_mark
            else (
                O.PROBATION if rule.probation_mark is not None and value >= rule.probation_mark else O.REPEAT
            )
        )
    if rule.min_attendance is not None and attendance_rate is not None and outcome == O.PROMOTE:
        if Decimal(str(attendance_rate)) < rule.min_attendance:
            outcome = O.PROBATION
    return outcome


def class_below(school_class):
    """The class that promotes into this one (P4 for P5), for demotions."""
    return type(school_class).objects.filter(school=school_class.school, next_class=school_class).first()


def target_class(school_class, outcome):
    if outcome in (O.COMPLETE, O.REVIEW):
        return None
    if outcome == O.REPEAT:
        return school_class
    if outcome == O.DEMOTE:
        return class_below(school_class)
    return school_class.next_class


def partial_average(learner, term):
    """The average of the marks there are, shown for learners still missing marks."""
    result = ResultSummary.objects.filter(learner=learner, term=term).first()
    return result.average if result else None


def propose(term, school_class, stream_policy="keep", pass_mark=None):
    """Sort every learner in the class into passed (at or above the pass mark) and below it,
    and start the review chain with the class teacher.

    The class's promotion rule is used when there is one; otherwise the term average with a
    pass mark of 50% (or the pass mark given). A pass mark given here applies to this list only."""
    from apps.assessment.grading import compute_class_results

    rule = rule_for(school_class)
    base_rule = rule
    if rule is None:
        rule = PromotionRule(
            school=school_class.school,
            school_class=school_class,
            measure=PromotionRule.Measure.TERM3_AVERAGE,
            pass_mark=DEFAULT_PASS_MARK,
        )
    if pass_mark not in (None, ""):
        try:
            pass_mark = Decimal(str(pass_mark))
        except ArithmeticError:
            raise BusinessRuleError({"pass_mark": "The pass mark must be a number."})
        rule = PromotionRule(
            school=rule.school,
            school_class=school_class,
            measure=rule.measure,
            pass_mark=pass_mark,
            probation_mark=rule.probation_mark
            if rule.probation_mark is not None and rule.probation_mark < pass_mark
            else None,
            fail_below=rule.fail_below,
            min_attendance=rule.min_attendance,
        )
    if PromotionBatch.objects.filter(term=term, school_class=school_class).exclude(status=B.UNDONE).exists():
        raise BusinessRuleError({"detail": "A promotion list already exists for this class and term."})
    if not school_class.is_candidate_class:
        compute_class_results(term, school_class)
    with transaction.atomic():
        batch = PromotionBatch.objects.create(
            school=school_class.school,
            term=term,
            school_class=school_class,
            rule=base_rule,
            pass_mark=rule.pass_mark,
            stream_policy=stream_policy,
        )
        for learner in learners_in(school_class.school, term, school_class):
            if school_class.is_candidate_class:
                value, outcome = None, O.COMPLETE
            else:
                value = measure(rule, learner, term)
                rate = learner_stats(learner, term)["rate"] if rule.min_attendance is not None else None
                outcome = decide(rule, value, rate)
                if value is None and rule.measure == PromotionRule.Measure.TERM3_AVERAGE:
                    value = partial_average(learner, term)
            target = target_class(school_class, outcome)
            PromotionDecision.objects.create(
                school=school_class.school,
                batch=batch,
                learner=learner,
                measure_value=value,
                proposed=outcome,
                final=outcome,
                to_class=target,
            )
    return batch


def override(decision, outcome, reason, user):
    """The DOS (while the list is with the class teacher or the DOS) or the director (once
    recommended) promotes, demotes or passes a learner whatever the marks say."""
    if decision.batch.status not in (B.PROPOSED, B.SUBMITTED, B.RECOMMENDED):
        raise BusinessRuleError({"detail": "This list is approved; undo the approval to change it."})
    if outcome not in O.values or outcome == O.REVIEW:
        raise BusinessRuleError({"final": "Choose promote, probation, repeat, demote or complete."})
    if not reason:
        raise BusinessRuleError({"reason": "Give a reason; it is kept with the decision."})
    school_class = decision.batch.school_class
    target = target_class(school_class, outcome)
    if outcome == O.DEMOTE and target is None:
        raise BusinessRuleError(
            {"final": f"No class promotes into {school_class}, so there is nowhere to demote to."}
        )
    decision.final = outcome
    decision.override_reason = reason
    decision.overridden_by = user
    decision.to_class = target
    decision.save()
    return decision


def comment(decision, text):
    """The class teacher's remark on a learner while reviewing the list."""
    if decision.batch.status != B.PROPOSED:
        raise BusinessRuleError({"detail": "The list has left the class teacher; comments are closed."})
    decision.teacher_comment = (text or "")[:300]
    decision.save(update_fields=["teacher_comment"])
    return decision


def submit(batch, user, note=""):
    """Class teacher: the list is reviewed; send it to the Director of Studies."""
    if batch.status != B.PROPOSED:
        raise BusinessRuleError({"detail": "Only a list with the class teacher can be sent to the DOS."})
    batch.status, batch.reviewed_by, batch.reviewed_at = B.SUBMITTED, user, timezone.now()
    batch.teacher_note = (note or "")[:500]
    batch.save()
    return batch


def recommend(batch, user, note=""):
    """DOS: recommend the list to the director for approval."""
    if batch.status not in (B.PROPOSED, B.SUBMITTED):
        raise BusinessRuleError(
            {"detail": "Only a list with the class teacher or the DOS can be recommended."}
        )
    unresolved = batch.decisions.filter(final=O.REVIEW).count()
    if unresolved:
        raise BusinessRuleError(
            {"detail": f"{unresolved} learner(s) are missing marks; decide for each before recommending."}
        )
    batch.status, batch.recommended_by, batch.recommended_at = B.RECOMMENDED, user, timezone.now()
    batch.dos_note = (note or "")[:500]
    batch.save()
    return batch


def send_back(batch, note=""):
    """DOS or director: return the list to the class teacher (e.g. to recheck marks)."""
    if batch.status not in (B.SUBMITTED, B.RECOMMENDED):
        raise BusinessRuleError({"detail": "Only a list with the DOS or the director can be sent back."})
    batch.status = B.PROPOSED
    batch.director_note = (note or "")[:500]
    batch.save()
    return batch


def promotion_note(decision):
    target = decision.to_class
    return {
        O.PROMOTE: f"Promoted to {target}" if target else "Promoted",
        O.PROBATION: f"Promoted to {target} on probation" if target else "Promoted on probation",
        O.REPEAT: f"To repeat {decision.batch.school_class}",
        O.DEMOTE: f"Moved down to {target}" if target else "Moved down",
        O.COMPLETE: f"Completed {decision.batch.school_class}",
    }.get(decision.final, "")


def approve(batch, user, note=""):
    """Director (or head teacher): the final approval, after the DOS's recommendation."""
    if batch.status != B.RECOMMENDED:
        raise BusinessRuleError(
            {"detail": "The DOS recommends the list first; then the director approves it."}
        )
    unresolved = batch.decisions.filter(final=O.REVIEW).count()
    if unresolved:
        raise BusinessRuleError({"detail": f"{unresolved} learner(s) still need a decision (missing marks)."})
    missing_target = batch.decisions.filter(
        final__in=[O.PROMOTE, O.PROBATION, O.DEMOTE], to_class__isnull=True
    ).count()
    if missing_target:
        raise BusinessRuleError({"detail": f"Set the next class for {batch.school_class} before approving."})
    with transaction.atomic():
        batch.status, batch.approved_by, batch.approved_at = B.APPROVED, user, timezone.now()
        batch.director_note = (note or "")[:500]
        batch.save()
        for decision in batch.decisions.select_related("to_class", "batch__school_class"):
            ReportCard.objects.filter(
                learner=decision.learner, term=batch.term, status=ReportCard.Status.DRAFT
            ).update(promotion_note=promotion_note(decision))
    return batch


def _assign_streams(batch, decisions, target_term):
    """Pick a stream in the destination class for each moving learner."""
    by_class = {}
    for d in decisions:
        by_class.setdefault(d.to_class_id, []).append(d)
    for decisions_in_class in by_class.values():
        to_class = decisions_in_class[0].to_class
        streams = list(to_class.streams.all())
        if not streams:
            continue
        current = {
            e.learner_id: e.stream
            for e in Enrolment.objects.filter(
                term=batch.term, learner__in=[d.learner for d in decisions_in_class]
            )
        }
        if batch.stream_policy == "keep":
            names = {s.name: s for s in streams}
            for d in decisions_in_class:
                old = current.get(d.learner_id)
                d.to_stream = names.get(old.name) if old else None
                d.to_stream = d.to_stream or streams[0]
        else:
            if batch.stream_policy == "performance":
                results = {
                    r.learner_id: r.average or 0 for r in ResultSummary.objects.filter(term=batch.term)
                }
                decisions_in_class.sort(key=lambda d: -results.get(d.learner_id, 0))
            # Snake order (1,2,3,3,2,1…) spreads strong and weaker learners evenly.
            order = streams + streams[::-1]
            for index, d in enumerate(decisions_in_class):
                d.to_stream = order[index % len(order)]


def apply(batch, target_term, user):
    """Open the new year for this class: enrol learners in their new classes and
    mark completers. Until the new term starts, undo() reverses it."""
    if batch.status != PromotionBatch.Status.APPROVED:
        raise BusinessRuleError({"detail": "The director must approve the list first."})
    if target_term.academic_year_id == batch.term.academic_year_id:
        raise BusinessRuleError({"detail": "Choose a term in the new academic year."})
    decisions = list(batch.decisions.select_related("learner", "to_class"))
    moving = [d for d in decisions if d.final in (O.PROMOTE, O.PROBATION, O.REPEAT, O.DEMOTE)]
    _assign_streams(batch, moving, target_term)
    with transaction.atomic():
        for d in decisions:
            if d.final == O.COMPLETE:
                LearnerExit.objects.create(
                    school=batch.school,
                    learner=d.learner,
                    kind=LearnerExit.Kind.COMPLETED,
                    date=batch.term.end_date,
                    reason=f"Completed {batch.school_class}",
                )
            elif d.to_class_id:
                enrolment, _ = Enrolment.objects.update_or_create(
                    school=batch.school,
                    learner=d.learner,
                    term=target_term,
                    defaults={
                        "school_class": d.to_class,
                        "stream": d.to_stream,
                        "residence": d.learner.residence,
                    },
                )
                d.created_enrolment = enrolment
            d.save()
        batch.status, batch.target_term, batch.applied_at = (
            PromotionBatch.Status.APPLIED,
            target_term,
            timezone.now(),
        )
        batch.save()
    return batch


def undo(batch):
    if batch.status == B.APPROVED:
        # Back to the director's desk; the class teacher's and DOS's work is kept.
        batch.status = B.RECOMMENDED
        batch.save()
        return batch
    if batch.status != PromotionBatch.Status.APPLIED:
        raise BusinessRuleError({"detail": "Only approved or applied batches can be undone."})
    if batch.target_term and batch.target_term.start_date <= timezone.localdate():
        raise BusinessRuleError({"detail": "The new term has started; promotions can no longer be undone."})
    with transaction.atomic():
        for d in batch.decisions.select_related("learner"):
            if d.created_enrolment_id:
                Enrolment.objects.filter(pk=d.created_enrolment_id).delete()
                d.created_enrolment = None
                d.save()
            if d.final == O.COMPLETE:
                LearnerExit.objects.filter(learner=d.learner, kind=LearnerExit.Kind.COMPLETED).delete()
                d.learner.status = Learner.Status.ACTIVE
                d.learner.save()
        batch.status = PromotionBatch.Status.UNDONE
        batch.save()
    return batch
