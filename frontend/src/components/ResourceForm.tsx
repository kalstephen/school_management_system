import {
  Alert,
  Button,
  Checkbox,
  ColorInput,
  FileInput,
  Grid,
  Group,
  Modal,
  MultiSelect,
  NumberInput,
  PasswordInput,
  Select,
  Stack,
  TagsInput,
  Text,
  TextInput,
  Textarea,
} from "@mantine/core";
import { DateInput, DateTimePicker, TimeInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { IconInfoCircle } from "@tabler/icons-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { api, ApiError, errorMessage } from "@/api/client";
import type { Option } from "@/api/types";
import { useOptions, type OptionSource } from "@/hooks/useOptions";

export type FieldType =
  | "text" | "textarea" | "number" | "money" | "date" | "time" | "select" | "multiselect" | "checkbox"
  | "file" | "password" | "email" | "hidden" | "datetime" | "tags" | "color";

export interface Field {
  name: string;
  label: string;
  type?: FieldType;
  required?: boolean;
  /** Fixed options, or options that depend on other values in the form (e.g. streams of the chosen class). */
  options?: Option[] | ((values: Record<string, any>) => Option[]);
  optionsFrom?: OptionSource;
  description?: string;
  placeholder?: string;
  span?: number;
  min?: number;
  max?: number;
  hidden?: (values: Record<string, any>) => boolean;
  /** Clear this field when that one changes (e.g. the sub-category when the category changes). */
  clearWhen?: string;
}

type Values = Record<string, any>;

function FieldInput({ field, value, values, error, onChange }: { field: Field; value: any; values: Values; error?: string; onChange: (v: any) => void }) {
  const { options: loaded } = useOptions(field.optionsFrom, !!field.optionsFrom);
  const options = (typeof field.options === "function" ? field.options(values) : field.options) ?? loaded;
  const common = { label: field.label, description: field.description, error, required: field.required, placeholder: field.placeholder };
  switch (field.type) {
    case "textarea":
      return <Textarea {...common} autosize minRows={3} value={value ?? ""} onChange={(e) => onChange(e.currentTarget.value)} />;
    case "number":
    case "money":
      return (
        <NumberInput
          {...common}
          value={value ?? ""}
          min={field.min}
          max={field.max}
          thousandSeparator={field.type === "money" ? "," : undefined}
          prefix={field.type === "money" ? "UGX " : undefined}
          onChange={(v) => onChange(v === "" ? null : v)}
        />
      );
    case "date":
      return <DateInput {...common} value={value || null} valueFormat="D MMM YYYY" clearable onChange={(v) => onChange(v ?? null)} />;
    case "datetime":
      return <DateTimePicker {...common} value={value || null} valueFormat="D MMM YYYY HH:mm" clearable onChange={(v) => onChange(v ?? null)} />;
    case "time":
      return <TimeInput {...common} value={value ?? ""} onChange={(e) => onChange(e.currentTarget.value)} />;
    case "select":
      return (
        <Select
          {...common}
          data={options}
          searchable
          clearable={!field.required}
          value={value === null || value === undefined ? null : String(value)}
          onChange={(v) => onChange(v)}
          nothingFoundMessage="No matches"
        />
      );
    case "multiselect":
      return (
        <MultiSelect
          {...common}
          data={options}
          searchable
          value={(value ?? []).map(String)}
          onChange={(v) => onChange(v)}
        />
      );
    case "tags":
      return <TagsInput {...common} value={value ?? []} onChange={(v) => onChange(v)} splitChars={[",", " "]} clearable />;
    case "color":
      return (
        <ColorInput
          {...common}
          format="hex"
          value={value ?? ""}
          onChange={(v) => onChange(v)}
          swatches={["#1d4ed8", "#047857", "#b91c1c", "#7c2d12", "#6d28d9", "#0f766e", "#be185d", "#334155"]}
        />
      );
    case "checkbox":
      return <Checkbox mt="lg" label={field.label} description={field.description} checked={!!value} onChange={(e) => onChange(e.currentTarget.checked)} />;
    case "file":
      return <FileInput {...common} clearable value={value instanceof File ? value : null} onChange={onChange} placeholder={typeof value === "string" && value ? "Keep current file" : "Choose a file"} />;
    case "password":
      return <PasswordInput {...common} value={value ?? ""} onChange={(e) => onChange(e.currentTarget.value)} />;
    default:
      return <TextInput {...common} type={field.type === "email" ? "email" : "text"} value={value ?? ""} onChange={(e) => onChange(e.currentTarget.value)} />;
  }
}

function toPayload(fields: Field[], values: Values): FormData | Values {
  const visible = fields.filter((f) => !f.hidden?.(values));
  const hasFile = visible.some((f) => f.type === "file" && values[f.name] instanceof File);
  const clean: Values = {};
  for (const field of visible) {
    let value = values[field.name];
    if (field.type === "file" && !(value instanceof File)) continue;
    if (value === "" && field.type !== "text" && field.type !== "textarea") value = null;
    clean[field.name] = value;
  }
  if (!hasFile) return clean;
  const form = new FormData();
  Object.entries(clean).forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    if (Array.isArray(value)) value.forEach((v) => form.append(key, String(v)));
    else form.append(key, value instanceof File ? value : String(value));
  });
  return form;
}

