import {
  ActionIcon,
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Group,
  SegmentedControl,
  Select,
  SimpleGrid,
  Skeleton,
  Stack,
  Tabs,
  Text,
  TextInput,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { IconArrowBackUp, IconBeach, IconChecks, IconCloudOff, IconDeviceFloppy, IconEraser, IconX } from "@tabler/icons-react";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { errorMessage, get, post } from "@/api/client";
import { PageHeader } from "@/components/common";
import { useClasses } from "@/hooks/useSchool";
import { cacheGet, cachePut, queueOp } from "@/offline/queue";
import { useOnline } from "@/offline/useSync";
import { today } from "@/utils/format";

import { ClassRegister } from "./ClassRegister";

type Status = "present" | "absent" | "late" | "excused";

interface RegisterRow {
  learner: number;
  name: string;
  adm_no: string;
  photo: string | null;
  status: Status | null;
  reason: string;
  version: number;
}

interface Register {
  session: number | null;
  date: string;
  school_day?: boolean;
  not_school_reason?: string;
  class_label: string;
  learners: RegisterRow[];
}

const STATUS_DATA = [
  { value: "present", label: "P" },
  { value: "absent", label: "A" },
  { value: "late", label: "L" },
  { value: "excused", label: "E" },
];

export default function RollCallPage() {
  const online = useOnline();
  const { options: classOptions, streamOptions } = useClasses();
  const [params] = useSearchParams();
  const [classId, setClassId] = useState<string | null>(params.get("class"));
  const [streamId, setStreamId] = useState<string | null>(params.get("stream"));
  const [day, setDay] = useState<string>(today());
  const [tab, setTab] = useState<string | null>("day");
  const [register, setRegister] = useState<Register | null>(null);
  const [rows, setRows] = useState<RegisterRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fromCache, setFromCache] = useState(false);
  const cacheKey = `roll:${classId}:${streamId ?? "all"}:${day}`;
  const listKey = `roll-learners:${classId}:${streamId ?? "all"}`;

  useEffect(() => {
    if (!classId) return;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const data = await get<Register>("/attendance/roll-call/", { school_class: classId, stream: streamId, date: day });
        if (cancelled) return;
        await cachePut(cacheKey, data);
        await cachePut(listKey, data);
        setRegister(data);
        setRows(data.learners);
        setFromCache(false);
      } catch (error) {
        const cached = (await cacheGet<Register>(cacheKey)) ?? (await cacheGet<Register>(listKey));
        if (cancelled) return;
        if (cached) {
          const sameDay = cached.value.date === day;
          setRegister({ ...cached.value, date: day });
          setRows(sameDay ? cached.value.learners : cached.value.learners.map((r) => ({ ...r, status: null, reason: "", version: 0 })));
          setFromCache(true);
        } else {
          setRegister(null);
          setRows([]);
          notifications.show({ color: "red", message: errorMessage(error) });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [classId, streamId, day, cacheKey, listKey]);

  const counts = useMemo(() => {
    const result: Record<string, number> = { present: 0, absent: 0, late: 0, excused: 0, unmarked: 0 };
    rows.forEach((r) => (result[r.status ?? "unmarked"] += 1));
    return result;
  }, [rows]);

  const changed = register ? rows.some((r, i) => r.status !== register.learners[i]?.status || r.reason !== register.learners[i]?.reason) : false;
  const clearOne = (learner: number) => setRows((current) => current.map((r) => (r.learner === learner ? { ...r, status: null, reason: "" } : r)));

  const setStatus = (learner: number, status: Status) =>
    setRows((current) => current.map((r) => (r.learner === learner ? { ...r, status, reason: status === "present" ? "" : r.reason } : r)));

  const save = async () => {
    if (!classId) return;
    const marked = rows.filter((r) => r.status);
    if (marked.length < rows.length) {
      notifications.show({ color: "orange", message: `${rows.length - marked.length} learner(s) not marked yet.` });
      return;
    }
    setSaving(true);
    const records = marked.map((r) => ({ learner: r.learner, status: r.status, reason: r.reason }));
    try {
      if (!navigator.onLine) throw new TypeError("offline");
      await post("/attendance/roll-call/", { school_class: classId, stream: streamId, date: day, records });
      notifications.show({ color: "green", title: "Register saved", message: `${counts.present + counts.late} present, ${counts.absent} absent.` });
      const fresh = await get<Register>("/attendance/roll-call/", { school_class: classId, stream: streamId, date: day });
      await cachePut(cacheKey, fresh);
      setRows(fresh.learners);
    } catch (error) {
      if (error instanceof TypeError) {
        for (const r of marked) {
          await queueOp(
            "attendance",
            { school_class: Number(classId), stream: streamId ? Number(streamId) : null, date: day, learner: r.learner, status: r.status, reason: r.reason },
            r.version,
            `${r.name}: ${r.status}`,
          );
        }
        await cachePut(cacheKey, { ...register, learners: rows });
        notifications.show({ color: "blue", title: "Saved on this device", message: "It will be sent automatically when you are back online." });
      } else {
        notifications.show({ color: "red", title: "Not saved", message: errorMessage(error) });
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack maw={tab === "month" ? undefined : 760}>
      <PageHeader title="Roll call" description="The class teacher marks the daily register on school days: not at weekends, on Uganda public holidays or between terms. Works without internet." />
      {!online && (
        <Alert color="gray" icon={<IconCloudOff size={18} />}>
          You are offline. Registers you opened before are available, and saving keeps them on this phone until you reconnect.
        </Alert>
      )}
      <Card>
        <SimpleGrid cols={{ base: 1, xs: 3 }}>
          <Select label="Class" placeholder="Choose class" data={classOptions} value={classId} onChange={(v) => { setClassId(v); setStreamId(null); }} searchable />
          <Select label="Stream" placeholder="Whole class" data={streamOptions(classId)} value={streamId} onChange={setStreamId} clearable disabled={!streamOptions(classId).length} />
          <DateInput
            label="Date"
            value={day}
            onChange={(v) => v && setDay(v)}
            maxDate={today()}
            excludeDate={(d) => [0, 6].includes(dayjs(d).day())}
            valueFormat="ddd D MMM YYYY"
            disabled={tab === "month"}
          />
        </SimpleGrid>
      </Card>

      <Tabs value={tab} onChange={setTab}>
        <Tabs.List>
          <Tabs.Tab value="day">Daily register</Tabs.Tab>
          <Tabs.Tab value="month">Month view</Tabs.Tab>
        </Tabs.List>
      </Tabs>

      {tab === "month" && (
        <ClassRegister
          classId={classId}
          streamId={streamId}
          onOpenDay={(d) => {
            setDay(d);
            setTab("day");
          }}
        />
      )}

      {tab === "day" && loading && <Skeleton h={300} radius="md" />}

      {tab === "day" && !loading && register && register.school_day === false && (
        <Alert color="gray" icon={<IconBeach size={18} />} title={`No school on ${dayjs(day).format("dddd D MMMM")}`}>
          {register.not_school_reason}. Registers are taken on school days only; choose another date.
        </Alert>
      )}

      {tab === "day" && !loading && register && register.school_day !== false && (
        <Card p={0}>
          <Group justify="space-between" p="md" wrap="wrap">
            <div>
              <Text fw={700}>{register.class_label}</Text>
              <Group gap={6}>
                <Badge color="green" variant="light">{counts.present} present</Badge>
                <Badge color="red" variant="light">{counts.absent} absent</Badge>
                <Badge color="yellow" variant="light">{counts.late} late</Badge>
                {counts.unmarked > 0 && <Badge color="gray" variant="light">{counts.unmarked} unmarked</Badge>}
                {fromCache && <Badge color="gray">From this device</Badge>}
              </Group>
            </div>
            <Group gap="xs">
              <Button variant="light" leftSection={<IconChecks size={16} />} onClick={() => setRows((c) => c.map((r) => (r.status ? r : { ...r, status: "present" })))}>
                Mark the rest present
              </Button>
              <Button
                variant="default"
                leftSection={<IconArrowBackUp size={16} />}
                disabled={!changed}
                onClick={() => register && setRows(register.learners)}
                title="Go back to the register as it was last saved"
              >
                Undo changes
              </Button>
              <Button
                variant="subtle"
                color="red"
                leftSection={<IconEraser size={16} />}
                disabled={!rows.some((r) => r.status)}
                onClick={() => setRows((c) => c.map((r) => ({ ...r, status: null, reason: "" })))}
              >
                Clear all marks
              </Button>
            </Group>
          </Group>
          {rows.map((row) => (
            <Group key={row.learner} className="roll-row" px="md" py="xs" justify="space-between" wrap="nowrap">
              <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                <Avatar src={row.photo} radius="xl" size={36} color="brand">
                  {row.name.slice(0, 2).toUpperCase()}
                </Avatar>
                <div style={{ minWidth: 0 }}>
                  <Text size="sm" fw={600} truncate>
                    {row.name}
                  </Text>
                  {row.status && row.status !== "present" ? (
                    <TextInput
                      size="xs"
                      placeholder="Reason (optional)"
                      value={row.reason}
                      onChange={(e) => {
                        const reason = e.currentTarget.value;
                        setRows((c) => c.map((r) => (r.learner === row.learner ? { ...r, reason } : r)));
                      }}
                    />
                  ) : (
                    <Text size="xs" c="dimmed">
                      {row.adm_no}
                    </Text>
                  )}
                </div>
              </Group>
              <Group gap={4} wrap="nowrap">
                <SegmentedControl
                  size="sm"
                  data={STATUS_DATA}
                  value={row.status ?? ""}
                  onChange={(v) => setStatus(row.learner, v as Status)}
                  color={row.status === "absent" ? "red" : row.status === "late" ? "yellow" : row.status === "excused" ? "gray" : "green"}
                />
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  aria-label={`Clear ${row.name}'s mark`}
                  title="Clear this mark"
                  onClick={() => clearOne(row.learner)}
                  style={{ visibility: row.status ? "visible" : "hidden" }}
                >
                  <IconX size={16} />
                </ActionIcon>
              </Group>
            </Group>
          ))}
          {rows.length === 0 && (
            <Text p="md" c="dimmed">
              No learners are enrolled in this class this term.
            </Text>
          )}
          <Group justify="flex-end" p="md">
            <Button size="md" leftSection={<IconDeviceFloppy size={18} />} onClick={save} loading={saving} disabled={!rows.length}>
              Save register
            </Button>
          </Group>
        </Card>
      )}
      {tab === "day" && !classId && (
        <Text c="dimmed" ta="center" py="xl">
          Choose a class to open its register. P = present, A = absent, L = late, E = excused.
        </Text>
      )}
    </Stack>
  );
}
