import { ActionIcon, Alert, Badge, Card, Group, ScrollArea, Skeleton, Table, Text, Tooltip } from "@mantine/core";
import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import { useState } from "react";

import { get } from "@/api/client";
import { Empty } from "@/components/common";

interface Day {
  date: string;
  school_day: boolean;
  reason: string;
  taken: boolean;
  past: boolean;
}

interface Register {
  class_label: string;
  month: string;
  days: Day[];
  school_days: number;
  registers_taken: number;
  missing: string[];
  learners: { learner: number; name: string; adm_no: string; days: Record<string, string | null>; present: number; absent: number; rate: number | null }[];
}

const MARK: Record<string, { text: string; color: string }> = {
  present: { text: "✓", color: "var(--mantine-color-green-7)" },
  late: { text: "L", color: "var(--mantine-color-yellow-8)" },
  absent: { text: "A", color: "var(--mantine-color-red-7)" },
  excused: { text: "E", color: "var(--mantine-color-gray-6)" },
};

/** The class register for a month: learners down, days across. Weekends, Uganda public
 *  holidays and days between terms are shaded; school days without a register are flagged. */
export function ClassRegister({ classId, streamId, onOpenDay }: { classId: string | null; streamId: string | null; onOpenDay?: (day: string) => void }) {
  const [month, setMonth] = useState(() => dayjs().startOf("month"));
  const { data, isLoading } = useQuery({
    queryKey: ["class-register", classId, streamId, month.format("YYYY-MM")],
    enabled: !!classId,
    queryFn: () => get<Register>("/attendance/register/", { school_class: classId, stream: streamId, month: month.format("YYYY-MM") }),
  });
  if (!classId) return <Empty title="Choose a class to see its register" />;
  return (
    <Card p={0}>
      <Group justify="space-between" p="md" wrap="wrap">
        <Group gap="xs">
          <ActionIcon variant="default" aria-label="Previous month" onClick={() => setMonth((m) => m.subtract(1, "month"))}>
            <IconChevronLeft size={16} />
          </ActionIcon>
          <Text fw={700} miw={170} ta="center">{data?.class_label ?? ""} · {month.format("MMMM YYYY")}</Text>
          <ActionIcon variant="default" aria-label="Next month" onClick={() => setMonth((m) => m.add(1, "month"))} disabled={month.add(1, "month").isAfter(dayjs())}>
            <IconChevronRight size={16} />
          </ActionIcon>
        </Group>
        {data && (
          <Group gap={6}>
            <Badge variant="light">{data.school_days} school days</Badge>
            <Badge variant="light" color="green">{data.registers_taken} registers taken</Badge>
            {data.missing.length > 0 && <Badge variant="light" color="red">{data.missing.length} not taken</Badge>}
          </Group>
        )}
      </Group>
      {isLoading && <Skeleton h={240} m="md" />}
      {data && data.missing.length > 0 && (
        <Alert color="orange" mx="md" mb="sm" p="xs">
          <Text size="sm">
            No register yet for:{" "}
            {data.missing.map((d, i) => (
              <Text key={d} span size="sm" fw={600} c={onOpenDay ? "brand" : undefined} style={onOpenDay ? { cursor: "pointer" } : undefined} onClick={() => onOpenDay?.(d)}>
                {dayjs(d).format("ddd D")}
                {i < data.missing.length - 1 ? ", " : ""}
              </Text>
            ))}
          </Text>
        </Alert>
      )}
      {data && !data.learners.length && <Empty title="No learners in this class" />}
      {data && data.learners.length > 0 && (
        <ScrollArea>
          <Table withColumnBorders fz="xs" horizontalSpacing={4} verticalSpacing={4} miw={900}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th miw={170} style={{ position: "sticky", left: 0, background: "var(--mantine-color-body)" }}>Learner</Table.Th>
                {data.days.map((d) => (
                  <Table.Th key={d.date} ta="center" p={2} bg={d.school_day ? undefined : "var(--mantine-color-default-hover)"}>
                    <Tooltip label={d.school_day ? (d.taken ? "Register taken" : d.past ? "No register yet" : "School day") : d.reason}>
                      <div style={{ lineHeight: 1.1 }}>
                        <div>{dayjs(d.date).format("dd")[0]}</div>
                        <div style={{ fontWeight: 700, color: d.school_day && d.past && !d.taken ? "var(--mantine-color-red-7)" : undefined }}>{dayjs(d.date).date()}</div>
                      </div>
                    </Tooltip>
                  </Table.Th>
                ))}
                <Table.Th ta="center">Present</Table.Th>
                <Table.Th ta="center">Absent</Table.Th>
                <Table.Th ta="center">%</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.learners.map((l) => (
                <Table.Tr key={l.learner}>
                  <Table.Td style={{ position: "sticky", left: 0, background: "var(--mantine-color-body)" }}>
                    <Text size="xs" fw={600} truncate>{l.name}</Text>
                  </Table.Td>
                  {data.days.map((d) => {
                    const mark = l.days[d.date];
                    return (
                      <Table.Td key={d.date} ta="center" p={2} bg={d.school_day ? undefined : "var(--mantine-color-default-hover)"}>
                        {mark ? <span style={{ color: MARK[mark]?.color, fontWeight: 700 }}>{MARK[mark]?.text}</span> : null}
                      </Table.Td>
                    );
                  })}
                  <Table.Td ta="center">{l.present}</Table.Td>
                  <Table.Td ta="center" c={l.absent ? "red" : undefined}>{l.absent}</Table.Td>
                  <Table.Td ta="center">{l.rate === null ? "–" : l.rate}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      )}
      <Text size="xs" c="dimmed" p="md">
        ✓ present · A absent · L late · E excused. Shaded columns are weekends, public holidays and school holidays; red dates are
        school days without a register.
      </Text>
    </Card>
  );
}
