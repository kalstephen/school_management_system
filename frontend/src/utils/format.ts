import dayjs from "dayjs";

const money = new Intl.NumberFormat("en-UG", { maximumFractionDigits: 0 });

export function ugx(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "–";
  return `UGX ${money.format(Number(value))}`;
}

/** Compact money for cards and chart axes: UGX 37.5M, UGX 383K. */
export function ugxShort(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "–";
  const n = Number(value);
  const abs = Math.abs(n);
  if (abs >= 1e9) return `UGX ${(n / 1e9).toFixed(1).replace(/\.0$/, "")}B`;
  if (abs >= 1e6) return `UGX ${(n / 1e6).toFixed(1).replace(/\.0$/, "")}M`;
  if (abs >= 1e4) return `UGX ${Math.round(n / 1e3)}K`;
  return ugx(n);
}

export function num(value: number | string | null | undefined, digits = 1): string {
  if (value === null || value === undefined || value === "") return "–";
  return Number(value).toLocaleString("en-UG", { maximumFractionDigits: digits });
}

export function date(value: string | null | undefined, format = "D MMM YYYY"): string {
  return value ? dayjs(value).format(format) : "–";
}

export function dateTime(value: string | null | undefined): string {
  return value ? dayjs(value).format("D MMM YYYY, HH:mm") : "–";
}

export function today(): string {
  return dayjs().format("YYYY-MM-DD");
}

export function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const STATUS_COLORS: Record<string, string> = {
  active: "green", approved: "green", paid: "teal", published: "green", present: "green", applied: "green",
  admitted: "green", closed: "gray", completed: "gray", resolved: "gray", fulfilled: "teal", received: "teal",
  draft: "gray", pending: "yellow", submitted: "blue", reviewed: "indigo", proposed: "blue", open: "orange",
  returned: "orange", interview: "blue", offered: "cyan", late: "yellow", probation: "yellow", review: "orange",
  rejected: "red", absent: "red", left: "gray", transferred: "gray", suspended: "red", superseded: "gray",
  over: "red", warning: "yellow", ok: "green", unbudgeted: "grape", repeat: "red", promote: "green",
  complete: "gray", undone: "gray", conflict: "red", part_paid: "yellow", unpaid: "red", on_leave: "yellow",
};

export function statusColor(status: string | null | undefined): string {
  return STATUS_COLORS[(status ?? "").toLowerCase()] ?? "gray";
}
