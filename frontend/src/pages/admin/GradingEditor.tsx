import { ActionIcon, Alert, Badge, Button, Card, Group, List, NumberInput, Select, SimpleGrid, Stack, Table, Text, TextInput } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconInfoCircle, IconPlus, IconTrash } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError, errorMessage, get, post, type Paginated } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";

interface Band {
  label: string;
  min_score: number | string;
  max_score: number | string;
  points: number | string;
  descriptor: string;
}

interface Preset {
  key: string;
  name: string;
  description: string;
  bands: Band[];
}

const num = (v: number | string) => (v === "" ? "" : Number(v));

/** Pick a grading scale, start it from a standard Ugandan preset, and adjust the cut-off marks. */
export function GradingEditor() {
  const client = useQueryClient();
  const { can } = useAuth();
  const editable = can("setup.manage") || can("assessment.manage");
  const { data: scales = [] } = useQuery({
    queryKey: ["grading-scales"],
    queryFn: async () => (await get<Paginated<any>>("/grading-scales/", { page_size: 100 })).results,
  });
  const { data: presets = [] } = useQuery({ queryKey: ["grading-presets"], queryFn: () => get<Preset[]>("/grading-scales/presets/") });
  const { data: sections = [] } = useQuery({
    queryKey: ["sections-for-grading"],
    queryFn: async () => (await get<Paginated<any>>("/sections/", { page_size: 50 })).results,
  });
  const [scaleId, setScaleId] = useState<string | null>(null);
  const [bands, setBands] = useState<Band[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const scale = scales.find((s: any) => String(s.id) === scaleId);

  useEffect(() => {
    if (!scaleId && scales.length) setScaleId(String(scales[0].id));
  }, [scales, scaleId]);
  useEffect(() => {
    setErrors([]);
    setBands(
      (scale?.bands ?? []).map((b: any) => ({ ...b, min_score: num(b.min_score), max_score: num(b.max_score), points: num(b.points) })),
    );
  }, [scale]);

  const save = async (body: Record<string, unknown>) => {
    setBusy(true);
    try {
      await post(`/grading-scales/${scaleId}/set-bands/`, body);
      setErrors([]);
      client.invalidateQueries({ queryKey: ["grading-scales"] });
      notifications.show({ color: "green", message: "Grading saved. New results use these cut-offs." });
    } catch (error) {
      const listed = error instanceof ApiError ? (error.data?.bands ?? error.data?.preset) : null;
      setErrors(listed ? ([] as string[]).concat(listed) : [errorMessage(error)]);
    } finally {
      setBusy(false);
    }
  };
  const update = (index: number, key: keyof Band, value: any) =>
    setBands((rows) => rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  const usedBy = sections.filter((s: any) => String(s.grading_scale) === scaleId).map((s: any) => s.name);

  return (
    <Stack>
      <Alert icon={<IconInfoCircle size={18} />} color="blue" title="How grading works">
        <List size="sm" spacing={4}>
          <List.Item>
            Each subject gets a <b>term score out of 100</b>: the weighted average of the term's assessments, for example
            continuous assessment (BOT 20% + MOT 30%) and the end-of-term exam (EOT 50%). Set the weights under Exams; they must add up to 100%.
          </List.Item>
          <List.Item>The term score is turned into a <b>grade</b> using the cut-off marks below (e.g. 90–100 = D1).</List.Item>
          <List.Item>
            Primary: the points of the four PLE subjects add up to the <b>aggregate</b> (4 is best, 36 the lowest) and give the division.
          </List.Item>
          <List.Item>The head teacher, director and Director of Studies can change the cut-offs. Start from a standard scale and adjust.</List.Item>
        </List>
      </Alert>

      <Card>
        <Group align="flex-end" justify="space-between" mb="md">
          <Select
            label="Grading scale"
            description={usedBy.length ? `Used by: ${usedBy.join(", ")}` : "Not used by any section yet (set it under Classes & streams → Sections)."}
            data={scales.map((s: any) => ({ value: String(s.id), label: s.name }))}
            value={scaleId}
            onChange={setScaleId}
            w={360}
            allowDeselect={false}
          />
          {editable && (
            <Group>
              <Button variant="default" leftSection={<IconPlus size={16} />} onClick={() => setBands((rows) => [...rows, { label: "", min_score: "", max_score: "", points: "", descriptor: "" }])}>
                Add grade
              </Button>
              <Button loading={busy} disabled={!scaleId} onClick={() => save({ bands })}>
                Save cut-offs
              </Button>
            </Group>
          )}
        </Group>
        {errors.length > 0 && (
          <Alert color="red" mb="md" title="Please fix these before saving">
            <List size="sm">{errors.map((e) => <List.Item key={e}>{e}</List.Item>)}</List>
          </Alert>
        )}
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={110}>Grade</Table.Th>
              <Table.Th w={120}>From mark</Table.Th>
              <Table.Th w={120}>To mark</Table.Th>
              <Table.Th w={110}>Points</Table.Th>
              <Table.Th>Remark on report card</Table.Th>
              <Table.Th w={50} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {bands.map((band, index) => (
              <Table.Tr key={index}>
                <Table.Td>
                  <TextInput aria-label="Grade" placeholder="e.g. D1" value={band.label} disabled={!editable} onChange={(e) => update(index, "label", e.currentTarget.value)} />
                </Table.Td>
                <Table.Td>
                  <NumberInput aria-label="From mark" placeholder="e.g. 80" min={0} max={100} decimalScale={2} value={band.min_score} disabled={!editable} onChange={(v) => update(index, "min_score", v)} />
                </Table.Td>
                <Table.Td>
                  <NumberInput aria-label="To mark" placeholder="e.g. 89.99" min={0} max={100} decimalScale={2} value={band.max_score} disabled={!editable} onChange={(v) => update(index, "max_score", v)} />
                </Table.Td>
                <Table.Td>
                  <NumberInput aria-label="Points" placeholder="e.g. 2" min={0} decimalScale={2} value={band.points} disabled={!editable} onChange={(v) => update(index, "points", v)} />
                </Table.Td>
                <Table.Td>
                  <TextInput aria-label="Remark" placeholder="e.g. Distinction" value={band.descriptor} disabled={!editable} onChange={(e) => update(index, "descriptor", e.currentTarget.value)} />
                </Table.Td>
                <Table.Td>
                  {editable && (
                    <ActionIcon variant="subtle" color="red" aria-label="Remove grade" onClick={() => setBands((rows) => rows.filter((_, i) => i !== index))}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
            {!bands.length && (
              <Table.Tr>
                <Table.Td colSpan={6}>
                  <Text c="dimmed" ta="center" py="md">No grades yet. Start from a standard scale below.</Text>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
        </Table>
        <Text size="xs" c="dimmed" mt="xs">
          The grades must cover every mark from 0 to 100 with no gaps or overlaps. Use 79.99 for "up to 80".
        </Text>
      </Card>

      {editable && (
        <>
          <Text fw={650}>Standard Ugandan scales</Text>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {presets.map((preset) => (
              <Card key={preset.key}>
                <Stack gap="xs">
                  <Text fw={650}>{preset.name}</Text>
                  <Text size="sm" c="dimmed">{preset.description}</Text>
                  <Group gap={4}>
                    {preset.bands.map((b) => (
                      <Badge key={b.label} variant="light" radius="sm">
                        {b.label} {Number(b.min_score)}+
                      </Badge>
                    ))}
                  </Group>
                  <Group justify="flex-end">
                    <Button size="xs" variant="light" disabled={!scaleId} loading={busy} onClick={() => save({ preset: preset.key })}>
                      Use for {scale?.name ?? "this scale"}
                    </Button>
                  </Group>
                </Stack>
              </Card>
            ))}
          </SimpleGrid>
          <Text size="xs" c="dimmed">Check bands against current UNEB/NCDC guidance before printing report cards.</Text>
        </>
      )}
    </Stack>
  );
}
