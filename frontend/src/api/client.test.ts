import { afterEach, describe, expect, it } from "vitest";

import { api, ApiError, buildUrl, errorMessage } from "./client";
import { mockFetch } from "@/test/render";

describe("api client", () => {
  afterEach(() => {
    document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("builds URLs and drops empty query values", () => {
    expect(buildUrl("/learners/", { search: "nak", page: 2, status: "", stream: null })).toBe("/api/learners/?search=nak&page=2");
  });

  it("sends the CSRF token on writes but not reads", async () => {
    document.cookie = "csrftoken=abc123";
    const calls = mockFetch({ "/api/learners/": { ok: true } });
    await api("/learners/");
    await api("/learners/", { method: "POST", body: { first_name: "Aisha" } });
    expect((calls[0].init?.headers as Record<string, string>)["X-CSRFToken"]).toBeUndefined();
    expect((calls[1].init?.headers as Record<string, string>)["X-CSRFToken"]).toBe("abc123");
    expect(calls[1].init?.body).toBe(JSON.stringify({ first_name: "Aisha" }));
  });

  it("turns server errors into readable messages", async () => {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ amount: ["The amount must be more than zero."] }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch;
    const error = await api("/finance/expenses/", { method: "POST", body: {} }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(400);
    expect(errorMessage(error)).toBe("amount: The amount must be more than zero.");
  });

  it("explains network failures in plain words", () => {
    expect(errorMessage(new TypeError("Failed to fetch"))).toMatch(/Cannot reach the server/);
  });
});
