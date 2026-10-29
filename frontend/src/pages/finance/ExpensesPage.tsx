import { ActionIcon, Badge, Button, Group, Modal, NumberInput, Select, Stack, Table, Tabs, Text, TextInput, Tooltip } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { IconCash, IconCheck, IconPlus, IconSend, IconTablePlus, IconTrash, IconX } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { errorMessage, get, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { modalsConfirm } from "@/components/confirm";
import { CrudPage } from "@/components/CrudPage";
import type { Field } from "@/components/ResourceForm";
import { useOptions } from "@/hooks/useOptions";
import { date, today, ugx } from "@/utils/format";

const METHODS = [
  { value: "cash", label: "Cash" }, { value: "mobile_money", label: "Mobile money" },
  { value: "bank", label: "Bank transfer" }, { value: "cheque", label: "Cheque" },
];
const STATUSES = [
  ["draft", "Draft"], ["pending", "Awaiting approval"], ["approved", "Approved"], ["paid", "Paid"], ["rejected", "Rejected"],
].map(([value, label]) => ({ value, label }));
const LEVELS: Record<number, string> = { 1: "Bursar", 2: "Head teacher", 3: "Director" };

function DailySheet({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const { options: categories } = useOptions({ endpoint: "/finance/categories/", label: "name" }, opened);
  const blank = () => ({ category: null as string | null, description: "", amount: 0 as number, method: "cash", payee: "" });
  const [day, setDay] = useState(today());
  const [rows, setRows] = useState([blank(), blank(), blank()]);
  const [busy, setBusy] = useState(false);
  const total = rows.reduce((sum, r) => sum + (Number(r.amount) || 0), 0);
  const set = (i: number, patch: Partial<ReturnType<typeof blank>>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <Modal opened={opened} onClose={onClose} title="Daily cash sheet" size="xl">
      <Stack>
        <DateInput label="Date" value={day} onChange={(v) => v && setDay(v)} w={200} valueFormat="D MMM YYYY" />
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Category</Table.Th>
              <Table.Th>Description</Table.Th>
              <Table.Th>Paid to</Table.Th>
              <Table.Th>Method</Table.Th>
              <Table.Th>Amount (UGX)</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((row, i) => (
              <Table.Tr key={i}>
                <Table.Td><Select size="xs" data={categories} value={row.category} onChange={(v) => set(i, { category: v })} searchable /></Table.Td>
                <Table.Td><TextInput size="xs" value={row.description} onChange={(e) => set(i, { description: e.currentTarget.value })} /></Table.Td>
                <Table.Td><TextInput size="xs" value={row.payee} onChange={(e) => set(i, { payee: e.currentTarget.value })} /></Table.Td>
                <Table.Td><Select size="xs" data={METHODS} value={row.method} onChange={(v) => set(i, { method: v ?? "cash" })} w={130} /></Table.Td>
                <Table.Td><NumberInput size="xs" thousandSeparator="," value={row.amount} onChange={(v) => set(i, { amount: Number(v) })} min={0} hideControls /></Table.Td>
                <Table.Td>
                  <ActionIcon variant="subtle" color="red" onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))} aria-label="Remove line">
                    <IconTrash size={14} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Group justify="space-between">
          <Button variant="subtle" leftSection={<IconPlus size={14} />} onClick={() => setRows((rs) => [...rs, blank()])}>
            Add line
          </Button>
          <Text fw={700}>Total {ugx(total)}</Text>
        </Group>
        <Group justify="flex-end">
          <Button
            loading={busy}
            onClick={async () => {
              const filled = rows.filter((r) => r.category && r.amount > 0);
              if (!filled.length) return;
              setBusy(true);
              try {
                const result = await post("/finance/expenses/bulk/", {
                  rows: filled.map((r) => ({ ...r, date: day, description: r.description || "Daily expense" })),
                });
                notifications.show({
                  color: result.errors.length ? "orange" : "green",
                  message: `${result.created} expense(s) recorded and sent for approval${result.errors.length ? `; ${result.errors.length} line(s) had errors` : ""}.`,
                });
                client.invalidateQueries({ queryKey: ["list", "/finance/expenses/"] });
                setRows([blank(), blank(), blank()]);
                onClose();
              } catch (error) {
                notifications.show({ color: "red", message: errorMessage(error) });
              } finally {
                setBusy(false);
              }
            }}
          >
            Record all
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export default function ExpensesPage() {
  const { can, me } = useAuth();
  const client = useQueryClient();
  const [params] = useSearchParams();
  const [sheetOpen, setSheetOpen] = useState(false);
  const { options: categories, rows: categoryRows } = useOptions({ endpoint: "/finance/categories/", label: "name" });
  const subCategories = (categoryId: string | null) =>
    (categoryRows.find((c: any) => String(c.id) === String(categoryId))?.sub_categories ?? []).map((s: any) => ({ value: String(s.id), label: s.name }));
  const { data: awaiting = [] } = useQuery({
    queryKey: ["list", "/finance/expenses/", "awaiting"],
    enabled: can("finance.approve"),
    queryFn: () => get<any[]>("/finance/expenses/awaiting-me/"),
  });
  const refresh = () => client.invalidateQueries({ queryKey: ["list", "/finance/expenses/"] });

  const act = async (id: number, action: string, body?: object) => {
    try {
      const result = await post(`/finance/expenses/${id}/${action}/`, body);
      notifications.show({ color: "green", message: `Expense ${result.status === "pending" ? "sent for approval" : result.status}.` });
      refresh();
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    }
  };

  const fields: Field[] = [
    { name: "date", label: "Date", type: "date", required: true },
    { name: "amount", label: "Amount", type: "money", required: true },
    { name: "category", label: "Category", type: "select", options: categories, required: true },
    {
      name: "sub_category",
      label: "Sub-category",
      type: "select",
      options: (v) => subCategories(v.category ?? null),
      clearWhen: "category",
      placeholder: "Optional",
      description: "Only the chosen category's sub-categories are listed. Add more under Finance → Categories.",
      hidden: (v) => !v.category || !subCategories(v.category).length,
    },
    { name: "description", label: "Description", required: true, span: 12 },
    { name: "method", label: "Payment method", type: "select", options: METHODS },
    { name: "payee", label: "Paid to" },
    { name: "supplier", label: "Supplier", type: "select", optionsFrom: { endpoint: "/finance/suppliers/", label: "name" } },
    { name: "reference", label: "Reference / receipt no." },
    { name: "department", label: "Department", type: "select", optionsFrom: { endpoint: "/departments/", label: "name" } },
    { name: "project", label: "Project", placeholder: 'e.g. "S4 mock exams"' },
    { name: "receipt", label: "Receipt photo", type: "file" },
    { name: "period_override_reason", label: "Reason to change the finance period (optional)", description: "Normally the term is set from the date", hidden: (v) => !v.id },
  ];

  const actions = (row: any) => (
    <>
      {can("finance.manage") && ["draft", "rejected"].includes(row.status) && (
        <Tooltip label="Send for approval"><ActionIcon variant="light" onClick={() => act(row.id, "submit")}><IconSend size={16} /></ActionIcon></Tooltip>
      )}
      {can("finance.approve") && row.status === "pending" && row.required_level <= (me?.approval_level ?? 0) && (
        <>
          <Tooltip label="Approve"><ActionIcon variant="filled" color="green" onClick={() => act(row.id, "approve")}><IconCheck size={16} /></ActionIcon></Tooltip>
          <Tooltip label="Reject">
            <ActionIcon
              variant="light"
              color="red"
              onClick={() => modalsConfirm({ title: "Reject expense", reasonLabel: "Reason", confirmLabel: "Reject", danger: true, onConfirm: (comment) => act(row.id, "reject", { comment }) })}
            >
              <IconX size={16} />
            </ActionIcon>
          </Tooltip>
        </>
      )}
      {can("finance.manage") && row.status === "approved" && (
        <Tooltip label="Mark as paid"><ActionIcon variant="light" color="teal" onClick={() => act(row.id, "pay")}><IconCash size={16} /></ActionIcon></Tooltip>
      )}
    </>
  );

  const columns = [
    { key: "date", label: "Date", render: (r: any) => date(r.date) },
    { key: "description", label: "Description", render: (r: any) => <><Text size="sm">{r.description}</Text><Text size="xs" c="dimmed">{r.category_name}{r.sub_category_name ? ` · ${r.sub_category_name}` : ""}</Text></> },
    { key: "payee", label: "Paid to", render: (r: any) => r.supplier_name ?? r.payee ?? "–" },
    { key: "amount", label: "Amount", align: "right" as const, render: (r: any) => <Text fw={600} size="sm">{ugx(r.amount)}</Text> },
    { key: "status", label: "Status", render: (r: any) => <Group gap={4}><StatusBadge value={r.status} />{r.status === "pending" && <Badge size="xs" variant="outline">{LEVELS[r.required_level]}</Badge>}</Group> },
  ];

  return (
    <>
      <PageHeader
        title="Expenses"
        description="Every shilling the school spends: recorded daily, approved within limits (bursar → head teacher → director), and paid."
        actions={can("finance.manage") ? <Button variant="default" leftSection={<IconTablePlus size={16} />} onClick={() => setSheetOpen(true)}>Daily cash sheet</Button> : null}
      />
      <Tabs defaultValue={params.get("status") === "pending" && can("finance.approve") ? "awaiting" : "all"} keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="all">All expenses</Tabs.Tab>
          {can("finance.approve") && (
            <Tabs.Tab value="awaiting" rightSection={awaiting.length ? <Badge size="xs" color="red">{awaiting.length}</Badge> : null}>
              Awaiting my approval
            </Tabs.Tab>
          )}
        </Tabs.List>
        <Tabs.Panel value="all">
          <CrudPage
            hideHeader
            title="Expenses"
            singular="expense"
            formHelp="Record money the school spent. Larger amounts wait for approval by the head teacher or director before they count."
            endpoint="/finance/expenses/"
            writePerm="finance.manage"
            exportable
            defaults={{ date: today(), method: "cash" }}
            toForm={(r: any) => ({ ...r, category: String(r.category), sub_category: r.sub_category && String(r.sub_category), supplier: r.supplier && String(r.supplier), department: r.department && String(r.department) })}
            filters={[
              { name: "status", label: "Status", options: STATUSES },
              { name: "category", label: "Category", options: categories },
              { name: "method", label: "Method", options: METHODS },
              { name: "date__gte", label: "From", type: "date" },
              { name: "date__lte", label: "To", type: "date" },
            ]}
            extraActions={actions}
            columns={columns}
            fields={fields}
          />
        </Tabs.Panel>
        <Tabs.Panel value="awaiting">
          <Table.ScrollContainer minWidth={700}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  {columns.map((c) => <Table.Th key={c.key}>{c.label}</Table.Th>)}
                  <Table.Th>Entered by</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {awaiting.map((row) => (
                  <Table.Tr key={row.id}>
                    {columns.map((c) => <Table.Td key={c.key}>{c.render(row)}</Table.Td>)}
                    <Table.Td>{row.entered_by}</Table.Td>
                    <Table.Td><Group gap={4} wrap="nowrap">{actions(row)}</Group></Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          {!awaiting.length && <Text c="dimmed" ta="center" py="xl">Nothing is waiting for your approval.</Text>}
        </Tabs.Panel>
      </Tabs>
      <DailySheet opened={sheetOpen} onClose={() => setSheetOpen(false)} />
    </>
  );
}
