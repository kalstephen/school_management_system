import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";

import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { renderWithProviders } from "@/test/render";
import { theme } from "@/theme";

import { LoginPage } from "./LoginPage";

function respond(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function SignedInHome() {
  const { me } = useAuth();
  return <p>{me ? `Signed in as ${me.user.username}` : "Nobody signed in"}</p>;
}

describe("LoginPage", () => {
  it("leaves the login screen after a successful sign-in", async () => {
    document.cookie = "csrftoken=t0k3n";
    let signedIn = false;
    const me = {
      user: { id: 1, username: "admin", name: "Platform Owner", email: "", phone: "", is_platform_admin: true },
      schools: [], school: null, roles: [], perms: [], modules: [], module_labels: {}, access: null,
      approval_level: 0, rank: 101, is_superuser: true, portal: "platform",
    };
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/me/")) return signedIn ? respond(200, me) : respond(403, { detail: "Not signed in" });
      if (url.includes("/auth/login/")) {
        signedIn = true;
        return respond(200, me);
      }
      return respond(200, { ok: true });
    }) as typeof fetch;

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter(
      [
        { path: "/platform/login", element: <LoginPage portal="platform" /> },
        { path: "/platform", element: <SignedInHome /> },
      ],
      { initialEntries: ["/platform/login"] },
    );
    render(
      <MantineProvider theme={theme}>
        <QueryClientProvider client={client}>
          <AuthProvider>
            <RouterProvider router={router} />
          </AuthProvider>
        </QueryClientProvider>
      </MantineProvider>,
    );
    await userEvent.type(await screen.findByLabelText(/Username/), "admin");
    await userEvent.type(screen.getByLabelText(/Password/), "Kampala2020");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Signed in as admin")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/platform");
  });

  it("shows the server's message on a wrong password", async () => {
    document.cookie = "csrftoken=t0k3n";
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/me/")) return respond(403, { detail: "Not signed in" });
      if (url.includes("/auth/login/")) return respond(400, { detail: "Wrong username or password." });
      return respond(200, { ok: true });
    }) as typeof fetch;

    renderWithProviders(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
      "/login",
    );
    await userEvent.type(await screen.findByLabelText(/School ID/), "DemoPrimary-001");
    await userEvent.type(screen.getByLabelText(/Username/), "head");
    await userEvent.type(screen.getByLabelText(/Password/), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Wrong username or password.")).toBeInTheDocument();
  });
});
