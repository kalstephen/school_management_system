import { BarChart } from "@mantine/charts";
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Checkbox,
  ColorInput,
  Divider,
  Drawer,
  Grid,
  Group,
  NumberInput,
  Paper,
  PasswordInput,
  Radio,
  ScrollArea,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  ThemeIcon,
  Tooltip,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { IconBuildingCommunity, IconCheck, IconMapPin, IconPlus, IconSchool, IconSettings, IconUsers, IconUserShield, IconX } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { ApiError, api, errorMessage, get, openFile, post } from "@/api/client";
import type { RoleInfo } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, Section, StatCard, StatusBadge } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import { ModuleChecklist, useModuleCatalog } from "@/components/ModuleChecklist";
import { moduleIcon } from "@/components/moduleIcons";
import { ResourceForm } from "@/components/ResourceForm";
import { ResourceTable } from "@/components/ResourceTable";
import { useOptions } from "@/hooks/useOptions";
import NotFoundPage from "@/pages/NotFoundPage";
import { REPORT_TEMPLATES } from "@/pages/admin/ReportDesign";
import { date, dateTime, num, ugx } from "@/utils/format";

const REGIONS = ["Central", "Eastern", "Northern", "Western"].map((r) => ({ value: r, label: r }));
const OWNERSHIP = [
  { value: "private", label: "Private" }, { value: "government", label: "Government" }, { value: "community", label: "Community" },
  { value: "faith", label: "Faith-based" }, { value: "international", label: "International" },
];
const LEVELS = [
  { value: "nursery", label: "Nursery only" }, { value: "primary", label: "Nursery and primary" },
  { value: "olevel", label: "O-Level only" }, { value: "secondary", label: "Secondary (O and A-Level)" }, { value: "all", label: "Nursery to A-Level" },
];
const KINDS = [{ value: "day", label: "Day" }, { value: "boarding", label: "Boarding" }, { value: "mixed", label: "Day and boarding" }];
const DEFAULT_MODULES = ["admissions", "staff", "curriculum", "timetable", "attendance", "assessment", "promotion", "discipline", "communication", "finance"];

// ---------------------------------------------------------------- overview

