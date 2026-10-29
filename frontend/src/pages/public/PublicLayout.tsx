import { Anchor, Box, Burger, Button, Container, Drawer, Group, SimpleGrid, Stack, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconMail, IconMapPin, IconWorld } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { BEAM_TEXTURE, BrandStripe, BRAND, SpexLogo, TAGLINE } from "@/components/SpexLogo";

const LINKS = [
  { label: "Features", href: "/home#features" },
  { label: "How it works", href: "/home#how" },
  { label: "About us", href: "/home#about" },
  { label: "Contact", href: "/join" },
];

/** Header and footer shared by the public pages (home, request access). */
export function PublicLayout({ children }: { children: ReactNode }) {
  const [opened, { toggle, close }] = useDisclosure();
  return (
    <Box bg={BRAND.cloud} mih="100vh" style={{ display: "flex", flexDirection: "column" }}>
      <Box component="header" bg={BRAND.navy} pos="sticky" top={0} style={{ zIndex: 50 }}>
        <Container size="lg" h={68}>
          <Group h="100%" justify="space-between" wrap="nowrap">
            <Link to="/home" aria-label="SPEX School Manager home" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <SpexLogo variant="white" height={28} />
              <Text c="white" fw={700} ff="Montserrat, sans-serif" size="xs" tt="uppercase" visibleFrom="sm" style={{ letterSpacing: "0.18em" }}>
                School Manager
              </Text>
            </Link>
            <Group gap="lg" visibleFrom="md">
              {LINKS.map((l) => (
                <Anchor key={l.label} component={Link} to={l.href} c="rgba(255,255,255,0.85)" size="sm" fw={500}>
                  {l.label}
                </Anchor>
              ))}
              <Button component={Link} to="/login" variant="white" color="navy.8" size="sm">Sign in</Button>
              <Button component={Link} to="/join" color="brand.7" size="sm">Request access</Button>
            </Group>
            <Burger opened={opened} onClick={toggle} color="white" hiddenFrom="md" aria-label="Menu" />
          </Group>
        </Container>
        <BrandStripe height={4} />
      </Box>
      <Drawer opened={opened} onClose={close} position="right" size="xs" title={<SpexLogo height={24} />} hiddenFrom="md">
        <Stack>
          {LINKS.map((l) => (
            <Anchor key={l.label} component={Link} to={l.href} onClick={close} fw={500}>{l.label}</Anchor>
          ))}
          <Button component={Link} to="/login" variant="default" onClick={close}>Sign in</Button>
          <Button component={Link} to="/join" onClick={close}>Request access</Button>
        </Stack>
      </Drawer>

      <Box component="main" style={{ flex: 1 }}>{children}</Box>

      <Box component="footer" style={{ background: `${BEAM_TEXTURE}, ${BRAND.navy}` }} c="white">
        <Container size="lg" py={48}>
          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="xl">
            <Stack gap="sm">
              <SpexLogo variant="white" height={34} />
              <Text size="sm" c="rgba(255,255,255,0.75)">
                SPEX School Manager is built by SPEX Labs, the software division of Security, Power &amp; Engineering Experts Limited.
              </Text>
              <Text size="sm" fw={600} c={BRAND.amber}>{TAGLINE}</Text>
            </Stack>
            <Stack gap={8}>
              <Text fw={700} ff="Montserrat, sans-serif">The system</Text>
              <Anchor component={Link} to="/home#features" c="rgba(255,255,255,0.8)" size="sm">Features</Anchor>
              <Anchor component={Link} to="/home#how" c="rgba(255,255,255,0.8)" size="sm">How it works</Anchor>
              <Anchor component={Link} to="/login" c="rgba(255,255,255,0.8)" size="sm">School sign-in</Anchor>
              <Anchor component={Link} to="/join" c="rgba(255,255,255,0.8)" size="sm">Request access or a demo</Anchor>
            </Stack>
            <Stack gap={8}>
              <Text fw={700} ff="Montserrat, sans-serif">Talk to SPEX</Text>
              <Group gap={8} wrap="nowrap"><IconMail size={16} /><Anchor href="mailto:info@spex.co.ug" c="rgba(255,255,255,0.8)" size="sm">info@spex.co.ug</Anchor></Group>
              <Group gap={8} wrap="nowrap"><IconWorld size={16} /><Text size="sm" c="rgba(255,255,255,0.8)">spex.co.ug · @spexug</Text></Group>
              <Group gap={8} wrap="nowrap"><IconMapPin size={16} /><Text size="sm" c="rgba(255,255,255,0.8)">Seeta–Mukono, Uganda</Text></Group>
            </Stack>
          </SimpleGrid>
          <Text size="xs" c="rgba(255,255,255,0.5)" mt={40}>
            © {new Date().getFullYear()} Security, Power &amp; Engineering Experts Limited. Fees are collected through SchoolPay, not in this system.
          </Text>
        </Container>
        <BrandStripe height={6} />
      </Box>
    </Box>
  );
}
