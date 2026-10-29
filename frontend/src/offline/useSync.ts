import { notifications } from "@mantine/notifications";
import { useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/api/client";

import { flush, onQueueChange, pendingOps } from "./queue";

export function useOnline() {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}

/** Pending-change count, plus automatic sending when the connection returns. */
export function useSync(enabled: boolean) {
  const online = useOnline();
  const [pending, setPending] = useState(0);
  const [syncing, setSyncing] = useState(false);

  const refreshCount = useCallback(() => {
    pendingOps().then((ops) => setPending(ops.length)).catch(() => setPending(0));
  }, []);

  const syncNow = useCallback(async () => {
    if (!navigator.onLine) return;
    setSyncing(true);
    try {
      const results = await flush();
      const conflicts = results.filter((r) => r.status === "conflict").length;
      const rejected = results.filter((r) => r.status === "rejected").length;
      const applied = results.filter((r) => r.status === "applied").length;
      if (results.length) {
        notifications.show({
          color: conflicts || rejected ? "orange" : "green",
          title: "Offline changes sent",
          message: `${applied} saved${conflicts ? `, ${conflicts} need your review` : ""}${rejected ? `, ${rejected} refused` : ""}.`,
        });
      }
    } catch (error) {
      notifications.show({ color: "red", title: "Sync failed", message: errorMessage(error) });
    } finally {
      setSyncing(false);
      refreshCount();
    }
  }, [refreshCount]);

  useEffect(() => {
    if (!enabled) return;
    refreshCount();
    const unsubscribe = onQueueChange(refreshCount);
    return () => {
      unsubscribe();
    };
  }, [enabled, refreshCount]);

  useEffect(() => {
    if (enabled && online && pending > 0) void syncNow();
  }, [enabled, online, pending, syncNow]);

  return { online, pending, syncing, syncNow };
}
