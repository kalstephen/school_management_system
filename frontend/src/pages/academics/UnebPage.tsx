import { BarChart, LineChart } from "@mantine/charts";
import { Alert, Button, Card, FileButton, Grid, Group, NumberInput, SegmentedControl, Stack, Table, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconUpload } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, errorMessage, get } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Empty, PageHeader, Section } from "@/components/common";
import { ResourceTable } from "@/components/ResourceTable";

export default function UnebPage() {
  const { can } = useAuth();
  const client = useQueryClient();
  const [level, setLevel] = useState("PLE");
  const [year, setYear] = useState<number>(new Date().getFullYear() - 1);
  const { data } = useQuery({ queryKey: ["uneb-analysis", level], queryFn: () => get(`/uneb-results/analysis/`, { level }) });
  const divisionKeys: string[] = Array.from(new Set((data?.years ?? []).flatMap((y: any) => Object.keys(y.divisions)))).sort() as string[];

  const upload = async (file: File | null) => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("year", String(year));
    form.append("level", level);
    try {
      const result = await api("/uneb-results/import/", { method: "POST", body: form });
      notifications.show({
        color: result.errors.length ? "orange" : "green",
        message: `${result.created} new, ${result.updated} updated${result.errors.length ? `, ${result.errors.length} row(s) skipped` : ""}.`,
      });
      client.invalidateQueries({ queryKey: ["uneb-analysis"] });
      client.invalidateQueries({ queryKey: ["list", "/uneb-results/"] });
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    }
  };

  return (
    <>
      <PageHeader
        title="UNEB results"
        description="Import national results when UNEB releases them, then compare divisions, subjects and teachers across years."
        actions={<SegmentedControl value={level} onChange={setLevel} data={["PLE", "UCE", "UACE"]} />}
      />
      {can("assessment.manage") && (
        <Card mb="md">
          <Group align="flex-end">
            <NumberInput label="Results year" value={year} onChange={(v) => setYear(Number(v))} w={140} min={2000} max={2100} />
            <FileButton accept=".csv,text/csv" onChange={upload}>
              {(props) => (
                <Button leftSection={<IconUpload size={16} />} {...props}>
                  Import {level} CSV
                </Button>
              )}
            </FileButton>
            <Text size="xs" c="dimmed" maw={520}>
              Columns: index_number, candidate_name, sex, aggregate, division (or result), points, then one column per subject code (e.g. ENG, MTC) holding the grade.
            </Text>
          </Group>
        </Card>
      )}
      {!data?.years?.length ? (
        <Card>
          <Empty title={`No ${level} results imported yet`} />
        </Card>
      ) : (
        <Grid>
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <Section title="Divisions by year">
              <BarChart
                h={260}
                data={data.years.map((y: any) => ({ year: String(y.year), ...y.divisions }))}
                dataKey="year"
                type="stacked"
                series={divisionKeys.map((key, i) => ({ name: key, label: `Div ${key}`, color: ["green.6", "teal.5", "yellow.5", "orange.6", "red.6", "gray.5"][i % 6] }))}
                withLegend
              />
            </Section>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <Section title={level === "UACE" ? "Average points" : "Average aggregate (lower is better)"}>
              <LineChart
                h={260}
                data={data.years.map((y: any) => ({ year: String(y.year), value: level === "UACE" ? y.average_points : y.average_aggregate }))}
                dataKey="year"
                series={[{ name: "value", label: level === "UACE" ? "Points" : "Aggregate", color: "brand.6" }]}
              />
            </Section>
          </Grid.Col>
          <Grid.Col span={12}>
            <Section title={`Grades by subject — ${data.latest_year}`}>
              <Table.ScrollContainer minWidth={600}>
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Subject</Table.Th>
                      <Table.Th>Grades</Table.Th>
                      <Table.Th>Teachers (candidate classes)</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {data.subjects.map((s: any) => (
                      <Table.Tr key={s.code}>
                        <Table.Td fw={600}>{s.code}</Table.Td>
                        <Table.Td>
                          {Object.entries(s.grades)
                            .sort()
                            .map(([g, n]) => `${g}: ${n}`)
                            .join(" · ")}
                        </Table.Td>
                        <Table.Td>{s.teachers.join(", ") || "–"}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            </Section>
          </Grid.Col>
        </Grid>
      )}
      <Stack mt="lg">
        <Alert color="gray">Candidates are matched to learner records by name; unmatched rows are still counted.</Alert>
        <ResourceTable
          endpoint="/uneb-results/"
          query={{ level }}
          filters={[{ name: "year", label: "Year", options: (data?.years ?? []).map((y: any) => ({ value: String(y.year), label: String(y.year) })) }]}
          columns={[
            { key: "year", label: "Year" },
            { key: "index_number", label: "Index no." },
            { key: "candidate_name", label: "Candidate" },
            { key: "aggregate", label: "Aggregate" },
            { key: "division", label: "Division / result" },
            { key: "grades", label: "Grades", render: (r: any) => Object.entries(r.subject_grades).map(([k, v]) => `${k} ${v}`).join(", ") },
          ]}
        />
      </Stack>
    </>
  );
}
