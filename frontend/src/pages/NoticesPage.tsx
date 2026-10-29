import { ActionIcon, Badge, Button, Card, Group, Stack, Tabs, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconPrinter, IconSend } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { errorMessage, get, openFile, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Empty, PageHeader, StatusBadge } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { CrudPage } from "@/components/CrudPage";
import { useClasses } from "@/hooks/useSchool";
import { date, dateTime } from "@/utils/format";

const ROLES = [
  "director", "head_teacher", "dos", "hod", "class_teacher", "subject_teacher", "bursar", "storekeeper", "nurse", "librarian", "school_admin",
].map((r) => ({ value: r, label: r.replace(/_/g, " ") }));

function MyNotifications() {
  const client = useQueryClient();
  const { data } = useQuery({ queryKey: ["list", "/notifications/"], queryFn: () => get("/notifications/", { page_size: 50 }) });
  const rows = data?.results ?? [];
  return (
    <Stack>
      <Group justify="flex-end">
        <Button
          variant="default"
          size="xs"
          onClick={async () => {
            await post("/notifications/read-all/");
            client.invalidateQueries({ queryKey: ["list", "/notifications/"] });
            client.invalidateQueries({ queryKey: ["unread-notifications"] });
          }}
        >
          Mark all as read
        </Button>
      </Group>
      {rows.length === 0 && <Empty title="No notifications" />}
      {rows.map((n: any) => (
        <Card key={n.id} padding="md" style={{ opacity: n.read_at ? 0.65 : 1 }}>
          <Group justify="space-between" wrap="nowrap">
            <Text fw={600}>{n.title}</Text>
            <Group gap="xs">
              {!n.read_at && <Badge size="xs">New</Badge>}
              <Text size="xs" c="dimmed">{dateTime(n.created_at)}</Text>
            </Group>
          </Group>
          {n.body && <Text size="sm" mt={4}>{n.body}</Text>}
        </Card>
      ))}
    </Stack>
  );
}

export default function NoticesPage() {
  const { can } = useAuth();
  const client = useQueryClient();
  const { options: classOptions } = useClasses();

  const publish = (row: any) =>
    modalsConfirm({
      title: `Publish "${row.title}"?`,
      message: row.email_guardians ? "Staff are notified in the app, and guardians with an email address receive it as a circular." : "Staff in the chosen audience are notified in the app.",
      confirmLabel: "Publish",
      onConfirm: async () => {
        try {
          const result = await post(`/notices/${row.id}/publish/`);
          notifications.show({ color: "green", message: `${result.staff_notified} staff notified${row.email_guardians ? `, ${result.emails_sent} email(s) sent` : ""}.` });
          client.invalidateQueries({ queryKey: ["list", "/notices/"] });
        } catch (error) {
          notifications.show({ color: "red", message: errorMessage(error) });
        }
      },
    });

  return (
    <>
      <PageHeader title="Notices & communication" description="Staff notices, printable circulars, email to guardians and the school calendar. (No SMS in this version.)" />
      <Tabs defaultValue="notices" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="notices">Notices</Tabs.Tab>
          <Tabs.Tab value="mine">My notifications</Tabs.Tab>
          <Tabs.Tab value="calendar">Calendar</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="notices">
          <CrudPage
            hideHeader
            title="Notices"
            singular="notice"
            formHelp="A notice for staff (and, if ticked, emailed to guardians). Staff see it under Notices and get a notification."
            endpoint="/notices/"
            writePerm="communication.post"
            defaults={{ audience: "all_staff" }}
            toForm={(r: any) => ({ ...r, guardian_classes: r.guardian_classes.map(String) })}
            extraActions={(row: any) => (
              <>
                <Tooltip label="Printable circular">
                  <ActionIcon variant="subtle" onClick={() => openFile(`/notices/${row.id}/circular/`)}>
                    <IconPrinter size={16} />
                  </ActionIcon>
                </Tooltip>
                {can("communication.post") && !row.published_at && (
                  <Tooltip label="Publish">
                    <ActionIcon variant="light" color="green" onClick={() => publish(row)}>
                      <IconSend size={16} />
                    </ActionIcon>
                  </Tooltip>
                )}
              </>
            )}
            columns={[
              { key: "title", label: "Notice", render: (r: any) => <><Text size="sm" fw={600}>{r.pinned ? "📌 " : ""}{r.title}</Text><Text size="xs" c="dimmed" lineClamp={1}>{r.body}</Text></> },
              { key: "audience", label: "To", render: (r: any) => (r.audience === "roles" ? r.roles.join(", ") : r.audience.replace("_", " ")) + (r.email_guardians ? " + guardians" : "") },
              { key: "published_at", label: "Status", render: (r: any) => (r.published_at ? <StatusBadge value="published" label={`Published ${date(r.published_at)}`} /> : <StatusBadge value="draft" />) },
            ]}
            fields={[
              { name: "title", label: "Title", required: true, span: 12 },
              { name: "body", label: "Message", type: "textarea", required: true },
              { name: "audience", label: "Staff audience", type: "select", options: [{ value: "all_staff", label: "All staff" }, { value: "teachers", label: "Teaching staff" }, { value: "roles", label: "Selected roles" }] },
              { name: "roles", label: "Roles", type: "multiselect", options: ROLES, hidden: (v) => v.audience !== "roles" },
              { name: "expires_on", label: "Show until", type: "date" },
              { name: "pinned", label: "Pin to the top", type: "checkbox" },
              { name: "email_guardians", label: "Also email guardians (circular)", type: "checkbox" },
              { name: "guardian_classes", label: "Only guardians of these classes", type: "multiselect", options: classOptions, hidden: (v) => !v.email_guardians },
              { name: "attachment", label: "Attachment", type: "file" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="mine">
          <MyNotifications />
        </Tabs.Panel>
        <Tabs.Panel value="calendar">
          <CrudPage
            hideHeader
            title="Calendar"
            singular="event"
            formHelp="An event on the school calendar. An event of kind Holiday closes the school: no register is taken on those days."
            endpoint="/calendar/"
            writePerm="communication.post"
            defaults={{ kind: "event" }}
            columns={[
              { key: "start_date", label: "Date", render: (r: any) => `${date(r.start_date, "ddd D MMM YYYY")}${r.end_date ? ` – ${date(r.end_date, "D MMM")}` : ""}` },
              { key: "title", label: "Event" },
              { key: "kind", label: "Type", render: (r: any) => <Badge variant="light">{r.kind}</Badge> },
            ]}
            fields={[
              { name: "title", label: "Title", required: true },
              { name: "kind", label: "Type", type: "select", options: [{ value: "event", label: "School event" }, { value: "holiday", label: "Holiday" }, { value: "exam", label: "Exams" }, { value: "meeting", label: "Meeting" }] },
              { name: "start_date", label: "Starts", type: "date", required: true },
              { name: "end_date", label: "Ends", type: "date" },
              { name: "description", label: "Details", type: "textarea" },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
