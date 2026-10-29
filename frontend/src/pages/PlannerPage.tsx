import { ActionIcon, Badge, Button, Card, Checkbox, Group, Modal, Progress, Select, SimpleGrid, Stack, Text, TextInput, Textarea, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconArrowForward, IconChevronLeft, IconChevronRight, IconPlus, IconTrash } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { useState } from "react";

import { del, errorMessage, get, patch, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/common";
import { useOptions } from "@/hooks/useOptions";
import { useClasses } from "@/hooks/useSchool";

interface Task {
  id: number;
  user: number;
  owner: string;
  week_start: string;
  day: number | null;
  title: string;
  details: string;
  school_class: number | null;
  class_name: string | null;
  priority: "low" | "normal" | "high";
  done: boolean;
}

const DAYS = [
  { value: "1", label: "Monday" },
  { value: "2", label: "Tuesday" },
  { value: "3", label: "Wednesday" },
  { value: "4", label: "Thursday" },
  { value: "5", label: "Friday" },
];
const PRIORITY_COLOR = { high: "red", normal: "blue", low: "gray" } as const;

const monday = (d: dayjs.Dayjs) => d.subtract((d.day() + 6) % 7, "day");

/** Each teacher's weekly to-do list. Heads (staff.view) can look at any teacher's planner. */
export default function PlannerPage() {
  const client = useQueryClient();
  const { can, me } = useAuth();
  const { options: classOptions } = useClasses();
  const [week, setWeek] = useState(() => monday(dayjs()));
  const [viewing, setViewing] = useState<string | null>(null);
  const [adding, setAdding] = useState<string | null>(null);
  const { rows: staff } = useOptions({ endpoint: "/staff/", label: "full_name" }, can("staff.view"));
  const teacherOptions = staff
    .filter((s: any) => s.user && s.user !== me?.user.id)
    .map((s: any) => ({ value: String(s.user), label: s.full_name }));
  const weekKey = week.format("YYYY-MM-DD");
  const own = !viewing;
  const queryKey = ["planner", weekKey, viewing];
  const { data: tasks = [] } = useQuery({
    queryKey,
    queryFn: () => get<Task[]>("/planner/", { week_start: weekKey, user: viewing }),
  });
  const refresh = () => client.invalidateQueries({ queryKey: ["planner"] });
  const doneCount = tasks.filter((t) => t.done).length;

  const toggle = async (task: Task) => {
    client.setQueryData<Task[]>(queryKey, (rows = []) => rows.map((r) => (r.id === task.id ? { ...r, done: !r.done } : r)));
    try {
      await patch(`/planner/${task.id}/`, { done: !task.done });
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    }
    refresh();
  };

  const columns = [...DAYS, { value: "", label: "Any day this week" }];

  return (
    <>
      <PageHeader
        title={own ? "My planner" : `Planner — ${teacherOptions.find((t) => t.value === viewing)?.label ?? ""}`}
        description="Plan the week's work: lessons to prepare, books to mark, meetings and follow-ups. Tick items off as you finish them."
        actions={
          can("staff.view") ? (
            <Select placeholder="View a teacher's planner" data={teacherOptions} value={viewing} onChange={setViewing} clearable searchable w={260} />
          ) : null
        }
      />
      <Card mb="md">
        <Group justify="space-between">
          <Group gap="xs">
            <ActionIcon variant="default" aria-label="Previous week" onClick={() => setWeek((w) => w.subtract(7, "day"))}>
              <IconChevronLeft size={16} />
            </ActionIcon>
            <Text fw={650} miw={220} ta="center">
              Week of {week.format("D MMM")} – {week.add(4, "day").format("D MMM YYYY")}
            </Text>
            <ActionIcon variant="default" aria-label="Next week" onClick={() => setWeek((w) => w.add(7, "day"))}>
              <IconChevronRight size={16} />
            </ActionIcon>
            {!week.isSame(monday(dayjs()), "day") && (
              <Button variant="subtle" size="xs" onClick={() => setWeek(monday(dayjs()))}>This week</Button>
            )}
          </Group>
          <Group>
            <Stack gap={2} w={180}>
              <Text size="xs" c="dimmed">{doneCount} of {tasks.length} done</Text>
              <Progress value={tasks.length ? (doneCount / tasks.length) * 100 : 0} color="green" />
            </Stack>
            {own && (
              <Tooltip label="Copy last week's unfinished items into this week">
                <Button
                  variant="default"
                  leftSection={<IconArrowForward size={16} />}
                  onClick={async () => {
                    const result = await post("/planner/carry-over/", { week_start: weekKey });
                    notifications.show({ message: result.copied ? `${result.copied} item(s) carried over.` : "Nothing left over from last week." });
                    refresh();
                  }}
                >
                  Carry over
                </Button>
              </Tooltip>
            )}
          </Group>
        </Group>
      </Card>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {columns.map((col) => {
          const items = tasks.filter((t) => String(t.day ?? "") === col.value);
          const isToday = col.value && week.add(Number(col.value) - 1, "day").isSame(dayjs(), "day");
          return (
            <Card key={col.value} withBorder style={isToday ? { borderColor: "var(--mantine-color-brand-5)" } : undefined}>
              <Group justify="space-between" mb="xs">
                <Text fw={650} size="sm">
                  {col.label}
                  {col.value && <Text span c="dimmed" size="xs"> {week.add(Number(col.value) - 1, "day").format("D MMM")}</Text>}
                </Text>
                {own && (
                  <ActionIcon variant="subtle" aria-label={`Add to ${col.label}`} onClick={() => setAdding(col.value)}>
                    <IconPlus size={16} />
                  </ActionIcon>
                )}
              </Group>
              <Stack gap="xs">
                {items.map((task) => (
                  <Card key={task.id} padding="xs" withBorder bg={task.done ? "var(--mantine-color-default-hover)" : undefined}>
                    <Group gap="xs" wrap="nowrap" align="flex-start">
                      <Checkbox checked={task.done} disabled={!own} onChange={() => toggle(task)} mt={2} aria-label="Done" />
                      <Stack gap={2} style={{ flex: 1 }}>
                        <Text size="sm" td={task.done ? "line-through" : undefined} c={task.done ? "dimmed" : undefined}>
                          {task.title}
                        </Text>
                        {task.details && <Text size="xs" c="dimmed">{task.details}</Text>}
                        <Group gap={4}>
                          {task.class_name && <Badge size="xs" variant="outline">{task.class_name}</Badge>}
                          {task.priority !== "normal" && <Badge size="xs" color={PRIORITY_COLOR[task.priority]} variant="light">{task.priority}</Badge>}
                        </Group>
                      </Stack>
                      {own && (
                        <ActionIcon
                          size="sm"
                          variant="subtle"
                          color="red"
                          aria-label="Delete"
                          onClick={async () => {
                            await del(`/planner/${task.id}/`);
                            refresh();
                          }}
                        >
                          <IconTrash size={14} />
                        </ActionIcon>
                      )}
                    </Group>
                  </Card>
                ))}
                {!items.length && <Text size="xs" c="dimmed">Nothing planned</Text>}
              </Stack>
            </Card>
          );
        })}
      </SimpleGrid>
      <AddTask
        day={adding}
        weekStart={weekKey}
        classOptions={classOptions}
        onClose={() => setAdding(null)}
        onSaved={() => {
          setAdding(null);
          refresh();
        }}
      />
    </>
  );
}

function AddTask({ day, weekStart, classOptions, onClose, onSaved }: { day: string | null; weekStart: string; classOptions: { value: string; label: string }[]; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [schoolClass, setSchoolClass] = useState<string | null>(null);
  const [priority, setPriority] = useState<string | null>("normal");
  const [chosenDay, setChosenDay] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const opened = day !== null;
  const currentDay = chosenDay ?? day;

  const reset = () => {
    setTitle("");
    setDetails("");
    setSchoolClass(null);
    setPriority("normal");
    setChosenDay(null);
  };

  return (
    <Modal opened={opened} onClose={() => { reset(); onClose(); }} title="Add to planner" centered>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await post("/planner/", { week_start: weekStart, day: currentDay ? Number(currentDay) : null, title, details, school_class: schoolClass, priority });
            reset();
            onSaved();
          } catch (error) {
            notifications.show({ color: "red", message: errorMessage(error) });
          } finally {
            setBusy(false);
          }
        }}
      >
        <Stack>
          <TextInput label="What needs doing" placeholder="e.g. Mark P5 Maths homework" required value={title} onChange={(e) => setTitle(e.currentTarget.value)} data-autofocus />
          <Group grow>
            <Select label="Day" data={DAYS} value={currentDay || null} onChange={(v) => setChosenDay(v ?? "")} placeholder="Any day" clearable />
            <Select label="Priority" data={[{ value: "high", label: "High" }, { value: "normal", label: "Normal" }, { value: "low", label: "Low" }]} value={priority} onChange={setPriority} allowDeselect={false} />
          </Group>
          <Select label="Class (optional)" data={classOptions} value={schoolClass} onChange={setSchoolClass} placeholder="e.g. P5" clearable searchable />
          <Textarea label="Notes (optional)" placeholder="Details, page numbers, who to see…" value={details} onChange={(e) => setDetails(e.currentTarget.value)} autosize minRows={2} />
          <Group justify="flex-end">
            <Button type="submit" loading={busy} disabled={!title.trim()}>Add</Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
