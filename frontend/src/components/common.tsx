import { Badge, Card, Group, Stack, Text, ThemeIcon, Title, type MantineColor } from "@mantine/core";
import type { ReactNode } from "react";

import { statusColor, titleCase } from "@/utils/format";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <Group justify="space-between" align="flex-start" mb="lg" wrap="wrap" gap="sm">
      <Stack gap={2}>
        <Title order={2}>{title}</Title>
        {description && (
          <Text c="dimmed" size="sm" maw={720}>
            {description}
          </Text>
        )}
      </Stack>
      {actions && <Group gap="xs">{actions}</Group>}
    </Group>
  );
}

export function StatusBadge({ value, label }: { value: string | null | undefined; label?: string }) {
  if (!value) return <Text c="dimmed">–</Text>;
  return (
    <Badge color={statusColor(value)} variant="light" radius="sm">
      {label ?? titleCase(value)}
    </Badge>
  );
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  color = "brand",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  color?: MantineColor;
}) {
  return (
    <Card>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Stack gap={4}>
          <Text size="xs" tt="uppercase" fw={600} c="dimmed">
            {label}
          </Text>
          <Text fw={700} fz={26} lh={1.1}>
            {value}
          </Text>
          {hint && (
            <Text size="xs" c="dimmed">
              {hint}
            </Text>
          )}
        </Stack>
        {icon && (
          <ThemeIcon variant="light" color={color} size={42} radius="md">
            {icon}
          </ThemeIcon>
        )}
      </Group>
    </Card>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <Stack align="center" gap={4} py="xl">
      <Text fw={600}>{title}</Text>
      {children && (
        <Text c="dimmed" size="sm" ta="center" maw={420}>
          {children}
        </Text>
      )}
    </Stack>
  );
}

export function Section({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <Card>
      <Group justify="space-between" mb="md">
        <Text fw={650}>{title}</Text>
        {actions}
      </Group>
      {children}
    </Card>
  );
}
