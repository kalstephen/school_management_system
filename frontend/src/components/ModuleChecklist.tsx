import { Badge, Button, Checkbox, Group, SimpleGrid, Stack, Text, UnstyledButton } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";

import { get } from "@/api/client";

import { moduleIcon } from "./moduleIcons";

export interface ModuleInfo {
  key: string;
  label: string;
  description: string;
  group: "core" | "add-on";
  required: boolean;
}

export function useModuleCatalog() {
  return useQuery({ queryKey: ["module-catalog"], queryFn: () => get<ModuleInfo[]>("/modules/"), staleTime: 60 * 60_000 }).data ?? [];
}

/**
 * Tick list of every module in the system. Required modules are always ticked.
 * `available` limits the choice (e.g. a user can only inherit the school's modules).
 */
export function ModuleChecklist({
  value,
  onChange,
  available,
  disabled,
}: {
  value: string[];
  onChange: (modules: string[]) => void;
  available?: string[];
  disabled?: boolean;
}) {
  const catalog = useModuleCatalog();
  const choosable = catalog.filter((m) => !m.required && (!available || available.includes(m.key)));
  const toggle = (key: string, on: boolean) => onChange(on ? Array.from(new Set([...value, key])) : value.filter((k) => k !== key));

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {value.filter((k) => choosable.some((m) => m.key === k)).length + catalog.filter((m) => m.required).length} of{" "}
          {available ? available.length : catalog.length} modules ticked
        </Text>
        {!disabled && (
          <Group gap="xs">
            <Button size="compact-xs" variant="subtle" onClick={() => onChange(choosable.map((m) => m.key))}>
              Tick all
            </Button>
            <Button size="compact-xs" variant="subtle" color="gray" onClick={() => onChange([])}>
              Clear
            </Button>
          </Group>
        )}
      </Group>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="xs">
        {catalog
          .filter((m) => !available || available.includes(m.key) || m.required)
          .map((m) => {
            const checked = m.required || value.includes(m.key);
            const Icon = moduleIcon(m.key);
            return (
              <UnstyledButton
                key={m.key}
                onClick={() => !m.required && !disabled && toggle(m.key, !checked)}
                style={{
                  border: `1px solid ${checked ? "var(--mantine-color-brand-4)" : "var(--mantine-color-default-border)"}`,
                  background: checked ? "var(--mantine-color-brand-light)" : undefined,
                  borderRadius: 10,
                  padding: 10,
                  cursor: m.required || disabled ? "default" : "pointer",
                }}
              >
                <Group gap="sm" wrap="nowrap" align="flex-start">
                  <Checkbox checked={checked} readOnly disabled={m.required || disabled} tabIndex={-1} aria-label={m.label} mt={2} />
                  <Icon size={20} color="var(--mantine-color-brand-6)" style={{ flexShrink: 0, marginTop: 1 }} />
                  <div>
                    <Group gap={6}>
                      <Text size="sm" fw={600}>
                        {m.label}
                      </Text>
                      {m.required && <Badge size="xs" variant="light" color="gray">required</Badge>}
                      {m.group === "add-on" && <Badge size="xs" variant="light" color="grape">add-on</Badge>}
                    </Group>
                    <Text size="xs" c="dimmed">
                      {m.description}
                    </Text>
                  </div>
                </Group>
              </UnstyledButton>
            );
          })}
      </SimpleGrid>
    </Stack>
  );
}
