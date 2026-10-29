import { ActionIcon, Alert, Badge, Button, Card, Group, Modal, ScrollArea, SegmentedControl, Select, Stack, Table, Tabs, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconEyeOff, IconFileTypePdf, IconSend, IconTrash, IconWand } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { del, errorMessage, get, openFile, post, type Paginated } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { CrudPage } from "@/components/CrudPage";
import { ResourceForm } from "@/components/ResourceForm";
import { useOptions } from "@/hooks/useOptions";
import { useClasses, useCurrentTerm, useTerms } from "@/hooks/useSchool";
import { date } from "@/utils/format";

const DAYS = [
  [1, "Monday"], [2, "Tuesday"], [3, "Wednesday"], [4, "Thursday"], [5, "Friday"],
] as const;

function Grid({ term, mode, target, title, subtitle }: { term: string; mode: string; target: string; title: string; subtitle?: string }) {
  const { can } = useAuth();
  const client = useQueryClient();
  const [adding, setAdding] = useState<{ day: number; period: number } | null>(null);
  const filterKey = mode === "class" ? "school_class" : mode;  // "mine" sends ?mine=1
  const { data: periods } = useQuery({ queryKey: ["periods"], queryFn: () => get<Paginated<any>>("/periods/", { page_size: 50 }) });
  const { data: slots = [] } = useQuery({
    queryKey: ["timetable", term, mode, target],
    queryFn: () => get<any[]>("/timetable/", { term, [filterKey]: target }),
  });
  const refresh = () => client.invalidateQueries({ queryKey: ["timetable"] });
  const writable = can("timetable.manage") && mode === "class";

  return (
    <Card p={0}>
      <Group justify="space-between" px="md" py="sm" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
        <div>
          <Text fw={700} ff="Montserrat, Inter, sans-serif">{title}</Text>
          {subtitle && <Text size="xs" c="dimmed">{subtitle}</Text>}
        </div>
        <Text size="xs" c="dimmed">Each lesson: subject · teacher · class</Text>
      </Group>
      <ScrollArea>
        <Table withColumnBorders miw={800}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={130}>Period</Table.Th>
              {DAYS.map(([, name]) => (
                <Table.Th key={name}>{name}</Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {(periods?.results ?? []).map((period: any) => (
              <Table.Tr key={period.id}>
                <Table.Td>
                  <Text size="sm" fw={600}>{period.name}</Text>
                  <Text size="xs" c="dimmed">{period.start_time.slice(0, 5)}–{period.end_time.slice(0, 5)}</Text>
                </Table.Td>
                {DAYS.map(([day]) => {
                  if (period.is_break)
                    return (
                      <Table.Td key={day} bg="var(--mantine-color-gray-light)">
                        <Text size="xs" c="dimmed" ta="center">Break</Text>
                      </Table.Td>
                    );
                  const here = slots.filter((s) => s.day === day && s.period === period.id);
                  return (
                    <Table.Td key={day} p={4} onClick={() => writable && !here.length && setAdding({ day, period: period.id })} style={{ cursor: writable && !here.length ? "copy" : undefined }}>
                      {here.map((slot) => (
                        <Group key={slot.id} className="tt-cell" justify="space-between" wrap="nowrap" mb={2}>
                          <div>
                            <Text size="xs" fw={700}>{slot.subject_name}</Text>
                            <Text size="xs">{slot.teacher_name ?? "No teacher yet"}</Text>
                            <Text size="xs" c="dimmed">
                              {slot.class_label}
                              {slot.room_name ? ` · ${slot.room_name}` : ""}
                            </Text>
                          </div>
                          {writable && (
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="red"
                              onClick={async (e) => {
                                e.stopPropagation();
                                await del(`/timetable/${slot.id}/`);
                                refresh();
                              }}
                              aria-label="Remove lesson"
                            >
                              <IconTrash size={12} />
                            </ActionIcon>
                          )}
                        </Group>
                      ))}
                    </Table.Td>
                  );
                })}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
      {!periods?.results?.length && (
        <Text p="md" c="dimmed">
          Add the school's periods in the Periods tab first.
        </Text>
      )}
      <Modal opened={!!adding} onClose={() => setAdding(null)} title="Add a lesson" centered>
        {adding && (
          <ResourceForm
            endpoint="/timetable/"
            initial={{ term, day: adding.day, period: adding.period, school_class: target }}
            fields={[
              { name: "subject", label: "Subject", type: "select", required: true, optionsFrom: { endpoint: "/subjects/", label: (s: any) => `${s.name} (${s.level})` } },
              { name: "teacher", label: "Teacher", type: "select", optionsFrom: { endpoint: "/staff/", label: "full_name", query: { kind: "teaching" } } },
              { name: "room", label: "Room", type: "select", optionsFrom: { endpoint: "/rooms/", label: "name" } },
              { name: "stream", label: "Stream (optional)", type: "select", optionsFrom: { endpoint: "/streams/", label: "label", query: { school_class: target } } },
              { name: "term", label: "", type: "hidden" },
              { name: "day", label: "", type: "hidden" },
              { name: "period", label: "", type: "hidden" },
              { name: "school_class", label: "", type: "hidden" },
            ]}
            submitLabel="Add lesson"
            onSaved={() => {
              setAdding(null);
              refresh();
            }}
          />
        )}
      </Modal>
    </Card>
  );
}

/** Draft or published: the DOS publishes the term's timetable; teachers see it only then. */
function PublishBar({ term }: { term: string }) {
  const client = useQueryClient();
  const { can } = useAuth();
  const { data: status, refetch } = useQuery({
    queryKey: ["timetable-status", term],
    queryFn: () => get<{ published: boolean; published_at: string | null; published_by: string | null; lessons: number }>("/timetable/status/", { term }),
  });
  if (!status) return null;
  const change = (action: "publish" | "unpublish") =>
    modalsConfirm({
      title: action === "publish" ? "Publish the timetable?" : "Take the timetable back to draft?",
      message:
        action === "publish"
          ? "Every teacher will see it in their portal and get a notification. You can still make changes afterwards."
          : "Teachers will no longer see it until you publish again.",
      confirmLabel: action === "publish" ? "Publish" : "Unpublish",
      onConfirm: async () => {
        try {
          await post(`/timetable/${action}/`, { term });
          refetch();
          client.invalidateQueries({ queryKey: ["timetable"] });
          notifications.show({ color: "green", message: action === "publish" ? "Published. Teachers have been notified." : "Back to draft." });
        } catch (error) {
          notifications.show({ color: "red", message: errorMessage(error) });
        }
      },
    });
  if (!can("timetable.manage")) {
    return status.published ? null : (
      <Alert color="yellow">The timetable for this term has not been published yet. The Director of Studies publishes it when it is ready.</Alert>
    );
  }
  return (
    <Card padding="sm">
      <Group justify="space-between">
        <Group gap="sm">
          {status.published ? <Badge color="green" size="lg" variant="light">Published</Badge> : <Badge color="gray" size="lg" variant="light">Draft</Badge>}
          <Text size="sm" c="dimmed">
            {status.lessons} lesson(s)
            {status.published ? ` · published ${date(status.published_at)}${status.published_by ? ` by ${status.published_by}` : ""}` : " · only you and other timetable managers can see it"}
          </Text>
        </Group>
        {status.published ? (
          <Button variant="default" leftSection={<IconEyeOff size={16} />} onClick={() => change("unpublish")}>Unpublish</Button>
        ) : (
          <Button color="green" leftSection={<IconSend size={16} />} disabled={!status.lessons} onClick={() => change("publish")}>
            Publish to teachers
          </Button>
        )}
      </Group>
    </Card>
  );
}

export default function TimetablePage() {
  const { can } = useAuth();
  const client = useQueryClient();
  const current = useCurrentTerm();
  const { options: termOptions } = useTerms();
  const { options: classOptions, classes } = useClasses();
  const { options: teacherOptions } = useOptions({ endpoint: "/staff/", label: "full_name", query: { kind: "teaching" } });
  const { options: roomOptions } = useOptions({ endpoint: "/rooms/", label: "name" });
  const [term, setTerm] = useState<string | null>(null);
  const [mode, setMode] = useState(can("timetable.manage") ? "class" : "mine");
  const [target, setTarget] = useState<string | null>(null);
  const termId = term ?? (current ? String(current.id) : null);
  const targetOptions = mode === "class" ? classOptions : mode === "teacher" ? teacherOptions : roomOptions;
  const shown = mode === "mine" ? "1" : target;
  const pdf = () => openFile("/timetable/pdf/", { term: termId, [mode === "class" ? "school_class" : mode]: shown });
  const termLabel = termOptions.find((t) => t.value === termId)?.label ?? "";
  const chosen = targetOptions.find((o) => o.value === target)?.label ?? "";
  const chosenClass: any = mode === "class" ? classes.find((c) => String(c.id) === target) : null;
  const gridTitle =
    mode === "mine" ? "My lessons" : mode === "class" ? `Class timetable — ${chosen}` : mode === "teacher" ? `Teacher's timetable — ${chosen}` : `Room timetable — ${chosen}`;
  const gridSubtitle = [
    termLabel,
    chosenClass?.class_teacher_name ? `Class teacher: ${chosenClass.class_teacher_name}` : null,
    chosenClass?.deputy_class_teacher_name ? `Deputy: ${chosenClass.deputy_class_teacher_name}` : null,
  ].filter(Boolean).join(" · ");

  const generate = () =>
    modalsConfirm({
      title: "Generate the timetable?",
      message: "Lessons are spread across the week from teachers' subject allocations, avoiding every clash. Existing lessons for the term are replaced.",
      confirmLabel: "Generate",
      onConfirm: async () => {
        try {
          const result = await post("/timetable/generate/", { term: termId });
          notifications.show({
            color: result.unplaced.length ? "orange" : "green",
            message: `${result.placed} lessons placed${result.unplaced.length ? `; ${result.unplaced.length} allocation(s) could not be fully placed` : ""}.`,
          });
          client.invalidateQueries({ queryKey: ["timetable"] });
        } catch (error) {
          notifications.show({ color: "red", message: errorMessage(error) });
        }
      },
    });

  return (
    <>
      <PageHeader
        title="Timetable"
        description={
          can("timetable.manage")
            ? "Build the week in the class view (click an empty cell to add a lesson) or generate it, then publish it to teachers."
            : "Your lessons for the week, and any class, teacher or room timetable."
        }
        actions={
          can("timetable.manage") && termId ? (
            <Button leftSection={<IconWand size={16} />} onClick={generate}>
              Generate automatically
            </Button>
          ) : null
        }
      />
      <Tabs defaultValue="grid" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="grid">Timetable</Tabs.Tab>
          <Tabs.Tab value="subs">Substitutions</Tabs.Tab>
          <Tabs.Tab value="periods">Periods</Tabs.Tab>
          <Tabs.Tab value="rooms">Rooms</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="grid">
          <Stack>
            <Group justify="space-between">
              <Group>
                <Select data={termOptions} value={termId} onChange={setTerm} w={200} aria-label="Term" />
                <SegmentedControl
                  value={mode}
                  onChange={(v) => {
                    setMode(v);
                    setTarget(null);
                  }}
                  data={[{ value: "mine", label: "My lessons" }, { value: "class", label: "Class" }, { value: "teacher", label: "Teacher" }, { value: "room", label: "Room" }]}
                />
                {mode !== "mine" && <Select placeholder={`Choose ${mode}`} data={targetOptions} value={target} onChange={setTarget} searchable w={240} />}
              </Group>
              {termId && shown && (
                <Button variant="default" leftSection={<IconFileTypePdf size={16} />} onClick={pdf}>
                  Download PDF
                </Button>
              )}
            </Group>
            {termId && <PublishBar term={termId} />}
            {termId && shown ? <Grid term={termId} mode={mode} target={shown} title={gridTitle} subtitle={gridSubtitle} /> : <Text c="dimmed">Choose a {mode} to see its week.</Text>}
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="subs">
          <CrudPage
            hideHeader
            title="Substitutions"
            singular="substitution"
            formHelp="Someone covers a lesson for an absent teacher on a date. The cover teacher sees it in their lessons for that day."
            endpoint="/substitutions/"
            writePerm="timetable.manage"
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date, "ddd D MMM") },
              { key: "lesson", label: "Lesson", render: (r: any) => `${r.slot_detail.period_name}: ${r.slot_detail.subject_name} ${r.slot_detail.class_label}` },
              { key: "absent", label: "Absent teacher", render: (r: any) => r.slot_detail.teacher_name },
              { key: "substitute_name", label: "Covered by" },
              { key: "reason", label: "Reason" },
            ]}
            fields={[
              { name: "slot", label: "Lesson", type: "select", required: true, optionsFrom: { endpoint: "/timetable/", query: { term: termId }, label: (s: any) => `${DAYS.find(([d]) => d === s.day)?.[1]} ${s.period_name} · ${s.subject_name} ${s.class_label} (${s.teacher_name ?? "no teacher"})` } },
              { name: "date", label: "Date", type: "date", required: true },
              { name: "substitute", label: "Covering teacher", type: "select", options: teacherOptions, required: true },
              { name: "reason", label: "Reason" },
            ]}
          />
          <Tooltip label="Tip">
            <Text size="xs" c="dimmed" mt="xs">
              Teachers on approved leave are not offered automatically; check the Staff page for who is away.
            </Text>
          </Tooltip>
        </Tabs.Panel>
        <Tabs.Panel value="periods">
          <CrudPage
            hideHeader
            title="Periods"
            singular="period"
            formHelp="A slot in the school day (e.g. Period 1, 08:00–08:40). Mark breaks and lunch as breaks so no lessons are placed in them."
            endpoint="/periods/"
            writePerm="timetable.manage"
            columns={[
              { key: "order", label: "#" },
              { key: "name", label: "Name" },
              { key: "time", label: "Time", render: (r: any) => `${r.start_time.slice(0, 5)}–${r.end_time.slice(0, 5)}` },
              { key: "is_break", label: "Break", render: (r: any) => (r.is_break ? "Yes" : "") },
            ]}
            fields={[
              { name: "name", label: "Name", required: true },
              { name: "order", label: "Order", type: "number", required: true },
              { name: "start_time", label: "Starts", type: "time", required: true },
              { name: "end_time", label: "Ends", type: "time", required: true },
              { name: "is_break", label: "Break or lunch", type: "checkbox" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="rooms">
          <CrudPage
            hideHeader
            title="Rooms"
            singular="room"
            formHelp="A classroom, laboratory or hall. Lessons placed in a room are checked so it is never double-booked."
            endpoint="/rooms/"
            writePerm="timetable.manage"
            columns={[
              { key: "name", label: "Room" },
              { key: "kind", label: "Type" },
              { key: "capacity", label: "Capacity" },
            ]}
            fields={[
              { name: "name", label: "Name", required: true },
              { name: "kind", label: "Type", placeholder: "Classroom, Laboratory…" },
              { name: "capacity", label: "Capacity", type: "number" },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
