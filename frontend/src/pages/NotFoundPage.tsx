import { Button, Stack, Text, Title } from "@mantine/core";
import { Link } from "react-router";

export default function NotFoundPage() {
  return (
    <Stack align="center" py={80}>
      <Title order={2}>Page not found</Title>
      <Text c="dimmed">The page may have moved, or your role may not include it.</Text>
      <Button component={Link} to="/">
        Back to dashboard
      </Button>
    </Stack>
  );
}
