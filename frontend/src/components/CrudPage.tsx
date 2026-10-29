import { ActionIcon, Button, Tooltip } from "@mantine/core";
import { modalsConfirm } from "@/components/confirm";
import { notifications } from "@mantine/notifications";
import { IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { del, errorMessage, type Query } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";

import { PageHeader } from "./common";
import { FormModal, type Field } from "./ResourceForm";
import { ResourceTable, type Column, type Filter } from "./ResourceTable";

export interface CrudPageProps<T> {
  title: string;
  description?: string;
  endpoint: string;
  columns: Column<T>[];
  fields: Field[];
  writePerm?: string;
  singular?: string;
  defaults?: Record<string, any>;
  query?: Query;
  filters?: Filter[];
  exportable?: boolean;
  canDelete?: boolean;
  /** false hides the "New …" button (e.g. when the page offers its own way to add). */
  canCreate?: boolean;
  /** false hides the edit pencil (rows that can be added here but changed elsewhere). */
  canEdit?: boolean;
  /** A short note at the top of the add/edit form saying what the form is for. */
  formHelp?: ReactNode;
  extraActions?: (row: T) => ReactNode;
  headerActions?: ReactNode;
  onRowClick?: (row: T) => void;
  toForm?: (row: T) => Record<string, any>;
  hideHeader?: boolean;
  emptyText?: string;
}

export function CrudPage<T extends { id: number }>({
  title,
  description,
  endpoint,
  columns,
  fields,
  writePerm,
  singular,
  defaults,
  query,
  filters,
  exportable,
  canDelete = true,
  canCreate = true,
  canEdit = true,
  formHelp,
  extraActions,
  headerActions,
  onRowClick,
  toForm,
  hideHeader,
  emptyText,
}: CrudPageProps<T>) {
  const { can, me } = useAuth();
  const client = useQueryClient();
  const writable = (!writePerm || can(writePerm)) && me?.access !== "read_only" && me?.access !== "suspended";
  const [editing, setEditing] = useState<T | null>(null);
  const [creating, setCreating] = useState(false);
  const name = singular ?? title.replace(/s$/, "").toLowerCase();

  const remove = (row: T) =>
    modalsConfirm({
      title: `Delete this ${name}?`,
      message: "This cannot be undone. The change is recorded in the audit log.",
      confirmLabel: "Delete",
      danger: true,
      onConfirm: async () => {
        try {
          await del(`${endpoint}${row.id}/`);
          client.invalidateQueries({ queryKey: ["list", endpoint] });
          notifications.show({ color: "green", message: "Deleted" });
        } catch (error) {
          notifications.show({ color: "red", title: "Not deleted", message: errorMessage(error) });
        }
      },
    });

  const newButton = writable && canCreate ? (
    <Button leftSection={<IconPlus size={16} />} onClick={() => setCreating(true)}>
      New {name}
    </Button>
  ) : null;

  return (
    <>
      {!hideHeader && <PageHeader title={title} description={description} actions={<>{headerActions}{newButton}</>} />}
      <ResourceTable<T>
        endpoint={endpoint}
        columns={columns}
        query={query}
        filters={filters}
        exportable={exportable}
        onRowClick={onRowClick}
        emptyText={emptyText}
        toolbar={hideHeader ? <>{headerActions}{newButton}</> : undefined}
        rowActions={(row) => (
          <>
            {extraActions?.(row)}
            {writable && canEdit && (
              <Tooltip label="Edit">
                <ActionIcon variant="subtle" onClick={() => setEditing(row)}>
                  <IconPencil size={16} />
                </ActionIcon>
              </Tooltip>
            )}
            {writable && canDelete && (
              <Tooltip label="Delete">
                <ActionIcon variant="subtle" color="red" onClick={() => remove(row)}>
                  <IconTrash size={16} />
                </ActionIcon>
              </Tooltip>
            )}
          </>
        )}
      />
      <FormModal
        opened={creating}
        onClose={() => setCreating(false)}
        title={`New ${name}`}
        help={formHelp}
        fields={fields}
        endpoint={endpoint}
        initial={defaults}
      />
      <FormModal
        opened={!!editing}
        onClose={() => setEditing(null)}
        title={`Edit ${name}`}
        help={formHelp}
        fields={fields}
        endpoint={endpoint}
        id={editing?.id}
        initial={editing ? (toForm ? toForm(editing) : (editing as any)) : undefined}
      />
    </>
  );
}
