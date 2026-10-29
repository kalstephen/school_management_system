import { ActionIcon, Button, Checkbox, Group, SegmentedControl, Tabs, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconArrowBackUp, IconCheck, IconEye, IconLockOpen, IconPencil } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { errorMessage, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { ResourceTable } from "@/components/ResourceTable";
import { useClasses } from "@/hooks/useSchool";
import { dateTime } from "@/utils/format";

import { SubjectComments } from "./SubjectComments";

const STATUSES = [
  ["draft", "Draft"], ["submitted", "Submitted"], ["reviewed", "Reviewed by HOD"], ["approved", "Approved"], ["returned", "Returned"],
].map(([value, label]) => ({ value, label }));

export default function MarkSheetsPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [params] = useSearchParams();
  const [mine, setMine] = useState(params.get("mine") ? "mine" : "all");
  const [selected, setSelected] = useState<number[]>([]);
  const { options: classOptions } = useClasses();
  const refresh = () => client.invalidateQueries({ queryKey: ["list", "/mark-sheets/"] });

  const act = async (id: number, action: string, body?: object, success = "Done") => {
    try {
      await post(`/mark-sheets/${id}/${action}/`, body);
      notifications.show({ color: "green", message: success });
      refresh();
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    }
  };

  return (
    <>
      <PageHeader
        title="Mark sheets"
        description="The class teacher (or subject teacher) enters marks and submits; the DOS approves and locks them (a head of department may check them first). Approved marks feed report cards."
        actions={
          <>
            {can("marks.enter") && (
              <SegmentedControl
                value={mine}
                onChange={setMine}
                data={[
                  { value: "mine", label: "My subjects" },
                  { value: "all", label: "All I can see" },
                ]}
              />
            )}
            {can("marks.approve") && selected.length > 0 && (
              <Button
                color="green"
                leftSection={<IconCheck size={16} />}
                onClick={async () => {
                  try {
                    const result = await post("/mark-sheets/bulk-approve/", { ids: selected });
                    notifications.show({ color: "green", message: `${result.approved} sheet(s) approved and locked.` });
                    setSelected([]);
                    refresh();
                  } catch (error) {
                    notifications.show({ color: "red", message: errorMessage(error) });
                  }
                }}
              >
                Approve {selected.length} selected
              </Button>
            )}
          </>
        }
      />
      <Tabs defaultValue="sheets" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="sheets">Mark sheets</Tabs.Tab>
          <Tabs.Tab value="comments">Subject comments</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="sheets">
      <ResourceTable
        endpoint="/mark-sheets/"
        query={{ mine: mine === "mine" ? 1 : undefined }}
        searchable={false}
        pageSize={50}
        filters={[
          { name: "exam", label: "Exam", optionsFrom: { endpoint: "/exams/", label: (e: any) => `${e.name} (${e.term_label})` } },
          { name: "school_class", label: "Class", options: classOptions },
          { name: "status", label: "Status", options: STATUSES },
          { name: "subject", label: "Subject", optionsFrom: { endpoint: "/subjects/", label: (s: any) => `${s.name} (${s.level})` } },
        ]}
        onRowClick={(row: any) => navigate(`/marks/${row.id}`)}
        columns={[
          ...(can("marks.approve")
            ? [
                {
                  key: "select",
                  label: "",
                  width: 36,
                  render: (r: any) =>
                    ["submitted", "reviewed"].includes(r.status) ? (
                      <Checkbox
                        onClick={(e) => e.stopPropagation()}
                        checked={selected.includes(r.id)}
                        onChange={(e) => {
                          const on = e.currentTarget.checked;
                          setSelected((s) => (on ? [...s, r.id] : s.filter((x) => x !== r.id)));
                        }}
                        aria-label="Select sheet"
                      />
                    ) : null,
                },
              ]
            : []),
          { key: "exam_name", label: "Exam" },
          { key: "subject", label: "Subject", render: (r: any) => `${r.subject_name}${r.paper_label ? ` · ${r.paper_label}` : ""}` },
          { key: "class_label", label: "Class" },
          { key: "marks_entered", label: "Marks entered" },
          { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} label={r.status_label} /> },
          { key: "submitted_at", label: "Submitted", render: (r: any) => dateTime(r.submitted_at) },
        ]}
        rowActions={(r: any) => (
          <Group gap={4} wrap="nowrap">
            <Tooltip label={["draft", "returned"].includes(r.status) && can("marks.enter") ? "Enter marks" : "View"}>
              <ActionIcon variant="subtle" onClick={() => navigate(`/marks/${r.id}`)}>
                {["draft", "returned"].includes(r.status) ? <IconPencil size={16} /> : <IconEye size={16} />}
              </ActionIcon>
            </Tooltip>
            {can("marks.review") && r.status === "submitted" && (
              <Tooltip label="Mark reviewed (HOD)">
                <ActionIcon variant="light" color="indigo" onClick={() => act(r.id, "review", undefined, "Reviewed")}>
                  <IconCheck size={16} />
                </ActionIcon>
              </Tooltip>
            )}
            {can("marks.approve") && ["submitted", "reviewed"].includes(r.status) && (
              <Tooltip label="Approve and lock">
                <ActionIcon variant="filled" color="green" onClick={() => act(r.id, "approve", undefined, "Approved and locked")}>
                  <IconCheck size={16} />
                </ActionIcon>
              </Tooltip>
            )}
            {(can("marks.review") || can("marks.approve")) && ["submitted", "reviewed"].includes(r.status) && (
              <Tooltip label="Return to teacher">
                <ActionIcon
                  variant="light"
                  color="orange"
                  onClick={() =>
                    modalsConfirm({
                      title: "Return for correction",
                      reasonLabel: "What needs correcting?",
                      confirmLabel: "Return",
                      onConfirm: (comment) => act(r.id, "return", { comment }, "Returned to the teacher"),
                    })
                  }
                >
                  <IconArrowBackUp size={16} />
                </ActionIcon>
              </Tooltip>
            )}
            {can("marks.approve") && r.status === "approved" && (
              <Tooltip label="Reopen (logged)">
                <ActionIcon
                  variant="light"
                  color="red"
                  onClick={() =>
                    modalsConfirm({
                      title: "Reopen approved marks?",
                      message: "Published report cards built on these marks will be reissued under a new serial when regenerated.",
                      reasonLabel: "Reason for reopening",
                      confirmLabel: "Reopen",
                      danger: true,
                      onConfirm: (reason) => act(r.id, "reopen", { reason }, "Reopened"),
                    })
                  }
                >
                  <IconLockOpen size={16} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
        )}
        emptyTitle="No mark sheets"
        emptyText="Create them from the Exams page (one click per exam)."
      />
        </Tabs.Panel>
        <Tabs.Panel value="comments">
          <SubjectComments />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
