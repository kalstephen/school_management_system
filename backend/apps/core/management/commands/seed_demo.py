"""Create a realistic demo primary school so every screen has data.

    python manage.py seed_demo            # creates "Demo Primary School" once
    python manage.py seed_demo --reset    # deletes and recreates it

For development and demonstrations only: all demo accounts share one password.
"""

import datetime
import os
import random
import secrets

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Membership, RoleAssignment, User
from apps.assessment.models import Exam, Mark, MarkSheet
from apps.assessment.services import prepare_sheets
from apps.attendance.services import save_roll_call
from apps.communication.models import Notice
from apps.communication.services import publish_notice
from apps.core.context import acting_as
from apps.core.models import School
from apps.curriculum.models import Subject, SubjectAllocation
from apps.finance.models import (
    Budget,
    BudgetLine,
    Expense,
    ExpenseCategory,
    OtherIncome,
    PettyCashEntry,
    PettyCashFloat,
    Supplier,
)
from apps.finance.services import approve_expense, submit_expense
from apps.learners.models import Guardian, Learner, LearnerGuardian
from apps.learners.services import admit_learner
from apps.promotion.models import PromotionRule
from apps.schoolsetup.defaults import seed_school_defaults
from apps.schoolsetup.models import AcademicYear, CalendarEvent, SchoolClass, Stream, Term
from apps.staff.models import StaffProfile
from apps.subscriptions.models import Plan, Subscription
from apps.subscriptions.services import apply_plan
from apps.timetable.models import Period
from apps.timetable.services import generate_timetable

DEMO_NAME = "Demo Primary School"
# Passwords never live in the code: set them in the environment, or a random one is generated
# and printed once. They apply only to accounts this command creates.
PASSWORD = os.environ.get("SPEX_DEMO_PASSWORD") or secrets.token_urlsafe(9)
SUPERUSER = ("admin", os.environ.get("SPEX_SUPERUSER_PASSWORD") or secrets.token_urlsafe(12))
FIRST = [
    "Aisha",
    "Brian",
    "Catherine",
    "Daniel",
    "Esther",
    "Francis",
    "Grace",
    "Henry",
    "Irene",
    "Joseph",
    "Kevin",
    "Lydia",
    "Moses",
    "Naomi",
    "Oscar",
    "Patience",
    "Ronald",
    "Sarah",
    "Timothy",
    "Vivian",
    "Winnie",
    "Yusuf",
    "Zainab",
    "Allan",
    "Brenda",
    "Collins",
    "Doreen",
    "Emmanuel",
    "Faith",
    "Gloria",
]
LAST = [
    "Nakato",
    "Okello",
    "Namubiru",
    "Mugisha",
    "Atim",
    "Ssemakula",
    "Achieng",
    "Kato",
    "Nansubuga",
    "Opio",
    "Tumusiime",
    "Akello",
    "Wasswa",
    "Nalwoga",
    "Byaruhanga",
    "Apio",
    "Lubega",
    "Kyomuhendo",
    "Odongo",
    "Nabirye",
]
STAFF = [
    ("head", "Margaret", "Nambi", ["head_teacher"]),
    ("dos", "Peter", "Mukasa", ["dos"]),
    ("bursar", "Ruth", "Akena", ["bursar"]),
    ("director", "Samuel", "Kiggundu", ["director"]),
    ("nurse", "Joyce", "Auma", ["nurse"]),
    ("librarian", "Isaac", "Ochieng", ["librarian"]),
    ("store", "Agnes", "Namata", ["storekeeper"]),
    ("schooladmin", "Edward", "Sserwadda", ["school_admin"]),
    ("support", "Joseph", "Mutebi", ["staff"]),
]
TEACHERS = [
    ("t.english", "Florence", "Nalubega", "ENG"),
    ("t.maths", "Robert", "Ojok", "MTC"),
    ("t.science", "Harriet", "Kemigisha", "SCI"),
    ("t.sst", "Julius", "Barigye", "SST"),
    ("t.re", "Annet", "Nakirya", "RE"),
    ("t.literacy", "Simon", "Etyang", "LIT"),
]


