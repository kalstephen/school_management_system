import {
  ActionIcon,
  Alert,
  AppShell,
  Avatar,
  Badge,
  Box,
  Burger,
  Divider,
  Group,
  Indicator,
  Menu,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  Tooltip,
  UnstyledButton,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure, useMediaQuery } from "@mantine/hooks";
import {
  IconBell,
  IconCloudOff,
  IconCloudUpload,
  IconDatabaseCog,
  IconKey,
  IconLogout,
  IconMoon,
  IconSun,
  IconSwitchHorizontal,
} from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, useLocation, useNavigate } from "react-router";

import { get } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { LearnerSearch } from "@/components/LearnerSearch";
import { APP_NAME, BrandStripe, BRAND, SpexLogo, SpexSymbol } from "@/components/SpexLogo";
import { useSync } from "@/offline/useSync";

import { visibleNavigation } from "./navigation";

function SyncStatus() {
  const { online, pending, syncing, syncNow } = useSync(true);
  if (online && pending === 0) return null;
  return (
    <Tooltip label={online ? `${pending} offline change(s) waiting — click to send` : "You are offline. Roll call and marks are saved on this device."}>
      <Badge
        component="button"
        onClick={() => syncNow()}
        color={online ? "orange" : "gray"}
        variant="light"
        leftSection={online ? <IconCloudUpload size={14} /> : <IconCloudOff size={14} />}
        style={{ cursor: "pointer", border: 0 }}
      >
        {syncing ? "Sending…" : online ? `${pending} to sync` : "Offline"}
      </Badge>
    </Tooltip>
  );
}

function ThemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const scheme = useComputedColorScheme("light");
  return (
    <ActionIcon variant="default" size="lg" aria-label="Toggle colour scheme" onClick={() => setColorScheme(scheme === "light" ? "dark" : "light")}>
      {scheme === "light" ? <IconMoon size={18} /> : <IconSun size={18} />}
    </ActionIcon>
  );
}

