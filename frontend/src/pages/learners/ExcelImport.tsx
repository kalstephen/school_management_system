import { Alert, Badge, Button, FileInput, Group, List, Modal, ScrollArea, Select, SimpleGrid, Stack, Stepper, Table, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconDownload, IconFileSpreadsheet, IconFirstAidKit, IconUpload } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, ApiError, errorMessage, openFile } from "@/api/client";
import { useClasses, useYears } from "@/hooks/useSchool";

interface ImportResult {
  rows: number;
  valid: number;
  created: number;
  dry_run: boolean;
  target: string;
  errors: { row: number; name: string; error: string }[];
  preview: { row: number; name: string; sex: string; residence: string; medical: boolean }[];
}

/** Bulk enrolment: download the template, fill it in Excel, choose where the learners go,
 * check the file, then import. */
export function ExcelImport({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const { options: yearOptions, current: currentYear } = useYears();
  const { options: classOptions, streamOptions } = useClasses();
  const [term, setTerm] = useState<string | null>(null);
  const [schoolClass, setSchoolClass] = useState<string | null>(null);
  const [stream, setStream] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [check, setCheck] = useState<ImportResult | null>(null);
  const [done, setDone] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (!term && currentYear) setTerm(String(currentYear.id));
  }, [currentYear, term]);
  useEffect(() => setCheck(null), [term, schoolClass, stream, file]);

  const streams = streamOptions(schoolClass);
  const step = done ? 3 : check ? 2 : file ? 1 : 0;

  const send = async (dryRun: boolean) => {
    if (!file || !term || !schoolClass) return;
    const form = new FormData();
    form.append("file", file);
    form.append("academic_year", term);
    form.append("school_class", schoolClass);
    if (stream) form.append("stream", stream);
    if (dryRun) form.append("dry_run", "true");
    setBusy(true);
    setProblem(null);
    try {
      const result = await api<ImportResult>("/learners/import-excel/", { method: "POST", body: form });
      if (dryRun) setCheck(result);
      else {
        setDone(result);
        client.invalidateQueries({ queryKey: ["list", "/learners/"] });
        client.invalidateQueries({ queryKey: ["classes"] });
        notifications.show({ color: "green", message: `${result.created} learner(s) enrolled in ${result.target}.` });
      }
    } catch (error) {
      setProblem(error instanceof ApiError && error.data && !error.data.detail ? Object.values(error.data).flat().join(" ") : errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const close = () => {
    setFile(null);
    setCheck(null);
    setDone(null);
    setProblem(null);
    onClose();
  };

  return (
    <Modal opened={opened} onClose={close} title="Enrol learners from Excel" size="xl" centered>
      <Stack>
        <Stepper active={step} size="sm">
          <Stepper.Step label="Fill the template" />
          <Stepper.Step label="Choose class & file" />
          <Stepper.Step label="Check" />
          <Stepper.Step label="Import" />
        </Stepper>

        <Alert color="blue" icon={<IconFileSpreadsheet size={18} />}>
          <Group justify="space-between" wrap="nowrap">
            <Text size="sm">
              The template has one column for each detail: names, sex, date of birth, LIN, residence, district and village,
              father, mother and guardian, allergies and illnesses. Fill one row per learner and leave the admission number
              empty: the system gives each learner the next number.
            </Text>
            <Button variant="white" leftSection={<IconDownload size={16} />} onClick={() => openFile("/learners/excel-template/")} style={{ flexShrink: 0 }}>
              Download template
            </Button>
          </Group>
        </Alert>

        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <Select label="Academic year" description="They join its current term" data={yearOptions} value={term} onChange={setTerm} required allowDeselect={false} />
          <Select
            label="Class"
            description="All rows go into this class"
            placeholder="e.g. P1"
            data={classOptions}
            value={schoolClass}
            onChange={(v) => {
              setSchoolClass(v);
              setStream(null);
            }}
            searchable
            required
          />
          <Select
            label="Stream"
            description={schoolClass && !streams.length ? "This class has no streams" : "Optional"}
            placeholder={schoolClass ? "e.g. East" : "Choose the class first"}
            data={streams}
            value={stream}
            onChange={setStream}
            disabled={!streams.length}
            clearable
          />
        </SimpleGrid>
        <FileInput
          label="Filled template"
          placeholder="Choose the .xlsx file"
          accept=".xlsx,.csv"
          leftSection={<IconUpload size={16} />}
          value={file}
          onChange={setFile}
          clearable
        />

        {problem && <Alert color="red">{problem}</Alert>}

        {(done ?? check) && <ResultView result={(done ?? check)!} />}

        <Group justify="flex-end">
          {done ? (
            <Button onClick={close}>Close</Button>
          ) : check ? (
            <>
              <Button variant="default" onClick={() => setCheck(null)}>Back</Button>
              <Button loading={busy} disabled={!check.valid} onClick={() => send(false)}>
                Enrol {check.valid} learner{check.valid === 1 ? "" : "s"}
              </Button>
            </>
          ) : (
            <Button loading={busy} disabled={!file || !term || !schoolClass} onClick={() => send(true)}>
              Check file
            </Button>
          )}
        </Group>
      </Stack>
    </Modal>
  );
}

function ResultView({ result }: { result: ImportResult }) {
  return (
    <Stack gap="sm">
      <Group>
        <Badge size="lg" variant="light" color="blue">{result.rows} row(s) read</Badge>
        <Badge size="lg" variant="light" color="green">{result.dry_run ? `${result.valid} ready` : `${result.created} enrolled`}</Badge>
        {!!result.errors.length && <Badge size="lg" variant="light" color="orange">{result.errors.length} with problems</Badge>}
        <Text size="sm" c="dimmed">into {result.target}</Text>
      </Group>
      {!!result.errors.length && (
        <Alert color="orange" title={result.dry_run ? "These rows will be skipped. Fix them in Excel and check again, or import the rest." : "Skipped rows"}>
          <List size="sm">
            {result.errors.slice(0, 40).map((e) => (
              <List.Item key={e.row}>
                Row {e.row}{e.name ? ` (${e.name})` : ""}: {e.error}
              </List.Item>
            ))}
          </List>
        </Alert>
      )}
      {result.dry_run && !!result.preview.length && (
        <ScrollArea.Autosize mah={260}>
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Row</Table.Th>
                <Table.Th>Learner</Table.Th>
                <Table.Th>Sex</Table.Th>
                <Table.Th>Day/boarding</Table.Th>
                <Table.Th>Health</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {result.preview.map((p) => (
                <Table.Tr key={p.row}>
                  <Table.Td>{p.row}</Table.Td>
                  <Table.Td>{p.name}</Table.Td>
                  <Table.Td>{p.sex}</Table.Td>
                  <Table.Td>{p.residence}</Table.Td>
                  <Table.Td>{p.medical && <Badge color="red" variant="light" leftSection={<IconFirstAidKit size={12} />}>Medical note</Badge>}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea.Autosize>
      )}
    </Stack>
  );
}
