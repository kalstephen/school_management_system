import { ActionIcon, Alert, Badge, Button, Card, Checkbox, Group, Image, Modal, NumberInput, Select, SimpleGrid, Stack, Switch, Table, Tabs, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconCalendarPlus, IconInfoCircle, IconLock, IconUserStar, IconWand } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { useState } from "react";

import { errorMessage, get, post } from "@/api/client";
import { useAuth, useSetupSchool } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import { ResourceForm } from "@/components/ResourceForm";
import { useOptions } from "@/hooks/useOptions";
import { useClasses } from "@/hooks/useSchool";
import { date } from "@/utils/format";

import { GradingEditor } from "./GradingEditor";
import { ReportDesign } from "./ReportDesign";

const LEVELS = [
  { value: "nursery", label: "Nursery" }, { value: "primary", label: "Primary" }, { value: "olevel", label: "O-Level" }, { value: "alevel", label: "A-Level" },
];
const RULE_SETS = [
  { value: "nursery", label: "Nursery (descriptive ratings)" }, { value: "generic", label: "Marks and grades (e.g. P1–P3)" },
  { value: "ple", label: "Primary (PLE aggregates and divisions)" }, { value: "cbc", label: "O-Level CBC (achievement levels)" },
  { value: "uace", label: "A-Level UACE (points)" },
];

function QuickSetup() {
  const client = useQueryClient();
  const [levels, setLevels] = useState<string[]>(["primary"]);
  const [busy, setBusy] = useState(false);
  return (
    <Card>
      <Stack>
        <Text fw={650}>Levels and Ugandan defaults</Text>
        <Text size="sm" c="dimmed">
          Creates sections, classes (with the next class for promotion), NCDC subjects, A-Level papers and combinations, grading scales,
          departments, expense categories and a comment bank. Existing records are kept; everything stays editable.
        </Text>
        <Checkbox.Group value={levels} onChange={setLevels} label="Levels this school teaches">
          <Group mt="xs">
            {LEVELS.map((l) => (
              <Checkbox key={l.value} value={l.value} label={l.label} />
            ))}
          </Group>
        </Checkbox.Group>
        <Alert color="yellow">This also loads the standard Ugandan grading scales (PLE D1–F9, CBC A–E, UACE). The school sees them and can adjust the cut-offs or add grades.</Alert>
        <Group>
          <Button
            leftSection={<IconWand size={16} />}
            loading={busy}
            disabled={!levels.length}
            onClick={async () => {
              setBusy(true);
              try {
                const result = await post("/setup/seed-defaults/", { levels });
                notifications.show({ color: "green", message: `Added ${result.sections} section(s), ${result.classes} class(es), ${result.subjects} subject(s).` });
                client.invalidateQueries();
              } catch (error) {
                notifications.show({ color: "red", message: errorMessage(error) });
              } finally {
                setBusy(false);
              }
            }}
          >
            Load defaults
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}

/** Years and terms come from the standard Ugandan calendar in one step (owner console). */
function GenerateYear() {
  const client = useQueryClient();
  const [year, setYear] = useState<number | string>(dayjs().month() >= 9 ? dayjs().year() + 1 : dayjs().year());
  const [busy, setBusy] = useState(false);
  return (
    <Card>
      <Group align="flex-end" wrap="wrap">
        <Stack gap={4} style={{ flex: 1, minWidth: 260 }}>
          <Text fw={650}>Create a school year</Text>
          <Text size="sm" c="dimmed">
            Adds the year and its three terms on the usual Ugandan dates (Term 1 February–May, Term 2 late May–August, Term 3
            September–early December) and opens the term running today. Adjust any date afterwards with the pencil.
          </Text>
        </Stack>
        <NumberInput label="Year" value={year} onChange={setYear} min={2000} max={2100} w={110} />
        <Button
          leftSection={<IconCalendarPlus size={16} />}
          loading={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const result = await post("/setup/generate-year/", { year });
              notifications.show({ color: "green", message: `${result.year}: ${result.terms_created} term(s) added.` });
              client.invalidateQueries();
            } catch (error) {
              notifications.show({ color: "red", message: errorMessage(error) });
            } finally {
              setBusy(false);
            }
          }}
        >
          Create year and terms
        </Button>
      </Group>
    </Card>
  );
}

