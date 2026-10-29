import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, renderWithProviders } from "@/test/render";

import { ResourceForm } from "./ResourceForm";

describe("ResourceForm", () => {
  it("posts the visible fields and shows server field errors", async () => {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ name: ["This name is already used."] }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch;
    renderWithProviders(
      <ResourceForm
        endpoint="/houses/"
        fields={[
          { name: "name", label: "Name", required: true },
          { name: "colour", label: "Colour", hidden: () => true },
        ]}
      />,
    );
    await userEvent.type(await screen.findByLabelText(/Name/), "Mutesa");
    expect(screen.queryByLabelText("Colour")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("This name is already used.")).toBeInTheDocument();
  });

  it("includes hidden-type values in the payload", async () => {
    const calls = mockFetch({ "/api/timetable/": { id: 1 } });
    renderWithProviders(
      <ResourceForm
        endpoint="/timetable/"
        initial={{ day: 2, period: 5 }}
        fields={[
          { name: "day", label: "", type: "hidden" },
          { name: "period", label: "", type: "hidden" },
        ]}
      />,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    const post = calls.find((c) => c.init?.method === "POST");
    expect(JSON.parse(String(post?.init?.body))).toEqual({ day: 2, period: 5 });
  });
});
