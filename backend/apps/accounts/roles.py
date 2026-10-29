"""Access levels, roles and the permissions each one grants.

From the top:
  Super admin (platform)  – Django superuser: everything in the content manager, creates the
                            platform team. Not a school role.
  Platform team           – registers schools, plans, add-ons and each school's first
                            administrator; reads school records only with the school's
                            time-limited support grant.
  School roles            – ranked below (director highest, general staff lowest).

A user can hold several roles in a school, each limited to a scope (a class, a
department, a store); their permissions are the union of all roles held, plus the
baseline every active staff member gets.
"""

VIEW_ALL = {
    "dashboard.view",
    "setup.view",
    "learners.view",
    "admissions.view",
    "staff.view",
    "curriculum.view",
    "timetable.view",
    "attendance.view",
    "assessment.view",
    "reports.view",
    "promotion.view",
    "discipline.view",
    "communication.view",
    "finance.view",
    "library.view",
    "stores.view",
}

# Every staff member can raise a requisition (it then climbs the ranks above them).
BASE = {"dashboard.view", "communication.view", "timetable.view", "finance.request"}

# School setup (profile, years and terms, classes, streams, subjects) is done in the owner
# console. No school role holds this permission, so schools see their setup read-only.
PLATFORM_ONLY = "setup.platform"

# Every active member of a school has these, even with no role yet ("normal user").
MEMBER_BASE = BASE

ROLE_PERMS = {
    "staff": set(BASE),
    "school_admin": BASE
    | {
        "setup.view",
        "setup.manage",
        "users.manage",
        "audit.view",
        "learners.view",
        "staff.view",
        "curriculum.view",
        "communication.post",
        "admissions.view",
        "admissions.manage",
        "classes.assign",
        "staff.manage",
    },
    "director": VIEW_ALL
    | {
        "setup.manage",
        "users.manage",
        "classes.assign",
        "learners.manage",
        "learners.enrol",
        "admissions.manage",
        "finance.approve",
        "promotion.manage",
        "promotion.review",
        "promotion.approve",
        "reports.approve",
        "reports.generate",
        "communication.post",
        "hr.approve",
        "staff.manage",
        "curriculum.manage",
        "curriculum.propose",
        "curriculum.approve",
        "timetable.manage",
        "assessment.manage",
        "discipline.manage",
        "finance.manage",
        "finance.request",
        "library.manage",
        "stores.manage",
    },
    "head_teacher": VIEW_ALL
    | {
        "setup.manage",
        "classes.assign",
        "learners.manage",
        "learners.enrol",
        "admissions.manage",
        "staff.manage",
        "hr.approve",
        "curriculum.manage",
        "curriculum.propose",
        "curriculum.approve",
        "timetable.manage",
        "attendance.take",
        "assessment.manage",
        "marks.review",
        "marks.approve",
        "reports.approve",
        "reports.comment",
        "reports.generate",
        "promotion.manage",
        "promotion.review",
        "promotion.approve",
        "discipline.manage",
        "communication.post",
        "finance.approve",
        "finance.request",
        "health.view",
        "health.manage",
        "library.manage",
        "stores.manage",
    },
    "dos": BASE
    | {
        "setup.view",
        "classes.assign",
        "learners.view",
        "learners.manage",
        "learners.enrol",
        "admissions.view",
        "admissions.manage",
        "staff.view",
        "curriculum.view",
        "curriculum.manage",
        "curriculum.propose",
        "curriculum.approve",
        "timetable.manage",
        "attendance.view",
        "attendance.take",
        "assessment.view",
        "assessment.manage",
        "marks.review",
        "marks.approve",
        "reports.view",
        "reports.comment",
        "reports.generate",
        "promotion.view",
        "promotion.manage",
        "promotion.review",
        "discipline.view",
        "discipline.manage",
        "finance.request",
        "communication.post",
    },
    "hod": BASE
    | {
        "learners.view",
        "curriculum.view",
        "curriculum.manage",
        "curriculum.propose",
        "assessment.view",
        "marks.enter",
        "marks.review",
        "attendance.view",
        "reports.view",
        "finance.request",
    },
    "class_teacher": BASE
    | {
        "learners.view",
        "learners.enrol",
        "curriculum.view",
        "attendance.take",
        "attendance.view",
        "assessment.view",
        "marks.enter",
        "reports.view",
        "reports.comment",
        "reports.generate",
        "discipline.view",
        "discipline.manage",
        "promotion.view",
        "promotion.review",
        "finance.request",
    },
    "subject_teacher": BASE
    | {
        "learners.view",
        "curriculum.view",
        "assessment.view",
        "marks.enter",
        "attendance.take",
        "attendance.view",
    },
    "bursar": BASE | {"finance.view", "finance.manage", "finance.approve", "finance.request"},
    "storekeeper": BASE | {"stores.view", "stores.manage", "finance.request"},
    "nurse": BASE | {"learners.view", "health.view", "health.manage"},
    "librarian": BASE | {"learners.view", "library.view", "library.manage"},
}

