import { Box, Group, Paper, SimpleGrid, Stack, Text } from "@mantine/core";
import { IconCheck } from "@tabler/icons-react";
import type { CSSProperties, ReactNode } from "react";

import { BrandStripe, BRAND, SpexSymbol } from "@/components/SpexLogo";

/** Illustrations for the public pages, drawn with the brand colours (no photos of people). */

function Window({ title, children, style }: { title: string; children: ReactNode; style?: CSSProperties }) {
  return (
    <Paper shadow="xl" radius="lg" withBorder={false} style={{ overflow: "hidden", ...style }}>
      <Group gap={6} px="sm" h={30} bg="#e9edf3">
        {["#f87171", "#fbbf24", "#34d399"].map((c) => <Box key={c} w={9} h={9} style={{ borderRadius: 9, background: c }} />)}
        <Text size="10px" c="dimmed" ml="xs">{title}</Text>
      </Group>
      {children}
    </Paper>
  );
}

const bar = (w: string, c: string, h = 8) => <Box h={h} w={w} style={{ borderRadius: 4, background: c }} />;

/** A dashboard on a laptop with a phone taking the register in front of it. */
export function HeroVisual() {
  return (
    <Box pos="relative" maw={560} mx="auto" pb={40}>
      <Window title="SPEX School Manager · Dashboard">
        <Group gap={0} wrap="nowrap" align="stretch">
          <Box w={84} bg={BRAND.navy} p={10}>
            <SpexSymbol size={26} />
            <Stack gap={8} mt={14}>
              {[0, 1, 2, 3, 4, 5].map((i) => bar(i === 1 ? "100%" : "70%", i === 1 ? BRAND.blue : "rgba(255,255,255,0.25)", 6))}
            </Stack>
          </Box>
          <Box p="md" style={{ flex: 1 }} bg="white">
            <SimpleGrid cols={3} spacing={8}>
              {[["Learners", "642", BRAND.blue], ["Present today", "96%", BRAND.teal], ["Marks approved", "38/40", BRAND.violet]].map(([label, value, color]) => (
                <Box key={label} p={8} style={{ borderRadius: 8, background: BRAND.cloud, borderTop: `3px solid ${color}` }}>
                  <Text size="9px" c="dimmed">{label}</Text>
                  <Text fw={800} size="lg" ff="Montserrat, sans-serif" c={BRAND.navy}>{value}</Text>
                </Box>
              ))}
            </SimpleGrid>
            <Text size="10px" fw={700} mt="sm" mb={6} c={BRAND.navy}>Average by class</Text>
            <Group align="flex-end" gap={10} h={86}>
              {[62, 74, 58, 81, 69, 77, 88].map((v, i) => (
                <Stack key={i} gap={3} align="center" style={{ flex: 1 }}>
                  <Box w="100%" h={v} style={{ borderRadius: "4px 4px 0 0", background: [BRAND.blue, BRAND.violet, BRAND.amber, BRAND.teal][i % 4] }} />
                  <Text size="8px" c="dimmed">P{i + 1}</Text>
                </Stack>
              ))}
            </Group>
          </Box>
        </Group>
      </Window>
      <Paper
        shadow="xl"
        radius={22}
        withBorder={false}
        w={150}
        p={8}
        pos="absolute"
        right={-10}
        bottom={0}
        style={{ border: `6px solid ${BRAND.graphite}`, background: "white" }}
      >
        <Text size="9px" fw={700} c={BRAND.navy}>Roll call · P4 East</Text>
        <Stack gap={5} mt={6}>
          {["Aisha N.", "Brian O.", "Joan A.", "Peter K.", "Ruth M."].map((name, i) => (
            <Group key={name} justify="space-between" wrap="nowrap">
              <Text size="8px">{name}</Text>
              <Box px={5} style={{ borderRadius: 4, background: i === 2 ? "#fde2e2" : "#dcfce7" }}>
                <Text size="8px" fw={700} c={i === 2 ? "red.7" : "green.8"}>{i === 2 ? "A" : "P"}</Text>
              </Box>
            </Group>
          ))}
        </Stack>
        <Box mt={8} py={4} style={{ borderRadius: 6, background: "#1565c0", textAlign: "center" }}>
          <Text size="8px" c="white" fw={700}>Save register</Text>
        </Box>
      </Paper>
    </Box>
  );
}