export function AppLayout() {
  const { me, can, has, logout, switchSchool } = useAuth();
  const [opened, { toggle, close }] = useDisclosure();
  const location = useLocation();
  const navigate = useNavigate();
  const wide = useMediaQuery("(min-width: 62em)");
  const groups = visibleNavigation(can, has, !!(me?.user.is_platform_admin || me?.is_superuser));
  const { data: unread } = useQuery({
    queryKey: ["unread-notifications"],
    enabled: !!me?.school,
    refetchInterval: 60_000,
    queryFn: () => get<{ count: number }>("/notifications/", { read_at__isnull: true, page_size: 1 }),
  });
  const { data: term } = useQuery({
    queryKey: ["current-term"],
    enabled: !!me?.school,
    queryFn: () => get<{ label: string } | null>("/current-term/"),
  });

  const scheme = useComputedColorScheme("light");
  const isActive = (path: string) => (path === "/" ? location.pathname === "/" : location.pathname.startsWith(path));

  return (
    <AppShell header={{ height: 68 }} navbar={{ width: 260, breakpoint: "md", collapsed: { mobile: !opened } }} padding="lg">
      <AppShell.Header style={{ background: BRAND.navy, borderBottom: 0, display: "flex", flexDirection: "column" }}>
        <Group h={64} px="md" justify="space-between" wrap="nowrap">
          <Group gap="md" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="md" size="sm" color="white" aria-label="Menu" />
            <UnstyledButton component={Link} to="/" aria-label={`${APP_NAME} home`}>
              <Box visibleFrom="sm">
                <SpexLogo variant="white" height={26} />
              </Box>
              <Box hiddenFrom="sm">
                <SpexSymbol size={34} />
              </Box>
            </UnstyledButton>
            <Divider orientation="vertical" color="rgba(255,255,255,0.18)" my={14} visibleFrom="sm" />
            <UnstyledButton component={Link} to="/">
              <Group gap="xs" wrap="nowrap">
                {me?.school?.logo && <Avatar src={me.school.logo} radius="md" size={34} bg="white" />}
                <Stack gap={0}>
                  <Text fw={700} size="sm" lh={1.2} lineClamp={1} c="white" ff="Montserrat, Inter, sans-serif">
                    {me?.school?.name ?? (me?.portal === "platform" ? "Owner console" : "School Manager")}
                  </Text>
                  <Text size="xs" lh={1.2} c="rgba(255,255,255,0.7)" visibleFrom="xs">
                    {me?.school ? `${me.school.code} · ${term?.label ?? "No term set"}` : "All schools"}
                  </Text>
                </Stack>
              </Group>
            </UnstyledButton>
          </Group>
          {wide && can("learners.view") && <LearnerSearch width={380} />}
          <Group gap="xs" wrap="nowrap">
            <SyncStatus />
            <Tooltip label="Notifications">
              <Indicator disabled={!unread?.count} label={unread?.count} size={16} color="red">
                <ActionIcon variant="default" size="lg" component={Link} to="/notices" aria-label="Notifications">
                  <IconBell size={18} />
                </ActionIcon>
              </Indicator>
            </Tooltip>
            <ThemeToggle />
            <Menu position="bottom-end" width={240} shadow="md">
              <Menu.Target>
                <UnstyledButton aria-label="Account menu">
                  <Avatar color="brand" radius="xl">
                    {me?.user.name
                      .split(" ")
                      .map((part) => part[0])
                      .join("")
                      .slice(0, 2)
                      .toUpperCase()}
                  </Avatar>
                </UnstyledButton>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>
                  <Text size="sm" fw={600} c="var(--mantine-color-text)">
                    {me?.user.name}
                  </Text>
                  <Text size="xs">{me?.roles.map((r) => r.label).join(", ") || "No role"}</Text>
                </Menu.Label>
                <Menu.Divider />
                {(me?.schools.length ?? 0) > 1 &&
                  me!.schools
                    .filter((s) => s.id !== me!.school?.id)
                    .map((s) => (
                      <Menu.Item key={s.id} leftSection={<IconSwitchHorizontal size={16} />} onClick={() => switchSchool(s.id).then(() => navigate("/"))}>
                        Switch to {s.name}
                      </Menu.Item>
                    ))}
                <Menu.Item leftSection={<IconKey size={16} />} component={Link} to="/account">
                  Change password
                </Menu.Item>
                {me?.portal === "platform" && me.is_superuser && (
                  <Menu.Item leftSection={<IconDatabaseCog size={16} />} component="a" href="/admin/" target="_blank">
                    Content manager
                  </Menu.Item>
                )}
                <Menu.Item color="red" leftSection={<IconLogout size={16} />} onClick={() => {
                    const door = me?.portal === "platform" ? "/platform/login" : "/login";
                    logout().then(() => navigate(door));
                  }}>
                  Sign out
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
        <BrandStripe height={4} />
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        <AppShell.Section grow component={ScrollArea}>
          {!wide && can("learners.view") && (
            <div style={{ marginBottom: 12 }}>
              <LearnerSearch width="100%" />
            </div>
          )}
          {groups.map((group) => (
            <div key={group.label} style={{ marginBottom: 10 }}>
              <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="sm" mb={4}>
                {group.label}
              </Text>
              {group.items.map((item) => (
                <NavLink
                  key={item.path}
                  component={Link}
                  to={item.path}
                  label={item.label}
                  leftSection={item.icon}
                  active={isActive(item.path) && !groups.some((g) => g.items.some((i) => i.path !== item.path && i.path.startsWith(item.path) && isActive(i.path)))}
                  onClick={close}
                  style={{ borderRadius: 8 }}
                />
              ))}
            </div>
          ))}
        </AppShell.Section>
        <AppShell.Section pt="sm" style={{ borderTop: "1px solid var(--mantine-color-default-border)" }}>
          <Stack gap={4} px="sm">
            <SpexLogo height={18} variant={scheme === "dark" ? "white" : "navy"} />
            <Text size="10px" c="dimmed" fw={600} tt="uppercase" style={{ letterSpacing: "0.12em" }}>
              School Manager
            </Text>
          </Stack>
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main>
        {me?.access === "read_only" && (
          <Alert color="orange" mb="md" title="Subscription expired">
            The school is read-only: you can view and export records but not change them until the subscription is renewed.
          </Alert>
        )}
        {me && !me.school && !me.user.is_platform_admin && !me.is_superuser && (
          <Alert color="blue" mb="md" title="No school selected">
            Your account is not linked to a school yet.
          </Alert>
        )}
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
