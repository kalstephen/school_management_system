import { AreaChart } from "@mantine/charts";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  NumberInput,
  Progress,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconArrowDownLeft, IconArrowUpRight, IconBook, IconCash, IconCopy, IconDownload, IconFileInvoice, IconRefresh, IconScale } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { errorMessage, get, openFile, patch, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Empty, PageHeader, Section, StatCard, StatusBadge } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import { useOptions } from "@/hooks/useOptions";
import { useCurrentTerm, useTerms } from "@/hooks/useSchool";
import { date, num, today, ugx, ugxShort } from "@/utils/format";

const REPORTS = [
  { key: "termly", label: "Termly expenditure statement" },
  { key: "budget-vs-actual", label: "Budget vs actual" },
  { key: "top-items", label: "Top 10 cost items" },
  { key: "compare-last-year", label: "Same term last year" },
  { key: "outstanding-bills", label: "Unpaid supplier bills" },
  { key: "daily", label: "Daily expense sheet (today)" },
  { key: "weekly", label: "Weekly summary (this week)" },
];

function Overview({ term }: { term: string | null }) {
  const { data: bva } = useQuery({ queryKey: ["bva", term], enabled: !!term, queryFn: () => get("/finance/reports/budget-vs-actual/", { term }) });
  const { data: statement } = useQuery({ queryKey: ["termly", term], enabled: !!term, queryFn: () => get("/finance/reports/termly/", { term }) });
  if (!bva || !statement) return null;
  return (
    <Stack>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <StatCard label="Spent this term" value={ugxShort(statement.total)} hint={ugx(statement.total)} icon={<IconArrowUpRight />} color="orange" />
        <StatCard label="Budget" value={ugxShort(bva.budget_total)} hint={bva.budget_total ? `${num((bva.actual_total / bva.budget_total) * 100, 0)}% used` : "No budget set"} icon={<IconScale />} />
        <StatCard label="Cost per learner" value={ugxShort(statement.cost_per_learner)} hint={`${statement.learners} learners enrolled`} icon={<IconCash />} color="teal" />
        <StatCard label="Other income (not fees)" value={ugxShort(statement.other_income)} hint={`Net cash position ${ugx(statement.net_cash_position)}`} icon={<IconArrowDownLeft />} color="green" />
      </SimpleGrid>
      <Section title="Budget vs actual">
        {bva.lines.length ? (
          <Table.ScrollContainer minWidth={640}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Category</Table.Th>
                  <Table.Th ta="right">Budget</Table.Th>
                  <Table.Th ta="right">Spent</Table.Th>
                  <Table.Th w="30%">Used</Table.Th>
                  <Table.Th>Status</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {bva.lines.map((line: any) => (
                  <Table.Tr key={line.category}>
                    <Table.Td fw={600}>{line.category}</Table.Td>
                    <Table.Td ta="right">{ugx(line.budget)}</Table.Td>
                    <Table.Td ta="right">{ugx(line.actual)}</Table.Td>
                    <Table.Td>
                      <Group gap="xs" wrap="nowrap">
                        <Progress value={Math.min(line.percent ?? 100, 100)} color={line.status === "over" ? "red" : line.status === "warning" ? "yellow" : "green"} style={{ flex: 1 }} />
                        <Text size="xs" w={44}>{line.percent === null ? "–" : `${line.percent}%`}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td><StatusBadge value={line.status} /></Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        ) : (
          <Empty title="No spending or budget for this term yet" />
        )}
      </Section>
      {bva.weeks.length > 0 && (
        <Section title="Spending week by week">
          <AreaChart
            h={240}
            data={bva.weeks.map((w: any) => ({ week: date(w.week_start, "D MMM"), spent: w.spent, cumulative: w.cumulative }))}
            dataKey="week"
            series={[
              { name: "cumulative", label: "Total so far", color: "brand.6" },
              { name: "spent", label: "That week", color: "orange.5" },
            ]}
            valueFormatter={(v) => ugxShort(v)}
            curveType="monotone"
            withLegend
          />
        </Section>
      )}
    </Stack>
  );
}

function PettyCash() {
  const { can } = useAuth();
  const client = useQueryClient();
  const { data } = useQuery({ queryKey: ["list", "/finance/petty-cash/"], queryFn: () => get("/finance/petty-cash/") });
  const { options: categories } = useOptions({ endpoint: "/finance/categories/", label: "name" });
  const [dialog, setDialog] = useState<{ kind: "spend" | "topup" | "count" | "book"; float: any } | null>(null);
  const [amount, setAmount] = useState<number>(0);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const book = useQuery({ queryKey: ["petty-book", dialog?.float?.id], enabled: dialog?.kind === "book", queryFn: () => get(`/finance/petty-cash/${dialog!.float.id}/book/`) });
  const refresh = () => client.invalidateQueries({ queryKey: ["list", "/finance/petty-cash/"] });

  const submit = async () => {
    if (!dialog) return;
    try {
      const body = dialog.kind === "count" ? { counted: amount } : { amount, description, category, date: today() };
      const result = await post(`/finance/petty-cash/${dialog.float.id}/${dialog.kind}/`, body);
      notifications.show({ color: "green", message: dialog.kind === "count" ? `Counted. Difference: ${ugx(result.difference)}` : "Recorded" });
      setDialog(null);
      setAmount(0);
      setDescription("");
      refresh();
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    }
  };

  return (
    <Stack>
      <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }}>
        {(data?.results ?? []).map((f: any) => (
          <Card key={f.id}>
            <Group justify="space-between" mb="xs">
              <Text fw={650}>{f.name}</Text>
              {f.needs_replenishment && <Badge color="orange">Top-up needed</Badge>}
            </Group>
            <Text fz={28} fw={700}>{ugx(f.balance)}</Text>
            <Text size="xs" c="dimmed" mb="md">Custodian {f.custodian_name} · float {ugx(f.float_amount)}</Text>
            <Progress value={(f.balance / Math.max(Number(f.float_amount), 1)) * 100} color={f.needs_replenishment ? "orange" : "green"} mb="md" />
            <Group gap="xs">
              {can("finance.manage") && <Button size="xs" onClick={() => setDialog({ kind: "spend", float: f })}>Spend</Button>}
              {can("finance.manage") && <Button size="xs" variant="light" onClick={() => setDialog({ kind: "topup", float: f })}>Top up</Button>}
              {can("finance.manage") && <Button size="xs" variant="default" onClick={() => setDialog({ kind: "count", float: f })}>Cash count</Button>}
              <Tooltip label="Petty cash book"><ActionIcon variant="default" onClick={() => setDialog({ kind: "book", float: f })}><IconBook size={16} /></ActionIcon></Tooltip>
            </Group>
          </Card>
        ))}
      </SimpleGrid>
      {can("finance.manage") && (
        <CrudPage
          hideHeader
          title="Floats"
          singular="float"
          formHelp="Cash given to someone for small purchases. Their spending is recorded against it until it is topped up."
          endpoint="/finance/petty-cash/"
          writePerm="finance.manage"
          canDelete={false}
          toForm={(r: any) => ({ ...r, custodian: String(r.custodian) })}
          columns={[
            { key: "name", label: "Float" },
            { key: "custodian_name", label: "Custodian" },
            { key: "float_amount", label: "Float", render: (r: any) => ugx(r.float_amount) },
            { key: "replenish_below", label: "Top up below", render: (r: any) => ugx(r.replenish_below) },
          ]}
          fields={[
            { name: "name", label: "Name", required: true },
            { name: "custodian", label: "Custodian", type: "select", required: true, optionsFrom: { endpoint: "/users/", value: "user_id", label: (u: any) => `${u.first_name} ${u.last_name}` } },
            { name: "float_amount", label: "Float amount", type: "money", required: true },
            { name: "replenish_below", label: "Ask for a top-up below", type: "money", required: true },
          ]}
        />
      )}
      <Modal opened={!!dialog && dialog.kind !== "book"} onClose={() => setDialog(null)} title={dialog?.kind === "spend" ? "Spend from petty cash" : dialog?.kind === "topup" ? "Top up the float" : "End-of-day cash count"} centered>
        <Stack>
          {dialog?.kind === "count" && <Text size="sm">Expected balance: <b>{ugx(dialog.float.balance)}</b></Text>}
          <NumberInput label={dialog?.kind === "count" ? "Cash counted" : "Amount"} thousandSeparator="," prefix="UGX " value={amount} onChange={(v) => setAmount(Number(v))} min={0} />
          {dialog?.kind !== "count" && <TextInput label="Description" value={description} onChange={(e) => setDescription(e.currentTarget.value)} />}
          {dialog?.kind === "spend" && <Select label="Category" data={categories} value={category} onChange={setCategory} required />}
          <Button onClick={submit} disabled={!amount || (dialog?.kind === "spend" && !category)}>Save</Button>
        </Stack>
      </Modal>
      <Modal opened={dialog?.kind === "book"} onClose={() => setDialog(null)} title={`Petty cash book — ${dialog?.float?.name ?? ""}`} size="lg">
        <Table>
          <Table.Thead>
            <Table.Tr><Table.Th>Date</Table.Th><Table.Th>Description</Table.Th><Table.Th ta="right">In</Table.Th><Table.Th ta="right">Out</Table.Th><Table.Th ta="right">Balance</Table.Th></Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {(book.data?.rows ?? []).map((r: any, i: number) => (
              <Table.Tr key={i}>
                <Table.Td>{date(r.date)}</Table.Td>
                <Table.Td>{r.description}</Table.Td>
                <Table.Td ta="right">{r.in ? num(r.in, 0) : ""}</Table.Td>
                <Table.Td ta="right">{r.out ? num(r.out, 0) : ""}</Table.Td>
                <Table.Td ta="right">{num(r.balance, 0)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Group justify="flex-end" mt="md">
          <Button variant="default" leftSection={<IconDownload size={16} />} onClick={() => openFile(`/finance/petty-cash/${dialog?.float?.id}/book/`, { download: "xlsx" })}>Excel</Button>
        </Group>
      </Modal>
    </Stack>
  );
}

function Budgets({ term }: { term: string | null }) {
  const { can } = useAuth();
  const client = useQueryClient();
  const { data: budgets, refetch } = useQuery({ queryKey: ["budget", term], enabled: !!term, queryFn: () => get("/finance/budgets/", { term }) });
  const { rows: categories } = useOptions({ endpoint: "/finance/categories/", label: "name" });
  const budget = budgets?.results?.[0];
  const [amounts, setAmounts] = useState<Record<number, number>>({});
  useEffect(() => {
    const map: Record<number, number> = {};
    budget?.lines.forEach((l: any) => (map[l.category] = Number(l.amount)));
    setAmounts(map);
  }, [budget]);
  const total = Object.values(amounts).reduce((a, b) => a + (b || 0), 0);
  const editable = can("finance.manage") && (!budget?.is_approved || can("finance.approve"));

  if (!term) return null;
  if (!budget)
    return (
      <Card>
        <Empty title="No budget for this term">
          {can("finance.manage") && (
            <Button mt="md" onClick={async () => { await post("/finance/budgets/", { term }); refetch(); }}>
              Create the budget
            </Button>
          )}
        </Empty>
      </Card>
    );

  return (
    <Card>
      <Group justify="space-between" mb="md">
        <Group gap="xs">
          <Text fw={650}>Budget for {budget.term_label}</Text>
          {budget.is_approved ? <Badge color="green">Approved</Badge> : <Badge color="gray">Draft</Badge>}
        </Group>
        <Group gap="xs">
          {can("finance.manage") && (
            <Button variant="default" size="xs" leftSection={<IconCopy size={14} />} onClick={async () => {
              try {
                const r = await post(`/finance/budgets/${budget.id}/copy-forward/`);
                notifications.show({ color: "green", message: `${r.copied} line(s) copied from the previous term.` });
                refetch();
              } catch (error) {
                notifications.show({ color: "red", message: errorMessage(error) });
              }
            }}>
              Copy from last term
            </Button>
          )}
          {can("finance.approve") && !budget.is_approved && (
            <Button size="xs" color="green" onClick={async () => { await post(`/finance/budgets/${budget.id}/approve/`); refetch(); }}>Approve budget</Button>
          )}
        </Group>
      </Group>
      <Table>
        <Table.Thead><Table.Tr><Table.Th>Category</Table.Th><Table.Th w={240}>Amount for the term (UGX)</Table.Th></Table.Tr></Table.Thead>
        <Table.Tbody>
          {categories.map((c: any) => (
            <Table.Tr key={c.id}>
              <Table.Td>{c.name}</Table.Td>
              <Table.Td>
                <NumberInput size="xs" thousandSeparator="," value={amounts[c.id] ?? 0} onChange={(v) => setAmounts((a) => ({ ...a, [c.id]: Number(v) }))} disabled={!editable} min={0} hideControls />
              </Table.Td>
            </Table.Tr>
          ))}
          <Table.Tr><Table.Th>Total</Table.Th><Table.Th>{ugx(total)}</Table.Th></Table.Tr>
        </Table.Tbody>
      </Table>
      {editable && (
        <Group justify="flex-end" mt="md">
          <Button onClick={async () => {
            try {
              await post(`/finance/budgets/${budget.id}/set-lines/`, { lines: Object.entries(amounts).map(([category, amount]) => ({ category, amount })) });
              notifications.show({ color: "green", message: "Budget saved" });
              refetch();
              client.invalidateQueries({ queryKey: ["bva"] });
            } catch (error) {
              notifications.show({ color: "red", message: errorMessage(error) });
            }
          }}>Save budget</Button>
        </Group>
      )}
    </Card>
  );
}

function Suppliers() {
  const { can } = useAuth();
  const client = useQueryClient();
  const [statement, setStatement] = useState<any>(null);
  const [paying, setPaying] = useState<any>(null);
  const [amount, setAmount] = useState<number>(0);
  const [method, setMethod] = useState<string | null>("bank");
  const { options: categories } = useOptions({ endpoint: "/finance/categories/", label: "name" });
  const { options: suppliers } = useOptions({ endpoint: "/finance/suppliers/", label: "name" });
  return (
    <Stack>
      <CrudPage
        hideHeader
        title="Suppliers"
        singular="supplier"
        formHelp="A business the school buys from. Bills and payments are kept against the supplier."
        endpoint="/finance/suppliers/"
        writePerm="finance.manage"
        extraActions={(row: any) => (
          <Tooltip label="Statement">
            <ActionIcon variant="light" onClick={async () => setStatement(await get(`/finance/suppliers/${row.id}/statement/`))}>
              <IconFileInvoice size={16} />
            </ActionIcon>
          </Tooltip>
        )}
        columns={[
          { key: "name", label: "Supplier" },
          { key: "contact_person", label: "Contact" },
          { key: "phone", label: "Phone" },
          { key: "tin", label: "TIN" },
          { key: "amount_owed", label: "We owe", render: (r: any) => (r.amount_owed ? <Text c="red" fw={600} size="sm">{ugx(r.amount_owed)}</Text> : "–") },
        ]}
        fields={[
          { name: "name", label: "Name", required: true },
          { name: "contact_person", label: "Contact person" },
          { name: "phone", label: "Phone" },
          { name: "email", label: "Email", type: "email" },
          { name: "tin", label: "TIN" },
          { name: "address", label: "Address" },
        ]}
      />
      <Text fw={650} mt="md">Supplier bills</Text>
      <CrudPage
        hideHeader
        title="Bills"
        singular="bill"
        formHelp="An invoice from a supplier. Record payments against it, in full or in parts."
        endpoint="/finance/bills/"
        writePerm="finance.manage"
        canDelete={false}
        defaults={{ date: today() }}
        toForm={(r: any) => ({ ...r, supplier: String(r.supplier), category: String(r.category) })}
        filters={[{ name: "status", label: "Status", options: [{ value: "unpaid", label: "Unpaid" }, { value: "part_paid", label: "Part paid" }, { value: "paid", label: "Paid" }] }]}
        extraActions={(row: any) =>
          can("finance.approve") && row.status !== "paid" ? (
            <Tooltip label="Pay">
              <ActionIcon variant="light" color="teal" onClick={() => { setPaying(row); setAmount(row.balance); }}>
                <IconCash size={16} />
              </ActionIcon>
            </Tooltip>
          ) : null
        }
        columns={[
          { key: "date", label: "Date", render: (r: any) => date(r.date) },
          { key: "supplier_name", label: "Supplier" },
          { key: "description", label: "For" },
          { key: "amount", label: "Amount", render: (r: any) => ugx(r.amount) },
          { key: "balance", label: "Balance", render: (r: any) => ugx(r.balance) },
          { key: "due_date", label: "Due", render: (r: any) => date(r.due_date) },
          { key: "status", label: "Status", render: (r: any) => <StatusBadge value={r.status} /> },
        ]}
        fields={[
          { name: "supplier", label: "Supplier", type: "select", options: suppliers, required: true },
          { name: "category", label: "Expense category", type: "select", options: categories, required: true },
          { name: "description", label: "Description", required: true },
          { name: "reference", label: "Invoice number" },
          { name: "amount", label: "Amount", type: "money", required: true },
          { name: "date", label: "Invoice date", type: "date", required: true },
          { name: "due_date", label: "Due date", type: "date" },
        ]}
      />
      <Modal opened={!!paying} onClose={() => setPaying(null)} title={`Pay ${paying?.supplier_name ?? ""}`} centered>
        <Stack>
          <Text size="sm">Balance: <b>{ugx(paying?.balance)}</b>. Part payments are allowed.</Text>
          <NumberInput label="Amount" thousandSeparator="," prefix="UGX " value={amount} onChange={(v) => setAmount(Number(v))} />
          <Select label="Method" data={[{ value: "bank", label: "Bank" }, { value: "mobile_money", label: "Mobile money" }, { value: "cheque", label: "Cheque" }, { value: "cash", label: "Cash" }]} value={method} onChange={setMethod} />
          <Button onClick={async () => {
            try {
              await post(`/finance/bills/${paying.id}/pay/`, { amount, method, date: today() });
              notifications.show({ color: "green", message: "Payment recorded as an expense." });
              setPaying(null);
              client.invalidateQueries({ queryKey: ["list", "/finance/bills/"] });
              client.invalidateQueries({ queryKey: ["list", "/finance/suppliers/"] });
            } catch (error) {
              notifications.show({ color: "red", message: errorMessage(error) });
            }
          }}>Record payment</Button>
        </Stack>
      </Modal>
      <Modal opened={!!statement} onClose={() => setStatement(null)} title={`Statement — ${statement?.supplier ?? ""}`} size="lg">
        <Table>
          <Table.Thead><Table.Tr><Table.Th>Date</Table.Th><Table.Th>Type</Table.Th><Table.Th>Ref.</Table.Th><Table.Th ta="right">Billed</Table.Th><Table.Th ta="right">Paid</Table.Th><Table.Th ta="right">Balance</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {(statement?.rows ?? []).map((r: any, i: number) => (
              <Table.Tr key={i}>
                <Table.Td>{date(r.date)}</Table.Td><Table.Td>{r.type}</Table.Td><Table.Td>{r.reference}</Table.Td>
                <Table.Td ta="right">{r.credit ? num(r.credit, 0) : ""}</Table.Td><Table.Td ta="right">{r.debit ? num(r.debit, 0) : ""}</Table.Td><Table.Td ta="right">{num(r.balance, 0)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Text fw={700} mt="md" ta="right">Amount owed: {ugx(statement?.amount_owed)}</Text>
      </Modal>
    </Stack>
  );
}

function Reports({ term }: { term: string | null }) {
  const [report, setReport] = useState<string>("termly");
  const { data } = useQuery({ queryKey: ["finance-report", report, term], queryFn: () => get(`/finance/reports/${report}/`, { term }) });
  const rows: any[] = data?.rows ?? data?.lines ?? data?.items ?? data?.categories ?? [];
  const columns = rows.length ? Object.keys(rows[0]).filter((k) => !["sub_categories", "category_id", "id"].includes(k)) : [];
  return (
    <Card>
      <Group justify="space-between" mb="md">
        <Select data={REPORTS.map((r) => ({ value: r.key, label: r.label }))} value={report} onChange={(v) => setReport(v ?? "termly")} w={320} />
        <Group gap="xs">
          <Button variant="default" leftSection={<IconDownload size={16} />} onClick={() => openFile(`/finance/reports/${report}/`, { term, download: "xlsx" })}>Excel</Button>
          <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={() => window.print()}>Print</Button>
        </Group>
      </Group>
      {data?.total !== undefined && <Text fw={700} mb="sm">Total: {ugx(data.total)}</Text>}
      {rows.length ? (
        <Table.ScrollContainer minWidth={600}>
          <Table striped>
            <Table.Thead><Table.Tr>{columns.map((c) => <Table.Th key={c}>{c.replace(/_/g, " ")}</Table.Th>)}</Table.Tr></Table.Thead>
            <Table.Tbody>
              {rows.map((row, i) => (
                <Table.Tr key={i}>
                  {columns.map((c) => (
                    <Table.Td key={c}>{typeof row[c] === "number" && !/percent|count/.test(c) ? num(row[c], 0) : row[c] === null ? "–" : String(row[c])}</Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      ) : (
        <Empty title="Nothing to report" />
      )}
    </Card>
  );
}

function Settings() {
  const { can } = useAuth();
  const { data, refetch } = useQuery({ queryKey: ["finance-settings"], queryFn: () => get("/finance/settings/") });
  const [values, setValues] = useState<{ bursar_limit: number; head_limit: number } | null>(null);
  useEffect(() => data && setValues({ bursar_limit: Number(data.bursar_limit), head_limit: Number(data.head_limit) }), [data]);
  if (!values) return null;
  return (
    <Card maw={520}>
      <Stack>
        <Text fw={650}>Approval limits</Text>
        <Text size="sm" c="dimmed">The bursar approves alone up to the first limit, the head teacher up to the second, and the director above it.</Text>
        <NumberInput label="Bursar can approve up to" thousandSeparator="," prefix="UGX " value={values.bursar_limit} onChange={(v) => setValues({ ...values, bursar_limit: Number(v) })} disabled={!can("finance.approve")} />
        <NumberInput label="Head teacher can approve up to" thousandSeparator="," prefix="UGX " value={values.head_limit} onChange={(v) => setValues({ ...values, head_limit: Number(v) })} disabled={!can("finance.approve")} />
        {can("finance.approve") && (
          <Button onClick={async () => {
            try { await patch("/finance/settings/", values); notifications.show({ color: "green", message: "Limits saved" }); refetch(); }
            catch (error) { notifications.show({ color: "red", message: errorMessage(error) }); }
          }}>Save limits</Button>
        )}
      </Stack>
    </Card>
  );
}

/** Spending categories and their sub-categories, kept by the bursar or director. */
function Categories() {
  return (
    <CrudPage
      hideHeader
      title="Categories"
      singular="category"
      formHelp="A spending category (e.g. Academics) and its sub-categories (e.g. Exam printing, Textbooks). When recording an expense, only the chosen category's sub-categories are offered. Budgets and reports are totalled by category."
      endpoint="/finance/categories/"
      writePerm="finance.manage"
      defaults={{ sub_category_names: [], is_capital: false }}
      toForm={(r: any) => ({ ...r, sub_category_names: r.sub_categories.map((s: any) => s.name) })}
      emptyText="No categories yet. Add one, e.g. Academics with its sub-categories."
      columns={[
        { key: "name", label: "Category", render: (r: any) => <><Text size="sm" fw={600}>{r.name}</Text>{r.is_capital && <Badge size="xs" variant="light" color="grape">Capital</Badge>}</> },
        {
          key: "sub_categories",
          label: "Sub-categories",
          render: (r: any) =>
            r.sub_categories.length ? (
              <Group gap={4}>{r.sub_categories.map((s: any) => <Badge key={s.id} size="sm" variant="outline" color="gray">{s.name}</Badge>)}</Group>
            ) : (
              <Text size="xs" c="dimmed">None</Text>
            ),
        },
        { key: "expenses", label: "Expenses", render: (r: any) => r.expenses },
      ]}
      fields={[
        { name: "name", label: "Category name", required: true, placeholder: "e.g. Academics" },
        { name: "order", label: "Position in lists", type: "number", placeholder: "e.g. 1" },
        { name: "sub_category_names", label: "Sub-categories", type: "tags", span: 12, placeholder: "Type a name and press Enter, e.g. Exam printing", description: "Remove a tag to delete a sub-category (only if no expense uses it)." },
        { name: "is_capital", label: "Capital spending (buildings, furniture, equipment that lasts years)", type: "checkbox", span: 12 },
      ]}
    />
  );
}

export default function FinanceOverviewPage() {
  const { can, me } = useAuth();
  const current = useCurrentTerm();
  const { options: termOptions } = useTerms();
  const [term, setTerm] = useState<string | null>(null);
  const termId = term ?? (current ? String(current.id) : null);
  return (
    <>
      <PageHeader
        title="Finance"
        description="What it costs to run the school — today, this week and this term — against plan. Expenditure only: fees stay in SchoolPay."
        actions={<Select data={termOptions} value={termId} onChange={setTerm} w={200} aria-label="Term" />}
      />
      {!termId && <Alert color="blue" mb="md">Add terms in School setup to see termly figures.</Alert>}
      <Tabs defaultValue="overview" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="overview">Overview</Tabs.Tab>
          <Tabs.Tab value="petty">Petty cash</Tabs.Tab>
          <Tabs.Tab value="budgets">Budgets</Tabs.Tab>
          <Tabs.Tab value="suppliers">Suppliers & bills</Tabs.Tab>
          {me?.school?.other_income_enabled && <Tabs.Tab value="income">Other income</Tabs.Tab>}
          <Tabs.Tab value="recurring">Recurring</Tabs.Tab>
          <Tabs.Tab value="reports">Reports</Tabs.Tab>
          <Tabs.Tab value="categories">Categories</Tabs.Tab>
          <Tabs.Tab value="settings">Approval limits</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="overview"><Overview term={termId} /></Tabs.Panel>
        <Tabs.Panel value="petty"><PettyCash /></Tabs.Panel>
        <Tabs.Panel value="budgets"><Budgets term={termId} /></Tabs.Panel>
        <Tabs.Panel value="suppliers"><Suppliers /></Tabs.Panel>
        <Tabs.Panel value="income">
          <CrudPage
            hideHeader
            title="Other income"
            singular="income entry"
            formHelp="Money received that is not school fees, e.g. a grant or donation. Fees are collected in SchoolPay."
            endpoint="/finance/other-income/"
            writePerm="finance.manage"
            defaults={{ date: today(), source: "capitation", method: "bank" }}
            query={{ term: termId }}
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date) },
              { key: "source", label: "Source", render: (r: any) => ({ capitation: "UPE/USE capitation", donation: "Donation", produce: "Farm produce", hire: "Facility hire", other: "Other" } as any)[r.source] },
              { key: "description", label: "Description" },
              { key: "received_from", label: "From" },
              { key: "amount", label: "Amount", render: (r: any) => ugx(r.amount) },
            ]}
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "source", label: "Source", type: "select", options: [{ value: "capitation", label: "UPE/USE capitation grant" }, { value: "donation", label: "Donation" }, { value: "produce", label: "Sale of farm produce" }, { value: "hire", label: "Hall or facility hire" }, { value: "other", label: "Other" }], required: true },
              { name: "description", label: "Description", required: true },
              { name: "amount", label: "Amount", type: "money", required: true },
              { name: "received_from", label: "Received from" },
              { name: "reference", label: "Reference" },
            ]}
          />
          <Text size="xs" c="dimmed" mt="xs">Non-fee money only. School fees are never recorded here.</Text>
        </Tabs.Panel>
        <Tabs.Panel value="recurring">
          {can("finance.manage") && (
            <Group justify="flex-end" mb="sm">
              <Button variant="default" onClick={async () => {
                const r = await post("/finance/expenses/generate-recurring/");
                notifications.show({ color: "green", message: `${r.created} expense(s) created and sent for approval.` });
              }}>Create due expenses now</Button>
            </Group>
          )}
          <CrudPage
            hideHeader
            title="Recurring expenses"
            singular="recurring expense"
            formHelp="A cost that repeats, e.g. monthly electricity. Each time it falls due a pending expense is created, ready for approval."
            endpoint="/finance/recurring/"
            writePerm="finance.manage"
            defaults={{ frequency: "monthly", method: "bank", is_active: true, next_date: today() }}
            toForm={(r: any) => ({ ...r, category: String(r.category) })}
            columns={[
              { key: "description", label: "Expense" },
              { key: "amount", label: "Amount", render: (r: any) => ugx(r.amount) },
              { key: "frequency", label: "Every", render: (r: any) => (r.frequency === "monthly" ? "Month" : "Term") },
              { key: "next_date", label: "Next", render: (r: any) => date(r.next_date) },
              { key: "is_active", label: "Active", render: (r: any) => (r.is_active ? "Yes" : "No") },
            ]}
            fields={[
              { name: "description", label: "Description", required: true, placeholder: "Rent, Yaka, internet, salaries total…" },
              { name: "category", label: "Category", type: "select", optionsFrom: { endpoint: "/finance/categories/", label: "name" }, required: true },
              { name: "amount", label: "Amount", type: "money", required: true },
              { name: "frequency", label: "Frequency", type: "select", options: [{ value: "monthly", label: "Monthly" }, { value: "termly", label: "Each term" }] },
              { name: "next_date", label: "Next date", type: "date", required: true },
              { name: "payee", label: "Paid to" },
              { name: "is_active", label: "Active", type: "checkbox" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="reports"><Reports term={termId} /></Tabs.Panel>
        <Tabs.Panel value="categories"><Categories /></Tabs.Panel>
        <Tabs.Panel value="settings"><Settings /></Tabs.Panel>
      </Tabs>
    </>
  );
}
