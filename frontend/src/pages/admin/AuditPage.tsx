import { Code, Text } from "@mantine/core";

import { PageHeader, StatusBadge } from "@/components/common";
import { ResourceTable } from "@/components/ResourceTable";
import { dateTime } from "@/utils/format";

export default function AuditPage() {
  return (
    <>
      <PageHeader title="Audit log" description="Every create, edit and delete in the school, with the values before and after and who made the change." />
      <ResourceTable
        endpoint="/audit-log/"
        pageSize={50}
        searchPlaceholder="Search records…"
        filters={[
          { name: "action", label: "Action", options: [{ value: "create", label: "Created" }, { value: "update", label: "Updated" }, { value: "delete", label: "Deleted" }] },
          { name: "timestamp__gte", label: "From", type: "date" },
        ]}
        columns={[
          { key: "timestamp", label: "When", render: (r: any) => dateTime(r.timestamp) },
          { key: "user_name", label: "By", render: (r: any) => r.user_name ?? "system" },
          { key: "action", label: "Action", render: (r: any) => <StatusBadge value={r.action === "create" ? "active" : r.action === "delete" ? "rejected" : "submitted"} label={r.action} /> },
          { key: "entity", label: "Record", render: (r: any) => <><Text size="sm">{r.object_repr}</Text><Text size="xs" c="dimmed">{r.entity} #{r.object_id}</Text></> },
          {
            key: "changes",
            label: "Changes",
            render: (r: any) => (
              <Code block style={{ maxWidth: 420, whiteSpace: "pre-wrap", fontSize: 11 }}>
                {Object.entries(r.changes)
                  .slice(0, 6)
                  .map(([field, [before, after]]: any) => `${field}: ${before ?? "–"} → ${after ?? "–"}`)
                  .join("\n")}
              </Code>
            ),
          },
        ]}
      />
    </>
  );
}
