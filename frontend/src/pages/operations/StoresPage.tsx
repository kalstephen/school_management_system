import { ActionIcon, Badge, Button, Drawer, Group, NumberInput, Table, Tabs, Text, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconChecklist } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, get, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import { useOptions } from "@/hooks/useOptions";
import { useClasses, useCurrentTerm, useTerms } from "@/hooks/useSchool";
import { date, num, today, ugx } from "@/utils/format";

function RequirementDrawer({ requirement, onClose }: { requirement: any; onClose: () => void }) {
  const { can } = useAuth();
  const { data, refetch } = useQuery({ queryKey: ["requirement", requirement.id], queryFn: () => get(`/stores/requirements/${requirement.id}/status/`) });
  const [qty, setQty] = useState<Record<number, number>>({});
  return (
    <Drawer opened onClose={onClose} title={data?.requirement ?? requirement.name} position="right" size="lg">
      <Group mb="md">
        <Badge color="green">{data?.cleared ?? 0} cleared</Badge>
        <Badge color="orange">{data?.pending ?? 0} pending</Badge>
      </Group>
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Learner</Table.Th>
            <Table.Th>Brought</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(data?.rows ?? []).map((row: any) => (
            <Table.Tr key={row.learner}>
              <Table.Td>{row.name}</Table.Td>
              <Table.Td>{row.cleared ? <StatusBadge value="completed" label={`Cleared (${row.brought})`} /> : row.brought || "–"}</Table.Td>
              <Table.Td>
                {!row.cleared && can("stores.manage") && (
                  <Group gap={4} wrap="nowrap">
                    <NumberInput size="xs" w={70} value={qty[row.learner] ?? Number(requirement.quantity_per_learner)} onChange={(v) => setQty((q) => ({ ...q, [row.learner]: Number(v) }))} min={0} />
                    <Button
                      size="xs"
                      onClick={async () => {
                        try {
                          await post(`/stores/requirements/${requirement.id}/clear/`, { learner: row.learner, quantity: qty[row.learner] ?? requirement.quantity_per_learner, date: today() });
                          refetch();
                        } catch (error) {
                          notifications.show({ color: "red", message: errorMessage(error) });
                        }
                      }}
                    >
                      Record
                    </Button>
                  </Group>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Drawer>
  );
}

export default function StoresPage() {
  const { options: stores } = useOptions({ endpoint: "/stores/stores/", label: "name" });
  const { options: items } = useOptions({ endpoint: "/stores/items/", label: (i: any) => `${i.name} (${i.unit})` });
  const { options: classOptions } = useClasses();
  const { options: termOptions } = useTerms();
  const term = useCurrentTerm();
  const [requirement, setRequirement] = useState<any>(null);

  return (
    <>
      <PageHeader title="Stores, inventory & assets" description="Stock in and out across stores, reorder alerts, scholastic requirements each learner brings, and the fixed asset register." />
      <Tabs defaultValue="items" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="items">Stock</Tabs.Tab>
          <Tabs.Tab value="movements">Stock movements</Tabs.Tab>
          <Tabs.Tab value="requirements">Scholastic requirements</Tabs.Tab>
          <Tabs.Tab value="assets">Asset register</Tabs.Tab>
          <Tabs.Tab value="stores">Stores</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="items">
          <CrudPage
            hideHeader
            title="Items"
            singular="item"
            formHelp="Something the school keeps in stock, e.g. chalk or maize flour, with the level at which to reorder."
            endpoint="/stores/items/"
            writePerm="stores.manage"
            toForm={(r: any) => ({ ...r, store: String(r.store) })}
            filters={[{ name: "store", label: "Store", options: stores }]}
            columns={[
              { key: "name", label: "Item" },
              { key: "store_name", label: "Store" },
              { key: "quantity", label: "In stock", render: (r: any) => <Text fw={600} c={r.below_reorder ? "red" : undefined}>{num(r.quantity)} {r.unit}</Text> },
              { key: "reorder_level", label: "Reorder at", render: (r: any) => `${num(r.reorder_level)} ${r.unit}` },
              { key: "below_reorder", label: "", render: (r: any) => (r.below_reorder ? <Badge color="red">Reorder</Badge> : null) },
            ]}
            fields={[
              { name: "store", label: "Store", type: "select", options: stores, required: true },
              { name: "name", label: "Item", required: true },
              { name: "unit", label: "Unit", placeholder: "kg, bags, reams, pcs" },
              { name: "reorder_level", label: "Reorder level", type: "number" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="movements">
          <CrudPage
            hideHeader
            title="Stock movements"
            singular="stock movement"
            formHelp="Stock coming in (delivered) or going out (issued). The balance updates at once."
            endpoint="/stores/movements/"
            writePerm="stores.manage"
            canDelete={false}
            defaults={{ date: today(), kind: "out" }}
            filters={[
              { name: "item", label: "Item", options: items },
              { name: "kind", label: "Type", options: [{ value: "in", label: "In" }, { value: "out", label: "Out" }, { value: "adjust", label: "Adjustment" }] },
            ]}
            columns={[
              { key: "date", label: "Date", render: (r: any) => date(r.date) },
              { key: "item_name", label: "Item" },
              { key: "kind", label: "Type", render: (r: any) => <StatusBadge value={r.kind === "in" ? "received" : r.kind === "out" ? "pending" : "draft"} label={r.kind} /> },
              { key: "quantity", label: "Quantity", render: (r: any) => num(r.quantity) },
              { key: "issued_to", label: "Issued to" },
              { key: "reference", label: "Reference" },
            ]}
            fields={[
              { name: "item", label: "Item", type: "select", options: items, required: true },
              { name: "kind", label: "Type", type: "select", options: [{ value: "in", label: "Stock in" }, { value: "out", label: "Stock out" }, { value: "adjust", label: "Adjustment (count)" }], required: true },
              { name: "quantity", label: "Quantity", type: "number", required: true },
              { name: "date", label: "Date", type: "date", required: true },
              { name: "issued_to", label: "Issued to", hidden: (v) => v.kind !== "out", placeholder: "Kitchen, department, person" },
              { name: "reference", label: "Reference" },
              { name: "notes", label: "Notes" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="requirements">
          <CrudPage
            hideHeader
            title="Scholastic requirements"
            singular="requirement"
            formHelp="Items each learner brings at the start of term, e.g. a ream of paper. Track who has cleared them."
            endpoint="/stores/requirements/"
            writePerm="stores.manage"
            defaults={{ term: term ? String(term.id) : null }}
            toForm={(r: any) => ({ ...r, term: String(r.term), item: r.item && String(r.item), school_class: r.school_class && String(r.school_class), section: r.section && String(r.section) })}
            filters={[{ name: "term", label: "Term", options: termOptions }]}
            extraActions={(row: any) => (
              <Tooltip label="Who has cleared it">
                <ActionIcon variant="light" onClick={() => setRequirement(row)}>
                  <IconChecklist size={16} />
                </ActionIcon>
              </Tooltip>
            )}
            onRowClick={(row: any) => setRequirement(row)}
            columns={[
              { key: "name", label: "Requirement" },
              { key: "quantity_per_learner", label: "Per learner", render: (r: any) => num(r.quantity_per_learner) },
              { key: "applies", label: "Applies to", render: (r: any) => classOptions.find((c) => c.value === String(r.school_class))?.label ?? (r.section ? "Section" : "Whole school") },
            ]}
            fields={[
              { name: "name", label: "Requirement", required: true, placeholder: "e.g. Reams of paper" },
              { name: "quantity_per_learner", label: "Quantity per learner", type: "number", required: true },
              { name: "term", label: "Term", type: "select", options: termOptions, required: true },
              { name: "item", label: "Adds to stock item", type: "select", options: items },
              { name: "school_class", label: "Class (optional)", type: "select", options: classOptions },
              { name: "section", label: "Section (optional)", type: "select", optionsFrom: { endpoint: "/sections/", label: "name" } },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="assets">
          <CrudPage
            hideHeader
            title="Assets"
            singular="asset"
            formHelp="Equipment the school owns, e.g. a projector, with where it is and its condition."
            endpoint="/stores/assets/"
            writePerm="stores.manage"
            exportable
            defaults={{ condition: "good" }}
            filters={[{ name: "condition", label: "Condition", options: ["new", "good", "fair", "poor", "disposed"].map((v) => ({ value: v, label: v })) }]}
            columns={[
              { key: "name", label: "Asset" },
              { key: "tag", label: "Tag" },
              { key: "category", label: "Category" },
              { key: "location", label: "Location" },
              { key: "condition", label: "Condition", render: (r: any) => <StatusBadge value={r.condition === "poor" || r.condition === "disposed" ? "warning" : "ok"} label={r.condition} /> },
              { key: "purchase_cost", label: "Cost", render: (r: any) => ugx(r.purchase_cost) },
            ]}
            fields={[
              { name: "name", label: "Asset", required: true },
              { name: "tag", label: "Tag / serial" },
              { name: "category", label: "Category", placeholder: "Furniture, ICT, Vehicle…" },
              { name: "location", label: "Location" },
              { name: "condition", label: "Condition", type: "select", options: ["new", "good", "fair", "poor", "disposed"].map((v) => ({ value: v, label: v })) },
              { name: "custodian", label: "Custodian" },
              { name: "purchase_date", label: "Purchase date", type: "date" },
              { name: "purchase_cost", label: "Purchase cost", type: "money" },
              { name: "supplier", label: "Supplier" },
              { name: "notes", label: "Notes", type: "textarea" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="stores">
          <CrudPage
            hideHeader
            title="Stores"
            singular="store"
            formHelp="A place where stock is kept, e.g. the main store or the kitchen store."
            endpoint="/stores/stores/"
            writePerm="stores.manage"
            columns={[{ key: "name", label: "Store" }, { key: "keeper", label: "Keeper" }]}
            fields={[{ name: "name", label: "Name", required: true }, { name: "keeper", label: "Keeper" }]}
          />
        </Tabs.Panel>
      </Tabs>
      {requirement && <RequirementDrawer requirement={requirement} onClose={() => setRequirement(null)} />}
    </>
  );
}