class Command(BaseCommand):
    help = "Create a demo primary school with staff, learners, marks, attendance and expenses."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete the demo school first")

    def handle(self, *args, **options):
        random.seed(7)
        if options["reset"]:
            School.objects.filter(name=DEMO_NAME).delete()
        if School.objects.filter(name=DEMO_NAME).exists():
            self.stdout.write("Demo school already exists (use --reset to rebuild).")
            return
        with transaction.atomic():
            self.build()
        self.stdout.write(self.style.SUCCESS("Demo school ready."))
        self.stdout.write(
            f"Sign in with any of: head, dos, bursar, director, nurse, librarian, store, schooladmin, "
            f"t.maths, t.english ... - password {PASSWORD}"
        )
        shown = SUPERUSER[1] if self.superuser_created else "(existing password kept)"
        self.stdout.write(
            f"Super admin: {SUPERUSER[0]} / {shown}  (owner console and content manager at /admin/)"
        )

    def user(self, username, first, last, school=None, roles=(), scope=None):
        user, created = User.objects.get_or_create(
            username=username, defaults={"first_name": first, "last_name": last}
        )
        if created:
            user.set_password(PASSWORD)
            user.save()
        if school:
            membership = Membership.objects.create(school=school, user=user)
            for role in roles:
                scope_type, scope_id = scope or ("school", None)
                RoleAssignment.objects.create(
                    school=school, membership=membership, role=role, scope_type=scope_type, scope_id=scope_id
                )
        return user

    def build(self):
        today = timezone.localdate()
        self.superuser_created = not User.objects.filter(username=SUPERUSER[0]).exists()
        platform = self.user(SUPERUSER[0], "Platform", "Owner")
        if self.superuser_created:
            platform.set_password(SUPERUSER[1])
        platform.is_platform_admin = platform.is_staff = platform.is_superuser = True
        platform.save()

        school = School.objects.create(
            name=DEMO_NAME,
            short_name="DPS",
            motto="Knowledge is light",
            address="Plot 12, Ntinda, Kampala",
            phone="+256 700 000 000",
            email="info@demoprimary.ac.ug",
            report_card_footer="Fees are paid through SchoolPay.",
            region="Central",
            district="Kampala",
            county="Kampala Capital City",
            sub_county="Nakawa Division",
            parish="Ntinda",
            village="Ntinda II",
            registration_number="ME/P/10421",
            emis_number="EMIS-21007",
            ownership="private",
            levels="primary",
            established=2008,
            head_teacher_name="Margaret Nambi",
            head_teacher_phone="+256 772 100 200",
            director_name="Samuel Kiggundu",
            director_phone="+256 701 300 400",
            director_email="director@demoprimary.ac.ug",
        )
        plan, _ = Plan.objects.get_or_create(
            name="Professional",
            defaults={
                "max_learners": 700,
                "price_per_term": 149000,
                "included_addons": ["library", "sickbay", "stores"],
            },
        )
        Plan.objects.get_or_create(name="Basic", defaults={"max_learners": 300, "price_per_term": 99000})
        Plan.objects.get_or_create(
            name="Standard", defaults={"max_learners": 500, "price_per_term": 120000, "addon_choices": 1}
        )
        Subscription.objects.create(
            school=school,
            plan=plan,
            status="active",
            starts_on=today - datetime.timedelta(days=30),
            ends_on=today + datetime.timedelta(days=330),
        )
        apply_plan(school, plan, user=platform)

        head = self.user("head", "Margaret", "Nambi", school, ["head_teacher"])
        with acting_as(head, school):
            self.populate(school, today, head)

    def populate(self, school, today, head):
        seed_school_defaults(school, ["nursery", "primary"])
        year = AcademicYear.objects.create(
            school=school,
            name=str(today.year),
            is_current=True,
            start_date=today - datetime.timedelta(days=45),
            end_date=today + datetime.timedelta(days=270),
        )
        term = Term.objects.create(
            school=school,
            academic_year=year,
            number=1,
            status="open",
            start_date=today - datetime.timedelta(days=45),
            end_date=today + datetime.timedelta(days=45),
            next_term_begins=today + datetime.timedelta(days=70),
        )
        Term.objects.create(
            school=school,
            academic_year=year,
            number=2,
            start_date=today + datetime.timedelta(days=70),
            end_date=today + datetime.timedelta(days=160),
        )
        for username, first, last, roles in STAFF[1:]:
            user = self.user(username, first, last, school, roles)
            StaffProfile.objects.create(
                school=school,
                user=user,
                first_name=first,
                last_name=last,
                kind="teaching" if roles[0] in ("dos",) else "non_teaching",
                designation=roles[0],
            )
        StaffProfile.objects.create(
            school=school, user=head, first_name="Margaret", last_name="Nambi", designation="Head teacher"
        )

        classes = list(SchoolClass.objects.filter(school=school, section__level="primary").order_by("order"))
        for school_class in classes:
            for name in ("A", "B") if school_class.name in ("P5", "P6", "P7") else ():
                Stream.objects.create(school=school, school_class=school_class, name=name)
        subjects = {s.short_name: s for s in Subject.objects.filter(school=school, level="primary")}
        teachers = {}
        for username, first, last, code in TEACHERS:
            user = self.user(username, first, last, school, ["subject_teacher"])
            teachers[code] = StaffProfile.objects.create(
                school=school,
                user=user,
                first_name=first,
                last_name=last,
                kind="teaching",
                specialisation=subjects[code].name,
                max_periods_per_week=40,
                registration_number=f"TR{random.randint(10000, 99999)}",
            )
        p5 = SchoolClass.objects.get(school=school, name="P5")
        class_teacher = self.user(
            "ct.p5", "Lillian", "Babirye", school, ["class_teacher"], scope=("class", p5.id)
        )
        StaffProfile.objects.create(
            school=school, user=class_teacher, first_name="Lillian", last_name="Babirye", kind="teaching"
        )
        for school_class in classes:
            for code in ("ENG", "MTC", "SCI", "SST", "RE", "LIT"):
                SubjectAllocation.objects.create(
                    school=school,
                    teacher=teachers[code],
                    subject=subjects[code],
                    school_class=school_class,
                    periods_per_week=5 if code in ("ENG", "MTC") else 3,
                )

        learners_by_class = {}
        for school_class in classes:
            streams = list(school_class.streams.all()) or [None]
            rows = []
            for index in range(14):
                first, last = random.choice(FIRST), random.choice(LAST)
                guardian = Guardian.objects.create(
                    school=school,
                    full_name=f"{random.choice(FIRST)} {last}",
                    phone=f"07{random.randint(10000000, 99999999)}",
                    email=f"guardian{school_class.order}{index}@example.com" if index % 3 == 0 else "",
                )
                learner = admit_learner(
                    school,
                    {
                        "first_name": first,
                        "last_name": last,
                        "sex": random.choice("MF"),
                        "admitted_on": year.start_date,
                        "date_of_birth": datetime.date(
                            today.year - 6 - school_class.order % 10,
                            random.randint(1, 12),
                            random.randint(1, 28),
                        ),
                        "residence": random.choice(["day", "day", "boarding"]),
                        "lin": f"LIN{random.randint(1000000, 9999999)}",
                        "year_of_entry": today.year - (school_class.order % 10),
                    },
                    term=term,
                    school_class=school_class,
                    stream=streams[index % len(streams)],
                )
                LearnerGuardian.objects.create(
                    school=school, learner=learner, guardian=guardian, relationship="Parent", is_primary=True
                )
                rows.append(learner)
            learners_by_class[school_class.id] = rows
        Learner.objects.filter(pk=learners_by_class[p5.id][0].pk).update(
            allergies="Penicillin", has_medical_alert=True
        )

        for order, (start, end) in enumerate(
            [
                ("08:00", "08:40"),
                ("08:40", "09:20"),
                ("09:20", "10:00"),
                ("10:20", "11:00"),
                ("11:00", "11:40"),
                ("11:40", "12:20"),
                ("14:00", "14:40"),
                ("14:40", "15:20"),
            ]
        ):
            Period.objects.create(
                school=school,
                name=f"Period {order + 1}",
                order=order,
                start_time=datetime.time.fromisoformat(start),
                end_time=datetime.time.fromisoformat(end),
            )
        generate_timetable(school, term)

        for days_ago in range(12, -1, -1):
            date = today - datetime.timedelta(days=days_ago)
            if date.weekday() >= 5:
                continue
            for school_class in classes:
                records = [
                    {"learner": l.id, "status": "absent" if random.random() < 0.06 else "present"}
                    for l in learners_by_class[school_class.id]
                ]
                save_roll_call(school, head, term, date, school_class, None, records)

        bot = Exam.objects.create(
            school=school,
            term=term,
            name="Beginning of term",
            kind="bot",
            weight=30,
            start_date=term.start_date + datetime.timedelta(days=7),
        )
        mot = Exam.objects.create(
            school=school,
            term=term,
            name="Mid-term",
            kind="mot",
            weight=70,
            start_date=today - datetime.timedelta(days=5),
        )
        for exam_obj in (bot, mot):
            exam_obj.classes.set(classes)
            for school_class in classes:
                prepare_sheets(exam_obj, school_class)
        ability = {l.id: random.gauss(64, 13) for rows in learners_by_class.values() for l in rows}
        for sheet in MarkSheet.objects.filter(school=school).select_related("exam", "school_class"):
            for learner in learners_by_class[sheet.school_class_id]:
                if sheet.subject.category != "core":
                    continue
                score = max(5, min(100, round(ability[learner.id] + random.gauss(0, 9))))
                Mark.objects.create(school=school, mark_sheet=sheet, learner=learner, score=score)
            sheet.status = (
                "approved"
                if sheet.exam_id == bot.id or sheet.school_class.name in ("P6", "P7")
                else ("submitted" if sheet.subject.short_name in ("ENG", "MTC") else "draft")
            )
            sheet.save()
        for school_class in classes:
            PromotionRule.objects.create(
                school=school,
                school_class=school_class,
                measure="annual_average",
                pass_mark=50,
                probation_mark=45,
            ) if not school_class.is_candidate_class else None

        bursar = User.objects.get(username="bursar")
        categories = {c.name: c for c in ExpenseCategory.objects.filter(school=school)}
        supplier = Supplier.objects.create(school=school, name="Mukwano Wholesalers", phone="0414 000 111")
        budget = Budget.objects.create(school=school, term=term, is_approved=True)
        for name, amount in [
            ("Feeding / kitchen", 18_000_000),
            ("Salaries & allowances", 42_000_000),
            ("Utilities", 3_000_000),
            ("Academics", 4_500_000),
            ("Maintenance & repairs", 2_000_000),
            ("Transport", 1_500_000),
        ]:
            BudgetLine.objects.create(school=school, budget=budget, category=categories[name], amount=amount)
        samples = [
            ("Feeding / kitchen", "Posho 20 bags", 1_900_000),
            ("Feeding / kitchen", "Beans 10 bags", 1_450_000),
            ("Feeding / kitchen", "Sugar 5 bags", 950_000),
            ("Utilities", "Yaka electricity", 420_000),
            ("Utilities", "Internet (monthly)", 250_000),
            ("Academics", "Exam printing", 680_000),
            ("Academics", "Chalk and markers", 120_000),
            ("Transport", "Fuel for school van", 300_000),
            ("Maintenance & repairs", "Fix classroom roof", 1_250_000),
            ("Salaries & allowances", "Staff salaries (total)", 13_500_000),
        ]
        with acting_as(bursar, school):
            for index, (category, description, amount) in enumerate(samples * 2):
                date = today - datetime.timedelta(days=(index * 2) % 40)
                expense = Expense.objects.create(
                    school=school,
                    date=date,
                    category=categories[category],
                    description=description,
                    amount=amount,
                    method="bank" if amount > 500_000 else "cash",
                    payee="Various",
                    supplier=supplier if category == "Feeding / kitchen" else None,
                )
                submit_expense(expense, bursar)
                if expense.status == Expense.Status.PENDING and index % 6:  # leave a few waiting for approval
                    approver = User.objects.get(
                        username="director" if expense.required_level == 3 else "head"
                    )
                    approve_expense(expense, approver)
            petty = PettyCashFloat.objects.create(
                school=school,
                name="Front office float",
                custodian=bursar,
                float_amount=500_000,
                replenish_below=150_000,
            )
            PettyCashEntry.objects.create(
                school=school,
                float=petty,
                date=today - datetime.timedelta(days=10),
                kind="topup",
                amount=500_000,
                description="Float",
            )
        OtherIncome.objects.create(
            school=school,
            date=today - datetime.timedelta(days=20),
            source="capitation",
            description="UPE capitation grant",
            amount=6_400_000,
        )
        CalendarEvent.objects.create(
            school=school, title="Sports day", kind="event", start_date=today + datetime.timedelta(days=12)
        )
        CalendarEvent.objects.create(
            school=school,
            title="End of term exams",
            kind="exam",
            start_date=today + datetime.timedelta(days=30),
        )
        notice = Notice.objects.create(
            school=school,
            title="Staff meeting on Friday",
            body="All staff meet in the library at 4:00 pm to review mid-term results.",
            pinned=True,
        )
        publish_notice(notice)
