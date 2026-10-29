import { Alert, Autocomplete, Badge, Button, Card, Group, Select, SimpleGrid, Stack, Table, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconDeviceFloppy, IconWand } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { errorMessage, get, post } from "@/api/client";
import { Empty } from "@/components/common";
import { useClasses, useCurrentTerm, useTerms } from "@/hooks/useSchool";

interface Row {
  learner: number;
  name: string;
  adm_no: string;
  score: number | null;
  grade: string;
  suggested: string;
  comment: string;
}

/** The subject teacher's comment for each learner, printed beside the subject on the report
 *  card. Preset comments by mark are suggested; anything typed replaces them. */
export function SubjectComments() {
  const current = useCurrentTerm();
  const { options: termOptions } = useTerms();
  const { classes, options: classOptions, streamOptions } = useClasses();
  const [term, setTerm] = useState<string | null>(null);
  const [schoolClass, setSchoolClass] = useState<string | null>(null);
  const [stream, setStream] = useState<string | null>(null);
  const [subject, setSubject] = useState<string | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const termId = term ?? (current ? String(current.id) : null);
  const level = classes.find((c) => String(c.id) === schoolClass) as any;
  const { data: subjects } = useQuery({
    queryKey: ["subjects-for-comments", level?.section],
    enabled: !!level,
    queryFn: () => get("/subjects/", { page_size: 100 }),
  });
  const { data, refetch } = useQuery({
    queryKey: ["subject-comments", termId, schoolClass, stream, subject],
    enabled: !!(termId && schoolClass && subject),
    queryFn: () => get("/subject-comments/", { term: termId, school_class: schoolClass, stream, subject }),
  });
  useEffect(() => setRows(data?.learners ?? []), [data]);
  const presets: string[] = Array.from(new Set((data?.presets ?? []).map((p: any) => p.text)));
  const editable = !!data?.editable;

  const save = async () => {
    setBusy(true);
    try {
      const result = await post("/subject-comments/", {
        term: termId,
        school_class: schoolClass,
        subject,
        comments: rows.map((r) => ({ learner: r.learner, text: r.comment })),
      });
      notifications.show({ color: "green", message: `${result.saved} comment(s) saved. Draft report cards are updated.` });
      refetch();
    } catch (error) {
      notifications.show({ color: "red", message: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack>
      <Card>
        <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }}>
          <Select label="Term" data={termOptions} value={termId} onChange={setTerm} />
          <Select label="Class" data={classOptions} value={schoolClass} onChange={(v) => { setSchoolClass(v); setStream(null); }} searchable placeholder="e.g. P5" />
          <Select label="Stream" data={streamOptions(schoolClass)} value={stream} onChange={setStream} clearable placeholder="Whole class" disabled={!streamOptions(schoolClass).length} />
          <Select
            label="Subject"
            data={(subjects?.results ?? []).filter((s: any) => !level || s.level === level.level).map((s: any) => ({ value: String(s.id), label: s.name }))}
            value={subject}
            onChange={setSubject}
            searchable
            placeholder={schoolClass ? "Choose the subject" : "Choose the class first"}
            disabled={!schoolClass}
          />
        </SimpleGrid>
        <Text size="xs" c="dimmed" mt="sm">
          Comments show on the report card next to the subject, with the subject teacher's initials. Where no comment is written,
          the preset for the learner's mark is printed. Presets are edited under School setup → Grading → Comment bank.
        </Text>
      </Card>
      {!subject && <Empty title="Choose a class and subject">The learners' marks and suggested comments appear here.</Empty>}
      {subject && data && (
        <Card p={0}>
          <Group justify="space-between" p="md">
            <Text fw={650}>{rows.length} learners</Text>
            {editable ? (
              <Group gap="xs">
                <Button
                  variant="light"
                  leftSection={<IconWand size={16} />}
                  onClick={() => setRows((c) => c.map((r) => (r.comment ? r : { ...r, comment: r.suggested })))}
                >
                  Fill empty with presets
                </Button>
                <Button leftSection={<IconDeviceFloppy size={16} />} loading={busy} onClick={save}>Save comments</Button>
              </Group>
            ) : (
              <Badge variant="light" color="gray">View only: you do not teach this subject in this class</Badge>
            )}
          </Group>
          {rows.some((r) => r.score === null) && (
            <Alert color="gray" mx="md" mb="sm" p="xs">Learners without marks yet have no suggestion.</Alert>
          )}
          <Table.ScrollContainer minWidth={720}>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Learner</Table.Th>
                  <Table.Th w={80}>Mark</Table.Th>
                  <Table.Th w={70}>Grade</Table.Th>
                  <Table.Th>Comment</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rows.map((r) => (
                  <Table.Tr key={r.learner}>
                    <Table.Td>
                      <Text size="sm" fw={600}>{r.name}</Text>
                      <Text size="xs" c="dimmed">{r.adm_no}</Text>
                    </Table.Td>
                    <Table.Td>{r.score ?? "–"}</Table.Td>
                    <Table.Td>{r.grade || "–"}</Table.Td>
                    <Table.Td>
                      {editable ? (
                        <Autocomplete
                          size="xs"
                          data={presets}
                          value={r.comment}
                          placeholder={r.suggested ? `Preset: ${r.suggested}` : "Type a comment"}
                          onChange={(value) => setRows((c) => c.map((x) => (x.learner === r.learner ? { ...x, comment: value } : x)))}
                          maxLength={300}
                        />
                      ) : (
                        <Text size="sm">{r.comment || <Text span c="dimmed" size="sm">{r.suggested || "–"}</Text>}</Text>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Card>
      )}
    </Stack>
  );
}

