/**
 * Offline store for teachers: cached registers / mark sheets and a queue of changes
 * made without a connection. Each change carries a UUID so the server applies it once,
 * and the version the phone last saw so the server can spot conflicting edits.
 */
import { openDB, type IDBPDatabase } from "idb";

import { post } from "@/api/client";

export type OpKind = "attendance" | "mark";

export interface SyncOp {
  op_id: string;
  kind: OpKind;
  payload: Record<string, unknown>;
  base_version: number;
  created_at: number;
  label: string;
}

export interface SyncResult {
  op_id: string;
  status: "applied" | "conflict" | "rejected" | "resolved";
  detail: string;
}

let dbPromise: Promise<IDBPDatabase> | null = null;

function db() {
  dbPromise ??= openDB("school-offline", 1, {
    upgrade(database) {
      database.createObjectStore("ops", { keyPath: "op_id" });
      database.createObjectStore("cache");
    },
  });
  return dbPromise;
}

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (Number(c) ^ (Math.random() * 16) >> (Number(c) / 4)).toString(16),
  );
}

const listeners = new Set<() => void>();
export function onQueueChange(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
const notify = () => listeners.forEach((listener) => listener());

export async function queueOp(kind: OpKind, payload: Record<string, unknown>, baseVersion: number, label: string) {
  const op: SyncOp = { op_id: uuid(), kind, payload, base_version: baseVersion, created_at: Date.now(), label };
  await (await db()).put("ops", op);
  notify();
  return op;
}

export async function pendingOps(): Promise<SyncOp[]> {
  const ops = (await (await db()).getAll("ops")) as SyncOp[];
  return ops.sort((a, b) => a.created_at - b.created_at);
}

export async function cachePut(key: string, value: unknown) {
  await (await db()).put("cache", { value, saved_at: Date.now() }, key);
}

export async function cacheGet<T>(key: string): Promise<{ value: T; saved_at: number } | undefined> {
  return (await db()).get("cache", key);
}

let flushing: Promise<SyncResult[]> | null = null;

/** Send queued changes. Applied, duplicate, rejected and conflicting ones leave the
 *  queue (conflicts are kept on the server for the teacher to resolve). */
export function flush(): Promise<SyncResult[]> {
  flushing ??= (async () => {
    try {
      const ops = await pendingOps();
      const results: SyncResult[] = [];
      for (let i = 0; i < ops.length; i += 200) {
        const batch = ops.slice(i, i + 200);
        const response = await post<{ results: SyncResult[] }>("/sync/", {
          ops: batch.map(({ op_id, kind, payload, base_version }) => ({ op_id, kind, payload, base_version })),
        });
        const database = await db();
        for (const result of response.results) await database.delete("ops", result.op_id);
        results.push(...response.results);
      }
      notify();
      return results;
    } finally {
      flushing = null;
    }
  })();
  return flushing;
}
