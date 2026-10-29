"""Sample past results so Performance history has something to show.

    python manage.py seed_history --school DemoPrimary-001 --year 2025

Creates the year with its three terms on the standard Ugandan dates (closed), puts each
learner enrolled now into the class below for that year, and gives every term an approved
end-of-term exam with marks, computed results and published report cards. Learners' marks
drift gently from term to term so the trends are visible. Running it again changes nothing.
Meant for demonstration schools only.
"""

import random
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assessment.grading import compute_class_results
from apps.assessment.models import Exam, Mark, MarkSheet
from apps.assessment.reports import generate_report_cards, publish
from apps.assessment.services import prepare_sheets
from apps.core.models import School
from apps.learners.models import Enrolment
from apps.schoolsetup.calendar import generate_year
from apps.schoolsetup.models import SchoolClass, current_term


class Command(BaseCommand):
    help = "Add a past year of sample results to a demonstration school."

    def add_arguments(self, parser):
        parser.add_argument("--school", required=True, help="School ID, e.g. DemoPrimary-001")
        parser.add_argument("--year", type=int, required=True, help="The past year to add, e.g. 2025")

    def handle(self, *args, school, year, **options):
        school_obj = School.objects.filter(code__iexact=school).first()
        if school_obj is None:
            raise CommandError(f"No school with School ID {school}.")
        now = current_term(school_obj)
        if now is None:
            raise CommandError("The school has no current term; add one first.")
        if int(now.start_date.year) <= year:
            raise CommandError(f"{year} is not in the past for this school (current term: {now}).")
        academic_year, _ = generate_year(school_obj, year)
        terms = list(academic_year.terms.order_by("number"))
        enrolments = list(
            Enrolment.objects.filter(term=now).select_related("learner", "school_class", "stream")
        )
        below = {
            c.next_class_id: c
            for c in SchoolClass.objects.filter(school=school_obj, next_class__isnull=False)
        }
        rng = random.Random(f"{school_obj.pk}-{year}")
        ability = {e.learner_id: rng.uniform(42, 86) for e in enrolments}
        made = 0
        with transaction.atomic():
            for index, term in enumerate(terms):
                classes = {}
                for e in enrolments:
                    then = below.get(e.school_class_id, e.school_class)
                    stream = then.streams.filter(name=e.stream.name).first() if e.stream else None
                    Enrolment.objects.get_or_create(
                        school=school_obj,
                        learner=e.learner,
                        term=term,
                        defaults={"school_class": then, "stream": stream, "residence": e.learner.residence},
                    )
                    classes[then.pk] = then
                for school_class in classes.values():
                    exam, created = Exam.objects.get_or_create(
                        school=school_obj,
                        term=term,
                        name=f"End of Term {term.number}",
                        defaults={"kind": "eot", "weight": 100},
                    )
                    exam.classes.add(school_class)
                    prepare_sheets(exam, school_class)
                    learners = [e for e in Enrolment.objects.filter(term=term, school_class=school_class)]
                    for sheet in MarkSheet.objects.filter(exam=exam, school_class=school_class):
                        if sheet.status == MarkSheet.Status.APPROVED:
                            continue
                        for e in learners:
                            drift = (index - 1) * rng.uniform(-3, 5)
                            score = max(5, min(99, ability[e.learner_id] + drift + rng.uniform(-12, 12)))
                            Mark.objects.update_or_create(
                                school=school_obj,
                                mark_sheet=sheet,
                                learner=e.learner,
                                defaults={"score": Decimal(str(round(score)))},
                            )
                        sheet.status = MarkSheet.Status.APPROVED
                        sheet.save()
                        made += 1
                    compute_class_results(term, school_class)
                    publish(generate_report_cards(term, school_class), None)
        self.stdout.write(
            self.style.SUCCESS(
                f"{school_obj.name}: {year} has {len(terms)} terms; {made} mark sheet(s) filled and approved."
            )
        )
