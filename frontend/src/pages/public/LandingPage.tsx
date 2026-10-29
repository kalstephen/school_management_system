import { Badge, Box, Button, Container, Grid, Group, Paper, SimpleGrid, Stack, Text, ThemeIcon, Title } from "@mantine/core";
import {
  IconCalendarCheck,
  IconCalendarTime,
  IconCertificate,
  IconChartBar,
  IconCloudOff,
  IconFileSpreadsheet,
  IconListCheck,
  IconLock,
  IconReceipt2,
  IconSchool,
  IconStairsUp,
  IconUsersGroup,
} from "@tabler/icons-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { BEAM_TEXTURE, BrandStripe, BRAND, SpexSymbol, TAGLINE } from "@/components/SpexLogo";

import { PublicLayout } from "./PublicLayout";
import { ApprovalVisual, HeroVisual, RegisterVisual, ReportCardVisual } from "./Visuals";

const BEAMS = [BRAND.blue, BRAND.violet, BRAND.amber, BRAND.teal];
// Darker text shades of the beam colours, for icons on light tiles.
const SHADES = ["#1565C0", "#6A3DE8", "#9A5B00", "#0A7F8E"];

const FEATURES: { icon: typeof IconSchool; title: string; text: string }[] = [
  { icon: IconSchool, title: "Set up for you", text: "We set up your levels, classes, streams, subjects, terms and grading on Ugandan defaults. Your staff start working on day one." },
  { icon: IconFileSpreadsheet, title: "Enrol a whole class at once", text: "Fill one Excel template and import it, or use the form. Parents, health notes and admission numbers are handled for you." },
  { icon: IconCalendarCheck, title: "Daily register", text: "The class teacher marks the register on a phone in a minute, even offline. Weekends, public holidays and holidays are skipped." },
  { icon: IconListCheck, title: "Marks with approval", text: "Teachers enter marks, the DOS approves and locks them. Every change is recorded, so results can be trusted." },
  { icon: IconCertificate, title: "Professional report cards", text: "Letterhead designs in your school colours with your crest, graded and charted, each with a serial number and QR check." },
  { icon: IconChartBar, title: "Ugandan grading built in", text: "PLE aggregates and divisions, the new O-Level CBC, UCE and UACE. Your school can adjust its own cut-offs." },
  { icon: IconStairsUp, title: "Promotion with three checks", text: "Lists of who passed and who is below the mark go from class teacher to DOS to director before anyone moves up." },
  { icon: IconCalendarTime, title: "Timetables and exams", text: "The DOS builds class and exam timetables and publishes them; teachers see their own lessons and download PDFs." },
  { icon: IconUsersGroup, title: "Staff and weekly planner", text: "Staff records, sign-ins by role, duty rosters, leave and a weekly to-do planner for every teacher." },
  { icon: IconReceipt2, title: "School spending", text: "Expenses, budgets and approvals up to the director. Fees stay in SchoolPay; we do not collect them." },
  { icon: IconCloudOff, title: "Works when the internet doesn't", text: "Roll call and mark entry save on the phone and send themselves when the connection returns." },
  { icon: IconLock, title: "Right access for each person", text: "From general staff to the director, each person sees only what their role needs. Health records stay with the nurse." },
];

function Section({ id, eyebrow, title, intro, children, dark }: { id?: string; eyebrow: string; title: string; intro?: string; children: ReactNode; dark?: boolean }) {
  return (
    <Box id={id} py={{ base: 56, md: 88 }} style={dark ? { background: `${BEAM_TEXTURE}, ${BRAND.navy}` } : undefined} bg={dark ? undefined : "white"}>
      <Container size="lg">
        <Text size="xs" fw={700} tt="uppercase" c={dark ? BRAND.amber : "#1565C0"} style={{ letterSpacing: "0.2em" }}>{eyebrow}</Text>
        <Title order={2} mt={6} c={dark ? "white" : BRAND.navy} maw={720} fz={{ base: 28, md: 36 }}>{title}</Title>
        {intro && <Text mt="sm" c={dark ? "rgba(255,255,255,0.8)" : "dimmed"} maw={680} size="lg">{intro}</Text>}
        <Box mt={40}>{children}</Box>
      </Container>
    </Box>
  );
}

