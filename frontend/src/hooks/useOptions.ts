import { useQuery } from "@tanstack/react-query";

import { get, type Paginated, type Query } from "@/api/client";
import type { Option } from "@/api/types";

export interface OptionSource {
  endpoint: string;
  label: string | ((row: any) => string);
  value?: string;
  query?: Query;
}

/** Load a list endpoint once and turn it into Select options. */
export function useOptions(source: OptionSource | undefined, enabled = true) {
  const { data = [] } = useQuery({
    queryKey: ["options", source?.endpoint, source?.query],
    enabled: !!source && enabled,
    staleTime: 60_000,
    queryFn: async () => {
      const response = await get<Paginated<any> | any[]>(source!.endpoint, { page_size: 500, ...source!.query });
      return Array.isArray(response) ? response : response.results;
    },
  });
  const options: Option[] = data.map((row: any) => ({
    value: String(row[source?.value ?? "id"]),
    label: typeof source?.label === "function" ? source.label(row) : String(row[source?.label ?? "name"] ?? ""),
  }));
  return { options, rows: data };
}
