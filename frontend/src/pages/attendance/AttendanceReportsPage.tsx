import { Badge, Card, Group, Progress, Select, Table, Tabs, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { get } from "@/api/client";
import { Empty, PageHeader } from "@/components/common";
import { ResourceTable } from "@/components/ResourceTable";
import { useClasses } from "@/hooks/useSchool";
import { date } from "@/utils/format";

import { ClassRegister } from "./ClassRegister";

interface SummaryRow {
  learner_id: number;
  name: string;
  adm_no: string;
  days: number;
  present: number;
  absent: number;
  rate: number | null;
  consecutive_absences: number;
  chronic: boolean;
  class?: string;
}

function SummaryTable({ rows }: { rows: SummaryRow[] }) {
  if (!rows.length) return <Empty title="No attendance recorded yet" />;
  return (
    <Table.ScrollContainer minWidth={600}>
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Learner</Table.Th>
            {rows[0].class !== undefined && <Table.Th>Class</Table.Th>}
            <Table.Th>Days</Table.Th>
            <Table.Th>Absent</Table.Th>
            <Table.Th w={220}>Attendance</Table.Th>
            <Table.Th>Flag</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((r) => (
            <Table.Tr key={r.learner_id}>
              <Table.Td>
                <Text component={Link} to={`/learners/${r.learner_id}`} size="sm" fw={600} c="brand">
                  {r.name}
                </Text>
                <Text size="xs" c="dimmed">{r.adm_no}</Text>
              </Table.Td>
              {r.class !== undefined && <Table.Td>{r.class}</Table.Td>}
              <Table.Td>{r.days}</Table.Td>
              <Table.Td>{r.absent}</Table.Td>
              <Table.Td>
                <Group gap="xs" wrap="nowrap">
                  <Progress value={r.rate ?? 0} color={r.rate !== null && r.rate < 80 ? "red" : "green"} w={120} />
                  <Text size="sm">{r.rate === null ? "–" : `${r.rate}%`}</Text>
                </Group>
              </Table.Td>
              <Table.Td>
                {r.chronic && (
                  <Badge color="red" variant="light">
                    {r.consecutive_absences >= 3 ? `${r.consecutive_absences} days in a row` : "Chronic absence"}
                  </Badge>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

export default function AttendanceReportsPage() {
  const { options, streamOptions } = useClasses();
  const [classId, setClassId] = useState<string | null>(null);
  const [streamId, setStreamId] = useState<string | null>(null);
  const summary = useQuery({
    queryKey: ["attendance-summary", classId, streamId],
    enabled: !!classId,
    queryFn: () => get<SummaryRow[]>("/attendance/summary/", { school_class: classId, stream: streamId }),
  });
  const chronic = useQuery({
    queryKey: ["attendance-chronic", classId, streamId],
    queryFn: () => get<SummaryRow[]>("/attendance/chronic/", { school_class: classId, stream: streamId }),
  });

  return (
    <>
      <PageHeader title="Attendance reports" description="Rates per learner this term, chronic absence flags, the monthly register and every register taken." />
      <Card mb="md">
        <Group>
          <Select label="Class" placeholder="All classes" data={options} value={classId} onChange={(v) => { setClassId(v); setStreamId(null); }} searchable clearable w={200} />
          <Select
            label="Stream"
            placeholder={streamOptions(classId).length ? "All streams" : "No streams"}
            data={streamOptions(classId)}
            value={streamId}
            onChange={setStreamId}
            disabled={!streamOptions(classId).length}
            clearable
            w={200}
          />
          <Text size="xs" c="dimmed" mt={22}>The filters apply to every tab.</Text>
        </Group>
      </Card>
      <Tabs defaultValue="chronic" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="chronic">
            Chronic absence {chronic.data?.length ? <Badge size="xs" color="red" ml={4}>{chronic.data.length}</Badge> : null}
          </Tabs.Tab>
          <Tabs.Tab value="class">Rates by learner</Tabs.Tab>
          <Tabs.Tab value="month">Monthly register</Tabs.Tab>
          <Tabs.Tab value="registers">Registers taken</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="chronic">
          <Card p={0}>
            <Text p="md" size="sm" c="dimmed">
              Learners below 80% attendance this term, or absent three or more school days in a row.
            </Text>
            <SummaryTable rows={chronic.data ?? []} />
          </Card>
        </Tabs.Panel>
        <Tabs.Panel value="class">
          <Card p={0}>{classId ? <SummaryTable rows={summary.data ?? []} /> : <Empty title="Choose a class above" />}</Card>
        </Tabs.Panel>
        <Tabs.Panel value="month">
          <ClassRegister classId={classId} streamId={streamId} />
        </Tabs.Panel>
        <Tabs.Panel value="registers">
          <ResourceTable
            endpoint="/attendance/sessions/"
            searchable={false}
            query={{ school_class: classId, stream: streamId }}
            filters={[{ name: "date", label: "Date", type: "date" }]}
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date, "ddd D MMM YYYY") },
              { key: "class_label", label: "Class" },
              { key: "slot", label: "Type", render: (r: any) => (r.slot ? "Lesson" : "Daily register") },
              { key: "present", label: "Present" },
              { key: "absent", label: "Absent" },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