export default function LandingPage() {
  return (
    <PublicLayout>
      {/* Hero */}
      <Box pos="relative" style={{ background: `${BEAM_TEXTURE}, ${BRAND.navy}`, overflow: "hidden" }}>
        <Box pos="absolute" right={-120} top={-80} style={{ opacity: 0.18, pointerEvents: "none" }} visibleFrom="md">
          <SpexSymbol size={520} tile={false} />
        </Box>
        <Container size="lg" py={{ base: 56, md: 96 }} pos="relative">
          <Grid gap={48} align="center">
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Text size="xs" fw={700} tt="uppercase" c={BRAND.amber} style={{ letterSpacing: "0.22em" }}>SPEX School Manager</Text>
              <Title order={1} c="white" mt="sm" fz={{ base: 36, md: 52 }} lh={1.08}>
                Your whole school, in one place.
              </Title>
              <Text c="rgba(255,255,255,0.82)" size="lg" mt="lg" maw={520}>
                Registers, marks, report cards, promotion, timetables and spending for Ugandan nursery, primary and secondary
                schools. Set up for you, ready from the first day of term.
              </Text>
              <Group mt={32} gap="sm">
                <Button component={Link} to="/join" size="lg" color="brand.7">Request access</Button>
                <Button component={Link} to="/join?kind=demo" size="lg" variant="white" color="navy.8">Book a demo</Button>
              </Group>
              <Group mt="lg" gap="xs">
                <Text size="sm" c="rgba(255,255,255,0.7)">Already using it?</Text>
                <Button component={Link} to="/login" variant="subtle" color="gray.0" size="compact-sm">Sign in to your school →</Button>
              </Group>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <HeroVisual />
            </Grid.Col>
          </Grid>
        </Container>
        <BrandStripe height={6} />
      </Box>

      {/* Built for Uganda */}
      <Box bg="white" py={28} style={{ borderBottom: `1px solid #e5e9f0` }}>
        <Container size="lg">
          <SimpleGrid cols={{ base: 2, md: 4 }} spacing="lg">
            {[["PLE · UCE · UACE", "and the new CBC"], ["Term 1 · 2 · 3", "on the MoES calendar"], ["Public holidays", "skipped in the register"], ["No fees module", "SchoolPay stays as it is"]].map(([a, b], i) => (
              <Stack key={a} gap={0} style={{ borderLeft: `4px solid ${BEAMS[i]}` }} pl="md">
                <Text fw={800} ff="Montserrat, sans-serif" c={BRAND.navy}>{a}</Text>
                <Text size="sm" c="dimmed">{b}</Text>
              </Stack>
            ))}
          </SimpleGrid>
        </Container>
      </Box>

      {/* Features */}
      <Section id="features" eyebrow="Features" title="Everything the school office and the classroom need" intro="Each school gets the modules it chooses. These come standard; library, sickbay and stores can be added.">
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="lg">
          {FEATURES.map((f, i) => (
            <Paper key={f.title} p="lg" radius="lg" withBorder style={{ borderTop: `4px solid ${BEAMS[i % 4]}` }}>
              <ThemeIcon size={46} radius="md" variant="light" style={{ background: `${BEAMS[i % 4]}1f`, color: SHADES[i % 4] }}>
                <f.icon size={24} stroke={1.8} />
              </ThemeIcon>
              <Text fw={700} ff="Montserrat, sans-serif" mt="md" c={BRAND.navy}>{f.title}</Text>
              <Text size="sm" c="dimmed" mt={6}>{f.text}</Text>
            </Paper>
          ))}
        </SimpleGrid>
      </Section>

      {/* How it works */}
      <Box id="how" bg={BRAND.cloud} py={{ base: 56, md: 88 }}>
        <Container size="lg">
          <Text size="xs" fw={700} tt="uppercase" c="#1565C0" style={{ letterSpacing: "0.2em" }}>How it works</Text>
          <Title order={2} mt={6} c={BRAND.navy} fz={{ base: 28, md: 36 }}>From the register to the report card</Title>
          <Stack gap={72} mt={48}>
            {[
              { badge: "Every school day", title: "The register takes a minute", text: "The class teacher opens the class on a phone, taps P or A and saves. The month view shows every learner and day, with holidays shaded and any missing registers flagged. Learners absent three days in a row are flagged for follow-up.", visual: <RegisterVisual /> },
              { badge: "Every exam", title: "Marks are entered, checked and locked", text: "Class and subject teachers enter marks; the DOS approves them and they lock. Continuous assessment and end-of-term exams are weighted (for example BOT 20, MOT 30, EOT 50) so every class adds up the same way.", visual: <ApprovalVisual /> },
              { badge: "End of term", title: "Report cards your parents will keep", text: "One press prepares the whole class: grades, aggregates and divisions, positions, attendance and comments, on a letterhead in your school colours. Each card carries a QR code anyone can scan to confirm it is genuine.", visual: <ReportCardVisual /> },
            ].map((step, i) => (
              <Grid key={step.title} gap={48} align="center">
                <Grid.Col span={{ base: 12, md: 6 }} order={{ base: 1, md: i % 2 ? 2 : 1 }}>
                  <Badge variant="light" color={["brand", "violet", "orange"][i]} size="lg">{step.badge}</Badge>
                  <Title order={3} mt="md" c={BRAND.navy} fz={26}>{step.title}</Title>
                  <Text mt="sm" c="dimmed" size="lg">{step.text}</Text>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }} order={{ base: 2, md: i % 2 ? 1 : 2 }}>{step.visual}</Grid.Col>
              </Grid>
            ))}
          </Stack>
        </Container>
      </Box>

      {/* About */}
      <Section id="about" eyebrow="About us" title="Built in Uganda by SPEX" dark>
        <Grid gap={48}>
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Stack gap="md">
              <Text c="rgba(255,255,255,0.85)" size="lg">
                SPEX (said “specs”) is Security, Power &amp; Engineering Experts Limited, based in Seeta–Mukono. SPEX Labs, our
                software division, builds SPEX School Manager with Ugandan head teachers, directors of studies and class teachers.
              </Text>
              <Text c="rgba(255,255,255,0.85)" size="lg">
                We set the system up for your school, train your staff and stay on call. Your records belong to your school: each
                school's data is kept apart, every change is logged, and our team can only look in when your school grants
                support access, for a limited time.
              </Text>
              <Group gap="xs" mt="sm">
                {["Reliability", "Integrity", "Privacy", "Responsiveness", "Local innovation"].map((v) => (
                  <Badge key={v} size="lg" variant="outline" color="gray.0" radius="xl">{v}</Badge>
                ))}
              </Group>
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 5 }}>
            <Paper radius="lg" p="xl" withBorder={false} bg="rgba(255,255,255,0.06)" style={{ border: "1px solid rgba(255,255,255,0.12)" }}>
              <Text fw={700} c={BRAND.amber} size="xs" tt="uppercase" style={{ letterSpacing: "0.2em" }}>Our promise</Text>
              <Text c="white" fw={700} ff="Montserrat, sans-serif" fz={22} mt="sm" lh={1.3}>
                Your school's system stays working, and SPEX stays accountable for it.
              </Text>
              <Stack gap={8} mt="lg">
                {["Set-up done for you before term starts", "Staff training at your school", "Same-day answers to support calls"].map((t) => (
                  <Text key={t} c="rgba(255,255,255,0.85)" size="sm">✓ {t}</Text>
                ))}
              </Stack>
            </Paper>
          </Grid.Col>
        </Grid>
      </Section>

      {/* Call to action */}
      <Box bg="white" py={{ base: 56, md: 80 }}>
        <Container size="md">
          <Paper radius="xl" p={{ base: "xl", md: 48 }} withBorder={false} style={{ background: "#1565C0" }} pos="relative">
            <Grid align="center" gap="xl">
              <Grid.Col span={{ base: 12, md: 8 }}>
                <Title order={2} c="white" fz={{ base: 26, md: 32 }}>Ready to see it with your school's own classes?</Title>
                <Text c="rgba(255,255,255,0.85)" mt="sm">Tell us about your school. We will call you to arrange a demo or get you set up.</Text>
              </Grid.Col>
              <Grid.Col span={{ base: 12, md: 4 }}>
                <Stack>
                  <Button component={Link} to="/join" size="lg" variant="white" color="navy.8">Request access</Button>
                  <Text c={BRAND.amber} fw={700} ta="center" size="sm">{TAGLINE}</Text>
                </Stack>
              </Grid.Col>
            </Grid>
          </Paper>
        </Container>
      </Box>
    </PublicLayout>
  );
}
