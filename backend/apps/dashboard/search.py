"""Learner search: partial or misspelt names in any order, admission number, LIN,
class or stream, guardian name or phone. Former learners stay searchable."""

import difflib

from django.db.models import Q

from apps.learners.models import Enrolment, Learner
from apps.schoolsetup.models import current_term


def _row(learner, enrolment):
    return {
        "id": learner.id,
        "name": learner.full_name,
        "adm_no": learner.adm_no,
        "lin": learner.lin,
        "class": enrolment.school_class.name if enrolment else None,
        "stream": enrolment.stream.name if enrolment and enrolment.stream else None,
        "status": learner.status,
        "photo": learner.photo.url if learner.photo else None,
    }


def search_learners(request, query, limit=20):
    school = request.school
    query = (query or "").strip()
    if len(query) < 2:
        return []
    term = current_term(school)
    base = Learner.objects.filter(school=school)
    tokens = query.split()
    match = Q()
    for token in tokens:
        match &= (
            Q(first_name__icontains=token)
            | Q(last_name__icontains=token)
            | Q(other_names__icontains=token)
            | Q(adm_no__icontains=token)
            | Q(lin__icontains=token)
            | Q(guardian_links__guardian__full_name__icontains=token)
            | Q(guardian_links__guardian__phone__icontains=token)
        )
    found = list(base.filter(match).distinct()[:limit])
    if term and len(found) < limit:
        class_match = Enrolment.objects.filter(term=term, school=school).filter(
            Q(school_class__name__iexact=query)
            | Q(stream__name__iexact=query)
            | Q(school_class__name__iexact=query.replace(" ", ""))
        )
        stream_like = query.replace(" ", "").upper()
        extra = [e.learner for e in class_match.select_related("learner")[: limit - len(found)]]
        if not extra:
            # "P5B" style: class name followed by stream name
            for enrolment in Enrolment.objects.filter(
                term=term, school=school, stream__isnull=False
            ).select_related("learner", "school_class", "stream"):
                if f"{enrolment.school_class.name}{enrolment.stream.name}".upper() == stream_like:
                    extra.append(enrolment.learner)
                    if len(found) + len(extra) >= limit:
                        break
        ids = {l.id for l in found}
        found += [l for l in extra if l.id not in ids]
    if not found:
        # Misspelt names: compare against every learner's name.
        names = {}
        for learner in base.only("id", "first_name", "last_name", "other_names"):
            names[learner.id] = f"{learner.first_name} {learner.last_name} {learner.other_names}".lower()
        scored = []
        q = query.lower()
        for learner_id, name in names.items():
            parts = name.split()
            score = max(
                [difflib.SequenceMatcher(None, q, name).ratio()]
                + [difflib.SequenceMatcher(None, t, p).ratio() for t in q.split() for p in parts]
            )
            if score >= 0.75:
                scored.append((score, learner_id))
        scored.sort(reverse=True)
        found = list(base.filter(pk__in=[i for _, i in scored[:limit]]))
        order = {i: n for n, (_, i) in enumerate(scored)}
        found.sort(key=lambda l: order.get(l.id, 0))
    enrolments = {}
    if term:
        enrolments = {
            e.learner_id: e
            for e in Enrolment.objects.filter(term=term, learner__in=found).select_related(
                "school_class", "stream"
            )
        }
    return [_row(l, enrolments.get(l.id)) for l in found[:limit]]
