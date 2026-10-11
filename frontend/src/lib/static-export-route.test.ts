import { describe, expect, it } from "vitest"

import { STATIC_EXPORT_SHELL_PARAM, resolveDynamicRouteParam } from "./static-export-route"

describe("resolveDynamicRouteParam", () => {
  it("reads a single-segment id from the pathname", () => {
    expect(resolveDynamicRouteParam("/agent/2", { id: "__shell__" }, "id", "/agent/:id")).toBe("2")
  })

  it("ignores the static export placeholder in params and keeps the pathname value", () => {
    expect(
      resolveDynamicRouteParam(
        "/templates/sales-email-agent",
        { id: STATIC_EXPORT_SHELL_PARAM },
        "id",
        "/templates/:id",
      ),
    ).toBe("sales-email-agent")
  })

  it("falls back to params when the pathname does not match (standalone deployment)", () => {
    expect(resolveDynamicRouteParam("/settings", { id: "7" }, "id", "/agent/:id")).toBe("7")
  })

  it("falls back to params when there is no pathname yet", () => {
    expect(resolveDynamicRouteParam(null, { token: "abc" }, "token", "/share/:token")).toBe("abc")
  })

  it("unwraps an array param", () => {
    expect(resolveDynamicRouteParam("/settings", { id: ["5"] }, "id", "/agent/:id")).toBe("5")
  })

  it("decodes a percent-encoded segment", () => {
    expect(resolveDynamicRouteParam("/skill-hub/my%20skill", {}, "name", "/skill-hub/:name")).toBe(
      "my skill",
    )
  })

  it("matches a dynamic segment that is not the last one", () => {
    expect(
      resolveDynamicRouteParam("/workforces/3/run", {}, "id", "/workforces/:id/run"),
    ).toBe("3")
  })

  it("tolerates a trailing slash", () => {
    expect(resolveDynamicRouteParam("/agent/2/", {}, "id", "/agent/:id")).toBe("2")
  })

  it("does not treat a placeholder-only pathname as a real value", () => {
    expect(
      resolveDynamicRouteParam("/agent/__shell__", { id: "9" }, "id", "/agent/:id"),
    ).toBe("9")
  })

  it("returns undefined when neither source carries a value", () => {
    expect(resolveDynamicRouteParam("/settings", {}, "id", "/agent/:id")).toBeUndefined()
  })
})
