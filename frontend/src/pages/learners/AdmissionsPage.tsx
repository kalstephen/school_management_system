import { ActionIcon, Alert, Card, SimpleGrid, Tabs, Text, ThemeIcon, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconCalendarEvent, IconFileText, IconInfoCircle, IconLogout2, IconSchool, IconUserCheck } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { errorMessage, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { CrudPage } from "@/components/CrudPage";
import { SEX_OPTIONS, useClasses } from "@/hooks/useSchool";
import { date, dateTime } from "@/utils/format";

const APPLICATION_STATUS = [
  ["received", "Received"], ["interview", "Interview scheduled"], ["offered", "Place offered"],
  ["admitted", "Admitted"], ["rejected", "Not admitted"], ["withdrawn", "Withdrawn"],
].map(([value, label]) => ({ value, label }));

const STEPS = [
  { icon: IconFileText, title: "1. Record the application", text: "A parent applies on paper, walks in or applies online. Press “New application” and type the child's details, class wanted and parent's phone." },
  { icon: IconCalendarEvent, title: "2. Interview", text: "Set the status to “Interview scheduled” with a date. After the interview, add the score and notes." },
  { icon: IconSchool, title: "3. Offer a place", text: "Set the status to “Place offered” (or “Not admitted”). Edit the application with the pencil." },
  { icon: IconUserCheck, title: "4. Admit", text: "Press the green tick. The child becomes a learner in the class, gets the next admission number and the parent is linked." },
];

function HowItWorks({ canManage }: { canManage: boolean }) {
  return (
    <Card mb="md">
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        {STEPS.map((s) => (
          <div key={s.title}>
            <ThemeIcon variant="light" size="lg" mb={6}><s.icon size={18} /></ThemeIcon>
            <Text fw={650} size="sm">{s.title}</Text>
            <Text size="xs" c="dimmed">{s.text}</Text>
          </div>
        ))}
      </SimpleGrid>
      {!canManage && (
        <Alert icon={<IconInfoCircle size={16} />} color="gray" mt="md" p="xs">
          You can view admissions. Recording and admitting applicants is done by the head teacher, director, DOS or school administrator.
        </Alert>
      )}
      <Text size="xs" c="dimmed" mt="sm">
        Front desk: “Enquiries” keeps phone and walk-in questions with a follow-up date; the “Visitors' register” signs visitors in and out.
        Learners already at the school are enrolled under Learners (one at a time or a whole class from Excel).
      </Text>
    </Card>
  );
}

export default function AdmissionsPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const client = useQueryClient();
  const { options: classOptions } = useClasses();

  const admit = (row: any) =>
    modalsConfirm({
      title: `Admit ${row.first_name} ${row.last_name}?`,
      message: `This creates the learner in ${row.class_name}, gives them the next admission number and links the guardian.`,
      confirmLabel: "Admit",
      onConfirm: async () => {
        try {
          const result = await post(`/applications/${row.id}/admit/`);
          notifications.show({ color: "green", title: "Admitted", message: `Admission number ${result.adm_no}` });
          client.invalidateQueries({ queryKey: ["list", "/applications/"] });
          navigate(`/learners/${result.learner_id}`);
        } catch (error) {
          notifications.show({ color: "red", title: "Not admitted", message: errorMessage(error) });
        }
      },
    });

  return (
    <>
      <PageHeader title="Admissions & front desk" description="New children applying to join the school: application, interview, offer and admission. Also enquiries and the visitors' register." />
      <HowItWorks canManage={can("admissions.manage")} />
      <Tabs defaultValue="applications" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="applications">Applications</Tabs.Tab>
          <Tabs.Tab value="enquiries">Enquiries</Tabs.Tab>
          <Tabs.Tab value="visitors">Visitors' register</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="applications">
          <CrudPage
            hideHeader
            title="Applications"
            singular="application"
            formHelp="A child applying to join. Move it through interview and offer, then press the green tick to admit them as a learner."
            endpoint="/applications/"
            writePerm="admissions.manage"
            defaults={{ status: "received", channel: "paper", residence: "day" }}
            filters={[
              { name: "status", label: "Status", options: APPLICATION_STATUS },
              { name: "class_applied", label: "Class", options: classOptions },
            ]}
            extraActions={(row: any) =>
              can("admissions.manage") && !row.learner && !["rejected", "withdrawn"].includes(row.status) ? (
                <Tooltip label="Admit">
                  <ActionIcon variant="light" color="green" onClick={() => admit(row)}>
                    <IconUserCheck size={16} />
                  </ActionIcon>
                </Tooltip>
              ) : null
            }
            columns={[
              { key: "name", label: "Applicant", render: (r: any) => `${r.first_name} ${r.last_name}` },
              { key: "class_name", label: "Class" },
              { key: "guardian_name", label: "Guardian", render: (r: any) => `${r.guardian_name} · ${r.guardian_phone}` },
              { key: "interview_date", label: "Interview", render: (r: any) => date(r.interview_date) },
              { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} /> },
            ]}
            fields={[
              { name: "first_name", label: "First name", required: true },
              { name: "last_name", label: "Surname", required: true },
              { name: "other_names", label: "Other names" },
              { name: "sex", label: "Sex", type: "select", options: SEX_OPTIONS, required: true },
              { name: "date_of_birth", label: "Date of birth", type: "date" },
              { name: "lin", label: "LIN" },
              { name: "class_applied", label: "Class applied for", type: "select", options: classOptions, required: true },
              { name: "residence", label: "Day or boarding", type: "select", options: [{ value: "day", label: "Day" }, { value: "boarding", label: "Boarding" }] },
              { name: "previous_school", label: "Previous school" },
              { name: "previous_results", label: "Previous results", placeholder: "e.g. PLE aggregate 8" },
              { name: "guardian_name", label: "Guardian name", required: true },
              { name: "guardian_phone", label: "Guardian phone", required: true },
              { name: "guardian_email", label: "Guardian email", type: "email" },
              { name: "guardian_relationship", label: "Relationship" },
              { name: "channel", label: "Received by", type: "select", options: [{ value: "paper", label: "Paper form" }, { value: "walk_in", label: "Walk-in" }, { value: "online", label: "Online" }] },
              { name: "status", label: "Status", type: "select", options: APPLICATION_STATUS },
              { name: "interview_date", label: "Interview date", type: "date" },
              { name: "interview_score", label: "Interview score", type: "number" },
              { name: "interview_notes", label: "Interview notes", type: "textarea" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="enquiries">
          <CrudPage
            hideHeader
            title="Enquiries"
            singular="enquiry"
            formHelp="A question from a parent or visitor by phone or at the gate, with a date to follow it up."
            endpoint="/enquiries/"
            writePerm="admissions.manage"
            filters={[{ name: "is_closed", label: "Status", options: [{ value: "false", label: "Open" }, { value: "true", label: "Closed" }] }]}
            columns={[
              { key: "created_at", label: "Received", render: (r: any) => date(r.created_at) },
              { key: "name", label: "From", render: (r: any) => `${r.name}${r.phone ? ` · ${r.phone}` : ""}` },
              { key: "subject", label: "About" },
              { key: "follow_up_on", label: "Follow up", render: (r: any) => date(r.follow_up_on) },
              { key: "is_closed", label: "Status", render: (r: any) => <StatusBadge value={r.is_closed ? "closed" : "open"} /> },
            ]}
            fields={[
              { name: "name", label: "Name", required: true },
              { name: "phone", label: "Phone" },
              { name: "email", label: "Email", type: "email" },
              { name: "subject", label: "Subject", required: true },
              { name: "follow_up_on", label: "Follow up on", type: "date" },
              { name: "is_closed", label: "Closed", type: "checkbox" },
              { name: "details", label: "Details", type: "textarea" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="visitors">
          <CrudPage
            hideHeader
            title="Visitors"
            singular="visitor"
            formHelp="Sign a visitor in at the gate. Sign them out when they leave."
            endpoint="/visitors/"
            writePerm="admissions.manage"
            defaults={{ time_in: new Date().toISOString() }}
            extraActions={(row: any) =>
              !row.time_out && can("admissions.manage") ? (
                <Tooltip label="Sign out">
                  <ActionIcon
                    variant="light"
                    onClick={async () => {
                      await post(`/visitors/${row.id}/sign-out/`);
                      client.invalidateQueries({ queryKey: ["list", "/visitors/"] });
                    }}
                  >
                    <IconLogout2 size={16} />
                  </ActionIcon>
                </Tooltip>
              ) : null
            }
            columns={[
              { key: "name", label: "Visitor", render: (r: any) => `${r.name}${r.phone ? ` · ${r.phone}` : ""}` },
              { key: "purpose", label: "Purpose" },
              { key: "person_to_see", label: "To see" },
              { key: "time_in", label: "In", render: (r: any) => dateTime(r.time_in) },
              { key: "time_out", label: "Out", render: (r: any) => (r.time_out ? dateTime(r.time_out) : <StatusBadge value="open" label="On site" />) },
            ]}
            fields={[
              { name: "name", label: "Name", required: true },
              { name: "phone", label: "Phone" },
              { name: "id_number", label: "ID number" },
              { name: "purpose", label: "Purpose", required: true },
              { name: "person_to_see", label: "Person to see" },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