function PublicHolidays() {
  const year = dayjs().year();
  const { data } = useQuery({
    queryKey: ["school-days", "holidays", year],
    queryFn: () => get("/school-days/", { start: `${year}-01-01`, end: `${year + 1}-12-31` }),
  });
  const upcoming = (data?.public_holidays ?? []).filter((h: any) => !dayjs(h.date).isBefore(dayjs(), "day")).slice(0, 12);
  return (
    <Card>
      <Text fw={650} mb={4}>Uganda public holidays</Text>
      <Text size="sm" c="dimmed" mb="sm">
        No register is taken on these days, at weekends or between terms. Eid dates are confirmed by government each year; a
        changed date or a school closure is added as a "Holiday" on the school calendar.
      </Text>
      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing={6}>
        {upcoming.map((h: any) => (
          <Group key={h.date} gap="xs" wrap="nowrap">
            <Badge variant="light" w={110}>{dayjs(h.date).format("ddd D MMM YY")}</Badge>
            <Text size="sm">{h.name}</Text>
          </Group>
        ))}
      </SimpleGrid>
    </Card>
  );
}

/** The school's own choice: who is class teacher of each class. */
function AssignClassTeacher({ row, onClose }: { row: any; onClose: () => void }) {
  const client = useQueryClient();
  const { data } = useQuery({ queryKey: ["staff-teaching"], queryFn: () => get("/staff/", { kind: "teaching", page_size: 300 }) });
  const [teacher, setTeacher] = useState<string | null>(row.class_teacher ? String(row.class_teacher) : null);
  const [deputy, setDeputy] = useState<string | null>(row.deputy_class_teacher ? String(row.deputy_class_teacher) : null);
  const [busy, setBusy] = useState(false);
  return (
    <Modal opened onClose={onClose} title={`Class teacher of ${row.name}`} centered>
      <Stack>
        <Select
          label="Teacher"
          placeholder="Choose from your teachers"
          data={(data?.results ?? []).map((s: any) => ({ value: String(s.id), label: s.full_name }))}
          value={teacher}
          onChange={setTeacher}
          searchable
          clearable
          description="They get class-teacher access: the register, marks, report comments, enrolment and promotion review."
        />
        <Select
          label="Deputy class teacher"
          placeholder="Optional"
          data={(data?.results ?? []).filter((s: any) => String(s.id) !== teacher).map((s: any) => ({ value: String(s.id), label: s.full_name }))}
          value={deputy}
          onChange={setDeputy}
          searchable
          clearable
          description="Stands in for the class teacher with the same access. Streams have their own: set them on the Staff page."
        />
        <Group justify="flex-end">
          <Button
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await post(`/classes/${row.id}/class-teacher/`, { class_teacher: teacher, deputy_class_teacher: deputy });
                client.invalidateQueries({ queryKey: ["list", "/classes/"] });
                client.invalidateQueries({ queryKey: ["classes"] });
                notifications.show({ color: "green", message: "Class teacher saved" });
                onClose();
              } catch (error) {
                notifications.show({ color: "red", message: errorMessage(error) });
              } finally {
                setBusy(false);
              }
            }}
          >
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

const PROFILE_LABELS: [string, string][] = [
  ["name", "School name"], ["code", "School ID"], ["short_name", "Short name"], ["motto", "Motto"],
  ["registration_number", "Registration number"], ["emis_number", "EMIS number"], ["uneb_centre_number", "UNEB centre number"],
  ["district", "District"], ["address", "Address"], ["phone", "Phone"], ["email", "Email"], ["website", "Website"],
  ["head_teacher_name", "Head teacher"], ["director_name", "Director"], ["adm_no_format", "Admission number pattern"],
];

