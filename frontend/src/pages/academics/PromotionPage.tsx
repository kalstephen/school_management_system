import {
  Alert,
  Badge,
  Button,
  Card,
  Drawer,
  Group,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Stepper,
  Table,
  Tabs,
  Text,
  TextInput,
  Textarea,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconArrowBackUp, IconCheck, IconListCheck, IconPlayerPlay, IconSend } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, get, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { CrudPage } from "@/components/CrudPage";
import { ResourceTable } from "@/components/ResourceTable";
import { useClasses, useCurrentTerm, useTerms } from "@/hooks/useSchool";
import { dateTime, num } from "@/utils/format";

const MEASURES = [
  ["term3_average", "Term average (%)"], ["annual_average", "Average of all three terms (%)"],
  ["ple_aggregate", "PLE-style aggregate (lower is better)"], ["subjects_failed", "Number of subjects failed (lower is better)"],
  ["attendance", "Attendance rate (%)"],
].map(([value, label]) => ({ value, label }));

const OUTCOMES = [
  { value: "promote", label: "Promote" },
  { value: "probation", label: "Promote on probation" },
  { value: "repeat", label: "Repeat the class" },
  { value: "demote", label: "Demote to the class below" },
  { value: "complete", label: "Completed" },
];
const OUTCOME_COLOR: Record<string, string> = { promote: "green", probation: "yellow", repeat: "red", demote: "grape", complete: "blue", review: "orange" };

const STAGES = ["proposed", "submitted", "recommended", "approved", "applied"];
const STAGE_LABEL: Record<string, string> = {
  proposed: "With the class teacher",
  submitted: "With the DOS",
  recommended: "With the director",
  approved: "Approved",
  applied: "Applied",
  undone: "Undone",
};

function Outcome({ value }: { value: string }) {
  return (
    <Badge color={OUTCOME_COLOR[value] ?? "gray"} variant="light">
      {value === "review" ? "Missing marks" : OUTCOMES.find((o) => o.value === value)?.label ?? value}
    </Badge>
  );
}

