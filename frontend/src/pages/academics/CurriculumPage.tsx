import { ActionIcon, Alert, Anchor, Badge, Button, Group, List, Tabs, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconCheck, IconDownload, IconSparkles, IconX } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, post } from "@/api/client";

import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import { useClasses, useTerms } from "@/hooks/useSchool";

const LEVELS = [
  { value: "nursery", label: "Nursery" }, { value: "primary", label: "Primary" }, { value: "olevel", label: "O-Level" }, { value: "alevel", label: "A-Level" },
];

/** Who teaches what, schemes of work and lesson plans, and CBC competencies. The subject
 *  list itself is part of the school's setup (owner console). */
export default function CurriculumPage() {
  const { can } = useAuth();
  const client = useQueryClient();
  const [filled, setFilled] = useState<{ created: string[]; unfilled: string[] } | null>(null);
  const decide = async (row: any, decision: "approve" | "reject") => {
    try {
      await post(`/subjects/${row.id}/decide/`, { decision });
      notifications.show({ color: "green", message: decision === "approve" ? `${row.name} approved` : `${row.name} not approved` });
      client.invalidateQueries({ queryKey: ["list", "/subjects/"] });
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    }
  };
  const fill = async () => {
    try {
      const result = await post("/allocations/from-specialisations/", {});
      setFilled(result);
      client.invalidateQueries({ queryKey: ["list", "/allocations/"] });
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    }
  };
  const { classes, options: classOptions, streamOptions } = useClasses();
  const hasOLevel = classes.some((c) => c.level === "olevel");
  const { options: termOptions } = useTerms();
  const subjectSource = { endpoint: "/subjects/", label: (s: any) => `${s.name} (${LEVELS.find((l) => l.value === s.level)?.label ?? s.level})` };

  return (
    <>
      <PageHeader
        title="Curriculum"
        description="Allocate subjects to teachers (this decides who enters which marks), keep schemes of work and lesson plans, and list CBC competencies."
      />
      <Tabs defaultValue={can("curriculum.manage") ? "allocations" : "schemes"} keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="allocations">Who teaches what</Tabs.Tab>
          <Tabs.Tab value="schemes">Schemes of work & lesson plans</Tabs.Tab>
          <Tabs.Tab value="competencies">CBC competencies (O-Level)</Tabs.Tab>
          <Tabs.Tab value="subjects">Subjects</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="allocations">
          <Text size="sm" c="dimmed" mb="sm">
            A teacher allocated a subject in a class enters its marks and sees it under “My lessons”; the timetable is built from
            this list. Class teachers can already enter every subject of their own class.
          </Text>
          {can("curriculum.manage") && (
            <Group mb="sm">
              <Button variant="light" leftSection={<IconSparkles size={16} />} onClick={fill}>
                Fill from teachers' subject specialisations
              </Button>
              <Text size="xs" c="dimmed">Gives each subject without a teacher a specialist with room in their week. Set specialisations on the Staff page.</Text>
            </Group>
          )}
          {filled && (
            <Alert color={filled.unfilled.length ? "orange" : "green"} mb="sm" withCloseButton onClose={() => setFilled(null)} title={`${filled.created.length} allocation(s) added`}>
              {filled.unfilled.length > 0 && (
                <>
                  <Text size="sm">No specialist available for {filled.unfilled.length}:</Text>
                  <List size="xs">{filled.unfilled.slice(0, 15).map((u) => <List.Item key={u}>{u}</List.Item>)}</List>
                </>
              )}
            </Alert>
          )}
          <CrudPage
            hideHeader
            title="Allocations"
            singular="allocation"
            formHelp="Say which teacher takes a subject in a class (or one stream). That teacher can then enter its marks, sees it under My lessons, and the timetable is built from these allocations."
            endpoint="/allocations/"
            writePerm="curriculum.manage"
            defaults={{ periods_per_week: 5 }}
            filters={[{ name: "school_class", label: "Class", options: classOptions }]}
            toForm={(r: any) => ({ ...r, teacher: String(r.teacher), subject: String(r.subject), school_class: String(r.school_class), stream: r.stream && String(r.stream) })}
            columns={[
              { key: "teacher_name", label: "Teacher" },
              { key: "subject_name", label: "Subject" },
              { key: "class_name", label: "Class", render: (r: any) => [r.class_name, r.stream_name].filter(Boolean).join(" ") },
              { key: "periods_per_week", label: "Periods a week" },
            ]}
            fields={[
              { name: "teacher", label: "Teacher", type: "select", required: true, optionsFrom: { endpoint: "/staff/", label: "full_name", query: { kind: "teaching" } }, placeholder: "Choose from your teachers" },
              { name: "subject", label: "Subject", type: "select", required: true, optionsFrom: subjectSource, placeholder: "e.g. Mathematics" },
              { name: "school_class", label: "Class", type: "select", required: true, options: classOptions, placeholder: "e.g. P5" },
              { name: "stream", label: "Stream (optional)", type: "select", options: (v) => streamOptions(v.school_class ?? null), hidden: (v) => !streamOptions(v.school_class ?? null).length, description: "Leave empty when the teacher takes the whole class." },
              { name: "periods_per_week", label: "Periods a week", type: "number", description: "Used when the timetable is generated." },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="schemes">
          <CrudPage
            hideHeader
            title="Schemes of work"
            singular="document"
            formHelp="Keep a scheme of work or a lesson plan for a subject and class: attach the file (Word, PDF or a photo) so the DOS and head of department can check it."
            endpoint="/schemes/"
            writePerm="marks.enter"
            defaults={{ kind: "scheme" }}
            filters={[
              { name: "school_class", label: "Class", options: classOptions },
              { name: "kind", label: "Type", options: [{ value: "scheme", label: "Scheme of work" }, { value: "lesson_plan", label: "Lesson plan" }] },
              { name: "term", label: "Term", options: termOptions },
            ]}
            toForm={(r: any) => ({ ...r, subject: String(r.subject), school_class: String(r.school_class), term: r.term && String(r.term) })}
            emptyText="No schemes of work or lesson plans uploaded yet."
            columns={[
              { key: "title", label: "Title" },
              { key: "kind", label: "Type", render: (r: any) => <Badge variant="light" color={r.kind === "scheme" ? "blue" : "violet"}>{r.kind === "scheme" ? "Scheme of work" : "Lesson plan"}</Badge> },
              { key: "subject_name", label: "Subject" },
              { key: "class_name", label: "Class" },
              { key: "file", label: "File", render: (r: any) => (r.file ? <Anchor href={r.file} target="_blank" size="sm"><IconDownload size={14} /> Open</Anchor> : "–") },
            ]}
            fields={[
              { name: "kind", label: "Type", type: "select", required: true, options: [{ value: "scheme", label: "Scheme of work" }, { value: "lesson_plan", label: "Lesson plan" }] },
              { name: "title", label: "Title", required: true, placeholder: "e.g. P5 Science Term 1 scheme" },
              { name: "subject", label: "Subject", type: "select", required: true, optionsFrom: subjectSource },
              { name: "school_class", label: "Class", type: "select", required: true, options: classOptions },
              { name: "term", label: "Term", type: "select", options: termOptions },
              { name: "file", label: "Document", type: "file", description: "Word, PDF or a photo of the written scheme." },
              { name: "notes", label: "Notes", type: "textarea", span: 12 },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="competencies">
          {!hasOLevel ? (
            <Alert color="gray" title="Not needed for your school">
              Competencies are the learning outcomes and activities of integration of the O-Level competence-based curriculum
              (S1–S4). Your school has no O-Level classes, so there is nothing to set here. Nursery and primary classes are
              assessed with marks and grades (or ratings for nursery) as usual.
            </Alert>
          ) : (
          <>
          <Text size="sm" c="dimmed" mb="sm">
            O-Level CBC learning outcomes and activities of integration (AOI). Teachers score AOIs during the term; they count for
            20% of each subject.
          </Text>
          <CrudPage
            hideHeader
            title="Competencies"
            singular="competency"
            formHelp="O-Level (CBC) only: list a learning outcome or activity of integration for a subject. Teachers score activities of integration during the term; they make up 20% of the subject."
            endpoint="/competencies/"
            writePerm="curriculum.manage"
            defaults={{ is_aoi: true }}
            filters={[{ name: "school_class", label: "Class", options: classOptions }]}
            toForm={(r: any) => ({ ...r, subject: String(r.subject), school_class: r.school_class && String(r.school_class) })}
            columns={[
              { key: "topic", label: "Topic / outcome" },
              { key: "subject", label: "Subject", render: (r: any) => r.subject_name ?? r.subject },
              { key: "is_aoi", label: "", render: (r: any) => (r.is_aoi ? <Badge size="sm" variant="light">Activity of integration</Badge> : null) },
            ]}
            fields={[
              { name: "subject", label: "Subject", type: "select", required: true, optionsFrom: { ...subjectSource, query: { level: "olevel" } } },
              { name: "school_class", label: "Class (optional)", type: "select", options: classOptions },
              { name: "topic", label: "Topic / learning outcome", required: true, span: 12 },
              { name: "description", label: "Description", type: "textarea", span: 12 },
              { name: "is_aoi", label: "Activity of integration (scored during the term)", type: "checkbox", span: 12 },
            ]}
          />
          </>
          )}
        </Tabs.Panel>
        <Tabs.Panel value="subjects">
          <Text size="sm" c="dimmed" mb="sm">
            The standard list comes with your levels. To add one (for example a local language), the director, DOS, head teacher or
            a head of department proposes it; it counts once the head teacher, director or DOS approves it.
          </Text>
          <CrudPage
            hideHeader
            title="Subjects"
            singular="subject proposal"
            formHelp="Propose a subject the standard list does not have, e.g. a local language. It waits as pending and is used only after the head teacher, director or DOS approves it."
            endpoint="/subjects/"
            writePerm="curriculum.propose"
            canDelete={false}
            canEdit={false}
            defaults={{ category: "core", level: "primary" }}
            filters={[
              { name: "level", label: "Level", options: LEVELS },
              { name: "status", label: "Status", options: [{ value: "approved", label: "Approved" }, { value: "pending", label: "Waiting for approval" }, { value: "rejected", label: "Not approved" }] },
            ]}
            extraActions={(r: any) =>
              r.status === "pending" && can("curriculum.approve") ? (
                <Group gap={4} wrap="nowrap">
                  <Tooltip label="Approve"><ActionIcon variant="light" color="green" onClick={() => decide(r, "approve")}><IconCheck size={16} /></ActionIcon></Tooltip>
                  <Tooltip label="Do not approve"><ActionIcon variant="light" color="red" onClick={() => decide(r, "reject")}><IconX size={16} /></ActionIcon></Tooltip>
                </Group>
              ) : null
            }
            fields={[
              { name: "name", label: "Subject name", required: true, placeholder: "e.g. Luganda" },
              { name: "short_name", label: "Short code", placeholder: "e.g. LUG" },
              { name: "level", label: "Level", type: "select", options: LEVELS, required: true },
              { name: "category", label: "Type", type: "select", options: [{ value: "core", label: "Compulsory" }, { value: "elective", label: "Elective" }, { value: "principal", label: "A-Level principal" }, { value: "subsidiary", label: "A-Level subsidiary" }] },
              { name: "proposal_note", label: "Why the school needs it", type: "textarea", span: 12 },
            ]}
            columns={[
              { key: "name", label: "Subject" },
              { key: "short_name", label: "Code" },
              { key: "level", label: "Level", render: (r: any) => LEVELS.find((l) => l.value === r.level)?.label },
              { key: "category", label: "Type" },
              { key: "in_aggregate", label: "", render: (r: any) => (r.in_aggregate ? <Badge size="xs">PLE aggregate</Badge> : null) },
              { key: "specialists", label: "Specialist teachers", render: (r: any) => <Text size="xs" lineClamp={2}>{r.specialists?.join(", ") || "–"}</Text> },
              {
                key: "status",
                label: "Status",
                render: (r: any) =>
                  r.status === "approved" ? (
                    <Badge size="sm" variant="light" color="green">Approved</Badge>
                  ) : (
                    <>
                      <Badge size="sm" variant="light" color={r.status === "pending" ? "orange" : "gray"}>{r.status_label}</Badge>
                      {r.proposed_by_name && <Text size="10px" c="dimmed">Proposed by {r.proposed_by_name}</Text>}
                    </>
                  ),
              },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
