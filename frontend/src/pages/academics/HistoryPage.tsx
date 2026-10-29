import { LineChart } from "@mantine/charts";
import { Anchor, Badge, Card, Group, Loader, ScrollArea, Select, SimpleGrid, Stack, Table, Tabs, Text } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconArrowDownRight, IconArrowUpRight, IconFileTypePdf } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { get, openFile } from "@/api/client";
import { Empty, PageHeader, StatCard } from "@/components/common";
import { useClasses } from "@/hooks/useSchool";

// Two series checked with the colour validator (blue text shade and amber text shade).
const AVERAGE = "#1565C0";
const PASS_RATE = "#9A5B00";

/** A value with its change from the previous term. */
function Delta({ value, previous, suffix = "" }: { value: number | null | undefined; previous?: number | null; suffix?: string }) {
  if (value === null || value === undefined) return <Text size="sm" c="dimmed">–</Text>;
  const change = previous === null || previous === undefined ? null : Math.round((value - previous) * 10) / 10;
  return (
    <Group gap={4} wrap="nowrap" justify="flex-end">
      <Text size="sm" fw={600}>{value}{suffix}</Text>
      {change !== null && change !== 0 && (
        <Text size="xs" c={change > 0 ? "green.8" : "red.7"} style={{ display: "flex", alignItems: "center" }}>
          {change > 0 ? <IconArrowUpRight size={12} /> : <IconArrowDownRight size={12} />}
          {Math.abs(change)}
        </Text>
      )}
    </Group>
  );
}

function TrendChart({ data }: { data: { label: string; average: number | null; pass_rate?: number | null }[] }) {
  const withPass = data.some((d) => d.pass_rate !== undefined);
  return (
    <LineChart
      h={260}
      data={data}
      dataKey="label"
      yAxisProps={{ domain: [0, 100] }}
      unit="%"
      withLegend={withPass}
      legendProps={{ verticalAlign: "top", height: 32 }}
      strokeWidth={2}
      dotProps={{ r: 4 }}
      activeDotProps={{ r: 6 }}
      connectNulls
      series={[
        { name: "average", label: "Average mark", color: AVERAGE },
        ...(withPass ? [{ name: "pass_rate", label: "Learners passing (50%+)", color: PASS_RATE, strokeDasharray: "6 4" }] : []),
      ]}
    />
  );
}

