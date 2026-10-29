import { useQuery } from "@tanstack/react-query";

import { get, type Paginated } from "@/api/client";
import type { Option, SchoolClass, Term } from "@/api/types";

export function useTerms() {
  const { data } = useQuery({
    queryKey: ["terms"],
    staleTime: 5 * 60_000,
    queryFn: () => get<Paginated<Term>>("/terms/", { page_size: 100 }),
  });
  const terms = data?.results ?? [];
  const options: Option[] = terms.map((t) => ({ value: String(t.id), label: t.label }));
  return { terms, options };
}

export function useYears() {
  const { data } = useQuery({
    queryKey: ["academic-years"],
    staleTime: 5 * 60_000,
    queryFn: () => get<Paginated<{ id: number; name: string; is_current: boolean }>>("/academic-years/", { page_size: 50 }),
  });
  const years = data?.results ?? [];
  const options: Option[] = years.map((y) => ({ value: String(y.id), label: y.name + (y.is_current ? " (current)" : "") }));
  const current = years.find((y) => y.is_current) ?? years[0] ?? null;
  return { years, options, current };
}

export function useCurrentTerm() {
  return useQuery({ queryKey: ["current-term"], queryFn: () => get<Term | null>("/current-term/"), staleTime: 5 * 60_000 }).data ?? null;
}

export function useClasses() {
  const { data } = useQuery({
    queryKey: ["classes"],
    staleTime: 5 * 60_000,
    queryFn: () => get<Paginated<SchoolClass>>("/classes/", { page_size: 200 }),
  });
  const classes = data?.results ?? [];
  const options: Option[] = classes.map((c) => ({ value: String(c.id), label: c.name }));
  const streamOptions = (classId: string | null): Option[] =>
    classes.find((c) => String(c.id) === classId)?.streams.map((s) => ({ value: String(s.id), label: s.label })) ?? [];
  return { classes, options, streamOptions };
}

export const SEX_OPTIONS: Option[] = [
  { value: "F", label: "Female" },
  { value: "M", label: "Male" },
];
