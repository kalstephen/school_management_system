import { ActionIcon, Badge, Button, Group, Modal, NumberInput, Select, Stack, Tabs, TextInput, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconArrowBackUp, IconBarcode, IconDownload } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, openFile, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader, StatusBadge } from "@/components/common";
import { CrudPage } from "@/components/CrudPage";
import { useOptions } from "@/hooks/useOptions";
import { date } from "@/utils/format";

function IssueModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const { options: learners } = useOptions({ endpoint: "/learners/", label: (l: any) => `${l.full_name} (${l.adm_no})`, query: { status: "active" } }, opened);
  const [barcode, setBarcode] = useState("");
  const [learner, setLearner] = useState<string | null>(null);
  const [days, setDays] = useState<number>(14);
  const [busy, setBusy] = useState(false);
  return (
    <Modal opened={opened} onClose={onClose} title="Issue a book" centered>
      <Stack>
        <TextInput label="Copy barcode" leftSection={<IconBarcode size={16} />} value={barcode} onChange={(e) => setBarcode(e.currentTarget.value)} autoFocus placeholder="Scan or type" />
        <Select label="Learner" data={learners} value={learner} onChange={setLearner} searchable />
        <NumberInput label="Loan period (days)" value={days} onChange={(v) => setDays(Number(v))} min={1} max={120} description="A full term for textbooks" />
        <Button
          loading={busy}
          disabled={!barcode || !learner}
          onClick={async () => {
            setBusy(true);
            try {
              await post("/library/loans/issue-by-barcode/", { barcode, learner, days });
              notifications.show({ color: "green", message: "Book issued" });
              client.invalidateQueries({ queryKey: ["list", "/library/loans/"] });
              setBarcode("");
              onClose();
            } catch (error) {
              notifications.show({ color: "red", message: errorMessage(error) });
            } finally {
              setBusy(false);
            }
          }}
        >
          Issue
        </Button>
      </Stack>
    </Modal>
  );
}

export default function LibraryPage() {
  const { can } = useAuth();
  const client = useQueryClient();
  const [issuing, setIssuing] = useState(false);
  const { options: books } = useOptions({ endpoint: "/library/books/", label: "title" });

  return (
    <>
      <PageHeader
        title="Library"
        description="Catalogue, barcoded copies, issue and return, and overdue lists — including termly textbook issue."
        actions={
          can("library.manage") ? (
            <Button leftSection={<IconBarcode size={16} />} onClick={() => setIssuing(true)}>
              Issue a book
            </Button>
          ) : null
        }
      />
      <Tabs defaultValue="loans" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="loans">Loans</Tabs.Tab>
          <Tabs.Tab value="books">Catalogue</Tabs.Tab>
          <Tabs.Tab value="copies">Copies</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="loans">
          <Group mb="sm" justify="flex-end">
            <Button variant="default" leftSection={<IconDownload size={16} />} onClick={() => openFile("/library/loans/overdue/", { download: "xlsx" })}>
              Overdue list (Excel)
            </Button>
          </Group>
          <CrudPage
            hideHeader
            title="Loans"
            singular="loan"
            formHelp="Lend a book copy to a learner or staff member, with a due date. Mark it returned when it comes back."
            endpoint="/library/loans/"
            writePerm="library.manage"
            fields={[]}
            canDelete={false}
            filters={[{ name: "returned_on__isnull", label: "Status", options: [{ value: "true", label: "On loan" }, { value: "false", label: "Returned" }] }]}
            extraActions={(row: any) =>
              !row.returned_on && can("library.manage") ? (
                <Tooltip label="Return">
                  <ActionIcon
                    variant="light"
                    onClick={async () => {
                      await post(`/library/loans/${row.id}/return/`);
                      client.invalidateQueries({ queryKey: ["list", "/library/loans/"] });
                    }}
                  >
                    <IconArrowBackUp size={16} />
                  </ActionIcon>
                </Tooltip>
              ) : null
            }
            columns={[
              { key: "book_title", label: "Book" },
              { key: "barcode", label: "Copy" },
              { key: "borrower", label: "Borrower" },
              { key: "issued_on", label: "Issued", render: (r: any) => date(r.issued_on) },
              { key: "due_on", label: "Due", render: (r: any) => date(r.due_on) },
              { key: "state", label: "Status", render: (r: any) => (r.returned_on ? <StatusBadge value="completed" label={`Returned ${date(r.returned_on)}`} /> : r.is_overdue ? <Badge color="red">Overdue</Badge> : <StatusBadge value="open" label="On loan" />) },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="books">
          <CrudPage
            hideHeader
            title="Books"
            singular="book"
            formHelp="A title in the library. Add its copies separately so each one can be lent."
            endpoint="/library/books/"
            writePerm="library.manage"
            toForm={(r: any) => ({ ...r, subject: r.subject && String(r.subject) })}
            filters={[{ name: "is_textbook", label: "Type", options: [{ value: "true", label: "Textbooks" }, { value: "false", label: "Other books" }] }]}
            columns={[
              { key: "title", label: "Title" },
              { key: "author", label: "Author" },
              { key: "isbn", label: "ISBN" },
              { key: "copies", label: "Available", render: (r: any) => `${r.copies_available} of ${r.copies_total}` },
              { key: "is_textbook", label: "", render: (r: any) => (r.is_textbook ? <Badge variant="light">Textbook</Badge> : null) },
            ]}
            fields={[
              { name: "title", label: "Title", required: true, span: 12 },
              { name: "author", label: "Author" },
              { name: "isbn", label: "ISBN" },
              { name: "publisher", label: "Publisher" },
              { name: "year", label: "Year", type: "number" },
              { name: "subject", label: "Subject", type: "select", optionsFrom: { endpoint: "/subjects/", label: (s: any) => `${s.name} (${s.level})` } },
              { name: "shelf", label: "Shelf" },
              { name: "is_textbook", label: "Textbook (issued for the term)", type: "checkbox" },
            ]}
          />
        </Tabs.Panel>
        <Tabs.Panel value="copies">
          <CrudPage
            hideHeader
            title="Copies"
            singular="copy"
            formHelp="One physical copy of a book, with its barcode or number, so each copy can be lent and tracked."
            endpoint="/library/copies/"
            writePerm="library.manage"
            defaults={{ condition: "good" }}
            toForm={(r: any) => ({ ...r, book: String(r.book) })}
            filters={[{ name: "book", label: "Book", options: books }]}
            columns={[
              { key: "barcode", label: "Barcode" },
              { key: "book", label: "Book", render: (r: any) => books.find((b) => b.value === String(r.book))?.label },
              { key: "condition", label: "Condition", render: (r: any) => <StatusBadge value={r.condition === "lost" ? "rejected" : "active"} label={r.condition} /> },
              { key: "on_loan", label: "On loan", render: (r: any) => (r.on_loan ? "Yes" : "") },
            ]}
            fields={[
              { name: "book", label: "Book", type: "select", options: books, required: true },
              { name: "barcode", label: "Barcode", required: true },
              { name: "condition", label: "Condition", type: "select", options: ["good", "fair", "poor", "lost"].map((v) => ({ value: v, label: v })) },
            ]}
          />
        </Tabs.Panel>
      </Tabs>
      <IssueModal opened={issuing} onClose={() => setIssuing(false)} />
    </>
  );
}