ROLE_LABELS = {
    "staff": "General staff",
    "school_admin": "School administrator",
    "director": "Director / proprietor",
    "head_teacher": "Head teacher",
    "dos": "Deputy / Director of Studies",
    "hod": "Head of department",
    "class_teacher": "Class teacher",
    "subject_teacher": "Subject teacher",
    "bursar": "Bursar / accounts",
    "storekeeper": "Storekeeper",
    "nurse": "Nurse",
    "librarian": "Librarian",
}

# Roles that see every class in the school, not just the classes they are assigned to.
SCHOOL_WIDE_ROLES = {"school_admin", "director", "head_teacher", "dos"}

# Expense approval levels: a higher level can approve anything a lower level can.
APPROVAL_LEVELS = {"bursar": 1, "head_teacher": 2, "director": 3}

ALL_PERMS = sorted(set().union(*ROLE_PERMS.values()))

# Rank decides who may manage whom: you can assign, remove or edit only roles and people
# ranked below your own highest role. The director (top of the school) may also assign
# another director. Ranks are about authority over accounts, not about which data a role sees.
ROLE_RANK = {
    "director": 100,
    "school_admin": 90,
    "head_teacher": 80,
    "dos": 70,
    "bursar": 60,
    "hod": 50,
    "class_teacher": 40,
    "subject_teacher": 30,
    "storekeeper": 30,
    "nurse": 30,
    "librarian": 30,
    "staff": 10,
}
TOP_SCHOOL_RANK = 100

ROLE_DESCRIPTIONS = {
    "director": (
        "Owner level. Can act in every module: enrolment, staff, timetable, exams, expenses, "
        "library and stores; final promotion approval, top expense approvals and all user "
        "accounts. Marks approval stays with the DOS and health records with the nurse."
    ),
    "school_admin": (
        "Runs the system for the school: settings, user accounts and roles, audit log. No "
        "marks or finance detail."
    ),
    "head_teacher": (
        "Everything academic and operational; approves report cards, promotion, leave and "
        "expenses within limit."
    ),
    "dos": (
        "Curriculum, timetable, exams, mark approval, enrolment, admissions and promotion "
        "recommendations. No finance."
    ),
    "bursar": (
        "The Finance module: expenses, petty cash, budgets, suppliers and reports. No "
        "marks or health records."
    ),
    "hod": "Department mark sheets (review), schemes of work and requisitions.",
    "class_teacher": (
        "Their class: daily register, marks for every subject, report cards (prepare, comment, "
        "print), enrolment, promotion review and discipline."
    ),
    "subject_teacher": "Mark entry for allocated subjects and classes; lesson attendance.",
    "storekeeper": "Stock in and out, scholastic requirements and the asset register.",
    "nurse": "Sickbay and confidential health records.",
    "librarian": "Library catalogue, issue and return.",
    "staff": "Baseline for every staff account: dashboard, notices, timetable and own leave requests.",
}
