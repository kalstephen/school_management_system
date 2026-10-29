import { Alert, Badge, Button, Card, Grid, Group, Stack, Text } from "@mantine/core";
import { IconEye, IconInfoCircle } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { get, openFile } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { ResourceForm } from "@/components/ResourceForm";

export const REPORT_TEMPLATES: Record<string, { label: string; description: string }> = {
  classic: { label: "Classic", description: "Centred letterhead with a double rule and double-line page frame. Traditional and formal." },
  modern: { label: "Modern banner", description: "A full-width band in the school colour with the logo and learner photo." },
  prestige: { label: "Prestige letterhead", description: "A curved colour sweep with gold accents, framed page and crest; the most formal look." },
  compact: { label: "Compact", description: "Smaller type with the comments side by side; long subject lists fit on one page." },
};

/** The school's report card look: design, colour, logo, learner photo and footer. All of it is
 * set in the owner console; the school sees it and previews a sample card. */
export function ReportDesign() {
  const client = useQueryClient();
  const { can } = useAuth();
  const { data: school } = useQuery({ queryKey: ["school"], queryFn: () => get("/school/") });
  if (!school) return null;
  const current = REPORT_TEMPLATES[school.report_template] ?? REPORT_TEMPLATES.classic;
  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 7 }}>
        <Card>
          <Text fw={650} mb="sm">Colour, logo and footer</Text>
          {!can("setup.platform") ? (
            <Stack gap="xs">
              <Group gap="xs">
                <div style={{ width: 18, height: 18, borderRadius: 4, background: school.report_color }} />
                <Text size="sm">{school.report_color}</Text>
              </Group>
              <Text size="sm">Footer: {school.report_card_footer || "–"}</Text>
              <Text size="xs" c="dimmed">Set by your system provider. Contact them to change the colour, logo or footer.</Text>
            </Stack>
          ) : (
          <ResourceForm
            endpoint="/school/"
            method="PATCH"
            initial={school}
            onSaved={() => client.invalidateQueries({ queryKey: ["school"] })}
            fields={[
              { name: "report_color", label: "Report card colour", type: "color", description: "Used for headings and table borders. Pick your school colour.", placeholder: "#1d4ed8" },
              { name: "logo", label: "School logo / crest", type: "file", description: "A PNG or JPG, ideally square." },
              { name: "report_card_footer", label: "Footer line", placeholder: "e.g. Fees are paid through SchoolPay.", span: 12 },
              { name: "report_show_photo", label: "Print the learner's photo (when one is on file)", type: "checkbox", span: 12 },
            ]}
          />
          )}
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 5 }}>
        <Stack>
          <Card>
            <Group justify="space-between" mb="xs">
              <Text fw={650}>Design in use</Text>
              <Badge size="lg" variant="light">{current.label}</Badge>
            </Group>
            <Text size="sm" c="dimmed" mb="md">{current.description}</Text>
            <Button leftSection={<IconEye size={16} />} variant="light" onClick={() => openFile("/school/report-preview/", { t: Date.now() })}>
              Preview a sample report card
            </Button>
          </Card>
          <Alert icon={<IconInfoCircle size={18} />} color="gray" title="Other designs">
            <Stack gap={6}>
              {Object.entries(REPORT_TEMPLATES).map(([key, t]) => (
                <Text size="sm" key={key}>
                  <b>{t.label}</b> — {t.description}
                </Text>
              ))}
              <Text size="sm" mt={4}>To change the design, agree it with your system provider; they switch it for you.</Text>
            </Stack>
          </Alert>
        </Stack>
      </Grid.Col>
    </Grid>
  );
}
