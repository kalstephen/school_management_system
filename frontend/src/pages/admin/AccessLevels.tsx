import { Badge, Card, Group, ScrollArea, Stack, Table, Text, ThemeIcon, Timeline, Tooltip } from "@mantine/core";
import { IconCheck, IconCrown, IconShieldLock, IconUser, IconUsersGroup } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";

import { get } from "@/api/client";
import type { RoleInfo } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { Section } from "@/components/common";

/** Permission groups shown as columns of the matrix, in plain words. */
const AREAS: { label: string; perms: string[] }[] = [
  { label: "Dashboard & notices", perms: ["dashboard.view", "communication.view"] },
  { label: "Post notices", perms: ["communication.post"] },
  { label: "Learners (view)", perms: ["learners.view"] },
  { label: "Learners (edit)", perms: ["learners.manage"] },
  { label: "Roll call", perms: ["attendance.take"] },
  { label: "Enter marks", perms: ["marks.enter"] },
  { label: "Review / approve marks", perms: ["marks.review", "marks.approve"] },
  { label: "Approve report cards", perms: ["reports.approve"] },
  { label: "Promotion", perms: ["promotion.manage", "promotion.approve"] },
  { label: "Staff & HR", perms: ["staff.manage", "hr.approve"] },
  { label: "Finance (view)", perms: ["finance.view"] },
  { label: "Finance (record)", perms: ["finance.manage"] },
  { label: "Approve expenses", perms: ["finance.approve"] },
  { label: "Health records", perms: ["health.view"] },
  { label: "Library / stores", perms: ["library.manage", "stores.manage"] },
  { label: "School settings", perms: ["setup.manage"] },
  { label: "Users & roles", perms: ["users.manage"] },
  { label: "Audit log", perms: ["audit.view"] },
];

export function AccessLevels() {
  const { me } = useAuth();
  const { data: roles = [] } = useQuery({ queryKey: ["role-catalog"], queryFn: () => get<RoleInfo[]>("/roles/") });

  return (
    <Stack>
      <Section title="The access ladder">
        <Text size="sm" c="dimmed" mb="md">
          Each level can manage only the people and roles below it. Nobody can change their own access, and temporary
          permissions can only be given by someone who already holds them. A person may hold several roles; they get
          everything those roles allow together.
        </Text>
        <Timeline bulletSize={30} lineWidth={2}>
          <Timeline.Item bullet={<IconCrown size={16} />} title="Super admin (platform owner)" color="red">
            <Text size="sm" c="dimmed">
              Top of the system. Manages the platform team and has full access to the content manager. Not part of any school.
            </Text>
          </Timeline.Item>
          <Timeline.Item bullet={<IconShieldLock size={16} />} title="Platform team" color="orange">
            <Text size="sm" c="dimmed">
              Registers schools, plans and add-ons, and creates each school's first director or administrator. Can read a
              school's records only while that school grants time-limited support access.
            </Text>
          </Timeline.Item>
          {roles.map((role) => (
            <Timeline.Item
              key={role.value}
              bullet={role.value === "staff" ? <IconUser size={16} /> : <IconUsersGroup size={16} />}
              title={
                <Group gap="xs">
                  <Text fw={600} size="sm">
                    {role.label}
                  </Text>
                  <Badge size="xs" variant="light">
                    level {role.rank}
                  </Badge>
                  {me?.roles.some((r) => r.role === role.value) && (
                    <Badge size="xs" color="green">
                      you
                    </Badge>
                  )}
                  {role.assignable && (
                    <Badge size="xs" variant="outline" color="gray">
                      you can assign
                    </Badge>
                  )}
                </Group>
              }
            >
              <Text size="sm" c="dimmed">
                {role.description}
              </Text>
            </Timeline.Item>
          ))}
        </Timeline>
      </Section>
      <Card p={0}>
        <Text fw={650} p="md">
          What each role can do
        </Text>
        <ScrollArea>
          <Table withColumnBorders miw={1400} fz="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th miw={170}>Role</Table.Th>
                {AREAS.map((area) => (
                  <Table.Th key={area.label} ta="center" style={{ whiteSpace: "normal" }}>
                    {area.label}
                  </Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {roles.map((role) => (
                <Table.Tr key={role.value}>
                  <Table.Td fw={600}>{role.label}</Table.Td>
                  {AREAS.map((area) => {
                    const has = area.perms.some((p) => role.perms.includes(p));
                    return (
                      <Table.Td key={area.label} ta="center">
                        {has && (
                          <Tooltip label={area.perms.filter((p) => role.perms.includes(p)).join(", ")}>
                            <ThemeIcon size="sm" radius="xl" color="green" variant="light">
                              <IconCheck size={12} />
                            </ThemeIcon>
                          </Tooltip>
                        )}
                      </Table.Td>
                    );
                  })}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      </Card>
    </Stack>
  );
}
