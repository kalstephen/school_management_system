import { Anchor, Avatar, Badge, Button, Group, Text, Tooltip } from "@mantine/core";
import { IconAlertTriangle, IconFileSpreadsheet, IconUserPlus } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import type { LearnerRow } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { StatusBadge } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import type { Field } from "@/components/ResourceForm";
import { SEX_OPTIONS, useClasses } from "@/hooks/useSchool";

import { EnrolLearner } from "./EnrolLearner";
import { ExcelImport } from "./ExcelImport";

const STATUS = ["active", "suspended", "transferred", "left", "completed"].map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }));

function EnrolButtons() {
  const [importing, setImporting] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  return (
    <>
      <Button variant="default" leftSection={<IconFileSpreadsheet size={16} />} onClick={() => setImporting(true)}>
        Import a class from Excel
      </Button>
      <Button leftSection={<IconUserPlus size={16} />} onClick={() => setEnrolling(true)}>
        Enrol a learner
      </Button>
      <ExcelImport opened={importing} onClose={() => setImporting(false)} />
      {enrolling && <EnrolLearner onClose={() => setEnrolling(false)} />}
    </>
  );
}

export default function LearnersPage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const { options: classOptions } = useClasses();

  const fields: Field[] = [
    { name: "first_name", label: "First name", required: true, placeholder: "e.g. Aisha" },
    { name: "last_name", label: "Surname", required: true, placeholder: "e.g. Namubiru" },
    { name: "other_names", label: "Other names" },
    { name: "sex", label: "Sex", type: "select", options: SEX_OPTIONS, required: true, placeholder: "Female or Male" },
    { name: "date_of_birth", label: "Date of birth", type: "date", placeholder: "Pick a date" },
    { name: "lin", label: "LIN", description: "Learner Identification Number", placeholder: "Optional" },
    { name: "adm_no", label: "Admission number", description: "Leave empty to generate the next number", placeholder: "Automatic" },
    { name: "residence", label: "Day or boarding", type: "select", options: [{ value: "day", label: "Day" }, { value: "boarding", label: "Boarding" }] },
    { name: "house", label: "House", type: "select", optionsFrom: { endpoint: "/houses/", label: "name" } },
    { name: "religion", label: "Religion" },
    { name: "district", label: "District" },
    { name: "address", label: "Address" },
    { name: "previous_school", label: "Previous school" },
    { name: "has_medical_alert", label: "Medical alert (details go to the nurse)", type: "checkbox" },
    ...(can("health.view")
      ? ([
          { name: "allergies", label: "Allergies", type: "textarea" },
          { name: "medical_notes", label: "Medical notes", type: "textarea" },
        ] as Field[])
      : []),
    { name: "special_needs", label: "Special needs" },
    { name: "photo", label: "Photo", type: "file" },
    { name: "notes", label: "Notes", type: "textarea" },
  ];

  return (
    <CrudPage<LearnerRow>
      title="Learners"
      singular="learner"
      formHelp="Edit a learner's details. To add new learners use Enrol a learner or Import a class from Excel."
      description="Every learner, past and present. Click a learner for the full profile."
      endpoint="/learners/"
      writePerm="learners.manage"
      exportable
      canDelete={false}
      canCreate={false}
      fields={fields}
      onRowClick={(row) => navigate(`/learners/${row.id}`)}
      headerActions={can("learners.enrol") ? <EnrolButtons /> : null}
      filters={[
        { name: "school_class", label: "Class", options: classOptions },
        { name: "status", label: "Status", options: STATUS },
        { name: "sex", label: "Sex", options: SEX_OPTIONS },
        { name: "residence", label: "Day/boarding", options: [{ value: "day", label: "Day" }, { value: "boarding", label: "Boarding" }] },
      ]}
      columns={[
        {
          key: "full_name",
          label: "Learner",
          render: (row) => (
            <Group gap="sm" wrap="nowrap">
              <Avatar src={row.photo} radius="xl" size={34} color="brand">
                {row.first_name[0]}
                {row.last_name[0]}
              </Avatar>
              <div>
                <Anchor size="sm" fw={600} onClick={() => navigate(`/learners/${row.id}`)}>
                  {row.full_name}
                </Anchor>
                <Text size="xs" c="dimmed">
                  {row.adm_no}
                  {row.lin ? ` · ${row.lin}` : ""}
                </Text>
              </div>
              {row.medical_flag && (
                <Tooltip label="Medical alert — see the nurse">
                  <IconAlertTriangle size={16} color="var(--mantine-color-red-6)" />
                </Tooltip>
              )}
            </Group>
          ),
        },
        { key: "class", label: "Class", render: (row) => (row.current_class ? [row.current_class.class_name, row.current_class.stream_name].filter(Boolean).join(" ") : "–") },
        { key: "sex", label: "Sex" },
        { key: "residence", label: "Day/boarding", render: (row) => <Badge variant="outline" color={row.residence === "boarding" ? "grape" : "gray"}>{row.residence}</Badge> },
        { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
      ]}
    />
  );
}
