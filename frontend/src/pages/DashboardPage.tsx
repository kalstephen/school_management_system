import { BarChart, DonutChart } from "@mantine/charts";
import {
  Alert,
  Anchor,
  Avatar,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  List,
  Paper,
  Progress,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  ThemeIcon,
  UnstyledButton,
} from "@mantine/core";
import {
  IconAlertTriangle,
  IconCalendarEvent,
  IconCash,
  IconClipboardCheck,
  IconListCheck,
  IconMapPin,
  IconSchool,
  IconUsers,
  IconUsersGroup,
} from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate } from "react-router";

import { get } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Empty, Section, StatCard, StatusBadge } from "@/components/common";
import { MODULE_META } from "@/components/moduleIcons";
import { date, num, ugx, ugxShort } from "@/utils/format";

const CHART_COLORS = ["brand.6", "teal.6", "orange.6", "grape.6", "cyan.6", "red.6", "lime.6", "indigo.6"];

const TILE_LABELS: Record<string, string> = {
  setup: "School setup", admissions: "Admissions", learners: "Learners", staff: "Staff & HR", curriculum: "Curriculum",
  timetable: "Timetable", attendance: "Attendance", assessment: "Exams & reports", promotion: "Promotion",
  discipline: "Discipline", communication: "Notices", finance: "Finance", library: "Library", sickbay: "Sickbay",
  stores: "Stores & assets",
};

/** Permission needed to open each module's screen, so tiles only show what a role can open. */
const MODULE_PERM: Record<string, string> = {
  setup: "setup.view", admissions: "admissions.view", learners: "learners.view", staff: "dashboard.view",
  curriculum: "curriculum.view", timetable: "timetable.view", attendance: "attendance.view",
  assessment: "assessment.view", promotion: "promotion.view", discipline: "discipline.view",
  communication: "communication.view", finance: "finance.view", library: "library.view", sickbay: "health.view",
  stores: "stores.view",
};

function moduleVisible(key: string, can: (perm: string) => boolean) {
  return can(MODULE_PERM[key] ?? "dashboard.view");
}

