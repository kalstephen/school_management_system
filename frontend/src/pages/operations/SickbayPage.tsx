import { Alert, Anchor, List, Tabs } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import { Link } from "react-router";

import { get } from "@/api/client";
import { PageHeader, StatusBadge } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import type { Field } from "@/components/ResourceForm";
import { date, dateTime, titleCase, today } from "@/utils/format";

const learnerField: Field = {
  name: "learner",
  label: "Learner",
  type: "select",
  required: true,
  optionsFrom: { endpoint: "/learners/", label: (l: any) => `${l.full_name} (${l.adm_no})`, query: { status: "active" } },
};
const OUTCOMES = [
  ["class", "Returned to class"], ["rested", "Rested in sickbay"], ["home", "Sent home"], ["referred", "Referred to hospital"],
].map(([value, label]) => ({ value, label }));

export default function SickbayPage() {
  const { data: frequent = [] } = useQuery({ queryKey: ["sickbay-frequent"], queryFn: () => get<any[]>("/sickbay/visits/frequent/") });
  return (
    <>
      <PageHeader title="Sickbay" description="Visits, treatment and referrals, and immunisation records. Every view of a learner's health record is logged." />
      {frequent.length > 0 && (
        <Alert color="orange" title="Frequent visitors (3+ visits in 30 days)" mb="md">
          <List size="sm">
            {frequent.map((f) => (
              <List.Item key={f.learner}>
                <Anchor component={Link} to={`/learners/${f.learner}`}>
                  {f.name}
                </Anchor>{" "}
                — {f.visits} visits
              </List.Item>
            ))}
          </List>
        </Alert>
      )}
      <Tabs defaultValue="visits" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="visits">Visits</Tabs.Tab>
          <Tabs.Tab value="immunisations">Immunisations</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="visits">
          <CrudPage
            hideHeader
            title="Sickbay visits"
            singular="visit"
            formHelp="A learner's visit to the sickbay: complaint, treatment and whether they went home. Seen only by the nurse and head teacher."
            endpoint="/sickbay/visits/"
            writePerm="health.manage"
            defaults={{ visited_at: dayjs().format("YYYY-MM-DD HH:mm:ss"), outcome: "class" }}
            toForm={(r: any) => ({ ...r, learner: String(r.learner) })}
            filters={[{ name: "outcome", label: "Outcome", options: OUTCOMES }]}
            columns={[
              { key: "visited_at", label: "When", render: (r: any) => dateTime(r.visited_at) },
              { key: "learner_name", label: "Learner" },
              { key: "complaint", label: "Complaint" },
              { key: "treatment", label: "Treatment" },
              { key: "outcome", label: "Outcome", render: (r: any) => <StatusBadge value={r.outcome === "referred" || r.outcome === "home" ? "warning" : "ok"} label={OUTCOMES.find((o) => o.value === r.outcome)?.label} /> },
              { key: "guardian_informed", label: "Guardian told", render: (r: any) => (r.guardian_informed ? "Yes" : "No") },
            ]}
            fields={[
              learnerField,
              { name: "visited_at", label: "When", type: "datetime", required: true },
              { name: "complaint", label: "Complaint", required: true },
              { name: "temperature", label: "Temperature (°C)", type: "number" },
              { name: "diagnosis", label: "Diagnosis" },
              { name: "outcome", label: "Outcome", type: "select", options: OUTCOMES },
              { name: "referred_to", label: "Referred to", hidden: (v) => v.outcome !== "referred" },
              { name: "guardian_informed", label: "Guardian informed", type: "checkbox" },
              { name: "treatment", label: "Treatment given", type: "textarea" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="immunisations">
          <CrudPage
            hideHeader
            title="Immunisations"
            singular="immunisation"
            formHelp="A vaccination a learner has received, with the date."
            endpoint="/sickbay/immunisations/"
            writePerm="health.manage"
            defaults={{ date: today() }}
            toForm={(r: any) => ({ ...r, learner: String(r.learner) })}
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date) },
              { key: "learner_name", label: "Learner" },
              { key: "vaccine", label: "Vaccine", render: (r: any) => titleCase(r.vaccine) },
              { key: "dose", label: "Dose" },
            ]}
            fields={[
              learnerField,
              { name: "vaccine", label: "Vaccine", required: true, placeholder: "e.g. HPV, Tetanus" },
              { name: "dose", label: "Dose" },
              { name: "date", label: "Date", type: "date", required: true },
              { name: "notes", label: "Notes" },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
