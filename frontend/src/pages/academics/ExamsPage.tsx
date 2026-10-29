import { ActionIcon, Alert, Badge, Button, Card, Group, Progress, Select, Stack, Table, Tabs, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconEyeOff, IconFileTypePdf, IconSend, IconTablePlus } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, get, openFile, post, type Paginated } from "@/api/client";
import type { Option } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { CrudPage } from "@/components/CrudPage";
import { useClasses, useCurrentTerm, useTerms } from "@/hooks/useSchool";
import { date, num } from "@/utils/format";

import { GenerateExamTimetable, SeatingPlan } from "./ExamPlanner";

const KINDS = [
  ["bot", "Beginning of term"], ["mot", "Mid-term"], ["eot", "End of term"], ["mock", "Mock"], ["ca", "Continuous assessment"], ["other", "Other"],
].map(([value, label]) => ({ value, label }));

// Continuous assessment is spread through the term; final papers close it.
const CONTINUOUS = new Set(["bot", "mot", "ca"]);
const stageBadge = (kind: string) => (
  <Badge variant="light" color={CONTINUOUS.has(kind) ? "cyan" : "indigo"} radius="sm">
    {CONTINUOUS.has(kind) ? "Continuous assessment" : "Final exam"}
  </Badge>
);

/** How each class's term score is made up; the weights should add up to 100%. */
function Weights({ term }: { term: string | null }) {
  const { data = [] } = useQuery({
    queryKey: ["exam-weights", term],
    enabled: !!term,
    queryFn: () => get<any[]>("/exams/weights/", { term }),
  });
  return (
    <Stack>
      <Alert color="blue" title="How the term score is built">
        <Text size="sm">
          Each exam carries a weight. A subject's term score is the weighted average of the exams the class sits, for example
          BOT 20% + MOT 30% (continuous assessment) + EOT 50% (final exam) = 100%. If a learner misses an exam, the others are
          re-balanced so the learner is not marked down for it. The grade on the report card comes from this term score.
        </Text>
      </Alert>
      <Card p={0}>
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Class</Table.Th>
              <Table.Th>Exams and weights</Table.Th>
              <Table.Th w={240}>Total</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.map((row) => (
              <Table.Tr key={row.class_id}>
                <Table.Td fw={600}>{row.class}</Table.Td>
                <Table.Td>
                  <Group gap={6}>
                    {row.exams.map((e: any) => (
                      <Badge key={e.id} variant="light" color={CONTINUOUS.has(e.kind) ? "cyan" : "indigo"} radius="sm">
                        {e.name} · {num(e.weight, 0)}%
                      </Badge>
                    ))}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs" wrap="nowrap">
                    <Progress value={Math.min(row.total, 100)} color={row.ok ? "green" : "orange"} w={90} />
                    <Text size="sm" fw={600} c={row.ok ? "green" : "orange"}>
                      {num(row.total, 0)}%{row.ok ? "" : " — should be 100%"}
                    </Text>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
            {!data.length && (
              <Table.Tr>
                <Table.Td colSpan={3}>
                  <Text c="dimmed" ta="center" py="md">No exams set for this term yet.</Text>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Card>
    </Stack>
  );
}

/** The exam timetable for one exam: the DOS builds and publishes it; everyone can print it. */
function ExamTimetable({ term, classOptions }: { term: string | null; classOptions: Option[] }) {
  const { can } = useAuth();
  const client = useQueryClient();
  const [examId, setExamId] = useState<string | null>(null);
  const { data: exams } = useQuery({
    queryKey: ["exams-for-schedule", term],
    queryFn: () => get<Paginated<any>>("/exams/", { term, page_size: 100 }),
  });
  const list = exams?.results ?? [];
  const exam = list.find((e) => String(e.id) === examId) ?? list[0];
  const manage = can("assessment.manage");
  if (!exam) return <Text c="dimmed">Create an exam first (Exams tab).</Text>;
  const published = !!exam.schedule_published_at;
  const change = (action: "publish-schedule" | "unpublish-schedule") =>
    modalsConfirm({
      title: action === "publish-schedule" ? `Publish the ${exam.name} timetable?` : "Take it back to draft?",
      message: action === "publish-schedule" ? "Teachers will see it in their portal and get a notification." : "Teachers will no longer see it until you publish again.",
      confirmLabel: action === "publish-schedule" ? "Publish" : "Unpublish",
      onConfirm: async () => {
        try {
          await post(`/exams/${exam.id}/${action}/`);
          client.invalidateQueries({ queryKey: ["exams-for-schedule"] });
          client.invalidateQueries({ queryKey: ["list", "/exam-schedule/"] });
        } catch (error) {
          notifications.show({ color: "red", message: errorMessage(error) });
        }
      },
    });
  return (
    <Stack>
      <Card padding="sm">
        <Group justify="space-between">
          <Group>
            <Select data={list.map((e) => ({ value: String(e.id), label: e.name }))} value={String(exam.id)} onChange={setExamId} w={260} aria-label="Exam" allowDeselect={false} />
            {published ? <Badge color="green" variant="light" size="lg">Published</Badge> : <Badge color="gray" variant="light" size="lg">Draft</Badge>}
          </Group>
          <Group>
            {manage && <GenerateExamTimetable exam={exam} onDone={() => client.invalidateQueries({ queryKey: ["list", "/exam-schedule/"] })} />}
            {(published || manage) && <SeatingPlan exam={exam} manage={manage} />}
            {(published || manage) && (
              <Button variant="default" leftSection={<IconFileTypePdf size={16} />} onClick={() => openFile(`/exams/${exam.id}/schedule-pdf/`)}>
                Download PDF
              </Button>
            )}
            {manage &&
              (published ? (
                <Button variant="default" leftSection={<IconEyeOff size={16} />} onClick={() => change("unpublish-schedule")}>Unpublish</Button>
              ) : (
                <Button color="green" leftSection={<IconSend size={16} />} onClick={() => change("publish-schedule")}>Publish to teachers</Button>
              ))}
          </Group>
        </Group>
      </Card>
      {!published && !manage ? (
        <Alert color="yellow">This exam timetable has not been published yet. The Director of Studies publishes it when it is ready.</Alert>
      ) : (
        <CrudPage
          hideHeader
          title="Exam timetable"
          singular="paper"
          formHelp="One paper in the exam timetable: subject, date, time, room and invigilator. Publish the timetable for teachers to see it."
          endpoint="/exam-schedule/"
          query={{ exam: exam.id }}
          writePerm="assessment.manage"
          defaults={{ exam: String(exam.id) }}
          toForm={(r: any) => ({ ...r, exam: String(r.exam), subject: String(r.subject), school_class: String(r.school_class), room: r.room && String(r.room), invigilator: r.invigilator && String(r.invigilator) })}
          filters={[{ name: "school_class", label: "Class", options: classOptions }]}
          columns={[
            { key: "date", label: "Date", render: (r: any) => date(r.date, "ddd D MMM") },
            { key: "time", label: "Time", render: (r: any) => `${r.start_time.slice(0, 5)}–${r.end_time.slice(0, 5)}` },
            { key: "subject_name", label: "Paper" },
            { key: "class", label: "Class", render: (r: any) => classOptions.find((c) => c.value === String(r.school_class))?.label },
            { key: "room_name", label: "Room" },
            { key: "invigilator_name", label: "Invigilator" },
          ]}
          fields={[
            { name: "exam", label: "Exam", type: "hidden" },
            { name: "school_class", label: "Class", type: "select", options: classOptions, required: true, placeholder: "e.g. P7" },
            { name: "subject", label: "Subject", type: "select", optionsFrom: { endpoint: "/subjects/", label: (s: any) => `${s.name} (${s.level})` }, required: true, placeholder: "e.g. Mathematics" },
            { name: "paper", label: "Paper (A-Level)", type: "select", optionsFrom: { endpoint: "/papers/", label: "label" }, placeholder: "Only if the subject has papers" },
            { name: "date", label: "Date", type: "date", required: true, placeholder: "Pick the day" },
            { name: "start_time", label: "Starts", type: "time", required: true },
            { name: "end_time", label: "Ends", type: "time", required: true },
            { name: "room", label: "Room", type: "select", optionsFrom: { endpoint: "/rooms/", label: "name" }, placeholder: "Optional" },
            { name: "invigilator", label: "Invigilator", type: "select", optionsFrom: { endpoint: "/staff/", label: "full_name" }, placeholder: "Optional" },
          ]}
        />
      )}
    </Stack>
  );
}

export default function ExamsPage() {
  const { can } = useAuth();
  const client = useQueryClient();
  const { options: termOptions } = useTerms();
  const term = useCurrentTerm();
  const { options: classOptions } = useClasses();
  const termId = term ? String(term.id) : null;

  const prepare = (exam: any) =>
    modalsConfirm({
      title: `Prepare mark sheets for ${exam.name}?`,
      message: "One sheet is created per subject (and paper) for each class sitting this exam. Existing sheets are kept.",
      confirmLabel: "Create sheets",
      onConfirm: async () => {
        try {
          const result = await post(`/exams/${exam.id}/prepare-sheets/`);
          notifications.show({ color: "green", message: `${result.created} mark sheet(s) created.` });
          client.invalidateQueries({ queryKey: ["list", "/mark-sheets/"] });
        } catch (error) {
          notifications.show({ color: "red", message: errorMessage(error) });
        }
      },
    });

  return (
    <>
      <PageHeader
        title="Exams"
        description="Set up the term's assessments (BOT, MOT, CATs and EOT) with their weights, create mark sheets for teachers and publish the exam timetable."
      />
      <Tabs defaultValue="exams" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="exams">Exams</Tabs.Tab>
          <Tabs.Tab value="weights">How marks add up</Tabs.Tab>
          <Tabs.Tab value="schedule">Exam timetable</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="exams">
          <CrudPage
            hideHeader
            title="Exams"
            singular="exam"
            formHelp="An assessment in the term, e.g. Beginning of Term (BOT) or End of Term (EOT). Its weight is its share of the term mark; the weights of a class's exams should add up to 100%."
            endpoint="/exams/"
            writePerm="assessment.manage"
            defaults={{ term: termId, weight: 100, max_mark: 100, kind: "eot" }}
            toForm={(r: any) => ({ ...r, term: String(r.term), classes: r.classes.map(String) })}
            filters={[{ name: "term", label: "Term", options: termOptions }]}
            extraActions={(row: any) =>
              can("assessment.manage") ? (
                <Tooltip label="Create mark sheets">
                  <ActionIcon variant="light" onClick={() => prepare(row)}>
                    <IconTablePlus size={16} />
                  </ActionIcon>
                </Tooltip>
              ) : null
            }
            columns={[
              { key: "name", label: "Exam" },
              { key: "kind", label: "Type", render: (r: any) => KINDS.find((k) => k.value === r.kind)?.label },
              { key: "stage", label: "Counts as", render: (r: any) => stageBadge(r.kind) },
              { key: "term_label", label: "Term" },
              { key: "weight", label: "Weight", render: (r: any) => `${num(r.weight, 0)}%` },
              { key: "classes", label: "Classes", render: (r: any) => r.classes.map((id: number) => classOptions.find((c) => c.value === String(id))?.label).join(", ") },
              { key: "start_date", label: "Starts", render: (r: any) => date(r.start_date) },
            ]}
            fields={[
              { name: "name", label: "Name", required: true, placeholder: "e.g. End of Term 1" },
              { name: "kind", label: "Type", type: "select", options: KINDS, required: true, description: "BOT, MOT and CATs are continuous assessment; EOT and mocks are final exams." },
              { name: "term", label: "Term", type: "select", options: termOptions, required: true },
              { name: "weight", label: "Weight in the term score (%)", type: "number", min: 1, max: 100, placeholder: "e.g. 50", description: "e.g. BOT 20, MOT 30, EOT 50. A term's exams should add up to 100." },
              { name: "max_mark", label: "Marked out of", type: "number", min: 1, placeholder: "e.g. 100" },
              { name: "classes", label: "Classes sitting", type: "multiselect", options: classOptions, required: true, span: 12, placeholder: "Choose one or more classes" },
              { name: "start_date", label: "Start date", type: "date" },
              { name: "end_date", label: "End date", type: "date" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="weights">
          <Weights term={termId} />
        </Tabs.Panel>
        <Tabs.Panel value="schedule">
          <ExamTimetable term={termId} classOptions={classOptions} />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
