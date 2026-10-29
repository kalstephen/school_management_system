import { Alert, Center, Loader, Paper, Stack, Table, Text, ThemeIcon, Title } from "@mantine/core";
import { IconCircleCheck, IconCircleX } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { ApiError, get } from "@/api/client";
import { dateTime } from "@/utils/format";

interface Verification {
  valid: boolean;
  status: string;
  school: string;
  learner: string;
  term: string;
  serial: string;
  published_at: string;
  note: string;
}

/** Public page opened from the QR code on a report card. */
export function VerifyPage() {
  const { token } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["verify", token],
    queryFn: () => get<Verification>(`/public/verify/${token}/`),
    retry: false,
  });

  return (
    <Center mih="100vh" p="md">
      <Paper w={460} maw="100%" p="xl" radius="lg" shadow="md">
        {isLoading && <Loader />}
        {error && (
          <Stack align="center">
            <ThemeIcon color="red" size={56} radius="xl">
              <IconCircleX size={34} />
            </ThemeIcon>
            <Title order={3}>Not verified</Title>
            <Text c="dimmed" ta="center">
              {error instanceof ApiError && error.status === 404 ? "No published report card matches this code." : "The check could not be completed."}
            </Text>
          </Stack>
        )}
        {data && (
          <Stack>
            <Stack align="center" gap={6}>
              <ThemeIcon color={data.valid ? "green" : "orange"} size={56} radius="xl">
                {data.valid ? <IconCircleCheck size={34} /> : <IconCircleX size={34} />}
              </ThemeIcon>
              <Title order={3}>{data.valid ? "Genuine report card" : "Replaced report card"}</Title>
            </Stack>
            {data.note && <Alert color="orange">{data.note}</Alert>}
            <Table>
              <Table.Tbody>
                <Table.Tr><Table.Th>School</Table.Th><Table.Td>{data.school}</Table.Td></Table.Tr>
                <Table.Tr><Table.Th>Learner</Table.Th><Table.Td>{data.learner}</Table.Td></Table.Tr>
                <Table.Tr><Table.Th>Term</Table.Th><Table.Td>{data.term}</Table.Td></Table.Tr>
                <Table.Tr><Table.Th>Serial</Table.Th><Table.Td>{data.serial}</Table.Td></Table.Tr>
                <Table.Tr><Table.Th>Published</Table.Th><Table.Td>{dateTime(data.published_at)}</Table.Td></Table.Tr>
              </Table.Tbody>
            </Table>
            <Text size="xs" c="dimmed" ta="center">
              Only identifying details are shown here. Results are on the printed card.
            </Text>
          </Stack>
        )}
      </Paper>
    </Center>
  );
}
