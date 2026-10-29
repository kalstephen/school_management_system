import { BarChart, DonutChart } from "@mantine/charts";
import { Card, Grid, Group, Select, Table, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get } from "@/api/client";
import { Empty, PageHeader, Section } from "@/components/common";
import { useClasses, useTerms } from "@/hooks/useSchool";

const DIVISION_COLORS: Record<string, string> = { I: "green.6", II: "teal.5", III: "yellow.5", IV: "orange.6", U: "red.6" };

export default function AnalyticsPage() {
  const { options: termOptions } = useTerms();
  const { options: classOptions } = useClasses();
  const [term, setTerm] = useState<string | null>(null);
  const [schoolClass, setSchoolClass] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["analytics", term, schoolClass],
    queryFn: () => get("/analytics/", { term, school_class: schoolClass }),
  });

  return (
    <>
      <PageHeader
        title="Academic analytics"
        description="Subject and teacher performance, and how attendance relates to results. Built from computed term results."
        actions={
          <Group>
            <Select placeholder="Current term" data={termOptions} value={term} onChange={setTerm} clearable w={200} />
            <Select placeholder="All classes" data={classOptions} value={schoolClass} onChange={setSchoolClass} clearable w={160} />
          </Group>
        }
      />
      {!data?.subjects?.length ? (
        <Card>
          <Empty title="No results computed for this term yet">Results appear once report cards are generated (or a preview is computed).</Empty>
        </Card>
      ) : (
        <Grid>
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Section title={`Average score by subject — ${data.term}`}>
              <BarChart h={300} data={data.subjects} dataKey="subject" series={[{ name: "average", label: "Average %", color: "brand.6" }]} yAxisProps={{ domain: [0, 100] }} />
            </Section>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <Section title="Divisions (PLE classes)">
              {Object.keys(data.divisions).length ? (
                <Group justify="center">
                  <DonutChart
                    size={200}
                    thickness={30}
                    withLabels
                    data={Object.entries(data.divisions).map(([name, value]) => ({ name: `Div ${name}`, value: value as number, color: DIVISION_COLORS[name] ?? "gray.5" }))}
                  />
                </Group>
              ) : (
                <Empty title="No divisions" />
              )}
            </Section>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <Section title="Attendance against results">
              <BarChart h={260} data={data.attendance_vs_results} dataKey="attendance" series={[{ name: "average", label: "Average %", color: "teal.6" }]} yAxisProps={{ domain: [0, 100] }} />
              <Text size="xs" c="dimmed" mt="xs">
                Average term score of learners grouped by attendance rate.
              </Text>
            </Section>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <Section title="Teacher performance">
              <Table.ScrollContainer minWidth={420} mah={300}>
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Teacher</Table.Th>
                      <Table.Th>Subject · class</Table.Th>
                      <Table.Th>Average</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {data.teachers.flatMap((t: any) =>
                      t.classes.map((c: any, i: number) => (
                        <Table.Tr key={`${t.teacher}-${c.subject}-${c.class}`}>
                          <Table.Td>{i === 0 ? t.teacher : ""}</Table.Td>
                          <Table.Td>
                            {c.subject} · {c.class}
                          </Table.Td>
                          <Table.Td>{c.average}%</Table.Td>
                        </Table.Tr>
                      )),
                    )}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            </Section>
          </Grid.Col>
        </Grid>
      )}
    </>
  );
}
