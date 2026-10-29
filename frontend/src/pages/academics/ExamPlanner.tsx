import { Alert, Badge, Button, Card, Checkbox, Group, List, Modal, MultiSelect, NumberInput, SimpleGrid, Stack, Table, Text } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { IconArmchair, IconFileTypePdf, IconWand } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, get, openFile, post } from "@/api/client";
import { date } from "@/utils/format";

const SESSIONS = [
  { key: "morning", label: "Morning", times: ["08:30", "10:30"] },
  { key: "mid", label: "Late morning", times: ["11:00", "13:00"] },
  { key: "afternoon", label: "Afternoon", times: ["14:00", "16:00"] },
];

/** Make the exam timetable automatically. */
export function GenerateExamTimetable({ exam, onDone }: { exam: any; onDone: () => void }) {
  const client = useQueryClient();
  const [opened, setOpened] = useState(false);
  const [start, setStart] = useState<string | null>(exam.start_date ?? null);
  const [end, setEnd] = useState<string | null>(exam.end_date ?? null);
  const [sessions, setSessions] = useState<string[]>(["morning", "mid", "afternoon"]);
  const [maxPerDay, setMaxPerDay] = useState<number | string>(2);
  const [replace, setReplace] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);

  const run = async () => {
    setBusy(true);
    try {
      const data = await post(`/exams/${exam.id}/generate-timetable/`, {
        start_date: start,
        end_date: end,
        sessions: SESSIONS.filter((s) => sessions.includes(s.key)).map((s) => s.times),
        max_per_day: maxPerDay,
        replace,
      });
      setResult(data);
      client.invalidateQueries({ queryKey: ["list", "/exam-schedule/"] });
      client.invalidateQueries({ queryKey: ["exams-for-schedule"] });
      onDone();
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button leftSection={<IconWand size={16} />} onClick={() => { setResult(null); setOpened(true); }}>Generate automatically</Button>
      <Modal opened={opened} onClose={() => setOpened(false)} title={`Generate the ${exam.name} timetable`} size="lg" centered>
        <Stack>
          <Alert color="blue" p="sm">
            <Text size="sm">
              Every paper of the classes sitting this exam is placed on school days between the dates (weekends and public holidays
              are skipped). A paper is sat by all its classes at the same time, no class sits more than the set number of papers a
              day, and each class gets an invigilator who does not teach it that subject.
            </Text>
          </Alert>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <DateInput label="First day" value={start} onChange={setStart} valueFormat="ddd D MMM YYYY" required />
            <DateInput label="Last day" value={end} onChange={setEnd} valueFormat="ddd D MMM YYYY" minDate={start ?? undefined} required />
          </SimpleGrid>
          <Checkbox.Group label="Sessions each day" value={sessions} onChange={setSessions}>
            <Group mt={6}>
              {SESSIONS.map((s) => <Checkbox key={s.key} value={s.key} label={`${s.label} ${s.times[0]}–${s.times[1]}`} />)}
            </Group>
          </Checkbox.Group>
          <NumberInput label="Most papers a class sits in one day" value={maxPerDay} onChange={setMaxPerDay} min={1} max={3} w={260} />
          <Checkbox label="Start again (remove the papers already in this timetable)" checked={replace} onChange={(e) => setReplace(e.currentTarget.checked)} />
          {result && (
            <Alert color={result.unplaced.length ? "orange" : "green"} title={`${result.created} paper sitting(s) placed over ${result.days.length} school day(s)`}>
              {result.unplaced.length > 0 && (
                <>
                  <Text size="sm">{result.advice}</Text>
                  <List size="xs" mt={4}>{result.unplaced.slice(0, 12).map((u: string) => <List.Item key={u}>{u}</List.Item>)}</List>
                </>
              )}
            </Alert>
          )}
          <Group justify="flex-end">
            {result ? (
              <Button variant="default" onClick={() => setOpened(false)}>Close</Button>
            ) : (
              <Button onClick={run} loading={busy} disabled={!start || !end || !sessions.length}>Generate</Button>
            )}
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

/** Seat learners for every session across rooms, with classes mixed. */
export function SeatingPlan({ exam, manage }: { exam: any; manage: boolean }) {
  const [opened, setOpened] = useState(false);
  const [rooms, setRooms] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const { data: roomRows } = useQuery({ queryKey: ["rooms"], queryFn: () => get("/rooms/", { page_size: 200 }), enabled: opened });
  const { data: sessions = [], refetch } = useQuery({
    queryKey: ["seating", exam.id],
    enabled: opened,
    queryFn: () => get<any[]>(`/exams/${exam.id}/seating/`),
  });
  const roomList: any[] = roomRows?.results ?? [];
  const capacity = roomList.filter((r) => rooms.includes(String(r.id))).reduce((sum, r) => sum + (r.capacity || 40), 0);
  const largest = Math.max(0, ...sessions.map((s: any) => s.papers.length && s.seated)) || 0;

  const run = async () => {
    setBusy(true);
    try {
      await post(`/exams/${exam.id}/seating/`, { rooms: rooms.map(Number) });
      notifications.show({ color: "green", message: "Seating plan made. Classes are mixed in every room." });
      refetch();
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button variant="default" leftSection={<IconArmchair size={16} />} onClick={() => setOpened(true)}>Seating plan</Button>
      <Modal opened={opened} onClose={() => setOpened(false)} title={`Seating plan — ${exam.name}`} size="xl" centered>
        <Stack>
          <Text size="sm" c="dimmed">
            For each session, everyone sitting a paper is seated across the chosen rooms with classes and streams mixed, so no
            learner sits next to a classmate (as far as the numbers allow). Print it per room for the doors and invigilators.
          </Text>
          {manage && (
            <Card withBorder p="sm">
              <Group align="flex-end">
                <MultiSelect
                  label="Rooms for the exam"
                  data={roomList.map((r) => ({ value: String(r.id), label: `${r.name}${r.capacity ? ` (${r.capacity} seats)` : " (40 seats)"}` }))}
                  value={rooms}
                  onChange={setRooms}
                  placeholder={roomList.length ? "Choose rooms" : "Add rooms on the Timetable page first"}
                  style={{ flex: 1 }}
                  searchable
                />
                <Button leftSection={<IconArmchair size={16} />} onClick={run} loading={busy} disabled={!rooms.length}>Make seating plan</Button>
              </Group>
              {rooms.length > 0 && <Text size="xs" c="dimmed" mt={6}>{capacity} seats chosen. Rooms without a capacity count as 40.</Text>}
            </Card>
          )}
          {sessions.length === 0 ? (
            <Text c="dimmed" size="sm">Make the exam timetable first.</Text>
          ) : (
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Session</Table.Th>
                  <Table.Th>Papers</Table.Th>
                  <Table.Th>Seated</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sessions.map((s: any) => (
                  <Table.Tr key={`${s.date}-${s.start_time}`}>
                    <Table.Td>{date(s.date, "ddd D MMM")} · {s.start_time}–{s.end_time}</Table.Td>
                    <Table.Td><Text size="xs">{s.papers.join(", ")}</Text></Table.Td>
                    <Table.Td>{s.seated ? <Badge variant="light" color="green">{s.seated} in {s.rooms.join(", ")}</Badge> : <Badge variant="light" color="gray">Not yet</Badge>}</Table.Td>
                    <Table.Td>
                      {s.seated > 0 && (
                        <Button size="compact-xs" variant="subtle" leftSection={<IconFileTypePdf size={14} />} onClick={() => openFile(`/exams/${exam.id}/seating-pdf/`, { date: s.date, start_time: s.start_time })}>
                          Print
                        </Button>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
          {largest > capacity && manage && rooms.length > 0 && <Alert color="orange">Some sessions have more learners than the chosen seats. Add rooms.</Alert>}
          {sessions.some((s: any) => s.seated) && (
            <Group justify="flex-end">
              <Button variant="default" leftSection={<IconFileTypePdf size={16} />} onClick={() => openFile(`/exams/${exam.id}/seating-pdf/`)}>Print all rooms</Button>
            </Group>
          )}
        </Stack>
      </Modal>
    </>
  );
}
