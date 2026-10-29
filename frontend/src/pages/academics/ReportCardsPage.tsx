import { ActionIcon, Alert, Button, Card, Group, List, Select, SimpleGrid, Stack, Text, Textarea, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconFileTypePdf, IconMail, IconRefresh, IconRosetteDiscountCheck } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError, errorMessage, openFile, patch, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { ResourceTable } from "@/components/ResourceTable";
import { useClasses, useCurrentTerm, useTerms } from "@/hooks/useSchool";
import { num } from "@/utils/format";

function CommentCell({ card, field, editable }: { card: any; field: "class_teacher_comment" | "head_comment"; editable: boolean }) {
  const [value, setValue] = useState(card[field] ?? "");
  useEffect(() => setValue(card[field] ?? ""), [card, field]);
  if (!editable) return <Text size="xs">{card[field] || "–"}</Text>;
  return (
    <Textarea
      size="xs"
      autosize
      minRows={1}
      value={value}
      onChange={(e) => setValue(e.currentTarget.value)}
      onBlur={async () => {
        if (value === (card[field] ?? "")) return;
        try {
          await patch(`/report-cards/${card.id}/`, { [field]: value });
        } catch (error) {
          notifications.show({ color: "red", message: errorMessage(error) });
        }
      }}
    />
  );
}

export default function ReportCardsPage() {
  const { can } = useAuth();
  const client = useQueryClient();
  const { options: termOptions } = useTerms();
  const current = useCurrentTerm();
  const { options: classOptions } = useClasses();
  const [term, setTerm] = useState<string | null>(null);
  const [schoolClass, setSchoolClass] = useState<string | null>(null);
  const [pending, setPending] = useState<string[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const termId = term ?? (current ? String(current.id) : null);
  const body = { term: termId, school_class: schoolClass };
  const refresh = () => client.invalidateQueries({ queryKey: ["list", "/report-cards/"] });

  const run = async (name: string, action: () => Promise<void>) => {
    setBusy(name);
    try {
      await action();
    } finally {
      setBusy(null);
    }
  };

  const generate = (allowUnapproved = false) =>
    run("generate", async () => {
      try {
        const result = await post("/report-cards/generate/", { ...body, allow_unapproved: allowUnapproved });
        setPending(null);
        notifications.show({ color: "green", message: `${result.generated} report card(s) prepared.` });
        refresh();
      } catch (error) {
        if (error instanceof ApiError && error.data?.pending) setPending(error.data.pending);
        else notifications.show({ color: "red", message: errorMessage(error) });
      }
    });

  return (
    <>
      <PageHeader
        title="Report cards"
        description="Once the DOS has approved the marks, the class teacher (or the DOS, head teacher or director) generates the cards, writes comments and prints them. The head teacher adds a comment and publishes. Each card has a serial number and a QR code anyone can check."
      />
      <Card mb="md">
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
          <Select label="Term" data={termOptions} value={termId} onChange={setTerm} />
          <Select label="Class" data={classOptions} value={schoolClass} onChange={setSchoolClass} searchable placeholder="Choose class" />
        </SimpleGrid>
        {schoolClass && termId && (
          <Group mt="md" gap="xs">
            {can("reports.generate") && (
              <Button leftSection={<IconRefresh size={16} />} loading={busy === "generate"} onClick={() => generate()}>
                Generate / refresh
              </Button>
            )}
            {can("reports.approve") && (
              <Button
                color="green"
                leftSection={<IconRosetteDiscountCheck size={16} />}
                loading={busy === "publish"}
                onClick={() =>
                  modalsConfirm({
                    title: "Approve and publish these report cards?",
                    message: "Published cards cannot be edited. Corrections later produce a new card with a new serial.",
                    confirmLabel: "Publish",
                    onConfirm: async () => {
                      const result = await post("/report-cards/publish/", body);
                      notifications.show({ color: "green", message: `${result.published} card(s) published.` });
                      refresh();
                    },
                  })
                }
              >
                Approve & publish
              </Button>
            )}
            <Button variant="default" leftSection={<IconFileTypePdf size={16} />} onClick={() => openFile("/report-cards/class-pdf/", body)}>
              Print whole class (PDF)
            </Button>
            {can("reports.approve") && (
              <Button
                variant="default"
                leftSection={<IconMail size={16} />}
                loading={busy === "email"}
                onClick={() =>
                  run("email", async () => {
                    try {
                      const r = await post("/report-cards/email/", body);
                      notifications.show({ color: "green", message: `${r.sent} email(s) sent; ${r.no_email} learner(s) have no guardian email.` });
                    } catch (error) {
                      notifications.show({ color: "red", message: errorMessage(error) });
                    }
                  })
                }
              >
                Email to guardians
              </Button>
            )}
          </Group>
        )}
      </Card>
      {pending && (
        <Alert color="orange" title="Some mark sheets are not approved yet" mb="md">
          <List size="sm" mb="sm">
            {pending.slice(0, 12).map((p) => (
              <List.Item key={p}>{p}</List.Item>
            ))}
            {pending.length > 12 && <List.Item>…and {pending.length - 12} more</List.Item>}
          </List>
          {can("reports.generate") && (
            <Button size="xs" variant="light" color="orange" onClick={() => generate(true)}>
              Prepare a preview anyway (unapproved marks included)
            </Button>
          )}
        </Alert>
      )}
      {schoolClass && termId ? (
        <ResourceTable
          endpoint="/report-cards/"
          query={{ term: termId, result__school_class: schoolClass }}
          searchable={false}
          pageSize={100}
          filters={[{ name: "status", label: "Status", options: [{ value: "draft", label: "Draft" }, { value: "published", label: "Published" }, { value: "superseded", label: "Superseded" }] }]}
          columns={[
            { key: "learner_name", label: "Learner", render: (r: any) => <><Text size="sm" fw={600}>{r.learner_name}</Text><Text size="xs" c="dimmed">{r.serial}</Text></> },
            { key: "avg", label: "Average", render: (r: any) => num(r.summary.average) },
            { key: "agg", label: "Agg / Div", render: (r: any) => (r.summary.aggregate ? `${r.summary.aggregate} · ${r.summary.division}` : r.summary.points ?? "–") },
            { key: "pos", label: "Position", render: (r: any) => (r.summary.position ? `${r.summary.position}/${r.summary.out_of}` : "–") },
            { key: "ct", label: "Class teacher's comment", width: "26%", render: (r: any) => <CommentCell card={r} field="class_teacher_comment" editable={r.status === "draft" && can("reports.comment")} /> },
            { key: "ht", label: "Head teacher's comment", width: "22%", render: (r: any) => <CommentCell card={r} field="head_comment" editable={r.status === "draft" && can("reports.approve")} /> },
            { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} /> },
          ]}
          rowActions={(r: any) => (
            <Tooltip label="Open PDF">
              <ActionIcon variant="subtle" onClick={() => openFile(`/report-cards/${r.id}/pdf/`)}>
                <IconFileTypePdf size={16} />
              </ActionIcon>
            </Tooltip>
          )}
          emptyTitle="No report cards yet"
          emptyText="Generate them once the class's mark sheets are approved."
        />
      ) : (
        <Stack align="center" py="xl">
          <Text c="dimmed">Choose a class to see its report cards.</Text>
        </Stack>
      )}
    </>
  );
}
