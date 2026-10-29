import { ActionIcon, Badge, Button, Group, Modal, MultiSelect, Select, Stack, Tabs, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconCheck, IconUserStar, IconX } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, get, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { CrudPage } from "@/components/CrudPage";
import { useClasses, SEX_OPTIONS } from "@/hooks/useSchool";
import { date, titleCase, today } from "@/utils/format";

const staffSelect = { endpoint: "/staff/", label: "full_name" };
const LOGIN_ROLES = [
  { value: "subject_teacher", label: "Teacher" },
  { value: "hod", label: "Head of department" },
  { value: "dos", label: "Director of Studies / deputy" },
  { value: "bursar", label: "Bursar" },
  { value: "nurse", label: "Nurse" },
  { value: "librarian", label: "Librarian" },
  { value: "storekeeper", label: "Storekeeper" },
  { value: "staff", label: "General staff (support)" },
];
const LEVEL_LABEL: Record<string, string> = { nursery: "Nursery", primary: "Primary", olevel: "O-Level", alevel: "A-Level" };
const subjectSource = { endpoint: "/subjects/", label: (s: any) => `${s.name} (${LEVEL_LABEL[s.level] ?? s.level})` };

interface ClassPost {
  key: string;
  label: string;
  class_teacher: number | null;
  class_teacher_name: string | null;
  deputy: number | null;
  deputy_name: string | null;
}

/** Every class and stream, labelled with who holds each post now, for the pickers. */
function useClassPosts() {
  const { data = [] } = useQuery({ queryKey: ["class-teachers"], queryFn: () => get<ClassPost[]>("/class-teachers/") });
  const options = (post: "class_teacher" | "deputy", staffId?: number) =>
    data.map((c) => {
      const holder = post === "class_teacher" ? c.class_teacher_name : c.deputy_name;
      const holderId = post === "class_teacher" ? c.class_teacher : c.deputy;
      return { value: c.key, label: holder && holderId !== staffId ? `${c.label} — now ${holder}` : c.label };
    });
  return { posts: data, options };
}

/** The DOS, head teacher, director or administrator sets a teacher's class-teacher posts and
 *  subjects without editing the rest of the profile. */
