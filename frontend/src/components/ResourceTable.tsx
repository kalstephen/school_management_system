import { ActionIcon, Button, Card, Group, Pagination, ScrollArea, Select, Skeleton, Table, Text, TextInput, Tooltip } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { useDebouncedValue } from "@mantine/hooks";
import { IconDownload, IconRefresh, IconSearch } from "@tabler/icons-react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { get, openFile, type Paginated, type Query } from "@/api/client";
import type { Option } from "@/api/types";
import { useOptions, type OptionSource } from "@/hooks/useOptions";

import { Empty } from "./common";

export interface Column<T = any> {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
  width?: number | string;
  align?: "left" | "right" | "center";
}

export interface Filter {
  name: string;
  label: string;
  type?: "select" | "date";
  options?: Option[];
  optionsFrom?: OptionSource;
}

function FilterInput({ filter, value, onChange }: { filter: Filter; value: string | null; onChange: (v: string | null) => void }) {
  const { options: loaded } = useOptions(filter.optionsFrom, !!filter.optionsFrom);
  if (filter.type === "date") {
    return <DateInput placeholder={filter.label} value={value} onChange={onChange} clearable w={160} valueFormat="D MMM YYYY" />;
  }
  return (
    <Select
      placeholder={filter.label}
      data={filter.options ?? loaded}
      value={value}
      onChange={onChange}
      clearable
      searchable
      w={180}
    />
  );
}

export interface ResourceTableProps<T> {
  endpoint: string;
  columns: Column<T>[];
  query?: Query;
  filters?: Filter[];
  searchable?: boolean;
  searchPlaceholder?: string;
  exportable?: boolean;
  rowActions?: (row: T) => ReactNode;
  onRowClick?: (row: T) => void;
  toolbar?: ReactNode;
  emptyTitle?: string;
  emptyText?: string;
  pageSize?: number;
  paginated?: boolean;
}

export function ResourceTable<T extends { id: number | string }>({
  endpoint,
  columns,
  query,
  filters = [],
  searchable = true,
  searchPlaceholder = "Search…",
  exportable = false,
  rowActions,
  onRowClick,
  toolbar,
  emptyTitle = "Nothing here yet",
  emptyText,
  pageSize = 25,
  paginated = true,
}: ResourceTableProps<T>) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debounced] = useDebouncedValue(search, 300);
  const [filterValues, setFilterValues] = useState<Record<string, string | null>>({});
  const params: Query = { ...query, ...filterValues, search: debounced || undefined, page: paginated ? page : undefined, page_size: pageSize };

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["list", endpoint, params],
    queryFn: () => get<Paginated<T> | T[]>(endpoint, params),
    placeholderData: keepPreviousData,
  });
  const rows = Array.isArray(data) ? data : data?.results ?? [];
  const total = Array.isArray(data) ? data.length : data?.count ?? 0;

  return (
    <Card p={0}>
      {(searchable || filters.length > 0 || toolbar || exportable) && (
        <Group p="md" gap="sm" justify="space-between" wrap="wrap">
          <Group gap="sm" wrap="wrap">
            {searchable && (
              <TextInput
                leftSection={<IconSearch size={16} />}
                placeholder={searchPlaceholder}
                value={search}
                onChange={(e) => {
                  setSearch(e.currentTarget.value);
                  setPage(1);
                }}
                w={240}
              />
            )}
            {filters.map((filter) => (
              <FilterInput
                key={filter.name}
                filter={filter}
                value={filterValues[filter.name] ?? null}
                onChange={(value) => {
                  setFilterValues((current) => ({ ...current, [filter.name]: value }));
                  setPage(1);
                }}
              />
            ))}
          </Group>
          <Group gap="xs">
            {toolbar}
            {exportable && (
              <Button variant="default" leftSection={<IconDownload size={16} />} onClick={() => openFile(`${endpoint}export/`, { ...query, ...filterValues, search: debounced })}>
                Excel
              </Button>
            )}
            <Tooltip label="Refresh">
              <ActionIcon variant="default" size="lg" onClick={() => refetch()} loading={isFetching}>
                <IconRefresh size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      )}
      <ScrollArea>
        <Table striped={false} miw={600}>
          <Table.Thead>
            <Table.Tr>
              {columns.map((column) => (
                <Table.Th key={column.key} w={column.width} ta={column.align}>
                  {column.label}
                </Table.Th>
              ))}
              {rowActions && <Table.Th w={1} />}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {isLoading &&
              Array.from({ length: 5 }).map((_, i) => (
                <Table.Tr key={i}>
                  {columns.map((c) => (
                    <Table.Td key={c.key}>
                      <Skeleton h={14} />
                    </Table.Td>
                  ))}
                  {rowActions && <Table.Td />}
                </Table.Tr>
              ))}
            {rows.map((row) => (
              <Table.Tr key={row.id} onClick={onRowClick ? () => onRowClick(row) : undefined} style={onRowClick ? { cursor: "pointer" } : undefined}>
                {columns.map((column) => (
                  <Table.Td key={column.key} ta={column.align}>
                    {column.render ? column.render(row) : String((row as any)[column.key] ?? "–")}
                  </Table.Td>
                ))}
                {rowActions && (
                  <Table.Td onClick={(e) => e.stopPropagation()}>
                    <Group gap={4} wrap="nowrap" justify="flex-end">
                      {rowActions(row)}
                    </Group>
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
      {!isLoading && rows.length === 0 && <Empty title={emptyTitle}>{emptyText}</Empty>}
      {paginated && total > pageSize && (
        <Group justify="space-between" p="md">
          <Text size="sm" c="dimmed">
            {total.toLocaleString()} records
          </Text>
          <Pagination total={Math.ceil(total / pageSize)} value={page} onChange={setPage} size="sm" />
        </Group>
      )}
    </Card>
  );
}
