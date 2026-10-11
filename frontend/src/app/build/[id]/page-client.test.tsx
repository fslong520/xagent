import React from "react"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const navigation = vi.hoisted(() => ({
  params: { id: "2" } as Record<string, unknown>,
  pathname: "/build/2",
}))

vi.mock("next/navigation", () => ({
  useParams: () => navigation.params,
  usePathname: () => navigation.pathname,
}))

vi.mock("@/components/build/agent-builder", () => ({
  AgentBuilder: ({ agentId }: { agentId?: string }) => (
    <div data-testid="agent-builder">{agentId ?? "none"}</div>
  ),
}))

import BuildDetailPage from "./page-client"

beforeEach(() => {
  navigation.params = { id: "2" }
  navigation.pathname = "/build/2"
})

afterEach(cleanup)

describe("BuildDetailPage", () => {
  it("passes the pathname id to the builder when the static export placeholder is in params", () => {
    navigation.params = { id: "__shell__" }
    navigation.pathname = "/build/2"

    render(<BuildDetailPage />)

    expect(screen.getByTestId("agent-builder")).toHaveTextContent("2")
  })

  it("falls back to the route param when the pathname does not match", () => {
    navigation.params = { id: "2" }
    navigation.pathname = "/settings"

    render(<BuildDetailPage />)

    expect(screen.getByTestId("agent-builder")).toHaveTextContent("2")
  })

  it("passes no id when neither source carries one", () => {
    navigation.params = {}
    navigation.pathname = "/settings"

    render(<BuildDetailPage />)

    expect(screen.getByTestId("agent-builder")).toHaveTextContent("none")
  })
})
