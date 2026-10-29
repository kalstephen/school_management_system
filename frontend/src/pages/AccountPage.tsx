import { Button, Card, PasswordInput, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";

import { errorMessage, post } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/common";

export default function AccountPage() {
  const { me } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <>
      <PageHeader title="My account" description={`${me?.user.name} · ${me?.roles.map((r) => r.label).join(", ")}`} />
      <Card maw={480}>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            if (next !== confirm) {
              notifications.show({ color: "red", message: "The new passwords do not match." });
              return;
            }
            setBusy(true);
            try {
              await post("/auth/change-password/", { current_password: current, new_password: next });
              notifications.show({ color: "green", message: "Password changed." });
              setCurrent("");
              setNext("");
              setConfirm("");
            } catch (error) {
              notifications.show({ color: "red", title: "Not changed", message: errorMessage(error) });
            } finally {
              setBusy(false);
            }
          }}
        >
          <Stack>
            <Text fw={600}>Change password</Text>
            <PasswordInput label="Current password" required value={current} onChange={(e) => setCurrent(e.currentTarget.value)} />
            <PasswordInput label="New password" description="At least 8 characters, not only numbers." required value={next} onChange={(e) => setNext(e.currentTarget.value)} />
            <PasswordInput label="Repeat new password" required value={confirm} onChange={(e) => setConfirm(e.currentTarget.value)} />
            <Button type="submit" loading={busy}>
              Change password
            </Button>
          </Stack>
        </form>
      </Card>
    </>
  );
}