function ClassAndSubjects({ staff, onClose }: { staff: any; onClose: () => void }) {
  const { can } = useAuth();
  const client = useQueryClient();
  const { options } = useClassPosts();
  const current = (post: string) => staff.class_posts.find((p: any) => p.post === post)?.target ?? null;
  const [lead, setLead] = useState<string | null>(current("class_teacher"));
  const [deputy, setDeputy] = useState<string | null>(current("deputy"));
  const [subjects, setSubjects] = useState<string[]>((staff.subjects ?? []).map(String));
  const { data: subjectRows } = useQuery({ queryKey: ["subjects-all"], queryFn: () => get("/subjects/", { page_size: 300 }) });
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      if (can("classes.assign")) {
        for (const [post, value] of [["class_teacher", lead], ["deputy", deputy]] as const) {
          const before = current(post);
          if (value === before) continue;
          if (before) await post_(before, post, null);
          if (value) await post_(value, post, staff.id);
        }
      }
      if (can("curriculum.manage")) await post(`/staff/${staff.id}/specialisations/`, { subjects: subjects.map(Number) });
      notifications.show({ color: "green", message: `Saved for ${staff.full_name}` });
      client.invalidateQueries({ queryKey: ["list", "/staff/"] });
      client.invalidateQueries({ queryKey: ["class-teachers"] });
      client.invalidateQueries({ queryKey: ["classes"] });
      onClose();
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  };
  const post_ = (target: string, post_kind: string, staffId: number | null) =>
    post("/class-teachers/", { target, post: post_kind, staff: staffId });

  return (
    <Modal opened onClose={onClose} title={`${staff.full_name}: class and subjects`} centered size="lg">
      <Stack>
        {can("classes.assign") && (
          <>
            <Select label="Class teacher of" data={options("class_teacher", staff.id)} value={lead} onChange={setLead} clearable searchable placeholder="Not a class teacher" description="One class or stream. If it has a class teacher already, they are replaced." />
            <Select label="Deputy class teacher of" data={options("deputy", staff.id)} value={deputy} onChange={setDeputy} clearable searchable placeholder="Not a deputy" description="Stands in for the class teacher, with the same access." />
          </>
        )}
        {can("curriculum.manage") && (
          <MultiSelect
            label="Subject specialisation"
            description="Every subject they can teach, at any level. Used to fill “who teaches what” and the timetable."
            data={(subjectRows?.results ?? []).map((s: any) => ({ value: String(s.id), label: subjectSource.label(s) }))}
            value={subjects}
            onChange={setSubjects}
            searchable
            clearable
            placeholder="Choose subjects"
          />
        )}
        <Group justify="flex-end">
          <Button onClick={save} loading={busy}>Save</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

const LEAVE_KINDS = ["annual", "sick", "maternity", "paternity", "study", "compassionate"].map((k) => ({ value: k, label: titleCase(k) }));

export default function StaffPage() {
  const { can, me } = useAuth();
  const client = useQueryClient();
  const { options: classOptions } = useClasses();
  const { options: postOptions } = useClassPosts();
  const [posting, setPosting] = useState<any>(null);

  const decide = (row: any, action: "approve" | "reject") =>
    modalsConfirm({
      title: `${action === "approve" ? "Approve" : "Reject"} leave for ${row.staff_name}?`,
      message: `${titleCase(row.kind)} leave, ${row.days} day(s) from ${date(row.start_date)}.`,
      confirmLabel: action === "approve" ? "Approve" : "Reject",
      danger: action === "reject",
      onConfirm: async () => {
        try {
          await post(`/leave-requests/${row.id}/${action}/`);
          client.invalidateQueries({ queryKey: ["list", "/leave-requests/"] });
        } catch (error) {
          notifications.show({ color: "red", message: errorMessage(error) });
        }
      },
    });

  return (
    <>
      {posting && <ClassAndSubjects staff={posting} onClose={() => setPosting(null)} />}
      <PageHeader title="Staff & HR" description="Staff records, teaching allocations and load, leave, duty roster and staff attendance." />
      <Tabs defaultValue="staff" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="staff">Staff</Tabs.Tab>
          <Tabs.Tab value="allocations">Teaching allocations</Tabs.Tab>
          <Tabs.Tab value="leave">Leave</Tabs.Tab>
          <Tabs.Tab value="duty">Duty roster</Tabs.Tab>
          {can("staff.view") && <Tabs.Tab value="attendance">Staff attendance</Tabs.Tab>}
        </Tabs.List>
        <Tabs.Panel value="staff">
          <CrudPage
            hideHeader
            title="Staff"
            singular="staff member"
            formHelp="A member of staff. Teachers can get a sign-in now; set their subjects and class-teacher post here or later with the person button."
            endpoint="/staff/"
            writePerm="staff.manage"
            toForm={(r: any) => ({
              ...r,
              department: r.department && String(r.department),
              user: r.user && String(r.user),
              subjects: (r.subjects ?? []).map(String),
              class_teacher_of: r.class_posts?.find((p: any) => p.post === "class_teacher")?.target ?? null,
              deputy_class_teacher_of: r.class_posts?.find((p: any) => p.post === "deputy")?.target ?? null,
            })}
            extraActions={(row: any) =>
              row.kind === "teaching" && (can("classes.assign") || can("curriculum.manage")) ? (
                <Tooltip label="Class teacher post and subjects">
                  <ActionIcon variant="light" onClick={() => setPosting(row)} aria-label="Class teacher post and subjects">
                    <IconUserStar size={16} />
                  </ActionIcon>
                </Tooltip>
              ) : null
            }
            exportable
            defaults={{ kind: "teaching", contract_type: "permanent", status: "active", create_login: true, login_role: "subject_teacher" }}
            filters={[
              { name: "kind", label: "Type", options: [{ value: "teaching", label: "Teaching" }, { value: "non_teaching", label: "Non-teaching" }] },
              { name: "status", label: "Status", options: [{ value: "active", label: "Active" }, { value: "on_leave", label: "On leave" }, { value: "left", label: "Left" }] },
              { name: "department", label: "Department", optionsFrom: { endpoint: "/departments/", label: "name" } },
            ]}
            columns={[
              { key: "full_name", label: "Name", render: (r: any) => <>{r.full_name}<br /><small style={{ color: "var(--mantine-color-dimmed)" }}>{r.designation || titleCase(r.kind)}</small></> },
              { key: "phone", label: "Phone" },
              {
                key: "class_posts",
                label: "Class teacher of",
                render: (r: any) =>
                  r.class_posts?.length ? (
                    <Stack gap={2}>
                      {r.class_posts.map((p: any) => (
                        <Text key={p.target + p.post} size="sm">
                          {p.label} {p.post === "deputy" && <Badge size="xs" variant="light" color="grape">deputy</Badge>}
                        </Text>
                      ))}
                    </Stack>
                  ) : (
                    "–"
                  ),
              },
              { key: "subject_names", label: "Subjects", render: (r: any) => (r.subject_names?.length ? <Text size="xs" lineClamp={2}>{r.subject_names.join(", ")}</Text> : "–") },
              { key: "username", label: "Sign-in", render: (r: any) => r.username ?? <small style={{ color: "var(--mantine-color-dimmed)" }}>None</small> },
              { key: "department_name", label: "Department", render: (r: any) => r.department_name ?? "–" },
              { key: "registration_number", label: "Reg. / TMIS", render: (r: any) => [r.registration_number, r.tmis_number].filter(Boolean).join(" · ") || "–" },
              { key: "teaching_load", label: "Periods/week", render: (r: any) => (r.kind === "teaching" ? `${r.teaching_load}${r.max_periods_per_week ? ` / ${r.max_periods_per_week}` : ""}` : "–") },
              { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} /> },
            ]}
            fields={[
              { name: "first_name", label: "First name", required: true, placeholder: "e.g. Grace" },
              { name: "last_name", label: "Surname", required: true, placeholder: "e.g. Akello" },
              { name: "other_names", label: "Other names" },
              { name: "sex", label: "Sex", type: "select", options: SEX_OPTIONS },
              { name: "staff_no", label: "Staff number" },
              { name: "nin", label: "National ID (NIN)" },
              { name: "phone", label: "Phone", placeholder: "e.g. 0772 123456" },
              { name: "email", label: "Email", type: "email", placeholder: "Optional" },
              { name: "kind", label: "Type", type: "select", options: [{ value: "teaching", label: "Teaching" }, { value: "non_teaching", label: "Non-teaching" }] },
              { name: "designation", label: "Designation", placeholder: "e.g. Teacher, Deputy head" },
              { name: "department", label: "Department", type: "select", optionsFrom: { endpoint: "/departments/", label: "name" } },
              { name: "class_teacher_of", label: "Class teacher of", type: "select", options: (v) => postOptions("class_teacher", v.id), description: "One class or stream. If it already has a class teacher, they are replaced. Leave empty if not a class teacher.", hidden: (v) => v.kind === "non_teaching" || !can("classes.assign") },
              { name: "deputy_class_teacher_of", label: "Deputy class teacher of", type: "select", options: (v) => postOptions("deputy", v.id), description: "Stands in for the class teacher with the same access.", hidden: (v) => v.kind === "non_teaching" || !can("classes.assign") },
              { name: "subjects", label: "Subject specialisation", type: "multiselect", optionsFrom: subjectSource, span: 12, description: "Every subject this teacher can teach, at any level (nursery, primary, secondary). Used to suggest who teaches what and to build the timetable.", hidden: (v) => v.kind === "non_teaching" },
              { name: "create_login", label: "Give this person a sign-in now (teachers need one to enter marks and see their timetable)", type: "checkbox", span: 12, hidden: (v) => !!v.id },
              { name: "login_username", label: "Username", placeholder: "e.g. gakello", description: "They sign in with your School ID and this username.", hidden: (v) => !!v.id || !v.create_login },
              { name: "login_password", label: "First password", type: "password", placeholder: "At least 8 characters", description: "They can change it after signing in.", hidden: (v) => !!v.id || !v.create_login },
              { name: "login_role", label: "Access level", type: "select", options: LOGIN_ROLES, description: "Class-teacher access is given when you pick them as a class's teacher.", hidden: (v) => !!v.id || !v.create_login },
              { name: "user", label: "Linked sign-in", type: "select", optionsFrom: { endpoint: "/users/", value: "user_id", label: (u: any) => `${u.first_name} ${u.last_name} (${u.username})` }, description: "The account this staff record belongs to.", hidden: (v) => !v.id },
              { name: "registration_number", label: "Teacher registration number" },
              { name: "tmis_number", label: "TMIS number" },
              { name: "highest_qualification", label: "Highest qualification" },
              { name: "specialisation", label: "Specialisation notes (optional)", placeholder: "e.g. Trained in early childhood; music" },
              { name: "contract_type", label: "Contract", type: "select", options: ["permanent", "contract", "part_time", "volunteer"].map((v) => ({ value: v, label: titleCase(v) })) },
              { name: "max_periods_per_week", label: "Maximum periods per week", type: "number" },
              { name: "contract_start", label: "Contract start", type: "date" },
              { name: "contract_end", label: "Contract end", type: "date" },
              { name: "status", label: "Status", type: "select", options: [{ value: "active", label: "Active" }, { value: "on_leave", label: "On leave" }, { value: "left", label: "Left" }] },
              { name: "photo", label: "Photo", type: "file" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="allocations">
          <CrudPage
            hideHeader
            title="Teaching allocations"
            singular="allocation"
            formHelp="Say which teacher takes a subject in a class. That teacher enters its marks and the timetable is built from these allocations."
            endpoint="/allocations/"
            writePerm="curriculum.manage"
            toForm={(r: any) => ({ ...r, teacher: String(r.teacher), subject: String(r.subject), school_class: String(r.school_class), stream: r.stream && String(r.stream) })}
            filters={[
              { name: "teacher", label: "Teacher", optionsFrom: staffSelect },
              { name: "school_class", label: "Class", options: classOptions },
            ]}
            columns={[
              { key: "teacher_name", label: "Teacher" },
              { key: "subject_name", label: "Subject" },
              { key: "class_name", label: "Class" },
              { key: "periods_per_week", label: "Periods/week" },
            ]}
            fields={[
              { name: "teacher", label: "Teacher", type: "select", optionsFrom: { ...staffSelect, query: { kind: "teaching" } }, required: true },
              { name: "subject", label: "Subject", type: "select", optionsFrom: { endpoint: "/subjects/", label: (s: any) => `${s.name} (${s.level})` }, required: true },
              { name: "school_class", label: "Class", type: "select", options: classOptions, required: true },
              { name: "stream", label: "Stream (optional)", type: "select", optionsFrom: { endpoint: "/streams/", label: "label" } },
              { name: "periods_per_week", label: "Periods per week", type: "number", min: 1, max: 20 },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="leave">
          <CrudPage
            hideHeader
            title="Leave requests"
            singular="leave request"
            formHelp="Ask for leave. It goes to the head teacher or director to approve."
            endpoint="/leave-requests/"
            canDelete={false}
            defaults={{ start_date: today(), end_date: today() }}
            toForm={(r: any) => ({ ...r, staff: String(r.staff) })}
            filters={[{ name: "status", label: "Status", options: ["pending", "approved", "rejected"].map((v) => ({ value: v, label: titleCase(v) })) }]}
            extraActions={(row: any) =>
              can("hr.approve") && row.status === "pending" ? (
                <>
                  <Tooltip label="Approve"><ActionIcon variant="light" color="green" onClick={() => decide(row, "approve")}><IconCheck size={16} /></ActionIcon></Tooltip>
                  <Tooltip label="Reject"><ActionIcon variant="light" color="red" onClick={() => decide(row, "reject")}><IconX size={16} /></ActionIcon></Tooltip>
                </>
              ) : null
            }
            columns={[
              { key: "staff_name", label: "Staff" },
              { key: "kind", label: "Leave", render: (r: any) => titleCase(r.kind) },
              { key: "dates", label: "Dates", render: (r: any) => `${date(r.start_date)} – ${date(r.end_date)}` },
              { key: "days", label: "Days" },
              { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} /> },
            ]}
            fields={[
              { name: "staff", label: "Staff member", type: "select", optionsFrom: can("staff.view") ? staffSelect : { ...staffSelect, query: { search: me?.user.username } }, required: true },
              { name: "kind", label: "Type of leave", type: "select", options: LEAVE_KINDS, required: true },
              { name: "start_date", label: "From", type: "date", required: true },
              { name: "end_date", label: "To", type: "date", required: true },
              { name: "reason", label: "Reason", type: "textarea" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="duty">
          <CrudPage
            hideHeader
            title="Duty roster"
            singular="duty"
            formHelp="Put a staff member on duty for a day, e.g. gate or dining duty."
            endpoint="/duty-roster/"
            writePerm="staff.manage"
            defaults={{ date: today() }}
            toForm={(r: any) => ({ ...r, staff: String(r.staff) })}
            filters={[{ name: "date", label: "Date", type: "date" }]}
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date, "ddd D MMM") },
              { key: "staff_name", label: "Staff" },
              { key: "duty", label: "Duty" },
              { key: "notes", label: "Notes" },
            ]}
            fields={[
              { name: "staff", label: "Staff member", type: "select", optionsFrom: staffSelect, required: true },
              { name: "date", label: "Date", type: "date", required: true },
              { name: "duty", label: "Duty", required: true, placeholder: "Teacher on duty, gate, dining hall…" },
              { name: "notes", label: "Notes" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="attendance">
          <CrudPage
            hideHeader
            title="Staff attendance"
            singular="attendance record"
            formHelp="Record a staff member's attendance for a day, with the times in and out."
            endpoint="/staff-attendance/"
            writePerm="staff.manage"
            defaults={{ date: today(), status: "present" }}
            toForm={(r: any) => ({ ...r, staff: String(r.staff) })}
            filters={[{ name: "date", label: "Date", type: "date" }]}
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date) },
              { key: "staff_name", label: "Staff" },
              { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} /> },
              { key: "time_in", label: "In", render: (r: any) => r.time_in?.slice(0, 5) ?? "–" },
              { key: "time_out", label: "Out", render: (r: any) => r.time_out?.slice(0, 5) ?? "–" },
            ]}
            fields={[
              { name: "staff", label: "Staff member", type: "select", optionsFrom: staffSelect, required: true },
              { name: "date", label: "Date", type: "date", required: true },
              { name: "status", label: "Status", type: "select", options: ["present", "absent", "late", "leave"].map((v) => ({ value: v, label: titleCase(v) })) },
              { name: "time_in", label: "Time in", type: "time" },
              { name: "time_out", label: "Time out", type: "time" },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
