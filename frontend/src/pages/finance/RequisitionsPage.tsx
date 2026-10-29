import { Alert, Badge, Button, Divider, Drawer, FileInput, Group, NumberInput, Select, SimpleGrid, Stack, Tabs, Text, Textarea, Timeline } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconCash, IconCheck, IconCircleDashed, IconClock, IconReceipt, IconX } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, errorMessage, get, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { CrudPage } from "@/components/CrudPage";
import { useOptions } from "@/hooks/useOptions";
import { date, dateTime, ugx } from "@/utils/format";

const METHODS = [
  { value: "cash", label: "Cash" },
  { value: "mobile_money", label: "Mobile money" },
  { value: "bank", label: "Bank transfer" },
  { value: "cheque", label: "Cheque" },
];
const STATUS_COLOR: Record<string, string> = { pending: "blue", approved: "violet", disbursed: "orange", accounted: "green", rejected: "red", fulfilled: "green" };

function Journey({ req }: { req: any }) {
  const finished = req.status === "accounted";
  const items = [
    ...req.steps.map((s: any) => ({ ...s, title: s.label })),
    {
      step: "account",
      title: "Requester accounts for the money",
      state: finished ? "done" : req.status === "disbursed" ? "current" : "todo",
      by: req.accounted_submitted_at ? req.requested_by : null,
      at: req.accounted_submitted_at,
      comment: req.spent_amount != null ? `Spent ${ugx(req.spent_amount)}, returned ${ugx(req.returned_amount ?? 0)}` : "",
    },
  ];
  const active = items.findIndex((i) => i.state === "current" || i.state === "rejected");
  return (
    <Timeline active={active === -1 ? items.length : active} bulletSize={22} lineWidth={2}>
      {items.map((i) => (
        <Timeline.Item
          key={i.step}
          title={i.title}
          color={i.state === "rejected" ? "red" : i.state === "done" ? "green" : "blue"}
          bullet={i.state === "done" ? <IconCheck size={12} /> : i.state === "rejected" ? <IconX size={12} /> : i.state === "current" ? <IconClock size={12} /> : <IconCircleDashed size={12} />}
        >
          {i.by && <Text size="xs">{i.state === "rejected" ? "Not approved" : "Done"} by {i.by}{i.at ? ` · ${dateTime(i.at)}` : ""}</Text>}
          {i.state === "current" && <Text size="xs" c="blue">Waiting here now</Text>}
          {i.comment && <Text size="xs" c="dimmed">“{i.comment}”</Text>}
        </Timeline.Item>
      ))}
    </Timeline>
  );
}

function RequisitionDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const { can } = useAuth();
  const client = useQueryClient();
  const { data: req, refetch } = useQuery({ queryKey: ["requisition", id], queryFn: () => get(`/finance/requisitions/${id}/`) });
  const { rows: categories } = useOptions({ endpoint: "/finance/categories/", label: "name" }, can("finance.manage"));
  const [amount, setAmount] = useState<number | string>("");
  const [method, setMethod] = useState<string | null>("cash");
  const [category, setCategory] = useState<string | null>(null);
  const [sub, setSub] = useState<string | null>(null);
  const [spent, setSpent] = useState<number | string>("");
  const [returned, setReturned] = useState<number | string>(0);
  const [note, setNote] = useState("");
  const [receipt, setReceipt] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  const done = (message: string) => {
    notifications.show({ color: "green", message });
    refetch();
    client.invalidateQueries({ queryKey: ["list", "/finance/requisitions/"] });
    client.invalidateQueries({ queryKey: ["requisitions-waiting"] });
  };
  const run = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await fn();
      done(message);
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  };
  if (!req) return null;
  const subs = (categories.find((c: any) => String(c.id) === category)?.sub_categories ?? []).map((s: any) => ({ value: String(s.id), label: s.name }));

  return (
    <Drawer opened onClose={onClose} position="right" size="lg" title={<Text fw={700}>{req.title}</Text>}>
      <Stack>
        <Group gap="xs">
          <Badge color={STATUS_COLOR[req.status]} variant="light" size="lg">{req.status_label}</Badge>
          <Badge variant="outline" size="lg">{ugx(req.estimated_amount)}</Badge>
        </Group>
        <SimpleGrid cols={2} spacing="xs">
          <Text size="sm"><b>Requested by:</b> {req.requested_by}</Text>
          <Text size="sm"><b>On:</b> {date(req.created_at)}</Text>
          <Text size="sm"><b>Department:</b> {req.department_name ?? "–"}</Text>
          <Text size="sm"><b>Needed by:</b> {req.needed_by ? date(req.needed_by) : "–"}</Text>
        </SimpleGrid>
        {req.details && <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{req.details}</Text>}
        {req.disbursed_amount && (
          <Alert color="orange" p="xs">Issued {ugx(req.disbursed_amount)} by {METHODS.find((m) => m.value === req.disbursement_method)?.label ?? req.disbursement_method} on {date(req.disbursed_at)}.</Alert>
        )}
        <Divider label="Journey" labelPosition="left" />
        <Journey req={req} />

        {req.can_act && req.status === "pending" && (
          <Group>
            <Button color="green" leftSection={<IconCheck size={16} />} loading={busy} onClick={() => run(() => post(`/finance/requisitions/${id}/approve/`, { comment: note }), "Approved and passed on")}>
              Approve and pass on
            </Button>
            <Button
              variant="default"
              color="red"
              leftSection={<IconX size={16} />}
              onClick={() =>
                modalsConfirm({
                  title: "Do not approve",
                  reasonLabel: "Why (the requester is told)",
                  confirmLabel: "Do not approve",
                  danger: true,
                  onConfirm: (c) => run(() => post(`/finance/requisitions/${id}/reject/`, { comment: c }), "Not approved; the requester is told"),
                })
              }
            >
              Do not approve
            </Button>
            <Textarea placeholder="Comment for the next person (optional)" value={note} onChange={(e) => setNote(e.currentTarget.value)} autosize minRows={1} w="100%" />
          </Group>
        )}

        {req.can_act && req.status === "approved" && (
          <Stack gap="xs">
            <Divider label="Issue the money" labelPosition="left" />
            <SimpleGrid cols={2}>
              <NumberInput label="Amount issued" thousandSeparator="," prefix="UGX " value={amount === "" ? Number(req.estimated_amount) : amount} onChange={setAmount} />
              <Select label="How" data={METHODS} value={method} onChange={setMethod} allowDeselect={false} />
              <Select label="Expense category" data={categories.map((c: any) => ({ value: String(c.id), label: c.name }))} value={category} onChange={(v) => { setCategory(v); setSub(null); }} required />
              <Select label="Sub-category" data={subs} value={sub} onChange={setSub} clearable disabled={!subs.length} placeholder={subs.length ? "Optional" : "None"} />
            </SimpleGrid>
            <Button
              leftSection={<IconCash size={16} />}
              disabled={!category}
              loading={busy}
              onClick={() => run(() => post(`/finance/requisitions/${id}/disburse/`, { amount: amount === "" ? req.estimated_amount : amount, method, category, sub_category: sub }), "Money issued and recorded as an expense; the requester is asked to account")}
            >
              Issue money
            </Button>
          </Stack>
        )}

        {req.status === "disbursed" && !req.accounted_submitted_at && (req.is_mine || can("finance.manage")) && (
          <Stack gap="xs">
            <Divider label="Account for the money" labelPosition="left" />
            <Text size="sm" c="dimmed">Say what you spent and give back any change. Attach the receipts (a photo is fine).</Text>
            <SimpleGrid cols={2}>
              <NumberInput label="Amount spent" thousandSeparator="," prefix="UGX " value={spent} onChange={setSpent} required />
              <NumberInput label="Change returned" thousandSeparator="," prefix="UGX " value={returned} onChange={setReturned} />
            </SimpleGrid>
            <FileInput label="Receipt(s)" placeholder="Photo or PDF" value={receipt} onChange={setReceipt} accept="image/*,.pdf" clearable />
            <Textarea label="Notes" placeholder="Explain any difference" value={note} onChange={(e) => setNote(e.currentTarget.value)} autosize minRows={1} />
            <Button
              leftSection={<IconReceipt size={16} />}
              disabled={spent === ""}
              loading={busy}
              onClick={() =>
                run(() => {
                  const form = new FormData();
                  form.append("spent_amount", String(spent));
                  form.append("returned_amount", String(returned || 0));
                  form.append("accountability_note", note);
                  if (receipt) form.append("receipt", receipt);
                  return api(`/finance/requisitions/${id}/account/`, { method: "POST", body: form });
                }, "Accounts sent to finance")
              }
            >
              Send my accounts
            </Button>
          </Stack>
        )}

        {req.status === "disbursed" && req.accounted_submitted_at && (
          <Alert color="blue" p="sm" title="Accounts submitted">
            <Text size="sm">Spent {ugx(req.spent_amount)}, change returned {ugx(req.returned_amount ?? 0)}.{req.accountability_note ? ` “${req.accountability_note}”` : ""}</Text>
            {req.receipt && <Text size="sm"><a href={req.receipt} target="_blank" rel="noreferrer">Open receipt</a></Text>}
            {can("finance.manage") && (
              <Button mt="xs" size="xs" color="green" loading={busy} onClick={() => run(() => post(`/finance/requisitions/${id}/confirm/`), "Accounts confirmed; the expense now shows what was spent")}>
                Confirm the accounts
              </Button>
            )}
          </Alert>
        )}
      </Stack>
    </Drawer>
  );
}