export interface ResourceFormProps {
  fields: Field[];
  endpoint: string;
  id?: number | string | null;
  initial?: Values;
  submitLabel?: string;
  invalidate?: string[];
  onSaved?: (row: any) => void;
  extra?: ReactNode;
  /** Force a method, e.g. PATCH on a single resource such as /school/. */
  method?: "POST" | "PATCH";
}

export function ResourceForm({ fields, endpoint, id, initial, submitLabel = "Save", invalidate = [], onSaved, extra, method }: ResourceFormProps) {
  const client = useQueryClient();
  const [values, setValues] = useState<Values>(initial ?? {});
  const [errors, setErrors] = useState<Record<string, string>>({});
  useEffect(() => setValues(initial ?? {}), [initial]);

  const mutation = useMutation({
    mutationFn: () =>
      api(id ? `${endpoint}${id}/` : endpoint, { method: method ?? (id ? "PATCH" : "POST"), body: toPayload(fields, values) }),
    onSuccess: (row) => {
      setErrors({});
      [endpoint, ...invalidate].forEach((key) => client.invalidateQueries({ queryKey: ["list", key] }));
      client.invalidateQueries({ queryKey: ["options"] });
      notifications.show({ color: "green", message: "Saved" });
      onSaved?.(row);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.data && typeof error.data === "object" && !error.data.detail) {
        const fieldErrors: Record<string, string> = {};
        Object.entries(error.data).forEach(([key, value]) => {
          fieldErrors[key] = Array.isArray(value) ? value.join(" ") : String(value);
        });
        setErrors(fieldErrors);
        const known = new Set(fields.map((f) => f.name));
        const other = Object.keys(fieldErrors).filter((k) => !known.has(k));
        if (other.length) notifications.show({ color: "red", message: other.map((k) => fieldErrors[k]).join(" ") });
      } else {
        notifications.show({ color: "red", title: "Not saved", message: errorMessage(error) });
      }
    },
  });

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <Stack>
        <Grid>
          {fields
            .filter((field) => !field.hidden?.(values) && field.type !== "hidden")
            .map((field) => (
              <Grid.Col key={field.name} span={{ base: 12, sm: field.span ?? (field.type === "textarea" ? 12 : 6) }}>
                <FieldInput
                  field={field}
                  value={values[field.name]}
                  values={values}
                  error={errors[field.name]}
                  onChange={(value) =>
                    setValues((current) => {
                      const next = { ...current, [field.name]: value };
                      for (const other of fields) if (other.clearWhen === field.name && current[field.name] !== value) next[other.name] = null;
                      return next;
                    })
                  }
                />
              </Grid.Col>
            ))}
        </Grid>
        {extra}
        <Group justify="flex-end">
          <Button type="submit" loading={mutation.isPending}>
            {submitLabel}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function FormModal({
  opened,
  onClose,
  title,
  size = "lg",
  help,
  ...props
}: ResourceFormProps & { opened: boolean; onClose: () => void; title: string; size?: string; help?: ReactNode }) {
  return (
    <Modal opened={opened} onClose={onClose} title={title} size={size} centered>
      {help && (
        <Alert icon={<IconInfoCircle size={18} />} color="blue" variant="light" mb="md" p="sm">
          <Text size="sm">{help}</Text>
        </Alert>
      )}
      <ResourceForm
        {...props}
        onSaved={(row) => {
          props.onSaved?.(row);
          onClose();
        }}
      />
    </Modal>
  );
}
