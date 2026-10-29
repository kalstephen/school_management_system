import { Button, Group, Modal, Stack, Text, Textarea } from "@mantine/core";
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { MantineProvider } from "@mantine/core";

import { theme } from "@/theme";

interface ConfirmOptions {
  title: string;
  message?: string;
  confirmLabel?: string;
  danger?: boolean;
  /** Ask for a reason (e.g. reopening approved marks); it is passed to onConfirm. */
  reasonLabel?: string;
  onConfirm: (reason: string) => Promise<void> | void;
}

function ConfirmDialog({ options, close }: { options: ConfirmOptions; close: () => void }) {
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  return (
    <Modal opened onClose={close} title={options.title} centered>
      <Stack>
        {options.message && <Text size="sm">{options.message}</Text>}
        {options.reasonLabel && (
          <Textarea label={options.reasonLabel} required autosize minRows={2} value={reason} onChange={(e) => setReason(e.currentTarget.value)} />
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={close}>
            Cancel
          </Button>
          <Button
            color={options.danger ? "red" : undefined}
            loading={busy}
            disabled={!!options.reasonLabel && !reason.trim()}
            onClick={async () => {
              setBusy(true);
              try {
                await options.onConfirm(reason.trim());
                close();
              } finally {
                setBusy(false);
              }
            }}
          >
            {options.confirmLabel ?? "Confirm"}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Imperative confirm dialog (with optional reason) that works from any event handler. */
export function modalsConfirm(options: ConfirmOptions) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const close = () => {
    root.unmount();
    host.remove();
  };
  root.render(
    <MantineProvider theme={theme} defaultColorScheme="auto">
      <ConfirmDialog options={options} close={close} />
    </MantineProvider>,
  );
}
