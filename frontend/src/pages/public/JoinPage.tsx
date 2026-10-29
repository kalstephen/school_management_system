import { Alert, Box, Button, Container, Grid, Group, NumberInput, Paper, SegmentedControl, Select, SimpleGrid, Stack, Text, Textarea, TextInput, ThemeIcon, Title } from "@mantine/core";
import { IconCircleCheck, IconHeadset, IconPresentation, IconSchool } from "@tabler/icons-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { ApiError, errorMessage, post } from "@/api/client";
import { BRAND } from "@/components/SpexLogo";

import { PublicLayout } from "./PublicLayout";

const KINDS = [
  { value: "join", label: "Register our school" },
  { value: "demo", label: "Book a demo" },
  { value: "info", label: "More information" },
];
const ROLES = ["Director / proprietor", "Head teacher", "Deputy / Director of Studies", "Bursar", "Teacher", "Other"];

/** "Request access": a school asks to join, for a demo or for information. The request goes
 *  to the SPEX team in the owner console (and by email), who call the school back. */
export default function JoinPage() {
  const [params] = useSearchParams();
  const [values, setValues] = useState<Record<string, any>>({
    kind: KINDS.some((k) => k.value === params.get("kind")) ? params.get("kind") : "join",
    website: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const set = (key: string) => (value: any) => setValues((v) => ({ ...v, [key]: value }));
  const text = (key: string, label: string, props: Record<string, any> = {}) => (
    <TextInput label={label} value={values[key] ?? ""} onChange={(e) => set(key)(e.currentTarget.value)} error={errors[key]} {...props} />
  );

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    try {
      const result = await post("/public/access-requests/", { ...values, learners: values.learners || null });
      setErrors({});
      setDone(result.reference ?? "");
    } catch (error) {
      if (error instanceof ApiError && error.status === 400 && error.data && typeof error.data === "object") {
        const e: Record<string, string> = {};
        Object.entries(error.data).forEach(([k, v]) => (e[k] = Array.isArray(v) ? v.join(" ") : String(v)));
        setErrors(e);
        setProblem("Please check the highlighted fields.");
      } else if (error instanceof ApiError && error.status === 429) {
        setProblem("We have received several requests from this connection. Please email info@spex.co.ug instead.");
      } else {
        setProblem(errorMessage(error));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <PublicLayout>
      <Container size="lg" py={{ base: 40, md: 72 }}>
        <Grid gap={48}>
          <Grid.Col span={{ base: 12, md: 5 }}>
            <Text size="xs" fw={700} tt="uppercase" c="#1565C0" style={{ letterSpacing: "0.2em" }}>Request access</Text>
            <Title order={1} c={BRAND.navy} mt={6} fz={{ base: 30, md: 40 }}>Bring SPEX School Manager to your school</Title>
            <Text c="dimmed" size="lg" mt="md">
              Tell us a little about your school. The SPEX team receives your request straight away and calls you back to arrange
              a demo, answer questions or set your school up.
            </Text>
            <Stack gap="lg" mt={36}>
              {[
                { icon: IconSchool, color: "#1565C0", title: "Register your school", text: "We set up your classes, terms, subjects and grading, then create your administrators' sign-ins." },
                { icon: IconPresentation, color: "#6A3DE8", title: "See a live demo", text: "At your school or at the SPEX office in Seeta–Mukono, with sample classes." },
                { icon: IconHeadset, color: "#0A7F8E", title: "Ask anything", text: "Modules, pricing per term, training and support." },
              ].map((item) => (
                <Group key={item.title} align="flex-start" wrap="nowrap" gap="md">
                  <ThemeIcon size={42} radius="md" variant="light" style={{ color: item.color, background: `${item.color}1a` }}>
                    <item.icon size={22} />
                  </ThemeIcon>
                  <div>
                    <Text fw={700} c={BRAND.navy}>{item.title}</Text>
                    <Text size="sm" c="dimmed">{item.text}</Text>
                  </div>
                </Group>
              ))}
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Paper p={{ base: "lg", md: 36 }} radius="lg" shadow="md" withBorder={false} style={{ borderTop: `5px solid ${BRAND.blue}` }}>
              {done !== null ? (
                <Stack align="center" py="xl" gap="sm" ta="center">
                  <IconCircleCheck size={56} color="#15803d" />
                  <Title order={3} c={BRAND.navy}>Thank you, we have your request</Title>
                  <Text c="dimmed" maw={420}>
                    The SPEX team will call you on {values.phone} soon{values.email ? ` and may also email ${values.email}` : ""}.
                    {done && <> Your reference is <b>{done}</b>.</>}
                  </Text>
                  <Group mt="md">
                    <Button component={Link} to="/home" variant="default">Back to the home page</Button>
                  </Group>
                </Stack>
              ) : (
                <form onSubmit={submit}>
                  <Stack>
                    <Box>
                      <Text size="sm" fw={600} mb={6}>What would you like?</Text>
                      <SegmentedControl fullWidth data={KINDS} value={values.kind} onChange={set("kind")} color="brand.7" />
                    </Box>
                    <SimpleGrid cols={{ base: 1, sm: 2 }}>
                      {text("school_name", "School name", { required: true, placeholder: "e.g. Seeta Hill Primary School" })}
                      {text("district", "District", { placeholder: "e.g. Mukono" })}
                      {text("contact_name", "Your name", { required: true })}
                      <Select label="Your role" data={ROLES} value={values.role ?? null} onChange={set("role")} error={errors.role} placeholder="Choose" clearable />
                      {text("phone", "Phone / WhatsApp", { required: true, placeholder: "e.g. 0772 123456" })}
                      {text("email", "Email", { type: "email", placeholder: "Optional" })}
                      <Select
                        label="Levels you teach"
                        data={["Nursery", "Primary", "Nursery and primary", "O-Level", "O and A-Level", "Nursery to A-Level"]}
                        value={values.levels ?? null}
                        onChange={set("levels")}
                        placeholder="Choose"
                        clearable
                      />
                      <NumberInput label="Number of learners (about)" value={values.learners ?? ""} onChange={set("learners")} min={1} max={20000} placeholder="e.g. 450" error={errors.learners} />
                    </SimpleGrid>
                    <Textarea label="Message" placeholder="Anything we should know: modules you need, a good time to call…" autosize minRows={3} value={values.message ?? ""} onChange={(e) => set("message")(e.currentTarget.value)} />
                    {/* Hidden from people; automated spam fills it in and is dropped. */}
                    <Box style={{ position: "absolute", left: -10000, width: 1, height: 1, overflow: "hidden" }} aria-hidden>
                      <TextInput label="Website" tabIndex={-1} autoComplete="off" value={values.website} onChange={(e) => set("website")(e.currentTarget.value)} />
                    </Box>
                    {problem && <Alert color="red">{problem}</Alert>}
                    <Button type="submit" size="lg" color="brand.7" loading={busy}>Send request</Button>
                    <Text size="xs" c="dimmed" ta="center">
                      We use these details only to contact you about SPEX School Manager. Already a user? <Link to="/login">Sign in</Link>.
                    </Text>
                  </Stack>
                </form>
              )}
            </Paper>
          </Grid.Col>
        </Grid>
      </Container>
    </PublicLayout>
  );
}