/** A report card with letterhead, colour-coded grades, a bar chart and the QR code. */
export function ReportCardVisual() {
  const rows: [string, number, string][] = [["English", 78, "D2"], ["Mathematics", 84, "D2"], ["Science", 69, "C3"], ["Social Studies", 73, "C3"]];
  return (
    <Paper shadow="lg" radius="md" p="md" withBorder={false} maw={360} mx="auto" style={{ border: `2px solid ${BRAND.navy}` }}>
      <Group justify="space-between" wrap="nowrap">
        <Box w={30} h={30} style={{ borderRadius: 30, background: BRAND.cloud, border: `2px solid ${BRAND.amber}` }} />
        <Stack gap={0} align="center">
          <Text fw={800} size="sm" ff="Montserrat, sans-serif" c={BRAND.navy}>YOUR SCHOOL NAME</Text>
          <Text size="9px" c="dimmed" fs="italic">School motto</Text>
        </Stack>
        <Box w={30} h={30} style={{ borderRadius: 6, background: BRAND.cloud }} />
      </Group>
      <Box my={8} py={3} style={{ background: BRAND.navy, textAlign: "center", borderRadius: 3 }}>
        <Text size="9px" c="white" fw={700}>TERMLY REPORT · TERM 3</Text>
      </Box>
      <Stack gap={4}>
        {rows.map(([s, v, g]) => (
          <Group key={s} justify="space-between" wrap="nowrap" gap={6}>
            <Text size="10px" w={90}>{s}</Text>
            <Box style={{ flex: 1, height: 7, borderRadius: 4, background: BRAND.cloud }}>
              <Box h={7} w={`${v}%`} style={{ borderRadius: 4, background: v >= 80 ? "#15803d" : "#1d4ed8" }} />
            </Box>
            <Text size="10px" fw={700} c={v >= 80 ? "green.8" : "blue.7"} w={34} ta="right">{v} {g}</Text>
          </Group>
        ))}
      </Stack>
      <Group justify="space-between" mt={10} align="flex-end">
        <Group gap={6}>
          {[["Aggregate", "10"], ["Division", "I"]].map(([l, v]) => (
            <Box key={l} px={8} py={4} style={{ borderRadius: 6, background: "#e8f3fd" }}>
              <Text size="8px" c="dimmed">{l}</Text>
              <Text fw={800} c="#1565c0" size="sm">{v}</Text>
            </Box>
          ))}
        </Group>
        <Box w={40} h={40} p={3} style={{ border: `1px solid ${BRAND.navy}`, borderRadius: 4 }}>
          <SimpleGrid cols={5} spacing={1}>
            {Array.from({ length: 25 }, (_, i) => <Box key={i} h={6} bg={(i * 7) % 3 ? BRAND.navy : "white"} />)}
          </SimpleGrid>
        </Box>
      </Group>
      <BrandStripe height={4} style={{ marginTop: 10, borderRadius: 2 }} />
    </Paper>
  );
}

/** A month of the class register: weekends and a public holiday shaded. */
export function RegisterVisual() {
  const days = Array.from({ length: 14 }, (_, i) => i + 1);
  const off = (d: number) => d % 7 === 6 || d % 7 === 0 || d === 9;
  return (
    <Paper shadow="lg" radius="md" p="md" withBorder={false} maw={380} mx="auto">
      <Text size="xs" fw={700} c={BRAND.navy} mb={8}>P4 East · October</Text>
      <Box style={{ display: "grid", gridTemplateColumns: `70px repeat(${days.length}, 1fr)`, gap: 2 }}>
        <span />
        {days.map((d) => (
          <Text key={d} size="8px" ta="center" fw={700} c={d === 9 ? "orange.8" : "dimmed"}>{d}</Text>
        ))}
        {["Aisha", "Brian", "Joan", "Peter", "Ruth"].map((name, r) => (
          <Box key={name} style={{ display: "contents" }}>
            <Text size="9px">{name}</Text>
            {days.map((d) => (
              <Box key={d} h={14} style={{ borderRadius: 2, background: off(d) ? "#e2e8f0" : "transparent", textAlign: "center" }}>
                {!off(d) && (
                  <Text size="9px" fw={800} c={(r + d) % 11 === 0 ? "red.7" : "green.7"} lh="14px">{(r + d) % 11 === 0 ? "A" : "✓"}</Text>
                )}
              </Box>
            ))}
          </Box>
        ))}
      </Box>
      <Text size="9px" c="dimmed" mt={8}>Grey: weekends and Independence Day (9 Oct). No register on those days.</Text>
    </Paper>
  );
}

/** Marks and promotion pass through clear desks. */
export function ApprovalVisual() {
  const steps = [
    { who: "Class teacher", what: "Enters marks", color: BRAND.blue },
    { who: "DOS", what: "Approves & locks", color: BRAND.violet },
    { who: "Head teacher", what: "Publishes reports", color: BRAND.amber },
  ];
  return (
    <Stack gap={10} maw={360} mx="auto">
      {steps.map((s, i) => (
        <Paper key={s.who} shadow="md" radius="md" p="sm" withBorder={false} style={{ borderLeft: `5px solid ${s.color}` }}>
          <Group justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap">
              <Box w={34} h={34} style={{ borderRadius: 34, background: s.color, display: "grid", placeItems: "center" }}>
                <Text c="white" fw={800} size="sm">{i + 1}</Text>
              </Box>
              <div>
                <Text fw={700} size="sm" c={BRAND.navy}>{s.who}</Text>
                <Text size="xs" c="dimmed">{s.what}</Text>
              </div>
            </Group>
            <Box w={22} h={22} style={{ borderRadius: 22, background: "#dcfce7", display: "grid", placeItems: "center" }}>
              <IconCheck size={14} color="#15803d" />
            </Box>
          </Group>
        </Paper>
      ))}
    </Stack>
  );
}
