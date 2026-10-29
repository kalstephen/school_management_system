import { ActionIcon, Badge, Button, Drawer, Group, Select, Stack, Table, Tabs, Text, TextInput, Tooltip } from "@mantine/core";
import { DateTimePicker } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { IconShieldCheck, IconTrash } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { del, errorMessage, get, post } from "@/api/client";
import type { RoleInfo } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import { useOptions } from "@/hooks/useOptions";
import { useClasses } from "@/hooks/useSchool";
import { dateTime } from "@/utils/format";

import { AccessLevels } from "./AccessLevels";

const SCOPES = [
  { value: "school", label: "Whole school" }, { value: "section", label: "Section" }, { value: "class", label: "Class" },
  { value: "stream", label: "Stream" }, { value: "department", label: "Department" }, { value: "store", label: "Store" },
];
const SCOPE_SOURCE: Record<string, { endpoint: string; label: string }> = {
  section: { endpoint: "/sections/", label: "name" },
  class: { endpoint: "/classes/", label: "name" },
  stream: { endpoint: "/streams/", label: "label" },
  department: { endpoint: "/departments/", label: "name" },
  store: { endpoint: "/stores/stores/", label: "name" },
};

function RolesDrawer({ member, onClose }: { member: any; onClose: () => void }) {
  const client = useQueryClient();
  const { data: allRoles = [] } = useQuery({ queryKey: ["role-catalog"], queryFn: () => get<RoleInfo[]>("/roles/") });
  // Only roles below your own level are offered; the server enforces the same rule.
  const catalog = allRoles.filter((r) => r.assignable).map((r) => ({ value: r.value, label: r.label }));
  const { data: roles = [], refetch } = useQuery({ queryKey: ["member-roles", member.id], queryFn: async () => (await get("/role-assignments/", { membership: member.id })).results });
  const [role, setRole] = useState<string | null>(null);
  const [scopeType, setScopeType] = useState<string>("school");
  const [scopeId, setScopeId] = useState<string | null>(null);
  const { options: scopeOptions } = useOptions(SCOPE_SOURCE[scopeType], scopeType !== "school");
  const { options: classOptions } = useClasses();
  const refresh = () => {
    refetch();
    client.invalidateQueries({ queryKey: ["list", "/users/"] });
  };

  return (
    <Drawer opened onClose={onClose} title={`Roles — ${member.first_name} ${member.last_name}`} position="right" size="lg">
      <Stack>
        <Text size="sm" c="dimmed">
          A person can hold several roles, each limited to a scope. Their access is everything their roles allow together.
        </Text>
        <Table>
          <Table.Tbody>
            {roles.map((r: any) => (
              <Table.Tr key={r.id}>
                <Table.Td fw={600}>{r.role_label}</Table.Td>
                <Table.Td>{r.scope_type === "school" ? "Whole school" : `${r.scope_type} ${r.scope_type === "class" ? classOptions.find((c) => c.value === String(r.scope_id))?.label ?? r.scope_id : r.scope_id}`}</Table.Td>
                <Table.Td w={40}>
                  <ActionIcon variant="subtle" color="red" onClick={async () => {
                      try {
                        await del(`/role-assignments/${r.id}/`);
                        refresh();
                      } catch (error) {
                        notifications.show({ color: "red", message: errorMessage(error) });
                      }
                    }} aria-label="Remove role">
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Group align="flex-end" wrap="wrap">
          <Select label="Role" data={catalog} value={role} onChange={setRole} w={200} />
          <Select label="Scope" data={SCOPES} value={scopeType} onChange={(v) => { setScopeType(v ?? "school"); setScopeId(null); }} w={150} />
          {scopeType !== "school" && <Select label="Which" data={scopeOptions} value={scopeId} onChange={setScopeId} w={160} searchable />}
          <Button
            disabled={!role || (scopeType !== "school" && !scopeId)}
            onClick={async () => {
              try {
                await post("/role-assignments/", { membership: member.id, role, scope_type: scopeType, scope_id: scopeId });
                setRole(null);
                refresh();
              } catch (error) {
                notifications.show({ color: "red", message: errorMessage(error) });
              }
            }}
          >
            Add role
          </Button>
        </Group>
      </Stack>
    </Drawer>
  );
}

function SupportAccess() {
  const { data, refetch } = useQuery({ queryKey: ["support-access"], queryFn: () => get("/support-access/") });
  const [reason, setReason] = useState("");
  const [until, setUntil] = useState<string | null>(null);
  const rows = data?.results ?? data ?? [];
  return (
    <Stack maw={720}>
      <Text size="sm" c="dimmed">
        The platform team cannot read your school's records unless you allow it here, for a limited time. Every grant is logged.
      </Text>
      <Group align="flex-end">
        <TextInput label="Reason" value={reason} onChange={(e) => setReason(e.currentTarget.value)} w={280} placeholder="e.g. Help with report cards" />
        <DateTimePicker label="Until" value={until} onChange={setUntil} w={220} minDate={new Date().toISOString()} />
        <Button
          leftSection={<IconShieldCheck size={16} />}
          disabled={!reason || !until}
          onClick={async () => {
            try {
              await post("/support-access/", { reason, expires_at: new Date(until!).toISOString() });
              setReason("");
              refetch();
            } catch (error) {
              notifications.show({ color: "red", message: errorMessage(error) });
            }
          }}
        >
          Grant access
        </Button>
      </Group>
      <Table>
        <Table.Thead><Table.Tr><Table.Th>Reason</Table.Th><Table.Th>Until</Table.Th><Table.Th /></Table.Tr></Table.Thead>
        <Table.Tbody>
          {rows.map((g: any) => (
            <Table.Tr key={g.id}>
              <Table.Td>{g.reason}</Table.Td>
              <Table.Td>{dateTime(g.expires_at)} {new Date(g.expires_at) > new Date() ? <Badge color="orange" size="xs">Active</Badge> : <Badge size="xs" color="gray">Expired</Badge>}</Table.Td>
              <Table.Td><Button size="xs" variant="subtle" color="red" onClick={async () => { await del(`/support-access/${g.id}/`); refetch(); }}>Revoke</Button></Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

export default function UsersPage() {
  const { me } = useAuth();
  const [member, setMember] = useState<any>(null);
  // A person can only inherit modules the school has; none chosen means all of them.
  const moduleOptions = (me?.modules ?? [])
    .filter((m) => m !== "setup" && m !== "learners")
    .map((m) => ({ value: m, label: me?.module_labels[m] ?? m }));
  return (
    <>
      <PageHeader title="Users & roles" description="Staff logins and what each person may see and do. There are no parent or learner logins." />
      <Tabs defaultValue="users" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="users">Users</Tabs.Tab>
          <Tabs.Tab value="grants">Temporary permissions</Tabs.Tab>
          <Tabs.Tab value="support">Support access</Tabs.Tab>
          <Tabs.Tab value="levels">Access levels</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="users">
          <CrudPage
            hideHeader
            title="Users"
            singular="user"
            formHelp="Give a staff member a sign-in and an access level. They sign in with the School ID and this username."
            endpoint="/users/"
            writePerm="users.manage"
            canDelete={false}
            defaults={{ is_active: true }}
            onRowClick={(row: any) => setMember(row)}
            extraActions={(row: any) => (
              <Tooltip label="Roles">
                <ActionIcon variant="light" onClick={() => setMember(row)}>
                  <IconShieldCheck size={16} />
                </ActionIcon>
              </Tooltip>
            )}
            columns={[
              { key: "name", label: "Name", render: (r: any) => <><Text size="sm" fw={600}>{r.first_name} {r.last_name}</Text><Text size="xs" c="dimmed">{r.username}</Text></> },
              { key: "roles", label: "Roles", render: (r: any) => <Group gap={4}>{r.roles.map((role: any) => <Badge key={role.id} variant="light" size="sm">{role.role_label}</Badge>)}</Group> },
              { key: "phone", label: "Phone" },
              { key: "last_login", label: "Last sign-in", render: (r: any) => dateTime(r.last_login) },
              { key: "is_active", label: "Status", render: (r: any) => <StatusBadge value={r.is_active ? "active" : "suspended"} label={r.is_active ? "Active" : "Disabled"} /> },
            ]}
            fields={[
              { name: "username", label: "Username", required: true },
              { name: "first_name", label: "First name" },
              { name: "last_name", label: "Surname" },
              { name: "email", label: "Email", type: "email" },
              { name: "phone", label: "Phone" },
              { name: "title", label: "Job title" },
              { name: "password", label: "Password", type: "password", description: "Required for a new user; leave empty to keep the current one" },
              { name: "modules", label: "Modules this person can open", type: "multiselect", options: moduleOptions, span: 12, description: "Leave empty to give every module the school has" },
              { name: "is_active", label: "Can sign in", type: "checkbox" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="grants">
          <CrudPage
            hideHeader
            title="Temporary permissions"
            singular="permission grant"
            formHelp="Give one extra right to a person for a limited time, e.g. let a teacher enter marks for a colleague on leave."
            endpoint="/permission-grants/"
            writePerm="users.manage"
            columns={[
              { key: "membership", label: "User" },
              { key: "permission", label: "Permission" },
              { key: "reason", label: "Reason" },
              { key: "expires_at", label: "Expires", render: (r: any) => dateTime(r.expires_at) },
            ]}
            fields={[
              { name: "membership", label: "User", type: "select", required: true, optionsFrom: { endpoint: "/users/", label: (u: any) => `${u.first_name} ${u.last_name} (${u.username})` } },
              { name: "permission", label: "Permission", required: true, placeholder: "e.g. discipline.view" },
              { name: "reason", label: "Reason", required: true },
              { name: "expires_at", label: "Expires", type: "datetime", required: true },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="levels">
          <AccessLevels />
        </Tabs.Panel>
        <Tabs.Panel value="support">
          <SupportAccess />
        </Tabs.Panel>
      </Tabs>
      {member && <RolesDrawer member={member} onClose={() => setMember(null)} />}
    </>
  );
}
