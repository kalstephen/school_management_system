import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Checkbox,
  Group,
  Loader,
  Modal,
  NumberInput,
  SimpleGrid,
  Stack,
  Table,
  Text,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconAlertTriangle, IconDeviceFloppy, IconHistory, IconSend } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router";

import { ApiError, errorMessage, get, post } from "@/api/client";
import { PageHeader, StatCard, StatusBadge } from "@/components/common";
import { cacheGet, cachePut, queueOp } from "@/offline/queue";
import { dateTime, num } from "@/utils/format";

interface Row {
  learner: number;
  name: string;
  adm_no: string;
  score: number | string | null;
  is_absent: boolean;
  version: number;
}

interface Entries {
  sheet: any;
  max_mark: string;
  editable: boolean;
  learners: Row[];
}

export default function MarkEntryPage() {
  const { id } = useParams();
  const client = useQueryClient();
  const [rows, setRows] = useState<Row[]>([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});
  const [historyOpen, setHistoryOpen] = useState(false);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["mark-entries", id],
    queryFn: async () => {
      try {
        const fresh = await get<Entries>(`/mark-sheets/${id}/entries/`);
        await cachePut(`marks:${id}`, fresh);
        return { ...fresh, offline: false };
      } catch (error) {
        const cached = await cacheGet<Entries>(`marks:${id}`);
        if (cached && !(error instanceof ApiError)) return { ...cached.value, offline: true };
        throw error;
      }
    },
  });
  const history = useQuery({ queryKey: ["mark-history", id], enabled: historyOpen, queryFn: () => get<any[]>(`/mark-sheets/${id}/history/`) });

  useEffect(() => {
    if (data) {
      setRows(data.learners.map((r) => ({ ...r, score: r.score === null ? null : Number(r.score) })));
      setDirty(false);
    }
  }, [data]);

  const max = Number(data?.max_mark ?? 100);
  const editable = !!data?.editable;
  const stats = useMemo(() => {
    const scored = rows.filter((r) => r.score !== null && r.score !== "").map((r) => Number(r.score));
    return {
      entered: scored.length + rows.filter((r) => r.is_absent).length,
      missing: rows.filter((r) => (r.score === null || r.score === "") && !r.is_absent).length,
      average: scored.length ? scored.reduce((a, b) => a + b, 0) / scored.length : null,
      outOfRange: rows.filter((r) => r.score !== null && r.score !== "" && (Number(r.score) < 0 || Number(r.score) > max)).length,
    };
  }, [rows, max]);

  const update = (learner: number, patch: Partial<Row>) => {
    setRows((current) => current.map((r) => (r.learner === learner ? { ...r, ...patch } : r)));
    setDirty(true);
  };

  const save = async (): Promise<boolean> => {
    if (stats.outOfRange) {
      notifications.show({ color: "red", message: `${stats.outOfRange} mark(s) are outside 0–${max}.` });
      return false;
    }
    setSaving(true);
    const marks = rows.map((r) => ({ learner: r.learner, score: r.score === "" ? null : r.score, is_absent: r.is_absent }));
    try {
      if (!navigator.onLine) throw new TypeError("offline");
      const result = await post(`/mark-sheets/${id}/entries/`, { marks });
      const errors: Record<number, string> = {};
      result.errors.forEach((e: any) => (errors[e.learner] = e.error));
      setRowErrors(errors);
      notifications.show({
        color: result.errors.length ? "orange" : "green",
        message: result.errors.length ? `${result.saved} saved, ${result.errors.length} need fixing.` : `${result.saved} marks saved.`,
      });
      setDirty(false);
      await refetch();
      return result.errors.length === 0;
    } catch (error) {
      if (error instanceof TypeError) {
        const original = new Map(data!.learners.map((r) => [r.learner, r]));
        for (const r of rows) {
          const before = original.get(r.learner);
          const changed = !before || Number(before.score ?? NaN) !== Number(r.score ?? NaN) || before.is_absent !== r.is_absent;
          if (changed && (r.score !== null || r.is_absent)) {
            await queueOp("mark", { mark_sheet: Number(id), learner: r.learner, score: r.score, is_absent: r.is_absent }, r.version, `${r.name}: ${r.score ?? "absent"}`);
          }
        }
        await cachePut(`marks:${id}`, { ...data, learners: rows });
        notifications.show({ color: "blue", title: "Saved on this device", message: "Marks will be sent when you are back online." });
        setDirty(false);
        return false;
      }
      notifications.show({ color: "red", title: "Not saved", message: errorMessage(error) });
      return false;
    } finally {
      setSaving(false);
    }
  };

  const submit = async () => {
    if (dirty && !(await save())) return;
    try {
      await post(`/mark-sheets/${id}/submit/`);
      notifications.show({ color: "green", title: "Submitted", message: "Sent to the head of department for review." });
      client.invalidateQueries({ queryKey: ["list", "/mark-sheets/"] });
      refetch();
    } catch (error) {
      notifications.show({ color: "red", title: "Not submitted", message: errorMessage(error) });
    }
  };

  if (isLoading || !data)
    return (
      <Center h="50vh">
        <Loader />
      </Center>
    );
  const sheet = data.sheet;

  return (
    <Stack>
      <PageHeader
        title={`${sheet.subject_name}${sheet.paper_label ? ` · ${sheet.paper_label}` : ""} — ${sheet.class_label}`}
        description={`${sheet.exam_name} · marked out of ${num(max, 0)}`}
        actions={
          <>
            <StatusBadge value={sheet.status} label={sheet.status_label} />
            <Button variant="default" leftSection={<IconHistory size={16} />} onClick={() => setHistoryOpen(true)}>
              Edit history
            </Button>
          </>
        }
      />
      {data.offline && <Alert color="gray">Showing the copy saved on this device. Changes will sync when you reconnect.</Alert>}
      {sheet.return_comment && sheet.status === "returned" && (
        <Alert color="orange" icon={<IconAlertTriangle size={18} />} title="Returned for correction">
          {sheet.return_comment}
          {sheet.reopen_reason ? ` (Reopened: ${sheet.reopen_reason})` : ""}
        </Alert>
      )}
      {!editable && (
        <Alert color="blue">
          {sheet.status === "approved"
            ? "These marks are approved and locked. The DOS can reopen them with a reason."
            : ["draft", "returned"].includes(sheet.status)
              ? "View only: the subject teacher allocated to this class enters these marks."
              : "This sheet is with the reviewers and cannot be edited now."}
        </Alert>
      )}
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <StatCard label="Entered" value={`${stats.entered}/${rows.length}`} />
        <StatCard label="Missing" value={stats.missing} color={stats.missing ? "orange" : "green"} />
        <StatCard label="Class average" value={stats.average === null ? "–" : num((stats.average / max) * 100)} hint="as a percentage" />
        <StatCard label="Out of range" value={stats.outOfRange} color={stats.outOfRange ? "red" : "green"} />
      </SimpleGrid>
      <Card p={0}>
        <Table.ScrollContainer minWidth={520}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={40}>#</Table.Th>
                <Table.Th>Learner</Table.Th>
                <Table.Th w={150}>Score (/{num(max, 0)})</Table.Th>
                <Table.Th w={110}>Absent</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((row, index) => {
                const out = row.score !== null && row.score !== "" && (Number(row.score) < 0 || Number(row.score) > max);
                return (
                  <Table.Tr key={row.learner}>
                    <Table.Td c="dimmed">{index + 1}</Table.Td>
                    <Table.Td>
                      <Text size="sm" fw={600}>
                        {row.name}
                      </Text>
                      <Text size="xs" c={rowErrors[row.learner] ? "red" : "dimmed"}>
                        {rowErrors[row.learner] ?? row.adm_no}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {!editable ? (
                        <Text fw={600} ta="center" ff="monospace">
                          {row.is_absent ? "ABS" : row.score === null || row.score === "" ? "–" : num(row.score)}
                        </Text>
                      ) : (
                      <NumberInput
                        className="mark-input"
                        ref={(el) => {
                          inputs.current[index] = el;
                        }}
                        value={row.score ?? ""}
                        onChange={(v) => update(row.learner, { score: v === "" ? null : v, is_absent: false })}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === "ArrowDown") {
                            e.preventDefault();
                            inputs.current[index + 1]?.focus();
                          } else if (e.key === "ArrowUp") {
                            e.preventDefault();
                            inputs.current[index - 1]?.focus();
                          }
                        }}
                        disabled={!editable || row.is_absent}
                        hideControls
                        decimalScale={1}
                        error={out ? `0–${num(max, 0)}` : undefined}
                        aria-label={`Score for ${row.name}`}
                      />
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Checkbox
                        checked={row.is_absent}
                        disabled={!editable}
                        onChange={(e) => update(row.learner, { is_absent: e.currentTarget.checked, score: e.currentTarget.checked ? null : row.score })}
                        aria-label={`${row.name} absent`}
                      />
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Card>
      {editable && (
        <Group justify="flex-end" className="no-print" style={{ position: "sticky", bottom: 12 }}>
          {dirty && <Badge color="orange">Unsaved changes</Badge>}
          <Button variant="default" size="md" leftSection={<IconDeviceFloppy size={18} />} onClick={save} loading={saving}>
            Save
          </Button>
          <Button size="md" leftSection={<IconSend size={18} />} onClick={submit} disabled={stats.missing > 0}>
            Submit for review
          </Button>
        </Group>
      )}
      <Modal opened={historyOpen} onClose={() => setHistoryOpen(false)} title="Edit history" size="lg">
        {history.isLoading ? (
          <Loader />
        ) : (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>When</Table.Th>
                <Table.Th>By</Table.Th>
                <Table.Th>Learner</Table.Th>
                <Table.Th>Change</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(history.data ?? []).map((h, i) => (
                <Table.Tr key={i}>
                  <Table.Td>{dateTime(h.at)}</Table.Td>
                  <Table.Td>{h.user}</Table.Td>
                  <Table.Td>{h.who.split(":")[0]}</Table.Td>
                  <Table.Td>{h.changes.score ? `${h.changes.score[0] ?? "–"} → ${h.changes.score[1] ?? "–"}` : h.action}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Modal>
    </Stack>
  );
}