function Overview({ onOpenSchool }: { onOpenSchool: (id: number) => void }) {
  const { data } = useQuery({ queryKey: ["platform-overview"], queryFn: () => get("/platform/overview/") });
  const catalog = useModuleCatalog();
  if (!data) return null;
  const t = data.totals;
  return (
    <Stack>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <StatCard label="Schools" value={t.schools} hint={`${t.active_schools} active`} icon={<IconSchool />} />
        <StatCard label="Learners on the platform" value={num(t.learners, 0)} icon={<IconUsers />} color="teal" />
        <StatCard label="User accounts" value={num(t.users, 0)} icon={<IconUserShield />} color="grape" />
        <StatCard
          label="Subscriptions"
          value={`${t.by_status.active ?? 0} active`}
          hint={`${t.by_status.trial ?? 0} trial · ${t.by_status.expired ?? 0} expired · ${t.by_status.suspended ?? 0} suspended · ${t.by_status.none ?? 0} none`}
          icon={<IconBuildingCommunity />}
          color="orange"
        />
      </SimpleGrid>

      <Section title="Which school has which module">
        <ScrollArea>
          <Table withColumnBorders highlightOnHover miw={1080} fz="xs" horizontalSpacing={6}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th miw={200}>School</Table.Th>
                <Table.Th w={92}>Status</Table.Th>
                {catalog.map((m) => {
                  const Icon = moduleIcon(m.key);
                  return (
                    <Table.Th key={m.key} ta="center" w={52}>
                      <Tooltip label={m.label}>
                        <Stack gap={2} align="center">
                          <Icon size={16} />
                          <Text size="9px" lh={1.1} style={{ whiteSpace: "normal", wordBreak: "break-word" }}>
                            {m.label.split(/[ (&,]/)[0]}
                          </Text>
                        </Stack>
                      </Tooltip>
                    </Table.Th>
                  );
                })}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.schools.map((s: any) => (
                <Table.Tr key={s.id} style={{ cursor: "pointer" }} onClick={() => onOpenSchool(s.id)}>
                  <Table.Td>
                    <Text size="sm" fw={600}>{s.name}</Text>
                    <Text size="xs" c="dimmed">{s.code}{s.district ? ` · ${s.district}` : ""} · {s.learners} learners</Text>
                  </Table.Td>
                  <Table.Td style={{ whiteSpace: "nowrap" }}>
                    <StatusBadge value={s.status === "none" ? "draft" : s.status} label={s.status === "none" ? "No plan" : s.status} />
                  </Table.Td>
                  {catalog.map((m) => (
                    <Table.Td key={m.key} ta="center">
                      {s.modules[m.key] ? (
                        <ThemeIcon size="sm" radius="xl" color="green" variant="light"><IconCheck size={12} /></ThemeIcon>
                      ) : (
                        <IconX size={12} color="var(--mantine-color-gray-4)" />
                      )}
                    </Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      </Section>

      <Grid>
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Section title="Schools using each module">
            <BarChart
              h={440}
              data={data.module_adoption.map((m: any) => ({ module: m.label.split(" (")[0], schools: m.schools }))}
              dataKey="module"
              orientation="vertical"
              yAxisProps={{ width: 180, interval: 0 }}
              xAxisProps={{ allowDecimals: false }}
              series={[{ name: "schools", label: "Schools", color: "brand.6" }]}
            />
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 5 }}>
          <Stack>
            <Section title="Subscriptions ending within 30 days">
              {data.expiring_soon.length ? (
                data.expiring_soon.map((s: any) => (
                  <Group key={s.id} justify="space-between">
                    <Anchor size="sm" onClick={() => onOpenSchool(s.id)}>{s.name}</Anchor>
                    <Text size="xs" c="dimmed">{date(s.ends_on)}</Text>
                  </Group>
                ))
              ) : (
                <Text size="sm" c="dimmed">None</Text>
              )}
            </Section>
            <Section title="Recent module changes">
              {data.recent_changes.length ? (
                <Stack gap={6}>
                  {data.recent_changes.map((c: any, i: number) => (
                    <Text size="xs" key={i}>
                      <b>{c.school}</b>: {c.module} {c.enabled ? "switched on" : "switched off"} · {c.by ?? "system"} · {dateTime(c.at)}
                    </Text>
                  ))}
                </Stack>
              ) : (
                <Text size="sm" c="dimmed">No changes yet</Text>
              )}
            </Section>
          </Stack>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

// ---------------------------------------------------------------- school form

type SchoolValues = Record<string, any>;

function SchoolForm({ school, onSaved }: { school?: any; onSaved: (school: any) => void }) {
  const client = useQueryClient();
  const isNew = !school;
  const [values, setValues] = useState<SchoolValues>(
    school ?? { ownership: "private", levels: "primary", kind: "day", is_active: true, report_template: "classic", report_color: "#1d4ed8", report_show_photo: true },
  );
  const [modules, setModules] = useState<string[]>(
    school ? Object.entries(school.module_map ?? {}).filter(([, on]) => on).map(([k]) => k) : DEFAULT_MODULES,
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const set = (key: string) => (value: any) => setValues((v) => ({ ...v, [key]: value }));
  const text = (key: string, label: string, props: Record<string, any> = {}) => (
    <TextInput label={label} value={values[key] ?? ""} onChange={(e) => set(key)(e.currentTarget.value)} error={errors[key]} {...props} />
  );

  const save = async () => {
    setBusy(true);
    try {
      // Send only the editable profile, not the read-only parts the server returned.
      const { subscription: _s, addons: _a, module_map: _m, usage: _u, location: _l, created_at: _c, ...profile } = values;
      const body = { ...profile, modules };
      const saved = await api(isNew ? "/platform/schools/" : `/platform/schools/${school.id}/`, { method: isNew ? "POST" : "PATCH", body });
      setErrors({});
      notifications.show({ color: "green", title: isNew ? "School registered" : "Saved", message: `School ID: ${saved.code}` });
      client.invalidateQueries({ queryKey: ["platform-overview"] });
      client.invalidateQueries({ queryKey: ["list", "/platform/schools/"] });
      onSaved(saved);
    } catch (error) {
      if (error instanceof ApiError && error.data && typeof error.data === "object") {
        const e: Record<string, string> = {};
        Object.entries(error.data).forEach(([k, v]) => (e[k] = Array.isArray(v) ? v.join(" ") : String(v)));
        setErrors(e);
      }
      notifications.show({ color: "red", title: "Not saved", message: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack>
      <Tabs defaultValue="identity">
        <Tabs.List mb="md">
          <Tabs.Tab value="identity">1. School</Tabs.Tab>
          <Tabs.Tab value="location">2. Location</Tabs.Tab>
          <Tabs.Tab value="head">3. Head teacher</Tabs.Tab>
          <Tabs.Tab value="director">4. Director</Tabs.Tab>
          <Tabs.Tab value="modules">5. Modules</Tabs.Tab>
          <Tabs.Tab value="report">6. Report card</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="identity">
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {text("name", "School name", { required: true, withAsterisk: true })}
            {text("code", "School ID", {
              description: "Used to sign in, e.g. NewHope-003. Leave empty to generate it from the name.",
              placeholder: "NewHope-003",
            })}
            {text("short_name", "Short name")}
            {text("motto", "Motto")}
            {text("registration_number", "MoES registration number")}
            {text("emis_number", "EMIS number")}
            {text("uneb_centre_number", "UNEB centre number")}
            <NumberInput label="Year established" value={values.established ?? ""} onChange={(v) => set("established")(v === "" ? null : v)} min={1900} max={2100} />
            <Select label="Ownership" data={OWNERSHIP} value={values.ownership} onChange={set("ownership")} />
            <Select label="Levels offered" data={LEVELS} value={values.levels} onChange={set("levels")} />
            <Select label="Day or boarding" data={KINDS} value={values.kind} onChange={set("kind")} />
            {text("phone", "School phone")}
            {text("email", "School email", { type: "email" })}
            {text("website", "Website")}
          </SimpleGrid>
        </Tabs.Panel>
        <Tabs.Panel value="location">
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <Select label="Region" data={REGIONS} value={values.region ?? null} onChange={set("region")} clearable />
            {text("district", "District", { placeholder: "e.g. Wakiso" })}
            {text("county", "County / municipality")}
            {text("sub_county", "Sub-county / division")}
            {text("parish", "Parish / ward")}
            {text("village", "Village / cell")}
            {text("address", "Physical address / landmark")}
            {text("gps", "GPS coordinates", { placeholder: "0.3476, 32.5825" })}
          </SimpleGrid>
        </Tabs.Panel>
        <Tabs.Panel value="head">
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {text("head_teacher_name", "Head teacher's full name")}
            {text("head_teacher_phone", "Phone")}
            {text("head_teacher_email", "Email", { type: "email" })}
          </SimpleGrid>
          <Text size="xs" c="dimmed" mt="sm">To give the head teacher a login, add them under "School administrators" after registering.</Text>
        </Tabs.Panel>
        <Tabs.Panel value="director">
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {text("director_name", "Director / proprietor's full name")}
            {text("director_phone", "Phone")}
            {text("director_email", "Email", { type: "email" })}
            {text("director_nin", "National ID (NIN)")}
            {text("director_address", "Address")}
          </SimpleGrid>
        </Tabs.Panel>
        <Tabs.Panel value="modules">
          <ModuleChecklist value={modules} onChange={setModules} />
        </Tabs.Panel>
        <Tabs.Panel value="report">
          <Stack>
            <Text size="sm" c="dimmed">
              Agree the report card design with the school. The logo and footer line are set under Open school setup → School
              profile. The school sees all of this but cannot change it.
            </Text>
            <Radio.Group value={values.report_template ?? "classic"} onChange={set("report_template")} label="Design">
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} mt="xs">
                {Object.entries(REPORT_TEMPLATES).map(([key, t]) => (
                  <Paper key={key} withBorder p="sm" radius="md">
                    <Radio value={key} label={<Text fw={600} size="sm">{t.label}</Text>} />
                    <Text size="xs" c="dimmed" mt={6} mb="xs">{t.description}</Text>
                    {!isNew && (
                      <Anchor size="xs" onClick={() => openFile(`/platform/schools/${school.id}/report-preview/`, { template: key, color: values.report_color })}>
                        Preview with this school's details
                      </Anchor>
                    )}
                  </Paper>
                ))}
              </SimpleGrid>
            </Radio.Group>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <ColorInput
                label="Colour"
                format="hex"
                value={values.report_color ?? ""}
                onChange={set("report_color")}
                swatches={["#1d4ed8", "#047857", "#b91c1c", "#7c2d12", "#6d28d9", "#0f766e", "#be185d", "#334155"]}
              />
              <Checkbox mt="xl" label="Print the learner's photo" checked={!!values.report_show_photo} onChange={(e) => set("report_show_photo")(e.currentTarget.checked)} />
            </SimpleGrid>
          </Stack>
        </Tabs.Panel>
      </Tabs>
      {Object.keys(errors).length > 0 && <Alert color="red">Check the highlighted fields{errors.code ? `: ${errors.code}` : ""}.</Alert>}
      <Group justify="flex-end">
        <Button onClick={save} loading={busy} disabled={!values.name}>
          {isNew ? "Register school" : "Save changes"}
        </Button>
      </Group>
    </Stack>
  );
}

// ---------------------------------------------------------------- school drawer

function Administrators({ schoolId }: { schoolId: number }) {
  const { data = [], refetch } = useQuery({ queryKey: ["school-admins", schoolId], queryFn: () => get<any[]>(`/platform/schools/${schoolId}/administrators/`) });
  return (
    <Stack gap="xs">
      <Text size="xs" c="dimmed">Create the school's first director or administrator; they then manage everyone below them.</Text>
      {data.map((a) => (
        <Group key={`${a.username}-${a.role}`} justify="space-between">
          <Text size="sm">{a.name} <Text span c="dimmed" size="xs">({a.username})</Text></Text>
          <Badge variant="light">{a.role.replace("_", " ")}</Badge>
        </Group>
      ))}
      <ResourceForm
        endpoint={`/platform/schools/${schoolId}/administrators/`}
        submitLabel="Create administrator"
        initial={{ role: "director" }}
        onSaved={() => refetch()}
        fields={[
          { name: "first_name", label: "First name", required: true },
          { name: "last_name", label: "Surname", required: true },
          { name: "username", label: "Username", required: true },
          { name: "phone", label: "Phone" },
          { name: "email", label: "Email", type: "email" },
          { name: "password", label: "Temporary password", type: "password", description: "Not needed if the username already exists" },
          { name: "role", label: "Level", type: "select", required: true, options: [
            { value: "director", label: "Director / proprietor (top of the school)" },
            { value: "school_admin", label: "School administrator" },
            { value: "head_teacher", label: "Head teacher" },
          ] },
        ]}
      />
    </Stack>
  );
}

function Subscription({ school, onSaved }: { school: any; onSaved: () => void }) {
  const { options: plans } = useOptions({ endpoint: "/platform/plans/", label: (p: any) => `${p.name} — ${ugx(p.price_per_term)}/term` });
  const sub = school.subscription ?? {};
  const [plan, setPlan] = useState<string | null>(sub.plan ? String(sub.plan) : null);
  const [status, setStatus] = useState<string | null>(sub.status ?? "trial");
  const [starts, setStarts] = useState<string | null>(sub.starts_on ?? null);
  const [ends, setEnds] = useState<string | null>(sub.ends_on ?? null);
  return (
    <Stack>
      <Select label="Plan" data={plans} value={plan} onChange={setPlan} />
      <Select label="Status" data={["trial", "active", "suspended", "expired"].map((s) => ({ value: s, label: s }))} value={status} onChange={setStatus} />
      <Group grow>
        <DateInput label="Starts" value={starts} onChange={setStarts} />
        <DateInput label="Ends" value={ends} onChange={setEnds} />
      </Group>
      <Text size="xs" c="dimmed">Saving does not change the module ticks; set those on the Modules tab.</Text>
      <Button
        onClick={async () => {
          try {
            await post(`/platform/schools/${school.id}/subscription/`, { plan, status, starts_on: starts, ends_on: ends });
            notifications.show({ color: "green", message: "Subscription saved" });
            onSaved();
          } catch (error) {
            notifications.show({ color: "red", message: errorMessage(error) });
          }
        }}
      >
        Save subscription
      </Button>
    </Stack>
  );
}

function SchoolDrawer({ schoolId, onClose }: { schoolId: number | "new"; onClose: () => void }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [createdId, setCreatedId] = useState<number | null>(null);
  const id = schoolId === "new" ? createdId : schoolId;
  const { data: school, refetch } = useQuery({ queryKey: ["platform-school", id], enabled: !!id, queryFn: () => get(`/platform/schools/${id}/`) });
  const [modules, setModules] = useState<string[]>([]);
  useEffect(() => {
    if (school) setModules(Object.entries(school.module_map).filter(([, on]) => on).map(([k]) => k));
  }, [school]);
  const refresh = () => {
    refetch();
    client.invalidateQueries({ queryKey: ["platform-overview"] });
    client.invalidateQueries({ queryKey: ["list", "/platform/schools/"] });
  };

  return (
    <Drawer opened onClose={onClose} position="right" size="xl" title={school ? `${school.name} · ${school.code}` : "Register a school"}>
      {!id && <SchoolForm onSaved={(s) => setCreatedId(s.id)} />}
      {school && (
        <Stack>
          <Paper p="sm" bg="var(--mantine-color-brand-light)">
            <Group gap="lg">
              <Group gap={6}><IconMapPin size={16} /><Text size="sm">{school.location || "Location not set"}</Text></Group>
              <Text size="sm">Head: <b>{school.head_teacher_name || "–"}</b></Text>
              <Text size="sm">Director: <b>{school.director_name || "–"}</b></Text>
              <Badge>{school.usage.learners} learners</Badge>
              <Badge variant="light">{school.usage.active_users} users</Badge>
            </Group>
          </Paper>
          <Paper withBorder p="sm">
            <Group justify="space-between" wrap="wrap">
              <div>
                <Text fw={650} size="sm">School setup</Text>
                <Text size="xs" c="dimmed">Levels, years and terms, classes and streams, subjects, grading scales, profile and logo. The school sees it read-only.</Text>
              </div>
              <Button leftSection={<IconSettings size={16} />} onClick={() => navigate(`/platform/schools/${school.id}/setup`)}>
                Open school setup
              </Button>
            </Group>
          </Paper>
          {schoolId === "new" && <Alert color="green">Registered with School ID <b>{school.code}</b>. Next: open the school setup (levels, year and terms, classes), add its first administrator and a subscription.</Alert>}
          <Tabs defaultValue={schoolId === "new" ? "admins" : "profile"} keepMounted={false}>
            <Tabs.List mb="md">
              <Tabs.Tab value="profile">Profile</Tabs.Tab>
              <Tabs.Tab value="modules">Modules</Tabs.Tab>
              <Tabs.Tab value="admins">School administrators</Tabs.Tab>
              <Tabs.Tab value="subscription">Subscription</Tabs.Tab>
            </Tabs.List>
            <Tabs.Panel value="profile"><SchoolForm school={school} onSaved={refresh} /></Tabs.Panel>
            <Tabs.Panel value="modules">
              <Stack>
                <ModuleChecklist value={modules} onChange={setModules} />
                <Group justify="flex-end">
                  <Button
                    onClick={async () => {
                      try {
                        await post(`/platform/schools/${school.id}/modules/`, { modules });
                        notifications.show({ color: "green", message: "Modules updated. Data of switched-off modules is kept." });
                        refresh();
                      } catch (error) {
                        notifications.show({ color: "red", message: errorMessage(error) });
                      }
                    }}
                  >
                    Save modules
                  </Button>
                </Group>
              </Stack>
            </Tabs.Panel>
            <Tabs.Panel value="admins"><Administrators schoolId={school.id} /></Tabs.Panel>
            <Tabs.Panel value="subscription"><Subscription school={school} onSaved={refresh} /></Tabs.Panel>
          </Tabs>
        </Stack>
      )}
    </Drawer>
  );
}

// ---------------------------------------------------------------- users

function UserDrawer({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const { rows: schools } = useOptions({ endpoint: "/platform/schools/", label: "name" });
  const { data: roles = [] } = useQuery({ queryKey: ["role-catalog"], queryFn: () => get<RoleInfo[]>("/roles/") });
  const [schoolId, setSchoolId] = useState<string | null>(null);
  const school = useMemo(() => schools.find((s: any) => String(s.id) === schoolId), [schools, schoolId]);
  const schoolModules = school ? Object.entries(school.module_map).filter(([, on]) => on).map(([k]) => k as string) : [];
  const [values, setValues] = useState<Record<string, string>>({ role: "subject_teacher" });
  const [modules, setModules] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => setModules(schoolModules), [schoolId]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k: string) => (v: string | null) => setValues((x) => ({ ...x, [k]: v ?? "" }));

  return (
    <Drawer opened onClose={onClose} position="right" size="lg" title="Create a user">
      <Stack>
        <Select
          label="School"
          description="The user belongs to this school and inherits its location and modules"
          data={schools.map((s: any) => ({ value: String(s.id), label: `${s.name} (${s.code})` }))}
          value={schoolId}
          onChange={setSchoolId}
          searchable
          required
        />
        {school && (
          <Paper p="sm" withBorder bg="var(--mantine-color-gray-light)">
            <Group gap="xs"><IconMapPin size={16} /><Text size="sm" fw={600}>{school.location || "No location recorded"}</Text></Group>
            <Text size="xs" c="dimmed">School ID {school.code} · {school.region || "region not set"} · Head teacher {school.head_teacher_name || "–"}</Text>
          </Paper>
        )}
        <SimpleGrid cols={2}>
          <TextInput label="First name" required value={values.first_name ?? ""} onChange={(e) => set("first_name")(e.currentTarget.value)} />
          <TextInput label="Surname" required value={values.last_name ?? ""} onChange={(e) => set("last_name")(e.currentTarget.value)} />
          <TextInput label="Username" required value={values.username ?? ""} onChange={(e) => set("username")(e.currentTarget.value)} />
          <PasswordInput label="Password" required value={values.password ?? ""} onChange={(e) => set("password")(e.currentTarget.value)} />
          <TextInput label="Phone" value={values.phone ?? ""} onChange={(e) => set("phone")(e.currentTarget.value)} />
          <TextInput label="Email" value={values.email ?? ""} onChange={(e) => set("email")(e.currentTarget.value)} />
          <TextInput label="Job title" value={values.title ?? ""} onChange={(e) => set("title")(e.currentTarget.value)} />
          <Select label="Role" data={roles.map((r) => ({ value: r.value, label: r.label }))} value={values.role} onChange={set("role")} required />
        </SimpleGrid>
        <Divider label="Modules this user inherits" labelPosition="left" />
        {school ? (
          <>
            <Text size="xs" c="dimmed">Only the school's modules are offered. Untick any this person should not open.</Text>
            <ModuleChecklist value={modules} onChange={setModules} available={schoolModules} />
          </>
        ) : (
          <Text size="sm" c="dimmed">Choose a school first.</Text>
        )}
        <Button
          loading={busy}
          disabled={!school}
          onClick={async () => {
            setBusy(true);
            try {
              const allTicked = schoolModules.every((m) => modules.includes(m) || m === "setup" || m === "learners");
              await post("/platform/users/", { ...values, school: Number(schoolId), modules: allTicked ? [] : modules });
              notifications.show({ color: "green", message: `Account created in ${school.name}. They sign in with School ID ${school.code}.` });
              client.invalidateQueries({ queryKey: ["list", "/platform/users/"] });
              onClose();
            } catch (error) {
              notifications.show({ color: "red", title: "Not created", message: errorMessage(error) });
            } finally {
              setBusy(false);
            }
          }}
        >
          Create user
        </Button>
      </Stack>
    </Drawer>
  );
}

function Users() {
  const [open, setOpen] = useState(false);
  const { options: schools } = useOptions({ endpoint: "/platform/schools/", label: (s: any) => `${s.name} (${s.code})` });
  const catalog = useModuleCatalog();
  return (
    <>
      <ResourceTable
        endpoint="/platform/users/"
        searchPlaceholder="Name, username, school…"
        filters={[{ name: "school", label: "School", options: schools }]}
        toolbar={<Button leftSection={<IconPlus size={16} />} onClick={() => setOpen(true)}>Create user</Button>}
        columns={[
          { key: "name", label: "User", render: (r: any) => <><Text size="sm" fw={600}>{r.first_name} {r.last_name}</Text><Text size="xs" c="dimmed">{r.username}</Text></> },
          { key: "school", label: "School", render: (r: any) => <><Text size="sm">{r.school_name}</Text><Text size="xs" c="dimmed">{r.school_code} · {r.school_location || "no location"}</Text></> },
          { key: "roles", label: "Role", render: (r: any) => <Group gap={4}>{r.roles.map((x: string) => <Badge key={x} size="sm" variant="light">{x}</Badge>)}</Group> },
          { key: "modules", label: "Modules", render: (r: any) => (r.modules.length ? <Tooltip label={r.modules.map((m: string) => catalog.find((c) => c.key === m)?.label ?? m).join(", ")}><Badge variant="outline">{r.modules.length} chosen</Badge></Tooltip> : <Badge variant="outline" color="gray">All school modules</Badge>) },
          { key: "last_login", label: "Last sign-in", render: (r: any) => dateTime(r.last_login) },
          { key: "is_active", label: "Status", render: (r: any) => <StatusBadge value={r.is_active ? "active" : "suspended"} label={r.is_active ? "Active" : "Disabled"} /> },
        ]}
      />
      {open && <UserDrawer onClose={() => setOpen(false)} />}
    </>
  );
}

// ---------------------------------------------------------------- page

const REQUEST_STATUS = [
  { value: "new", label: "New" },
  { value: "contacted", label: "Contacted" },
  { value: "demo_booked", label: "Demo booked" },
  { value: "registered", label: "School registered" },
  { value: "closed", label: "Closed" },
];

/** Requests sent from the public website (Request access), for the team to follow up. */
function Requests() {
  return (
    <CrudPage
      hideHeader
      title="Requests"
      singular="request"
      formHelp="Follow up a request from the website: set where it stands and note what was agreed (e.g. demo booked for Friday)."
      endpoint="/platform/requests/"
      canCreate={false}
      canDelete={false}
      filters={[
        { name: "status", label: "Status", options: REQUEST_STATUS },
        { name: "kind", label: "Type", options: [{ value: "join", label: "Register our school" }, { value: "demo", label: "Book a demo" }, { value: "info", label: "More information" }] },
      ]}
      emptyText="No requests yet. They arrive here from the Request access page of the website."
      columns={[
        { key: "created_at", label: "Received", render: (r: any) => dateTime(r.created_at) },
        { key: "school", label: "School", render: (r: any) => <><Text size="sm" fw={600}>{r.school_name}</Text><Text size="xs" c="dimmed">{[r.district, r.levels, r.learners ? `about ${r.learners} learners` : null].filter(Boolean).join(" · ") || "–"}</Text></> },
        { key: "contact", label: "Contact", render: (r: any) => <><Text size="sm">{r.contact_name}{r.role ? ` · ${r.role}` : ""}</Text><Text size="xs"><Anchor href={`tel:${r.phone}`} size="xs">{r.phone}</Anchor>{r.email ? <> · <Anchor href={`mailto:${r.email}`} size="xs">{r.email}</Anchor></> : null}</Text></> },
        { key: "kind", label: "Wants", render: (r: any) => <Text size="sm" fw={600} c={r.kind === "demo" ? "violet.7" : r.kind === "join" ? "blue.7" : "gray.7"} style={{ whiteSpace: "nowrap" }}>{r.kind_label}</Text> },
        { key: "message", label: "Message", render: (r: any) => <Text size="xs" lineClamp={3}>{r.message || "–"}</Text> },
        { key: "status", label: "Status", render: (r: any) => <><Text size="sm" fw={700} c={r.status === "new" ? "red.7" : r.status === "closed" ? "gray.6" : "green.8"} style={{ whiteSpace: "nowrap" }}>{r.status_label}</Text>{r.handled_by_name && <Text size="10px" c="dimmed">by {r.handled_by_name}</Text>}</> },
      ]}
      fields={[
        { name: "status", label: "Status", type: "select", options: REQUEST_STATUS, required: true },
        { name: "notes", label: "Follow-up notes", type: "textarea", span: 12, placeholder: "e.g. Called 3 Nov; demo booked for Friday 10 am" },
      ]}
    />
  );
}

export default function PlatformPage() {
  const { me } = useAuth();
  const { data: overview } = useQuery({ queryKey: ["platform-overview"], queryFn: () => get("/platform/overview/"), enabled: me?.portal === "platform" });
  const [school, setSchool] = useState<number | "new" | null>(null);
  // School sessions never see the owner area; they get the ordinary "not found" page.
  if (me?.portal !== "platform") return <NotFoundPage />;
  return (
    <>
      <PageHeader
        title="Owner console"
        description="Every school on the platform, the modules each one has, its users and subscriptions."
        actions={<Button leftSection={<IconPlus size={16} />} onClick={() => setSchool("new")}>Register a school</Button>}
      />
      <Tabs defaultValue="overview" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="overview">Overview</Tabs.Tab>
          <Tabs.Tab value="schools">Schools</Tabs.Tab>
          <Tabs.Tab value="users">Users</Tabs.Tab>
          <Tabs.Tab value="requests">
            Requests {overview?.new_requests ? <Badge size="xs" color="red" ml={4}>{overview.new_requests}</Badge> : null}
          </Tabs.Tab>
          <Tabs.Tab value="plans">Plans</Tabs.Tab>
          {me?.is_superuser && <Tabs.Tab value="team">Platform team</Tabs.Tab>}
        </Tabs.List>
        <Tabs.Panel value="overview"><Overview onOpenSchool={setSchool} /></Tabs.Panel>
        <Tabs.Panel value="schools">
          <ResourceTable
            endpoint="/platform/schools/"
            searchPlaceholder="Name, School ID, district…"
            onRowClick={(r: any) => setSchool(r.id)}
            filters={[
              { name: "region", label: "Region", options: REGIONS },
              { name: "ownership", label: "Ownership", options: OWNERSHIP },
            ]}
            columns={[
              { key: "name", label: "School", render: (r: any) => <><Text size="sm" fw={600}>{r.name}</Text><Text size="xs" c="dimmed">{r.code}</Text></> },
              { key: "location", label: "Location", render: (r: any) => r.location || "–" },
              { key: "head", label: "Head teacher · Director", render: (r: any) => <Text size="xs">{r.head_teacher_name || "–"}<br />{r.director_name || "–"}</Text> },
              { key: "modules", label: "Modules", render: (r: any) => `${Object.values(r.module_map).filter(Boolean).length} of 15` },
              { key: "plan", label: "Subscription", render: (r: any) => (r.subscription ? <Group gap={4}><StatusBadge value={r.subscription.status} /><Text size="xs">until {date(r.subscription.ends_on)}</Text></Group> : <Text size="xs" c="dimmed">None</Text>) },
              { key: "usage", label: "Learners · users", render: (r: any) => `${r.usage.learners} · ${r.usage.active_users}` },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="users"><Users /></Tabs.Panel>
        <Tabs.Panel value="requests"><Requests /></Tabs.Panel>
        <Tabs.Panel value="plans">
          <CrudPage
            hideHeader
            title="Plans"
            singular="plan"
            formHelp="A subscription plan schools can be put on: learner limit, price per term and which add-on modules it includes."
            endpoint="/platform/plans/"
            canDelete={false}
            columns={[
              { key: "name", label: "Plan" },
              { key: "max_learners", label: "Learners", render: (r: any) => (r.max_learners ? `up to ${r.max_learners}` : "Unlimited") },
              { key: "price_per_term", label: "Per term", render: (r: any) => ugx(r.price_per_term) },
              { key: "included_addons", label: "Add-ons included", render: (r: any) => r.included_addons.join(", ") || (r.addon_choices ? `${r.addon_choices} of choice` : "None") },
            ]}
            fields={[
              { name: "name", label: "Name", required: true },
              { name: "max_learners", label: "Maximum learners (empty = unlimited)", type: "number" },
              { name: "price_per_term", label: "Price per term", type: "money", required: true },
              { name: "included_addons", label: "Add-ons included", type: "multiselect", options: [{ value: "library", label: "Library" }, { value: "sickbay", label: "Sickbay" }, { value: "stores", label: "Stores" }] },
              { name: "addon_choices", label: "Add-ons of the school's choice", type: "number" },
              { name: "priority_support", label: "Priority support", type: "checkbox" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="team">
          <CrudPage
            hideHeader
            title="Platform team"
            singular="team member"
            formHelp="A person on the SPEX platform team. They sign in at the owner console, never through a school's sign-in."
            endpoint="/platform/team/"
            canDelete={false}
            defaults={{ is_active: true }}
            columns={[
              { key: "username", label: "Username" },
              { key: "name", label: "Name", render: (r: any) => `${r.first_name} ${r.last_name}` },
              { key: "level", label: "Level", render: (r: any) => (r.is_superuser ? <Badge color="red">Super admin</Badge> : <Badge color="orange" variant="light">Platform team</Badge>) },
              { key: "last_login", label: "Last sign-in", render: (r: any) => dateTime(r.last_login) },
              { key: "is_active", label: "Status", render: (r: any) => <StatusBadge value={r.is_active ? "active" : "suspended"} label={r.is_active ? "Active" : "Disabled"} /> },
            ]}
            fields={[
              { name: "username", label: "Username", required: true },
              { name: "first_name", label: "First name" },
              { name: "last_name", label: "Surname" },
              { name: "email", label: "Email", type: "email" },
              { name: "phone", label: "Phone" },
              { name: "password", label: "Password", type: "password", description: "Required for a new account" },
              { name: "is_active", label: "Can sign in", type: "checkbox" },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
      {school !== null && <SchoolDrawer schoolId={school} onClose={() => setSchool(null)} />}
    </>
  );
}
