import { ActionIcon, Tabs, Tooltip } from "@mantine/core";
import { IconCircleCheck } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";

import { post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import type { Field } from "@/components/ResourceForm";
import { date, today } from "@/utils/format";

const learnerField: Field = {
  name: "learner",
  label: "Learner",
  type: "select",
  required: true,
  optionsFrom: { endpoint: "/learners/", label: (l: any) => `${l.full_name} (${l.adm_no})`, query: { status: "active" } },
};

export default function DisciplinePage() {
  const { can } = useAuth();
  const client = useQueryClient();
  return (
    <>
      <PageHeader title="Discipline & welfare" description="Cases and sanctions, counselling referrals, and achievements worth celebrating." />
      <Tabs defaultValue="cases" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="cases">Cases</Tabs.Tab>
          <Tabs.Tab value="counselling">Counselling</Tabs.Tab>
          <Tabs.Tab value="achievements">Achievements</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="cases">
          <CrudPage
            hideHeader
            title="Discipline cases"
            singular="case"
            formHelp="Record an incident involving a learner and the action taken. Kept on the learner's profile."
            endpoint="/discipline-cases/"
            writePerm="discipline.manage"
            defaults={{ date: today(), severity: "minor", status: "open" }}
            filters={[
              { name: "status", label: "Status", options: [{ value: "open", label: "Open" }, { value: "closed", label: "Closed" }] },
              { name: "severity", label: "Severity", options: ["minor", "major", "critical"].map((s) => ({ value: s, label: s })) },
            ]}
            extraActions={(row: any) =>
              row.status === "open" && can("discipline.manage") ? (
                <Tooltip label="Close case">
                  <ActionIcon
                    variant="light"
                    color="green"
                    onClick={async () => {
                      await post(`/discipline-cases/${row.id}/close/`);
                      client.invalidateQueries({ queryKey: ["list", "/discipline-cases/"] });
                    }}
                  >
                    <IconCircleCheck size={16} />
                  </ActionIcon>
                </Tooltip>
              ) : null
            }
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date) },
              { key: "learner_name", label: "Learner" },
              { key: "category", label: "Category" },
              { key: "severity", label: "Severity", render: (r: any) => <StatusBadge value={r.severity === "minor" ? "pending" : "rejected"} label={r.severity} /> },
              { key: "action_taken", label: "Action taken" },
              { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} /> },
            ]}
            fields={[
              learnerField,
              { name: "date", label: "Date", type: "date", required: true },
              { name: "category", label: "Category", required: true, placeholder: "e.g. Lateness, Fighting" },
              { name: "severity", label: "Severity", type: "select", options: [{ value: "minor", label: "Minor" }, { value: "major", label: "Major" }, { value: "critical", label: "Critical" }] },
              { name: "reported_by", label: "Reported by" },
              { name: "status", label: "Status", type: "select", options: [{ value: "open", label: "Open" }, { value: "closed", label: "Closed" }] },
              { name: "description", label: "What happened", type: "textarea", required: true },
              { name: "action_taken", label: "Action taken / sanction", type: "textarea" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="counselling">
          <CrudPage
            hideHeader
            title="Counselling referrals"
            singular="referral"
            formHelp="Refer a learner for counselling or welfare support, and follow it up."
            endpoint="/counselling/"
            writePerm="discipline.manage"
            defaults={{ date: today(), status: "open" }}
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date) },
              { key: "learner_name", label: "Learner" },
              { key: "referred_to", label: "Referred to" },
              { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} /> },
            ]}
            fields={[
              learnerField,
              { name: "date", label: "Date", type: "date", required: true },
              { name: "referred_to", label: "Referred to" },
              { name: "status", label: "Status", type: "select", options: [{ value: "open", label: "Open" }, { value: "in_progress", label: "In progress" }, { value: "closed", label: "Closed" }] },
              { name: "reason", label: "Reason", type: "textarea", required: true },
              { name: "notes", label: "Notes (confidential)", type: "textarea" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="achievements">
          <CrudPage
            hideHeader
            title="Achievements"
            singular="achievement"
            formHelp="Record something a learner did well, e.g. a prize or leadership role. Shown on their profile."
            endpoint="/achievements/"
            writePerm="discipline.manage"
            defaults={{ date: today() }}
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date) },
              { key: "learner_name", label: "Learner" },
              { key: "title", label: "Achievement" },
              { key: "category", label: "Category" },
            ]}
            fields={[
              learnerField,
              { name: "date", label: "Date", type: "date", required: true },
              { name: "title", label: "Achievement", required: true },
              { name: "category", label: "Category", placeholder: "Sports, Music, Academic…" },
              { name: "description", label: "Description", type: "textarea" },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
