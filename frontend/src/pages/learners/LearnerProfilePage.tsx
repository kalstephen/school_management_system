import { BarChart, LineChart } from "@mantine/charts";
import {
  Alert,
  Anchor,
  Avatar,
  Badge,
  Button,
  Card,
  Center,
  Grid,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import {
  IconAlertTriangle,
  IconArrowDownRight,
  IconArrowUpRight,
  IconFileCertificate,
  IconPrinter,
  IconStethoscope,
} from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { get, openFile } from "@/api/client";
import { Empty, Section, StatusBadge } from "@/components/common";
import { date, dateTime, num, titleCase } from "@/utils/format";

function Indicator({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <Card padding="sm">
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
        {label}
      </Text>
      <Text fw={700} size="lg" c={color}>
        {value}
      </Text>
    </Card>
  );
}

function SimpleTable({ columns, rows }: { columns: [string, string, ((row: any) => React.ReactNode)?][]; rows: any[] }) {
  if (!rows?.length) return <Empty title="Nothing recorded" />;
  return (
    <Table.ScrollContainer minWidth={500}>
      <Table>
        <Table.Thead>
          <Table.Tr>
            {columns.map(([key, label]) => (
              <Table.Th key={key}>{label}</Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row, i) => (
            <Table.Tr key={row.id ?? i}>
              {columns.map(([key, , render]) => (
                <Table.Td key={key}>{render ? render(row) : String(row[key] ?? "–")}</Table.Td>
              ))}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

export default function LearnerProfilePage() {
  const { id } = useParams();
  const { data, isLoading, error } = useQuery({ queryKey: ["profile", id], queryFn: () => get(`/learners/${id}/profile/`) });

  if (isLoading)
    return (
      <Center h="50vh">
        <Loader />
      </Center>
    );
  if (error || !data) return <Alert color="red">This learner could not be loaded, or is outside your classes.</Alert>;

  const { header: h, tabs, analytics } = data;
  const ind = h.indicators;
  const latestCard = tabs.academics?.report_cards?.find((c: any) => c.status === "Published");

  return (
    <Stack gap="lg">
      <Card>
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Group gap="lg" wrap="nowrap">
            <Avatar src={h.photo} size={96} radius="md" color="brand">
              {h.first_name[0]}
              {h.last_name[0]}
            </Avatar>
            <Stack gap={4}>
              <Group gap="xs">
                <Title order={2}>{h.name}</Title>
                <StatusBadge value={h.status.toLowerCase()} />
                {ind.medical_alert && (
                  <Badge color="red" leftSection={<IconStethoscope size={12} />}>
                    {ind.medical_alert}
                  </Badge>
                )}
              </Group>
              <Text c="dimmed" size="sm">
                Adm. {h.adm_no}
                {h.lin ? ` · LIN ${h.lin}` : ""} · {h.sex}
                {h.date_of_birth ? ` · born ${date(h.date_of_birth)}` : ""}
              </Text>
              <Group gap="xs">
                <Badge size="lg" variant="light">
                  {h.class ? `${h.class}${h.stream ?? ""}` : "Not enrolled this term"}
                </Badge>
                {h.house && <Badge variant="outline">{h.house} house</Badge>}
                <Badge variant="outline" color="grape">
                  {h.residence}
                </Badge>
              </Group>
            </Stack>
          </Group>
          <Group gap="xs" className="no-print">
            {latestCard && (
              <Button variant="light" leftSection={<IconFileCertificate size={16} />} onClick={() => openFile(`/report-cards/${latestCard.id}/pdf/`)}>
                Latest report card
              </Button>
            )}
            <Button variant="default" leftSection={<IconPrinter size={16} />} onClick={() => window.print()}>
              Print profile
            </Button>
          </Group>
        </Group>
        <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }} mt="lg">
          <Indicator label="Average" value={ind.average === null ? "–" : `${num(ind.average)}%`} />
          <Indicator label="Position" value={ind.position ? `${ind.position} / ${ind.out_of}` : "–"} />
          <Indicator label="Aggregate" value={ind.aggregate ? `${ind.aggregate} · Div ${ind.division}` : "–"} />
          <Indicator label="Attendance" value={ind.attendance_rate === null ? "–" : `${ind.attendance_rate}%`} color={ind.attendance_rate !== null && ind.attendance_rate < 80 ? "red" : undefined} />
          <Indicator label="Open cases" value={ind.open_discipline_cases} color={ind.open_discipline_cases ? "orange" : undefined} />
          <Indicator label="Promotion" value={ind.promotion_status ?? analytics.projected_promotion?.outcome ?? "–"} />
        </SimpleGrid>
      </Card>

      {analytics.early_warnings?.length > 0 && (
        <Alert color="orange" icon={<IconAlertTriangle size={18} />} title="Early warnings">
          <Stack gap={2}>
            {analytics.early_warnings.map((w: any) => (
              <Text size="sm" key={w.kind}>
                {w.message}
              </Text>
            ))}
          </Stack>
        </Alert>
      )}

      <Tabs defaultValue="overview" keepMounted={false}>
        <Tabs.List className="no-print">
          <Tabs.Tab value="overview">Overview</Tabs.Tab>
          <Tabs.Tab value="personal">Personal & guardians</Tabs.Tab>
          {tabs.academics && <Tabs.Tab value="academics">Academics</Tabs.Tab>}
          {tabs.attendance && <Tabs.Tab value="attendance">Attendance</Tabs.Tab>}
          {tabs.discipline && <Tabs.Tab value="discipline">Discipline & welfare</Tabs.Tab>}
          {tabs.health && <Tabs.Tab value="health">Health</Tabs.Tab>}
          {tabs.library_requirements && <Tabs.Tab value="library">Library & requirements</Tabs.Tab>}
          <Tabs.Tab value="history">History</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="overview" pt="md">
          <Grid>
            <Grid.Col span={{ base: 12, lg: 6 }}>
              <Section title="Performance trend" actions={<Anchor component={Link} to={`/history?learner=${id}`} size="sm">Full history and past report cards</Anchor>}>
                {analytics.trend?.length ? (
                  <LineChart h={240} data={analytics.trend} dataKey="term" series={[{ name: "average", label: "Average %", color: "brand.6" }]} curveType="monotone" yAxisProps={{ domain: [0, 100] }} />
                ) : (
                  <Empty title="No results yet" />
                )}
              </Section>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 6 }}>
              <Section title="Subjects against the class average">
                {tabs.academics?.current_subjects?.length ? (
                  <BarChart
                    h={240}
                    data={tabs.academics.current_subjects}
                    dataKey="subject"
                    series={[
                      { name: "score", label: "Learner", color: "brand.6" },
                      { name: "class_average", label: "Class", color: "gray.5" },
                    ]}
                    yAxisProps={{ domain: [0, 100] }}
                    withLegend
                  />
                ) : (
                  <Empty title="No results this term" />
                )}
              </Section>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 6 }}>
              <Section title="Change since last term">
                <SimpleTable
                  rows={analytics.subject_changes}
                  columns={[
                    ["subject", "Subject"],
                    ["previous", "Last term"],
                    ["current", "This term"],
                    [
                      "change",
                      "Change",
                      (r) => (
                        <Group gap={4} c={r.dropped ? "red" : r.change >= 0 ? "green" : undefined}>
                          {r.change >= 0 ? <IconArrowUpRight size={14} /> : <IconArrowDownRight size={14} />}
                          {r.change}
                        </Group>
                      ),
                    ],
                  ]}
                />
              </Section>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 6 }}>
              <Section title="Attendance and results by term">
                <SimpleTable
                  rows={analytics.attendance_vs_results}
                  columns={[
                    ["term", "Term"],
                    ["rate", "Attendance", (r) => (r.rate === null ? "–" : `${r.rate}%`)],
                    ["absent", "Days absent"],
                    ["average", "Average", (r) => num(r.average)],
                  ]}
                />
                {analytics.projected_promotion && (
                  <Text size="sm" mt="sm">
                    Projected promotion: <b>{analytics.projected_promotion.outcome}</b>
                    {analytics.projected_promotion.rule ? ` (${analytics.projected_promotion.rule})` : ""}
                  </Text>
                )}
              </Section>
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        <Tabs.Panel value="personal" pt="md">
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <Section title="Bio data">
              <Table>
                <Table.Tbody>
                  {["nationality", "religion", "district", "address", "previous_school", "admitted_on", "special_needs"].map((key) => (
                    <Table.Tr key={key}>
                      <Table.Th w={180}>{titleCase(key)}</Table.Th>
                      <Table.Td>{key === "admitted_on" ? date(tabs.personal[key]) : tabs.personal[key] || "–"}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Section>
            <Stack>
              <Section title="Guardians">
                <SimpleTable
                  rows={tabs.personal.guardians}
                  columns={[
                    ["name", "Name", (g) => <Text size="sm" fw={g.is_primary ? 600 : 400}>{g.name}</Text>],
                    ["relationship", "Relationship"],
                    ["phone", "Phone", (g) => (g.phone ? <Anchor href={`tel:${g.phone}`}>{g.phone}</Anchor> : "–")],
                    ["email", "Email"],
                  ]}
                />
              </Section>
              <Section title="Siblings in the school">
                {tabs.personal.siblings.length ? (
                  <Group gap="xs">
                    {tabs.personal.siblings.map((s: any) => (
                      <Badge key={s.id} component="a" href={`/learners/${s.id}`} variant="light" style={{ cursor: "pointer" }}>
                        {s.name}
                      </Badge>
                    ))}
                  </Group>
                ) : (
                  <Text size="sm" c="dimmed">
                    None
                  </Text>
                )}
              </Section>
              <Section title="Documents">
                {tabs.personal.documents.length ? (
                  <Stack gap={4}>
                    {tabs.personal.documents.map((d: any) => (
                      <Anchor key={d.id} href={d.url} target="_blank">
                        {d.title}
                      </Anchor>
                    ))}
                  </Stack>
                ) : (
                  <Text size="sm" c="dimmed">
                    No documents uploaded
                  </Text>
                )}
              </Section>
            </Stack>
          </SimpleGrid>
        </Tabs.Panel>

        {tabs.academics && (
          <Tabs.Panel value="academics" pt="md">
            <Stack>
              <Section title="Results by term">
                <SimpleTable
                  rows={tabs.academics.results}
                  columns={[
                    ["term", "Term"],
                    ["average", "Average", (r) => num(r.average)],
                    ["position", "Position", (r) => (r.position ? `${r.position} / ${r.out_of}` : "–")],
                    ["aggregate", "Aggregate"],
                    ["division", "Division"],
                    ["points", "Points"],
                  ]}
                />
              </Section>
              <Section title="Report cards">
                <SimpleTable
                  rows={tabs.academics.report_cards}
                  columns={[
                    ["term", "Term"],
                    ["serial", "Serial"],
                    ["status", "Status", (r) => <StatusBadge value={r.status.toLowerCase()} />],
                    ["pdf", "", (r) => <Anchor onClick={() => openFile(`/report-cards/${r.id}/pdf/`)}>Open PDF</Anchor>],
                  ]}
                />
              </Section>
              {(tabs.academics.subjects_taken.length > 0 || tabs.academics.combination) && (
                <Section title="Subject choices">
                  <Group gap="xs">
                    {tabs.academics.combination && <Badge>{tabs.academics.combination}</Badge>}
                    {tabs.academics.subjects_taken.map((s: string) => (
                      <Badge key={s} variant="light">
                        {s}
                      </Badge>
                    ))}
                  </Group>
                </Section>
              )}
              {tabs.academics.competencies.length > 0 && (
                <Section title="CBC competencies (activities of integration)">
                  <SimpleTable
                    rows={tabs.academics.competencies}
                    columns={[
                      ["competency__subject__name", "Subject"],
                      ["competency__topic", "Topic"],
                      ["score", "Score (of 3)"],
                    ]}
                  />
                </Section>
              )}
            </Stack>
          </Tabs.Panel>
        )}

        {tabs.attendance && (
          <Tabs.Panel value="attendance" pt="md">
            <SimpleGrid cols={{ base: 1, md: 2 }}>
              <Section title="This term">
                {tabs.attendance.this_term ? (
                  <Group>
                    <Indicator label="Rate" value={tabs.attendance.this_term.rate === null ? "–" : `${tabs.attendance.this_term.rate}%`} />
                    <Indicator label="Present" value={tabs.attendance.this_term.present} />
                    <Indicator label="Absent" value={tabs.attendance.this_term.absent} />
                    <Indicator label="Late" value={tabs.attendance.this_term.late} />
                  </Group>
                ) : (
                  <Empty title="No term" />
                )}
              </Section>
              <Section title="Absences and lateness">
                <SimpleTable
                  rows={tabs.attendance.calendar.filter((r: any) => r.status !== "present")}
                  columns={[
                    ["date", "Date", (r) => date(r.date, "ddd D MMM")],
                    ["status", "Status", (r) => <StatusBadge value={r.status} />],
                    ["reason", "Reason"],
                  ]}
                />
              </Section>
            </SimpleGrid>
          </Tabs.Panel>
        )}

        {tabs.discipline && (
          <Tabs.Panel value="discipline" pt="md">
            <Stack>
              <Section title="Discipline cases">
                <SimpleTable
                  rows={tabs.discipline.cases}
                  columns={[
                    ["date", "Date", (r) => date(r.date)],
                    ["category", "Category"],
                    ["severity", "Severity", (r) => <StatusBadge value={r.severity} />],
                    ["description", "What happened"],
                    ["status", "Status", (r) => <StatusBadge value={r.status} />],
                  ]}
                />
              </Section>
              <SimpleGrid cols={{ base: 1, md: 2 }}>
                <Section title="Counselling referrals">
                  <SimpleTable rows={tabs.discipline.counselling} columns={[["date", "Date", (r) => date(r.date)], ["reason", "Reason"], ["status", "Status", (r) => <StatusBadge value={r.status} />]]} />
                </Section>
                <Section title="Achievements and awards">
                  <SimpleTable rows={tabs.discipline.achievements} columns={[["date", "Date", (r) => date(r.date)], ["title", "Achievement"], ["category", "Category"]]} />
                </Section>
              </SimpleGrid>
            </Stack>
          </Tabs.Panel>
        )}

        {tabs.health && (
          <Tabs.Panel value="health" pt="md">
            <Alert color="gray" mb="md" icon={<ThemeIcon size="sm" color="gray" variant="transparent"><IconStethoscope size={16} /></ThemeIcon>}>
              Health records are confidential. Your view has been recorded in the access log.
            </Alert>
            <SimpleGrid cols={{ base: 1, md: 2 }}>
              <Section title="Medical information">
                <Text size="sm">
                  <b>Allergies:</b> {tabs.health.allergies || "None recorded"}
                </Text>
                <Text size="sm" mt="xs">
                  <b>Notes:</b> {tabs.health.medical_notes || "None recorded"}
                </Text>
              </Section>
              <Section title="Immunisations">
                <SimpleTable rows={tabs.health.immunisations} columns={[["vaccine", "Vaccine"], ["dose", "Dose"], ["date", "Date", (r) => date(r.date)]]} />
              </Section>
            </SimpleGrid>
            <Section title="Sickbay visits">
              <SimpleTable
                rows={tabs.health.visits}
                columns={[
                  ["visited_at", "When", (r) => dateTime(r.visited_at)],
                  ["complaint", "Complaint"],
                  ["treatment", "Treatment"],
                  ["outcome", "Outcome", (r) => titleCase(r.outcome)],
                ]}
              />
            </Section>
          </Tabs.Panel>
        )}

        {tabs.library_requirements && (
          <Tabs.Panel value="library" pt="md">
            <SimpleGrid cols={{ base: 1, md: 2 }}>
              {tabs.library_requirements.loans && (
                <Section title="Books on loan">
                  <SimpleTable
                    rows={tabs.library_requirements.loans}
                    columns={[
                      ["title", "Book"],
                      ["due_on", "Due", (r) => date(r.due_on)],
                      ["returned_on", "Returned", (r) => (r.returned_on ? date(r.returned_on) : r.overdue ? <Badge color="red">Overdue</Badge> : "On loan")],
                    ]}
                  />
                </Section>
              )}
              {tabs.library_requirements.requirements && (
                <Section title="Scholastic requirements this term">
                  <SimpleTable
                    rows={tabs.library_requirements.requirements}
                    columns={[
                      ["name", "Item"],
                      ["needed", "Needed"],
                      ["brought", "Brought"],
                      ["cleared", "Status", (r) => <StatusBadge value={r.cleared ? "completed" : "pending"} label={r.cleared ? "Cleared" : "Pending"} />],
                    ]}
                  />
                </Section>
              )}
            </SimpleGrid>
          </Tabs.Panel>
        )}

        <Tabs.Panel value="history" pt="md">
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <Section title="Classes by term">
              <SimpleTable rows={tabs.history.enrolments} columns={[["term", "Term"], ["class", "Class"], ["stream", "Stream"]]} />
            </Section>
            <Section title="Promotions and changes">
              <SimpleTable
                rows={[
                  ...tabs.history.promotions.map((p: any) => ({ when: p.term, what: p.decision + (p.overridden ? ` (overridden: ${p.reason})` : "") })),
                  ...tabs.history.stream_changes.map((s: any) => ({ when: date(s.created_at), what: `Moved ${s.from_class__name} → ${s.to_class__name}: ${s.reason}` })),
                  ...tabs.history.exits.map((e: any) => ({ when: date(e.date), what: `${titleCase(e.kind)} ${e.destination_school ? `to ${e.destination_school}` : ""}` })),
                ]}
                columns={[["when", "When"], ["what", "What happened"]]}
              />
            </Section>
          </SimpleGrid>
          {tabs.history.audit && (
            <Section title="Edit trail">
              <SimpleTable
                rows={tabs.history.audit}
                columns={[
                  ["timestamp", "When", (r) => dateTime(r.timestamp)],
                  ["user__username", "By"],
                  ["action", "Action", (r) => <StatusBadge value={r.action === "create" ? "active" : r.action} label={titleCase(r.action)} />],
                  [
                    "changes",
                    "Changes",
                    (r) => (
                      <Text size="xs">
                        {Object.entries(r.changes)
                          .map(([k, v]: any) => `${k}: ${v[0] ?? "–"} → ${v[1] ?? "–"}`)
                          .join("; ")}
                      </Text>
                    ),
                  ],
                ]}
              />
            </Section>
          )}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