function DecisionTable({ title, hint, rows, batch, canDecide, canComment, refresh }: {
  title: string; hint: string; rows: any[]; batch: any; canDecide: boolean; canComment: boolean; refresh: () => void;
}) {
  if (!rows.length) return null;
  const change = (d: any, value: string | null) =>
    value &&
    modalsConfirm({
      title: `${OUTCOMES.find((o) => o.value === value)?.label}: ${d.learner_name}`,
      message: "This overrides the marks. The reason is kept with the decision and shown to the next desk.",
      reasonLabel: "Reason",
      confirmLabel: "Save",
      onConfirm: async (reason) => {
        try {
          await post(`/promotion-batches/${batch.id}/override/`, { decision: d.id, final: value, reason });
          refresh();
        } catch (error) {
          notifications.show({ color: "red", message: errorMessage(error) });
        }
      },
    });
  return (
    <Card withBorder p={0}>
      <Group justify="space-between" p="sm">
        <div>
          <Text fw={650}>{title} <Badge variant="light" ml={4}>{rows.length}</Badge></Text>
          <Text size="xs" c="dimmed">{hint}</Text>
        </div>
      </Group>
      <Table.ScrollContainer minWidth={640}>
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Learner</Table.Th>
              <Table.Th w={80}>Average</Table.Th>
              <Table.Th w={200}>Decision</Table.Th>
              <Table.Th>Class teacher's remark</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((d) => (
              <Table.Tr key={d.id}>
                <Table.Td>
                  <Text size="sm" fw={600}>{d.learner_name}</Text>
                  <Text size="xs" c="dimmed">{d.adm_no} · {d.note || "No class yet"}</Text>
                  {d.override_reason && (
                    <Text size="xs" c="orange.8">Changed{d.overridden_by_name ? ` by ${d.overridden_by_name}` : ""}: {d.override_reason}</Text>
                  )}
                </Table.Td>
                <Table.Td>{d.measure_value === null ? "–" : num(d.measure_value)}</Table.Td>
                <Table.Td>
                  {canDecide ? (
                    <Select
                      size="xs"
                      data={OUTCOMES}
                      value={d.final === "review" ? null : d.final}
                      placeholder="Decide…"
                      error={d.final === "review" ? "Missing marks: decide" : undefined}
                      onChange={(v) => change(d, v)}
                    />
                  ) : (
                    <Outcome value={d.final} />
                  )}
                </Table.Td>
                <Table.Td>
                  {canComment ? (
                    <TextInput
                      size="xs"
                      placeholder="e.g. Often absent; good effort"
                      defaultValue={d.teacher_comment}
                      onBlur={async (e) => {
                        const comment = e.currentTarget.value;
                        if (comment === d.teacher_comment) return;
                        try {
                          await post(`/promotion-batches/${batch.id}/comment/`, { decision: d.id, comment });
                          refresh();
                        } catch (error) {
                          notifications.show({ color: "red", message: errorMessage(error) });
                        }
                      }}
                    />
                  ) : (
                    <Text size="sm">{d.teacher_comment || "–"}</Text>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Card>
  );
}

function BatchDrawer({ batchId, onClose }: { batchId: number; onClose: () => void }) {
  const { can } = useAuth();
  const client = useQueryClient();
  const { terms } = useTerms();
  const [target, setTarget] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const { data: batch, refetch: refetchBatch } = useQuery({ queryKey: ["promotion-batch", batchId], queryFn: () => get(`/promotion-batches/${batchId}/`) });
  const { data = [], refetch } = useQuery({ queryKey: ["decisions", batchId], queryFn: () => get<any[]>(`/promotion-batches/${batchId}/decisions/`) });
  const refresh = () => {
    refetch();
    refetchBatch();
    client.invalidateQueries({ queryKey: ["list", "/promotion-batches/"] });
  };
  const act = async (action: string, body?: object, message = "Done") => {
    try {
      await post(`/promotion-batches/${batchId}/${action}/`, body);
      notifications.show({ color: "green", message });
      setNote("");
      refresh();
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    }
  };
  if (!batch) return null;
  const status: string = batch.status;
  const canDecide = (["proposed", "submitted"].includes(status) && can("promotion.manage")) || (status === "recommended" && can("promotion.approve"));
  const canComment = status === "proposed" && can("promotion.review");
  const futureTerms = terms.filter((t) => t.number === 1 && t.id !== batch.term).map((t) => ({ value: String(t.id), label: t.label }));
  const passMark = Number(batch.pass_mark ?? 50);
  const lowerBetter = /lower is better/.test(batch.measure_label);
  const missing = data.filter((d) => d.measure_value === null || d.proposed === "review");
  const scored = data.filter((d) => !missing.includes(d));
  const passed = scored.filter((d) => (lowerBetter ? Number(d.measure_value) <= passMark : Number(d.measure_value) >= passMark));
  const below = scored.filter((d) => !passed.includes(d));
  const candidate = data.length > 0 && data.every((d) => d.proposed === "complete");

  return (
    <Drawer opened onClose={onClose} title={<Text fw={700}>{batch.class_name} · {batch.term_label}</Text>} position="right" size="80rem">
      <Stack>
        <Stepper active={status === "undone" ? 0 : STAGES.indexOf(status)} size="sm">
          <Stepper.Step label="Class teacher" description={batch.reviewed_by_name ? `Reviewed by ${batch.reviewed_by_name}` : batch.class_teacher_name ?? "Reviews the list"} />
          <Stepper.Step label="Director of Studies" description={batch.recommended_by_name ? `Recommended by ${batch.recommended_by_name}` : "Recommends"} />
          <Stepper.Step label="Director" description={batch.approved_by_name ? `Approved by ${batch.approved_by_name}` : "Approves"} />
          <Stepper.Step label="New year" description={batch.applied_at ? `Applied ${dateTime(batch.applied_at)}` : "Learners move"} />
        </Stepper>
        <Group gap="xs">
          <Badge size="lg" variant="light">{batch.measure_label}{candidate ? "" : ` · pass mark ${num(batch.pass_mark)}`}</Badge>
          {!candidate && <Badge size="lg" color="green" variant="light">{passed.length} passed</Badge>}
          {!candidate && <Badge size="lg" color="red" variant="light">{below.length} below the pass mark</Badge>}
          {missing.length > 0 && !candidate && <Badge size="lg" color="orange" variant="light">{missing.length} missing marks</Badge>}
        </Group>
        {[["Class teacher", batch.teacher_note], ["DOS", batch.dos_note], ["Director", batch.director_note]].map(([who, text]) =>
          text ? <Alert key={who} color="gray" p="xs"><Text size="sm"><b>{who}:</b> {text}</Text></Alert> : null,
        )}
        {candidate ? (
          <DecisionTable title="Candidate class" hint="These learners complete the school." rows={data} batch={batch} canDecide={canDecide} canComment={canComment} refresh={refresh} />
        ) : (
          <>
            <DecisionTable title="Passed" hint={`At or ${lowerBetter ? "below" : "above"} the pass mark of ${num(batch.pass_mark)}.`} rows={passed} batch={batch} canDecide={canDecide} canComment={canComment} refresh={refresh} />
            <DecisionTable title="Below the pass mark" hint="Proposed to repeat or go on probation. The DOS or director may still promote them." rows={below} batch={batch} canDecide={canDecide} canComment={canComment} refresh={refresh} />
            <DecisionTable title="Missing marks" hint="The average shown is from the marks there are. The DOS decides for each learner." rows={missing} batch={batch} canDecide={canDecide} canComment={canComment} refresh={refresh} />
          </>
        )}

        <Card withBorder>
          <Stack gap="sm">
            {status === "proposed" && (
              <Text size="sm">
                <b>Class teacher:</b> check each learner, add a remark where useful, then send the list to the Director of Studies.
                {can("promotion.manage") && " The DOS may also change decisions now, or recommend the list directly."}
              </Text>
            )}
            {status === "submitted" && <Text size="sm"><b>Director of Studies:</b> change any decision (promote, demote or pass a learner below the mark), then recommend the list to the director.</Text>}
            {status === "recommended" && <Text size="sm"><b>Director:</b> make any final changes, then approve. Learners move to their new classes when the new year is opened.</Text>}
            {["proposed", "submitted", "recommended"].includes(status) && (
              <Textarea placeholder="Note for the next desk (optional)" value={note} onChange={(e) => setNote(e.currentTarget.value)} autosize minRows={1} />
            )}
            <Group>
              {status === "proposed" && can("promotion.review") && (
                <Button leftSection={<IconSend size={16} />} onClick={() => act("submit", { note }, "Sent to the Director of Studies")}>Send to the DOS</Button>
              )}
              {["proposed", "submitted"].includes(status) && can("promotion.manage") && (
                <Button color="teal" leftSection={<IconListCheck size={16} />} onClick={() => act("recommend", { note }, "Recommended to the director")}>
                  Recommend to the director
                </Button>
              )}
              {status === "recommended" && can("promotion.approve") && (
                <Button color="green" leftSection={<IconCheck size={16} />} onClick={() => act("approve", { note }, "Approved")}>Approve</Button>
              )}
              {((status === "submitted" && can("promotion.manage")) || (status === "recommended" && can("promotion.approve"))) && (
                <Button variant="default" leftSection={<IconArrowBackUp size={16} />} onClick={() => act("send-back", { note }, "Sent back to the class teacher")}>
                  Send back to the class teacher
                </Button>
              )}
              {status === "approved" && can("promotion.approve") && (
                <>
                  <Select placeholder="First term of the new year" data={futureTerms} value={target} onChange={setTarget} w={260} />
                  <Button leftSection={<IconPlayerPlay size={16} />} disabled={!target} onClick={() => act("apply", { target_term: target }, "Learners moved to their new classes")}>
                    Move learners to the new year
                  </Button>
                </>
              )}
              {["approved", "applied"].includes(status) && can("promotion.approve") && (
                <Button variant="default" color="red" onClick={() => act("undo")}>Undo</Button>
              )}
            </Group>
          </Stack>
        </Card>
      </Stack>
    </Drawer>
  );
}

export default function PromotionPage() {
  const { can } = useAuth();
  const client = useQueryClient();
  const { options: classOptions } = useClasses();
  const { options: termOptions } = useTerms();
  const current = useCurrentTerm();
  const [term, setTerm] = useState<string | null>(null);
  const [schoolClass, setSchoolClass] = useState<string | null>(null);
  const [passMark, setPassMark] = useState<number | string>(50);
  const [policy, setPolicy] = useState<string>("keep");
  const [open, setOpen] = useState<number | null>(null);

  return (
    <>
      <PageHeader
        title="Promotion"
        description="At the end of the year each class's list shows who passed and who is below the pass mark. The class teacher reviews it, the DOS recommends it and the director approves it."
      />
      <Tabs defaultValue="lists" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="lists">Promotion lists</Tabs.Tab>
          <Tabs.Tab value="rules">Rules</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="lists">
          <Stack>
            <Card>
              <Stepper active={-1} size="xs" allowNextStepsSelect={false}>
                <Stepper.Step label="1. Class teacher" description="Prepares and reviews the list" />
                <Stepper.Step label="2. Director of Studies" description="Changes decisions, recommends" />
                <Stepper.Step label="3. Director" description="Final changes, approves" />
                <Stepper.Step label="4. New year" description="Learners move up" />
              </Stepper>
            </Card>
            {can("promotion.review") && (
              <Card>
                <Text fw={650} mb="xs">Prepare a promotion list</Text>
                <SimpleGrid cols={{ base: 1, sm: 2, md: 5 }}>
                  <Select label="Term (normally Term 3)" data={termOptions} value={term ?? (current ? String(current.id) : null)} onChange={setTerm} />
                  <Select label="Class" data={classOptions} value={schoolClass} onChange={setSchoolClass} searchable placeholder="e.g. P4" />
                  <NumberInput label="Pass mark (average %)" value={passMark} onChange={setPassMark} min={0} max={100} description="Class rule if one is set" />
                  <Select
                    label="Streams next year"
                    data={[{ value: "keep", label: "Keep streams" }, { value: "balance", label: "Rebalance by number" }, { value: "performance", label: "Rebalance by performance" }]}
                    value={policy}
                    onChange={(v) => setPolicy(v ?? "keep")}
                  />
                  <Button
                    mt={24}
                    disabled={!schoolClass}
                    onClick={async () => {
                      try {
                        const batch = await post("/promotion-batches/", { term: term ?? current?.id, school_class: schoolClass, stream_policy: policy, pass_mark: passMark });
                        client.invalidateQueries({ queryKey: ["list", "/promotion-batches/"] });
                        setOpen(batch.id);
                      } catch (error) {
                        notifications.show({ color: "red", message: errorMessage(error) });
                      }
                    }}
                  >
                    Prepare list
                  </Button>
                </SimpleGrid>
              </Card>
            )}
            <ResourceTable
              endpoint="/promotion-batches/"
              searchable={false}
              onRowClick={(row: any) => setOpen(row.id)}
              emptyText="No promotion lists yet. A list is prepared for each class at the end of Term 3."
              columns={[
                { key: "class_name", label: "Class" },
                { key: "term_label", label: "Term" },
                { key: "pass_mark", label: "Pass mark", render: (r: any) => num(r.pass_mark) },
                {
                  key: "counts",
                  label: "Decisions",
                  render: (r: any) => (
                    <Group gap={4}>
                      {Object.entries(r.counts).map(([k, v]) => (
                        <Badge key={k} size="sm" variant="light" color={OUTCOME_COLOR[k]}>{String(v)} {k === "review" ? "missing marks" : k}</Badge>
                      ))}
                    </Group>
                  ),
                },
                { key: "status", label: "Where it is", render: (r: any) => <StatusBadge value={r.status} label={STAGE_LABEL[r.status] ?? r.status} /> },
              ]}
            />
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="rules">
          <Text size="sm" c="dimmed" mb="sm">
            Optional. Without a rule, the term average is used with the pass mark chosen when the list is prepared.
          </Text>
          <CrudPage
            hideHeader
            title="Promotion rules"
            singular="rule"
            formHelp="Optional. How a class (or a whole section) decides who passes at the end of the year, e.g. term average of 50%. Without a rule the average and the pass mark chosen on the list are used."
            endpoint="/promotion-rules/"
            writePerm="promotion.manage"
            toForm={(r: any) => ({ ...r, section: r.section && String(r.section), school_class: r.school_class && String(r.school_class) })}
            columns={[
              { key: "applies", label: "Applies to", render: (r: any) => classOptions.find((c) => c.value === String(r.school_class))?.label ?? `Section ${r.section}` },
              { key: "measure_label", label: "Measure" },
              { key: "pass_mark", label: "Pass mark", render: (r: any) => num(r.pass_mark) },
              { key: "probation_mark", label: "Probation from", render: (r: any) => num(r.probation_mark) },
            ]}
            fields={[
              { name: "section", label: "Section", type: "select", optionsFrom: { endpoint: "/sections/", label: "name" }, description: "A class rule overrides the section rule" },
              { name: "school_class", label: "Class", type: "select", options: classOptions },
              { name: "measure", label: "Measure", type: "select", options: MEASURES, required: true },
              { name: "pass_mark", label: "Pass mark", type: "number", required: true },
              { name: "probation_mark", label: "Probation band starts at", type: "number" },
              { name: "fail_below", label: "A subject fails below (%)", type: "number", hidden: (v) => v.measure !== "subjects_failed" },
              { name: "min_attendance", label: "Minimum attendance (%) — optional", type: "number" },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
      {open !== null && <BatchDrawer batchId={open} onClose={() => setOpen(null)} />}
    </>
  );
}