function SchoolHistory() {
  const { data, isLoading } = useQuery({ queryKey: ["history", "school"], queryFn: () => get("/analytics/history/") });
  if (isLoading) return <Loader />;
  if (!data?.terms.length) return <Empty title="No results yet">History appears once a term's marks are approved.</Empty>;
  const chart = data.school.map((s: any) => ({ label: data.terms.find((t: any) => t.id === s.term)?.label, average: s.average, pass_rate: s.pass_rate }));
  return (
    <Stack>
      <Card>
        <Text fw={650} mb="xs">Whole school, term by term</Text>
        <TrendChart data={chart} />
      </Card>
      <Card p={0}>
        <Text fw={650} p="md" pb={0}>Average mark by class</Text>
        <Text size="xs" c="dimmed" px="md">Arrows show the change from the term before.</Text>
        <ScrollArea>
          <Table miw={500} mt="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Class</Table.Th>
                {data.terms.map((t: any) => <Table.Th key={t.id} ta="right">{t.label}</Table.Th>)}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.classes.map((c: any) => (
                <Table.Tr key={c.id}>
                  <Table.Td fw={600}>{c.name}</Table.Td>
                  {data.terms.map((t: any, i: number) => (
                    <Table.Td key={t.id}>
                      <Delta value={c.terms[t.id]} previous={i ? c.terms[data.terms[i - 1].id] : undefined} />
                    </Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      </Card>
    </Stack>
  );
}

function ClassHistory() {
  const { options, streamOptions } = useClasses();
  const [schoolClass, setSchoolClass] = useState<string | null>(null);
  const [stream, setStream] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["history", "class", schoolClass, stream],
    enabled: !!schoolClass,
    queryFn: () => get("/analytics/history/", { school_class: schoolClass, stream }),
  });
  const terms: any[] = data?.terms ?? [];
  const last = terms[terms.length - 1];
  const before = terms[terms.length - 2];
  return (
    <Stack>
      <Group>
        <Select label="Class" data={options} value={schoolClass} onChange={(v) => { setSchoolClass(v); setStream(null); }} searchable w={200} placeholder="Choose a class" />
        <Select label="Stream" data={streamOptions(schoolClass)} value={stream} onChange={setStream} clearable w={200} placeholder="Whole class" disabled={!streamOptions(schoolClass).length} />
      </Group>
      {!schoolClass && <Empty title="Choose a class">See its results in every term, subject by subject.</Empty>}
      {isLoading && <Loader />}
      {schoolClass && data && !terms.length && <Empty title="No results for this class yet" />}
      {last && (
        <>
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
            <StatCard label={`Average · ${last.label}`} value={last.average === null ? "–" : `${last.average}%`} hint={before ? `${before.average ?? "–"}% the term before` : "First term on record"} />
            <StatCard label="Learners passing (50%+)" value={last.pass_rate === null ? "–" : `${last.pass_rate}%`} hint={`${last.learners} learners`} color="orange" />
            <StatCard label="Highest · lowest average" value={`${last.highest ?? "–"} · ${last.lowest ?? "–"}`} color="teal" />
            <StatCard
              label="Divisions"
              value={Object.keys(last.divisions).length ? Object.entries(last.divisions).map(([d, n]) => `${d}: ${n}`).join("  ") : "–"}
              hint="PLE classes only"
              color="grape"
            />
          </SimpleGrid>
          <Card>
            <Text fw={650} mb="xs">{data.class}: term by term</Text>
            <TrendChart data={terms.map((t) => ({ label: t.label, average: t.average, pass_rate: t.pass_rate }))} />
          </Card>
          <Card p={0}>
            <Text fw={650} p="md" pb={0}>Subject averages by term</Text>
            <ScrollArea>
              <Table miw={500} mt="xs">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Subject</Table.Th>
                    {terms.map((t) => <Table.Th key={t.term} ta="right">{t.label}</Table.Th>)}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {data.subjects.map((s: string) => (
                    <Table.Tr key={s}>
                      <Table.Td fw={600}>{s}</Table.Td>
                      {terms.map((t, i) => (
                        <Table.Td key={t.term}><Delta value={t.subjects[s]} previous={i ? terms[i - 1].subjects[s] : undefined} /></Table.Td>
                      ))}
                    </Table.Tr>
                  ))}
                  {terms.some((t) => Object.keys(t.streams).length > 1) &&
                    Object.keys(terms[terms.length - 1].streams).map((name) => (
                      <Table.Tr key={`stream-${name}`}>
                        <Table.Td c="dimmed">Stream {name}</Table.Td>
                        {terms.map((t, i) => (
                          <Table.Td key={t.term}><Delta value={t.streams[name]} previous={i ? terms[i - 1].streams[name] : undefined} /></Table.Td>
                        ))}
                      </Table.Tr>
                    ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          </Card>
        </>
      )}
    </Stack>
  );
}

function LearnerHistory({ initial }: { initial: string | null }) {
  const [learner, setLearner] = useState<string | null>(initial);
  const [search, setSearch] = useState("");
  const [query] = useDebouncedValue(search, 250);
  const { data: hits = [] } = useQuery({
    queryKey: ["learner-search", query],
    enabled: query.trim().length >= 2,
    queryFn: () => get<any[]>("/learners/search/", { q: query }),
  });
  const { data, isLoading, error } = useQuery({
    queryKey: ["history", "learner", learner],
    enabled: !!learner,
    retry: false,
    queryFn: () => get(`/analytics/history/learner/${learner}/`),
  });
  const terms: any[] = data?.terms ?? [];
  const subjects = Array.from(new Set(terms.flatMap((t) => Object.keys(t.subjects))));
  return (
    <Stack>
      <Select
        label="Learner"
        placeholder="Type a name or admission number"
        searchable
        searchValue={search}
        onSearchChange={setSearch}
        data={hits.map((h: any) => ({ value: String(h.id), label: `${h.name} · ${h.adm_no}${h.class ? ` · ${h.class}` : ""}` }))}
        value={learner}
        onChange={setLearner}
        nothingFoundMessage={query.length >= 2 ? "No learner found" : "Type at least two letters"}
        w={{ base: "100%", sm: 420 }}
        filter={({ options }) => options}
      />
      {!learner && <Empty title="Find a learner">See every term's results and open past report cards.</Empty>}
      {isLoading && <Loader />}
      {error && <Text c="red" size="sm">{(error as Error).message}</Text>}
      {data && (
        <>
          <Group justify="space-between">
            <div>
              <Anchor component={Link} to={`/learners/${data.learner.id}`} fw={700} size="lg">{data.learner.name}</Anchor>
              <Text size="sm" c="dimmed">{data.learner.adm_no} · {terms.length} term(s) on record</Text>
            </div>
          </Group>
          {!terms.length ? (
            <Empty title="No results on record yet" />
          ) : (
            <>
              <Card>
                <Text fw={650} mb="xs">Average mark, term by term</Text>
                <TrendChart data={terms.map((t) => ({ label: t.label, average: t.average }))} />
              </Card>
              <Card p={0}>
                <ScrollArea>
                  <Table miw={600}>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th />
                        {terms.map((t) => (
                          <Table.Th key={t.term} ta="right">
                            {t.label}
                            <Text size="xs" c="dimmed" fw={400}>{t.class}</Text>
                          </Table.Th>
                        ))}
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {subjects.map((s) => (
                        <Table.Tr key={s}>
                          <Table.Td fw={600}>{s}</Table.Td>
                          {terms.map((t, i) => (
                            <Table.Td key={t.term}>
                              <Group gap={6} justify="flex-end" wrap="nowrap">
                                <Delta value={t.subjects[s]} previous={i ? terms[i - 1].subjects[s] : undefined} />
                                {t.grades[s] && <Badge size="xs" variant="light">{t.grades[s]}</Badge>}
                              </Group>
                            </Table.Td>
                          ))}
                        </Table.Tr>
                      ))}
                      <Table.Tr>
                        <Table.Td fw={700}>Average</Table.Td>
                        {terms.map((t, i) => <Table.Td key={t.term}><Delta value={t.average} previous={i ? terms[i - 1].average : undefined} /></Table.Td>)}
                      </Table.Tr>
                      <Table.Tr>
                        <Table.Td fw={700}>Aggregate · division</Table.Td>
                        {terms.map((t) => <Table.Td key={t.term} ta="right">{t.aggregate ?? "–"}{t.division ? ` · Div ${t.division}` : ""}</Table.Td>)}
                      </Table.Tr>
                      <Table.Tr>
                        <Table.Td fw={700}>Position</Table.Td>
                        {terms.map((t) => <Table.Td key={t.term} ta="right">{t.position ? `${t.position} of ${t.out_of}` : "–"}</Table.Td>)}
                      </Table.Tr>
                      <Table.Tr>
                        <Table.Td fw={700}>Report card</Table.Td>
                        {terms.map((t) => (
                          <Table.Td key={t.term} ta="right">
                            {t.report_card ? (
                              <Anchor size="sm" onClick={() => openFile(`/report-cards/${t.report_card.id}/pdf/`)}>
                                <IconFileTypePdf size={14} /> {t.report_card.status === "published" ? "Open" : "Draft"}
                              </Anchor>
                            ) : (
                              <Text size="sm" c="dimmed">Not issued</Text>
                            )}
                          </Table.Td>
                        ))}
                      </Table.Tr>
                    </Table.Tbody>
                  </Table>
                </ScrollArea>
              </Card>
            </>
          )}
        </>
      )}
    </Stack>
  );
}

/** Results across terms: the whole school, a class or stream, and one learner. */
export default function HistoryPage() {
  const [params] = useSearchParams();
  const learner = params.get("learner");
  return (
    <>
      <PageHeader
        title="Performance history"
        description="How results have moved from term to term: the whole school, each class and stream, each subject and each learner, with past report cards."
      />
      <Tabs defaultValue={learner ? "learner" : "school"} keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="school">Whole school</Tabs.Tab>
          <Tabs.Tab value="class">Class & subjects</Tabs.Tab>
          <Tabs.Tab value="learner">Learner</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="school"><SchoolHistory /></Tabs.Panel>
        <Tabs.Panel value="class"><ClassHistory /></Tabs.Panel>
        <Tabs.Panel value="learner"><LearnerHistory initial={learner} /></Tabs.Panel>
      </Tabs>
    </>
  );
}
