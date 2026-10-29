import { Alert, Anchor, Box, Button, Center, Group, Paper, PasswordInput, Stack, Text, TextInput, ThemeIcon, Title } from "@mantine/core";
import { IconAlertCircle, IconSchool, IconShieldLock } from "@tabler/icons-react";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";

import { errorMessage } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { BEAM_TEXTURE, BrandStripe, BRAND, SpexLogo, TAGLINE } from "@/components/SpexLogo";

function storedSchoolId(): string {
  try {
    return window.localStorage.getItem("school-code") ?? "";
  } catch {
    return "";
  }
}

function rememberSchoolId(value: string) {
  try {
    window.localStorage.setItem("school-code", value);
  } catch {
    // Private browsing: the School ID simply is not remembered.
  }
}

/**
 * Two separate doors.
 *  - School sign-in (/login): every school user, from general staff to the director. School ID +
 *    username; only that school's modules, never owner rights.
 *  - Owner console (/platform/login): the software owners and developers. Not linked from the
 *    school sign-in, so school users are never pointed at it.
 */
export function LoginPage({ portal = "school" }: { portal?: "school" | "platform" }) {
  const { me, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isPlatform = portal === "platform";
  const [schoolCode, setSchoolCode] = useState(() => (isPlatform ? "" : storedSchoolId()));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const home = isPlatform ? "/platform" : "/";
  const from = (location.state as { from?: string } | null)?.from ?? home;

  // Already signed in through this door: go straight in. Signed in through the other door:
  // show the form, and signing in here replaces that session.
  if (me && me.portal === portal) return <Navigate to={from} replace />;

  return (
    <Box mih="100vh" style={{ display: "flex", flexDirection: "column", background: `${BEAM_TEXTURE}, ${isPlatform ? BRAND.graphite : BRAND.navy}` }}>
    <Center style={{ flex: 1 }} p="md">
      <Stack align="center" gap="lg" w={420} maw="100%">
      <Stack align="center" gap={6}>
        <Link to="/home" aria-label="SPEX School Manager home"><SpexLogo variant="white" height={56} /></Link>
        <Text c="white" fw={700} ff="Montserrat, Inter, sans-serif" tt="uppercase" size="sm" style={{ letterSpacing: "0.22em" }}>
          {isPlatform ? "School Manager · Owner console" : "School Manager"}
        </Text>
        <Text c={BRAND.amber} fw={600} size="sm">{TAGLINE}</Text>
      </Stack>
      <Paper w="100%" p="xl" radius="lg" shadow="xl" withBorder={false}>
        <Stack gap="lg">
          <Group gap="sm">
            <ThemeIcon size={48} radius="md" color={isPlatform ? "dark" : "navy.8"}>
              {isPlatform ? <IconShieldLock size={28} /> : <IconSchool size={28} />}
            </ThemeIcon>
            <Box>
              <Title order={3}>{isPlatform ? "Owner console" : "School sign-in"}</Title>
              <Text size="sm" c="dimmed">
                {isPlatform ? "For the software owners and developers only" : "Academics, operations and expenditure"}
              </Text>
            </Box>
          </Group>
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              setError(null);
              try {
                await login(username.trim(), password, isPlatform ? undefined : schoolCode.trim(), portal);
                if (!isPlatform) rememberSchoolId(schoolCode.trim());
                navigate(from === "/login" || from === "/platform/login" ? home : from, { replace: true });
              } catch (err) {
                setError(errorMessage(err));
              } finally {
                setBusy(false);
              }
            }}
          >
            <Stack>
              {error && (
                <Alert color="red" icon={<IconAlertCircle size={18} />}>
                  {error}
                </Alert>
              )}
              {!isPlatform && (
                <TextInput
                  label="School ID"
                  description="Given to your school, e.g. NewHope-003"
                  placeholder="NewHope-003"
                  required
                  value={schoolCode}
                  onChange={(e) => setSchoolCode(e.currentTarget.value)}
                  autoFocus={!schoolCode}
                />
              )}
              <TextInput
                label="Username"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.currentTarget.value)}
                autoFocus={isPlatform || !!schoolCode}
              />
              <PasswordInput label="Password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.currentTarget.value)} />
              <Button type="submit" loading={busy} size="md" fullWidth color={isPlatform ? "dark" : "brand.7"}>
                Sign in
              </Button>
            </Stack>
          </form>
          <Text size="xs" c="dimmed" ta="center">
            {isPlatform ? (
              <>
                School users sign in on the <Anchor component={Link} to="/login" size="xs">school sign-in page</Anchor>.
              </>
            ) : (
              <>
                Forgot your password? Ask your school administrator. Fees are handled in SchoolPay, not here.
              </>
            )}
          </Text>
        </Stack>
      </Paper>
      {!isPlatform && (
        <Group gap="lg">
          <Anchor component={Link} to="/home" c="rgba(255,255,255,0.8)" size="sm">About SPEX School Manager</Anchor>
          <Anchor component={Link} to="/join" c={BRAND.amber} size="sm" fw={600}>New school? Request access</Anchor>
        </Group>
      )}
      </Stack>
    </Center>
    <BrandStripe height={6} />
    </Box>
  );
}