function ProfileView({ school }: { school: any }) {
  return (
    <Card maw={900}>
      <Group align="flex-start" wrap="nowrap" gap="lg">
        {school.logo && <Image src={school.logo} w={88} h={88} fit="contain" alt="School logo" />}
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm" style={{ flex: 1 }}>
          {PROFILE_LABELS.map(([key, label]) => (
            <div key={key}>
              <Text size="xs" c="dimmed">{label}</Text>
              <Text size="sm" fw={500}>{school[key] || "–"}</Text>
            </div>
          ))}
        </SimpleGrid>
      </Group>
    </Card>
  );
}

function Addons() {
  const { can } = useAuth();
  const { data = [], refetch } = useQuery({ queryKey: ["addons"], queryFn: () => get<any[]>("/addons/") });
  return (
    <Card>
      <Text fw={650} mb="xs">Add-on modules</Text>
      <Text size="sm" c="dimmed" mb="md">
        Your plan decides which add-ons are available. Your system provider switches them on or off; data is always kept.
      </Text>
      <Table>
        <Table.Tbody>
          {data.map((a) => (
            <Table.Tr key={a.module}>
              <Table.Td fw={600}>{a.label}</Table.Td>
              <Table.Td>{a.in_plan ? <Badge color="green" variant="light">In your plan</Badge> : <Badge color="gray" variant="light">Not in your plan</Badge>}</Table.Td>
              <Table.Td>
                <Switch
                  label={a.active ? "Shown" : "Hidden"}
                  checked={a.active}
                  disabled={!a.in_plan || !can("setup.platform")}
                  onChange={async (e) => {
                    try {
                      await post("/addons/", { module: a.module, hidden: !e.currentTarget.checked });
                      refetch();
                      notifications.show({ message: "Updated. Reload to refresh the menu." });
                    } catch (error) {
                      notifications.show({ color: "red", message: errorMessage(error) });
                    }
                  }}
                />
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Card>
  );
}

export default function SetupPage() {
  const { refresh, can } = useAuth();
  const setupSchool = useSetupSchool();
  const [assigning, setAssigning] = useState<any>(null);
  const { data: school } = useQuery({ queryKey: ["school"], queryFn: () => get("/school/") });
  const { options: classOptions } = useClasses();
  const { options: years } = useOptions({ endpoint: "/academic-years/", label: "name" });
  const { options: scales } = useOptions({ endpoint: "/grading-scales/", label: "name" });
  const { options: sections } = useOptions({ endpoint: "/sections/", label: "name" });

  return (
    <>
      <PageHeader title="School setup" description="School profile, academic calendar, classes and streams, subjects, grading and add-ons." />
      {!setupSchool && (
        <Alert icon={<IconLock size={18} />} color="gray" mb="md" title="Set up by your system provider">
          The profile, years and terms, classes, streams and subjects were set up for your school and are shown here to view. To
          change them, contact your system provider. Your school chooses its class teachers (Classes tab) and may adjust the
          grade cut-offs (Grading tab).
        </Alert>
      )}
      <Tabs defaultValue={setupSchool ? "quick" : "profile"} keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="profile">School profile</Tabs.Tab>
          <Tabs.Tab value="calendar">Years & terms</Tabs.Tab>
          <Tabs.Tab value="classes">Classes & streams</Tabs.Tab>
          <Tabs.Tab value="subjects">Subjects</Tabs.Tab>
          <Tabs.Tab value="grading">Grading</Tabs.Tab>
          <Tabs.Tab value="report">Report card</Tabs.Tab>
          <Tabs.Tab value="other">Houses, departments & clubs</Tabs.Tab>
          <Tabs.Tab value="addons">Add-ons</Tabs.Tab>
          {setupSchool && <Tabs.Tab value="quick">Levels & defaults</Tabs.Tab>}
        </Tabs.List>
        <Tabs.Panel value="profile">
          {school && !setupSchool && <ProfileView school={school} />}
          {setupSchool && (
          <Card maw={900}>
            {school && (
              <ResourceForm
                endpoint="/school/"
                method="PATCH"
                initial={school}
                onSaved={() => refresh()}
                fields={[
                  { name: "name", label: "School name", required: true },
                  { name: "short_name", label: "Short name" },
                  { name: "motto", label: "Motto" },
                  { name: "kind", label: "Type", type: "select", options: [{ value: "day", label: "Day" }, { value: "boarding", label: "Boarding" }, { value: "mixed", label: "Day and boarding" }] },
                  { name: "address", label: "Address" },
                  { name: "phone", label: "Phone" },
                  { name: "email", label: "Email", type: "email" },
                  { name: "website", label: "Website" },
                  { name: "emis_number", label: "EMIS number" },
                  { name: "uneb_centre_number", label: "UNEB centre number" },
                  { name: "adm_no_format", label: "Admission number pattern", placeholder: "{year}/{seq:04d}", description: "Type the codes, not a number: {year} becomes the year and {seq:04d} the running number. NH/{year}/{seq:04d} gives NH/2026/0001." },
                  { name: "other_income_enabled", label: "Record other income (grants, donations — never fees)", type: "checkbox" },
                  { name: "logo", label: "Logo", type: "file", description: "Shown on report cards and printouts." },
                ]}
              />
            )}
          </Card>
          )}
        </Tabs.Panel>
        <Tabs.Panel value="calendar">
          <Stack>
            {setupSchool && <GenerateYear />}
            <CrudPage
              hideHeader
              title="Academic years"
              singular="academic year"
              formHelp="A school year. Usually created with Create year and terms, which adds the three terms on the standard dates."
              endpoint="/academic-years/"
              writePerm="setup.platform"
              columns={[
                { key: "name", label: "Year" },
                { key: "dates", label: "Dates", render: (r: any) => `${date(r.start_date)} – ${date(r.end_date)}` },
                { key: "is_current", label: "Current", render: (r: any) => (r.is_current ? <Badge>Current</Badge> : null) },
              ]}
              fields={[
                { name: "name", label: "Name", required: true, placeholder: "2027" },
                { name: "start_date", label: "Starts", type: "date", required: true },
                { name: "end_date", label: "Ends", type: "date", required: true },
                { name: "is_current", label: "Current year", type: "checkbox" },
              ]}
            />
            <CrudPage
              hideHeader
              title="Terms"
              singular="term"
              formHelp="A term's opening and closing dates. Registers can only be taken on school days inside a term; Next term begins is printed on report cards."
              endpoint="/terms/"
              writePerm="setup.platform"
              defaults={{ status: "planned" }}
              toForm={(r: any) => ({ ...r, academic_year: String(r.academic_year), number: String(r.number) })}
              columns={[
                { key: "label", label: "Term" },
                { key: "dates", label: "Dates", render: (r: any) => `${date(r.start_date)} – ${date(r.end_date)}` },
                { key: "next_term_begins", label: "Next term begins", render: (r: any) => date(r.next_term_begins) },
                { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} /> },
              ]}
              fields={[
                { name: "academic_year", label: "Academic year", type: "select", options: years, required: true },
                { name: "number", label: "Term", type: "select", options: [{ value: "1", label: "Term 1" }, { value: "2", label: "Term 2" }, { value: "3", label: "Term 3" }], required: true },
                { name: "start_date", label: "Opens", type: "date", required: true },
                { name: "end_date", label: "Closes", type: "date", required: true },
                { name: "next_term_begins", label: "Next term begins (printed on report cards)", type: "date" },
                { name: "status", label: "Status", type: "select", options: [{ value: "planned", label: "Planned" }, { value: "open", label: "Open" }, { value: "closed", label: "Closed" }] },
              ]}
            />
            <Text size="xs" c="dimmed">Spending between two terms (the holiday) counts towards the term that has just ended.</Text>
            <PublicHolidays />
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="classes">
          <Stack>
            <Alert icon={<IconInfoCircle size={18} />} color="blue" title="Classes, streams and sections">
              <Text size="sm">
                A <b>class</b> is a year group such as P1 or S2. A <b>stream</b> is a group within a class, such as P1 East and P1 West;
                the person button on each row chooses its class teacher. A <b>section</b> groups classes that share grading rules
                (Nursery, Primary, O-Level, A-Level). <b>Promotes to</b> is the class learners move to next year; the move happens at
                the end of the year on the Promotion page, after the class teacher, the DOS and the director have reviewed the list.
              </Text>
            </Alert>
            <Text fw={650}>Classes</Text>
            <CrudPage
              hideHeader
              title="Classes"
              singular="class"
              formHelp="A year group such as P1 or S2, with its streams. Promotes to is the class learners move to next year."
              endpoint="/classes/"
              writePerm="setup.platform"
              defaults={{ stream_names: [] }}
              extraActions={(row: any) =>
                !setupSchool && can("classes.assign") ? (
                  <Tooltip label="Choose the class teacher">
                    <ActionIcon variant="light" onClick={() => setAssigning(row)} aria-label="Choose the class teacher">
                      <IconUserStar size={16} />
                    </ActionIcon>
                  </Tooltip>
                ) : null
              }
              toForm={(r: any) => ({
                ...r,
                section: String(r.section),
                next_class: r.next_class && String(r.next_class),
                class_teacher: r.class_teacher && String(r.class_teacher),
                stream_names: r.streams.map((s: any) => s.name),
              })}
              columns={[
                { key: "name", label: "Class" },
                { key: "section_name", label: "Section" },
                { key: "streams", label: "Streams", render: (r: any) => r.streams.map((s: any) => s.name).join(", ") || "–" },
                {
                  key: "class_teacher_name",
                  label: "Class teacher · deputy",
                  render: (r: any) => (
                    <>
                      {r.class_teacher_name ?? <Text span c="dimmed" size="sm">Not set</Text>}
                      {r.deputy_class_teacher_name && <Text size="xs" c="dimmed">Deputy: {r.deputy_class_teacher_name}</Text>}
                      {r.streams.filter((s: any) => s.class_teacher_name).map((s: any) => (
                        <Text key={s.id} size="xs" c="dimmed">{s.label}: {s.class_teacher_name}</Text>
                      ))}
                    </>
                  ),
                },
                { key: "learners", label: "Learners" },
                { key: "next", label: "Promotes to", render: (r: any) => (r.is_candidate_class ? <Badge color="grape" variant="light">Candidate class</Badge> : r.next_class_name ?? "–") },
              ]}
              fields={[
                { name: "name", label: "Class name", required: true, placeholder: "e.g. P1", description: "As printed on report cards." },
                { name: "section", label: "Section", type: "select", options: sections, required: true, placeholder: "Choose: Nursery, Primary…", description: "Decides how the class is graded." },
                { name: "stream_names", label: "Streams", type: "tags", placeholder: "Type a name and press Enter, e.g. East", description: "Leave empty if the class has one group.", span: 12 },
                { name: "class_teacher", label: "Class teacher", type: "select", optionsFrom: { endpoint: "/staff/", label: "full_name", query: { kind: "teaching" } }, placeholder: "Choose from your teachers", description: "Gets class-teacher access to this class." },
                { name: "order", label: "Position in the school", type: "number", placeholder: "e.g. 1 for P1", description: "Lowest first: Baby = 1 … P7 = 10. Sets the order in lists." },
                { name: "next_class", label: "Promotes to", type: "select", options: classOptions, placeholder: "e.g. P2", description: "Where learners go next year.", hidden: (v) => !!v.is_candidate_class },
                { name: "is_candidate_class", label: "Candidate class (sits PLE, UCE or UACE: P7, S4, S6)", description: "Learners complete this class instead of being promoted.", type: "checkbox", span: 12 },
              ]}
            />
            <Text fw={650} mt="md">Streams</Text>
            <Text size="sm" c="dimmed">You can also add streams here, one at a time.</Text>
            <CrudPage
              hideHeader
              title="Streams"
              singular="stream"
              formHelp="A group within a class, e.g. P1 East. Each stream can have its own class teacher."
              endpoint="/streams/"
              writePerm="setup.platform"
              toForm={(r: any) => ({ ...r, school_class: String(r.school_class) })}
              columns={[
                { key: "label", label: "Stream" },
                { key: "capacity", label: "Capacity", render: (r: any) => r.capacity || "–" },
              ]}
              fields={[
                { name: "school_class", label: "Class", type: "select", options: classOptions, required: true, placeholder: "Choose the class, e.g. P1" },
                { name: "name", label: "Stream name", required: true, placeholder: "e.g. East, West, Blue or A" },
                { name: "capacity", label: "Most learners allowed", type: "number", placeholder: "Optional, e.g. 60", description: "Leave empty for no limit." },
              ]}
            />
            <Text fw={650} mt="md">Sections</Text>
            <CrudPage
              hideHeader
              title="Sections"
              singular="section"
              formHelp="A group of classes that share grading rules: Nursery, Primary (PLE), O-Level (CBC) or A-Level (UACE)."
              endpoint="/sections/"
              writePerm="setup.platform"
              toForm={(r: any) => ({ ...r, grading_scale: r.grading_scale && String(r.grading_scale) })}
              columns={[
                { key: "name", label: "Section" },
                { key: "level", label: "Level", render: (r: any) => LEVELS.find((l) => l.value === r.level)?.label },
                { key: "grading_rule_set", label: "Grading rules", render: (r: any) => RULE_SETS.find((x) => x.value === r.grading_rule_set)?.label },
                { key: "show_positions", label: "Positions", render: (r: any) => (r.show_positions ? "Shown" : "Hidden") },
              ]}
              fields={[
                { name: "name", label: "Name", required: true },
                { name: "level", label: "Level", type: "select", options: LEVELS, required: true },
                { name: "grading_rule_set", label: "Grading rules", type: "select", options: RULE_SETS, required: true },
                { name: "grading_scale", label: "Grading scale", type: "select", options: scales },
                { name: "order", label: "Order", type: "number" },
                { name: "show_positions", label: "Show class positions on report cards", type: "checkbox" },
              ]}
            />
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="subjects">
          <Stack>
            <CrudPage
              hideHeader
              title="Subjects"
              singular="subject"
              formHelp="A subject taught at one level. Subjects in the PLE aggregate count towards the aggregate and division."
              endpoint="/subjects/"
              writePerm="setup.platform"
              toForm={(r: any) => ({ ...r, department: r.department && String(r.department), classes: r.classes.map(String) })}
              filters={[{ name: "level", label: "Level", options: LEVELS }]}
              columns={[
                { key: "name", label: "Subject" },
                { key: "short_name", label: "Code" },
                { key: "uneb_code", label: "UNEB code" },
                { key: "level", label: "Level", render: (r: any) => LEVELS.find((l) => l.value === r.level)?.label },
                { key: "category", label: "Type" },
                { key: "in_aggregate", label: "", render: (r: any) => (r.in_aggregate ? <Badge size="xs">PLE aggregate</Badge> : null) },
                { key: "papers", label: "Papers", render: (r: any) => r.papers.length || "–" },
              ]}
              fields={[
                { name: "name", label: "Name", required: true },
                { name: "short_name", label: "Short code", placeholder: "MTC" },
                { name: "uneb_code", label: "UNEB code" },
                { name: "level", label: "Level", type: "select", options: LEVELS, required: true },
                { name: "category", label: "Type", type: "select", options: [{ value: "core", label: "Compulsory" }, { value: "elective", label: "Elective" }, { value: "principal", label: "A-Level principal" }, { value: "subsidiary", label: "A-Level subsidiary" }] },
                { name: "department", label: "Department", type: "select", optionsFrom: { endpoint: "/departments/", label: "name" } },
                { name: "classes", label: "Only in these classes (empty = all at this level)", type: "multiselect", options: classOptions, span: 12 },
                { name: "in_aggregate", label: "Counts towards the PLE aggregate", type: "checkbox" },
                { name: "order", label: "Order on report cards", type: "number" },
              ]}
            />
            <CrudPage
              hideHeader
              title="Papers"
              singular="paper"
              formHelp="A paper of a subject with several (mainly A-Level, e.g. Paper 1 and Paper 2). Marks are entered per paper."
              endpoint="/papers/"
              writePerm="setup.platform"
              toForm={(r: any) => ({ ...r, subject: String(r.subject) })}
              columns={[{ key: "label", label: "Paper" }, { key: "name", label: "Name" }]}
              fields={[
                { name: "subject", label: "Subject", type: "select", optionsFrom: { endpoint: "/subjects/", label: (s: any) => `${s.name} (${s.level})` }, required: true },
                { name: "number", label: "Paper number", type: "number", required: true },
                { name: "name", label: "Name" },
              ]}
            />
            <CrudPage
              hideHeader
              title="Combinations"
              singular="combination"
              formHelp="An A-Level subject combination such as PCM: its principal subjects and the subsidiary."
              endpoint="/combinations/"
              writePerm="setup.platform"
              toForm={(r: any) => ({ ...r, principals: r.principals.map(String), subsidiary: r.subsidiary && String(r.subsidiary) })}
              columns={[{ key: "code", label: "Combination" }, { key: "name", label: "Name" }]}
              fields={[
                { name: "code", label: "Code", required: true, placeholder: "PCM" },
                { name: "name", label: "Name" },
                { name: "principals", label: "Principal subjects", type: "multiselect", optionsFrom: { endpoint: "/subjects/", label: "name", query: { level: "alevel" } }, span: 12 },
                { name: "subsidiary", label: "Subsidiary", type: "select", optionsFrom: { endpoint: "/subjects/", label: "name", query: { level: "alevel", category: "subsidiary" } } },
              ]}
            />
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="grading">
          <Stack>
            <GradingEditor />
            <Text fw={650} mt="md">Comment bank</Text>
            <Text size="sm" c="dimmed">
              Preset report card comments by mark. Class and head teacher presets go by the learner's average; subject teacher
              presets by the mark in each subject (for one subject, or any). Teachers can still write their own.
            </Text>
            <CrudPage
              hideHeader
              title="Comment bank"
              singular="comment"
              formHelp="A preset report card comment used for marks in the range. Teachers can keep it or write their own."
              endpoint="/comment-bank/"
              writePerm="assessment.manage"
              columns={[
                { key: "role", label: "For", render: (r: any) => (r.role === "head" ? "Head teacher" : r.role === "subject" ? `Subject teacher${r.subject_name ? ` · ${r.subject_name}` : ""}` : "Class teacher") },
                { key: "range", label: "Mark", render: (r: any) => `${Number(r.min_average)} – ${Number(r.max_average)}` },
                { key: "text", label: "Suggested comment" },
              ]}
              fields={[
                { name: "role", label: "For", type: "select", options: [{ value: "class_teacher", label: "Class teacher" }, { value: "head", label: "Head teacher" }, { value: "subject", label: "Subject teacher (per subject)" }], required: true },
                { name: "subject", label: "Subject (optional)", type: "select", optionsFrom: { endpoint: "/subjects/", label: (s: any) => `${s.name} (${s.level})` }, description: "Leave empty to use it for any subject.", hidden: (v) => v.role !== "subject" },
                { name: "min_average", label: "From mark", type: "number", required: true },
                { name: "max_average", label: "To mark", type: "number", required: true },
                { name: "text", label: "Comment", required: true, span: 12 },
              ]}
            />
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="report">
          <ReportDesign />
        </Tabs.Panel>
        <Tabs.Panel value="other">
          <Stack>
            {[
              { title: "Houses", endpoint: "/houses/", fields: [{ name: "name", label: "Name", required: true }, { name: "colour", label: "Colour" }] },
              { title: "Departments", endpoint: "/departments/", fields: [{ name: "name", label: "Name", required: true }] },
              { title: "Clubs", endpoint: "/clubs/", fields: [{ name: "name", label: "Name", required: true }, { name: "patron", label: "Patron" }] },
            ].map((cfg) => (
              <div key={cfg.endpoint}>
                <Text fw={650} mb="xs">{cfg.title}</Text>
                <CrudPage hideHeader title={cfg.title} endpoint={cfg.endpoint} writePerm="setup.platform" columns={cfg.fields.map((f) => ({ key: f.name, label: f.label }))} fields={cfg.fields} />
              </div>
            ))}
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="addons">
          <Addons />
        </Tabs.Panel>
        {setupSchool && (
          <Tabs.Panel value="quick">
            <Stack>
              <QuickSetup />
              <GenerateYear />
            </Stack>
          </Tabs.Panel>
        )}
      </Tabs>
      {assigning && <AssignClassTeacher row={assigning} onClose={() => setAssigning(null)} />}
    </>
  );
}
