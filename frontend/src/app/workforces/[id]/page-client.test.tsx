import React from "react"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const navigation = vi.hoisted(() => ({
  params: { id: "1" } as Record<string, unknown>,
  pathname: "/workforces/1",
}))

vi.mock("next/navigation", () => ({
  useParams: () => navigation.params,
  usePathname: () => navigation.pathname,
}))

vi.mock("@/components/workforce/workforce-builder", () => ({
  WorkforceBuilder: ({ workforceId }: { workforceId?: string }) => (
    <div data-testid="workforce-builder">{workforceId ?? "none"}</div>
  ),
}))

import WorkforceDetailPage from "./page-client"

beforeEach(() => {
  navigation.params = { id: "1" }
  navigation.pathname = "/workforces/1"
})

afterEach(cleanup)

describe("WorkforceDetailPage", () => {
  it("passes the pathname id to the builder when the static export placeholder is in params", () => {
    navigation.params = { id: "__shell__" }
    navigation.pathname = "/workforces/1"

    render(<WorkforceDetailPage />)

    expect(screen.getByTestId("workforce-builder")).toHaveTextContent("1")
  })

  it("falls back to the route param when the pathname does not match", () => {
    navigation.params = { id: "1" }
    navigation.pathname = "/settings"

    render(<WorkforceDetailPage />)

    expect(screen.getByTestId("workforce-builder")).toHaveTextContent("1")
  })

  it("passes no id when neither source carries one", () => {
    navigation.params = {}
    navigation.pathname = "/settings"

    render(<WorkforceDetailPage />)

    expect(screen.getByTestId("workforce-builder")).toHaveTextContent("none")
  })
})
