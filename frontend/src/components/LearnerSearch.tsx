import { Avatar, Badge, Combobox, Group, Loader, Text, TextInput, useCombobox } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconSearch } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { get } from "@/api/client";
import { statusColor } from "@/utils/format";

interface Hit {
  id: number;
  name: string;
  adm_no: string;
  class: string | null;
  stream: string | null;
  status: string;
  photo: string | null;
}

/** Search any learner by name (partial or misspelt), admission number, LIN, class or guardian phone. */
export function LearnerSearch({ width = 340 }: { width?: number | string }) {
  const navigate = useNavigate();
  const combobox = useCombobox({ onDropdownClose: () => combobox.resetSelectedOption() });
  const [value, setValue] = useState("");
  const [query] = useDebouncedValue(value, 250);
  const { data = [], isFetching } = useQuery({
    queryKey: ["learner-search", query],
    enabled: query.trim().length >= 2,
    queryFn: () => get<Hit[]>("/learners/search/", { q: query }),
  });

  return (
    <Combobox
      store={combobox}
      onOptionSubmit={(id) => {
        combobox.closeDropdown();
        setValue("");
        navigate(`/learners/${id}`);
      }}
    >
      <Combobox.Target>
        <TextInput
          w={width}
          placeholder="Find a learner — name, adm. no, LIN, class, guardian phone"
          leftSection={<IconSearch size={16} />}
          rightSection={isFetching ? <Loader size={14} /> : null}
          value={value}
          onChange={(e) => {
            setValue(e.currentTarget.value);
            combobox.openDropdown();
            combobox.updateSelectedOptionIndex();
          }}
          onFocus={() => combobox.openDropdown()}
          onBlur={() => combobox.closeDropdown()}
          aria-label="Search learners"
        />
      </Combobox.Target>
      <Combobox.Dropdown hidden={query.trim().length < 2}>
        <Combobox.Options mah={380} style={{ overflowY: "auto" }}>
          {data.length === 0 && !isFetching && <Combobox.Empty>No learner found</Combobox.Empty>}
          {data.map((hit) => (
            <Combobox.Option value={String(hit.id)} key={hit.id}>
              <Group gap="sm" wrap="nowrap">
                <Avatar src={hit.photo} radius="xl" size={32} color="brand">
                  {hit.name.slice(0, 2).toUpperCase()}
                </Avatar>
                <div style={{ flex: 1 }}>
                  <Text size="sm" fw={600}>
                    {hit.name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {hit.adm_no} · {hit.class ? `${hit.class}${hit.stream ?? ""}` : "No class this term"}
                  </Text>
                </div>
                {hit.status !== "active" && (
                  <Badge size="xs" variant="light" color={statusColor(hit.status)}>
                    {hit.status}
                  </Badge>
                )}
              </Group>
            </Combobox.Option>
          ))}
        </Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
}