export default function DashboardPage() {
  const { me, can } = useAuth();
  const { data, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: () => get("/dashboard/"), refetchInterval: 120_000 });
  const b = data?.blocks ?? {};
  const firstName = me?.user.name.split(" ")[0];

  // The platform team and super admin work above any single school.
  if (me && !me.school && (me.user.is_platform_admin || me.is_superuser)) return <Navigate to="/platform" replace />;

  if (isLoading) {
    return (
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} h={110} radius="md" />
        ))}
      </SimpleGrid>
    );
  }

  const markTotal = b.marks?.total ?? 0;
  const approved = b.marks?.by_status?.approved ?? 0;

  const greeting = `Good ${new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}, ${firstName}`;
  const tiles = (me?.modules ?? []).filter((key) => MODULE_META[key] && moduleVisible(key, can));

  return (
    <Stack gap="lg">
      <Paper
        p="xl"
        radius="lg"
        withBorder={false}
        style={{ background: "linear-gradient(120deg, var(--mantine-color-brand-8), var(--mantine-color-brand-6) 60%, var(--mantine-color-cyan-6))", color: "white" }}
      >
        <Group justify="space-between" align="center" wrap="wrap" gap="lg">
          <Group gap="lg" wrap="nowrap">
            <Avatar src={me?.school?.logo} size={72} radius="md" color="white" variant="filled" styles={{ placeholder: { color: "var(--mantine-color-brand-7)" } }}>
              <IconSchool size={38} />
            </Avatar>
            <div>
              <Text fz={26} fw={800} lh={1.15}>{me?.school?.name}</Text>
              {me?.school?.motto && <Text size="sm" fs="italic" opacity={0.9}>"{me.school.motto}"</Text>}
              <Group gap="xs" mt={6}>
                <Badge variant="white" color="dark" radius="sm" tt="none">School ID {me?.school?.code}</Badge>
                {me?.school?.location && <Badge variant="outline" color="white" radius="sm" tt="none" leftSection={<IconMapPin size={12} />} style={{ color: "white", borderColor: "rgba(255,255,255,.6)" }}>{me.school.location}</Badge>}
              </Group>
            </div>
          </Group>
          <Stack gap={4} align="flex-end">
            <Text fw={700} fz="lg">{greeting}</Text>
            <Text size="sm" opacity={0.9}>{data?.term ? `${data.term} · ${date(data.today, "dddd D MMMM YYYY")}` : "No term set up yet"}</Text>
            <Group gap="xs" mt={4}>
              {can("attendance.take") && (
                <Button component={Link} to="/attendance" variant="white" color="dark" size="xs" leftSection={<IconClipboardCheck size={14} />}>Take roll call</Button>
              )}
              {can("marks.enter") && (
                <Button component={Link} to="/marks?mine=1" variant="white" color="dark" size="xs" leftSection={<IconListCheck size={14} />}>Enter marks</Button>
              )}
            </Group>
          </Stack>
        </Group>
      </Paper>

      {tiles.length > 0 && (
        <SimpleGrid cols={{ base: 3, xs: 4, sm: 5, md: 6, xl: 8 }} spacing="sm">
          {tiles.map((key) => {
            const meta = MODULE_META[key];
            const Icon = meta.icon;
            return (
              <UnstyledButton key={key} component={Link} to={meta.path} className="module-tile">
                <Stack align="center" gap={8} py="md" px={4}>
                  <ThemeIcon size={52} radius="xl" color={meta.color} variant="filled">
                    <Icon size={28} />
                  </ThemeIcon>
                  <Text size="xs" fw={600} ta="center" lh={1.2}>
                    {TILE_LABELS[key] ?? me?.module_labels[key]}
                  </Text>
                </Stack>
              </UnstyledButton>
            );
          })}
        </SimpleGrid>
      )}

      {!data?.term && can("setup.manage") && (
        <Alert color="blue" title="Finish setting up your school">
          Add the academic year and its three terms in <Anchor component={Link} to="/setup">School setup</Anchor>. One click there also loads
          Ugandan classes, NCDC subjects and grading scales.
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }}>
        {b.learners && (
          <StatCard label="Learners" value={num(b.learners.active, 0)} hint={`${b.learners.female} girls · ${b.learners.male} boys · ${b.learners.boarding} boarding`} icon={<IconUsers />} />
        )}
        {b.staff && <StatCard label="Staff" value={b.staff.total} hint={`${b.staff.teaching} teaching · ${b.staff.on_leave} on leave`} icon={<IconUsersGroup />} color="teal" />}
        {b.attendance_today && (
          <StatCard
            label="Present today"
            value={b.attendance_today.present_rate === null ? "–" : `${b.attendance_today.present_rate}%`}
            hint={`${b.attendance_today.registers_taken} register(s) taken`}
            icon={<IconClipboardCheck />}
            color="green"
          />
        )}
        {b.finance && (
          <StatCard label="Spent this term" value={ugxShort(b.finance.this_term)} hint={b.finance.cost_per_learner ? `${ugx(b.finance.cost_per_learner)} per learner` : `${ugx(b.finance.today)} today`} icon={<IconCash />} color="orange" />
        )}
        {b.marks && !b.finance && (
          <StatCard label="Mark sheets approved" value={`${approved}/${markTotal}`} hint="This term" icon={<IconListCheck />} color="indigo" />
        )}
      </SimpleGrid>

      <Grid>
        {b.learners?.by_class?.length > 0 && (
          <Grid.Col span={{ base: 12, lg: b.finance ? 7 : 12 }}>
            <Section title="Learners by class">
              <BarChart h={260} data={b.learners.by_class} dataKey="class" series={[{ name: "learners", color: "brand.6", label: "Learners" }]} tickLine="y" />
            </Section>
          </Grid.Col>
        )}
        {b.finance && (
          <Grid.Col span={{ base: 12, lg: 5 }}>
            <Section title="Spending by category this term" actions={<Anchor component={Link} to="/finance" size="sm">Finance</Anchor>}>
              {b.finance.by_category.length ? (
                <Group justify="center">
                  <DonutChart
                    size={200}
                    thickness={28}
                    withLabelsLine={false}
                    tooltipDataSource="segment"
                    valueFormatter={(v) => ugx(v)}
                    data={b.finance.by_category.map((row: any, i: number) => ({ name: row.category, value: row.total, color: CHART_COLORS[i % CHART_COLORS.length] }))}
                  />
                  <Stack gap={4}>
                    {b.finance.by_category.slice(0, 6).map((row: any, i: number) => (
                      <Group key={row.category} gap={6} wrap="nowrap">
                        <Badge size="xs" circle color={CHART_COLORS[i % CHART_COLORS.length]} />
                        <Text size="xs">{row.category}</Text>
                        <Text size="xs" c="dimmed">{ugx(row.total)}</Text>
                      </Group>
                    ))}
                  </Stack>
                </Group>
              ) : (
                <Empty title="No spending recorded this term" />
              )}
            </Section>
          </Grid.Col>
        )}
      </Grid>

      <SimpleGrid cols={{ base: 1, md: 2, xl: 3 }}>
        {b.marks && (
          <Section title="Marks this term" actions={<Anchor component={Link} to="/marks" size="sm">Open</Anchor>}>
            <Stack gap="xs">
              <Progress.Root size={18}>
                {(["approved", "reviewed", "submitted", "returned", "draft"] as const).map((status) => {
                  const value = ((b.marks.by_status?.[status] ?? 0) / Math.max(markTotal, 1)) * 100;
                  const color = { approved: "green", reviewed: "indigo", submitted: "blue", returned: "orange", draft: "gray" }[status];
                  return value ? <Progress.Section key={status} value={value} color={color} /> : null;
                })}
              </Progress.Root>
              <Group gap="xs">
                {Object.entries(b.marks.by_status ?? {}).map(([status, count]) => (
                  <Badge key={status} variant="light" color={{ approved: "green", reviewed: "indigo", submitted: "blue", returned: "orange" }[status] ?? "gray"}>
                    {String(count)} {status}
                  </Badge>
                ))}
              </Group>
              {b.sheets_awaiting_review > 0 && (
                <Text size="sm">
                  <b>{b.sheets_awaiting_review}</b> sheet(s) waiting for review or approval.
                </Text>
              )}
            </Stack>
          </Section>
        )}
        {b.my_mark_sheets && (
          <Section title="My mark sheets to finish">
            {b.my_mark_sheets.length === 0 ? (
              <Empty title="All done">No draft or returned sheets.</Empty>
            ) : (
              <Stack gap="xs">
                {b.my_mark_sheets.map((sheet: any) => (
                  <Group key={sheet.id} justify="space-between" wrap="nowrap">
                    <Anchor component={Link} to={`/marks/${sheet.id}`} size="sm" lineClamp={1}>
                      {sheet.label}
                    </Anchor>
                    <StatusBadge value={sheet.return_comment ? "returned" : "draft"} />
                  </Group>
                ))}
              </Stack>
            )}
          </Section>
        )}
        {b.attendance_today && b.attendance_today.classes_not_taken.length > 0 && (
          <Section title="Registers not taken today">
            <Group gap={6}>
              {b.attendance_today.classes_not_taken.map((c: { id: number; name: string }) => (
                <Badge key={c.id} variant="outline" color="orange" component={Link} to={`/attendance?class=${c.id}`} style={{ cursor: "pointer" }}>
                  {c.name}
                </Badge>
              ))}
            </Group>
          </Section>
        )}
        {b.finance && (
          <Section title="Finance follow-up" actions={<Anchor component={Link} to="/finance/expenses?status=pending" size="sm">Approvals</Anchor>}>
            <List spacing={6} size="sm">
              <List.Item>
                <b>{b.finance.pending_approvals}</b> expense(s) awaiting approval
              </List.Item>
              {b.finance.budget_alerts.map((line: any) => (
                <List.Item key={line.category}>
                  {line.category}: <b>{line.percent ?? "–"}%</b> of budget used <StatusBadge value={line.status} />
                </List.Item>
              ))}
              {b.finance.low_petty_cash.map((name: string) => (
                <List.Item key={name}>Petty cash "{name}" needs a top-up</List.Item>
              ))}
            </List>
          </Section>
        )}
        {b.alerts?.length > 0 && (
          <Section title="Alerts">
            <Stack gap="xs">
              {b.alerts.map((alert: any) => (
                <Group key={alert.kind} gap="xs" wrap="nowrap">
                  <IconAlertTriangle size={16} color="var(--mantine-color-orange-6)" />
                  <Anchor component={Link} to={alert.link} size="sm">
                    {alert.message}
                  </Anchor>
                </Group>
              ))}
            </Stack>
          </Section>
        )}
        <Section title="Coming up">
          {b.upcoming_events?.length ? (
            <Stack gap="xs">
              {b.upcoming_events.map((event: any) => (
                <Group key={event.id} gap="sm" wrap="nowrap">
                  <IconCalendarEvent size={16} />
                  <Text size="sm" style={{ flex: 1 }}>
                    {event.title}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {date(event.start_date, "ddd D MMM")}
                  </Text>
                </Group>
              ))}
            </Stack>
          ) : (
            <Empty title="No upcoming events" />
          )}
        </Section>
      </SimpleGrid>
      {!Object.keys(b).length && (
        <Card>
          <Empty title="Welcome">Your dashboard fills in as your role's modules are used.</Empty>
        </Card>
      )}
    </Stack>
  );
}