export default function RequisitionsPage() {
  const { can } = useAuth();
  const [open, setOpen] = useState<number | null>(null);
  const [tab, setTab] = useState<string | null>(null);
  const { data: waiting } = useQuery({ queryKey: ["requisitions-waiting"], queryFn: () => get("/finance/requisitions/", { waiting: 1, page_size: 1 }) });
  const columns = [
    { key: "created_at", label: "Requested", render: (r: any) => date(r.created_at) },
    { key: "title", label: "Request", render: (r: any) => <><Text size="sm" fw={600}>{r.title}</Text><Text size="xs" c="dimmed">{r.requested_by}{r.department_name ? ` · ${r.department_name}` : ""}</Text></> },
    { key: "estimated_amount", label: "Amount", render: (r: any) => ugx(r.disbursed_amount ?? r.estimated_amount) },
    { key: "status", label: "Where it is", render: (r: any) => <><Badge color={STATUS_COLOR[r.status]} variant="light">{r.status_label}</Badge>{r.waiting_for && <Text size="xs" c="dimmed">Waiting for: {r.waiting_for}</Text>}</> },
  ];
  const list = (query: Record<string, any>, empty: string, allowCreate = false) => (
    <CrudPage
      hideHeader
      title="Requisitions"
      singular="requisition"
      formHelp="Ask for money or items, e.g. chalk or lab chemicals. It goes up for approval (your head of department, the DOS, the head teacher, and the director for large amounts), then finance issues the money. Afterwards you account for what you spent."
      endpoint="/finance/requisitions/"
      query={query}
      writePerm="finance.request"
      canCreate={allowCreate}
      canEdit={false}
      canDelete={false}
      onRowClick={(r: any) => setOpen(r.id)}
      emptyText={empty}
      filters={[{ name: "status", label: "Status", options: Object.keys(STATUS_COLOR).filter((s) => s !== "fulfilled").map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) })) }]}
      columns={columns}
      fields={[
        { name: "title", label: "What is needed", required: true, span: 12, placeholder: "e.g. Chemicals for P7 science practicals" },
        { name: "department", label: "Department", type: "select", optionsFrom: { endpoint: "/departments/", label: "name" }, description: "Its head of department approves first." },
        { name: "estimated_amount", label: "How much (estimate)", type: "money", required: true },
        { name: "needed_by", label: "Needed by", type: "date" },
        { name: "details", label: "Details (items, quantities, why)", type: "textarea", span: 12 },
      ]}
    />
  );

  return (
    <>
      <PageHeader
        title="Requisitions"
        description="Ask for money or items. Requests go up the ranks for approval, finance issues the money at the end, and the requester accounts for what was spent."
      />
      <Tabs value={tab ?? (waiting?.count ? "waiting" : "mine")} onChange={setTab} keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="mine">My requests</Tabs.Tab>
          <Tabs.Tab value="waiting">
            Waiting for me {waiting?.count ? <Badge size="xs" color="red" ml={4}>{waiting.count}</Badge> : null}
          </Tabs.Tab>
          {can("finance.view") && <Tabs.Tab value="all">All requisitions</Tabs.Tab>}
        </Tabs.List>
        <Tabs.Panel value="mine">{list({ mine: 1 }, "You have not asked for anything yet.", true)}</Tabs.Panel>
        <Tabs.Panel value="waiting">{list({ waiting: 1 }, "Nothing is waiting for you.")}</Tabs.Panel>
        <Tabs.Panel value="all">{list({}, "No requisitions yet.")}</Tabs.Panel>
      </Tabs>
      {open !== null && <RequisitionDrawer id={open} onClose={() => setOpen(null)} />}
    </>
  );
}
