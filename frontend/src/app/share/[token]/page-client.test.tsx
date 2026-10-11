import React from "react"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const navigation = vi.hoisted(() => ({
  params: { token: "abc" } as Record<string, unknown>,
  pathname: "/share/abc",
}))

vi.mock("next/navigation", () => ({
  useParams: () => navigation.params,
  usePathname: () => navigation.pathname,
}))

vi.mock("@/components/widget/public-agent-chat-page", () => ({
  PublicAgentChatPage: ({ authMode, routeToken }: { authMode: string; routeToken: string }) => (
    <div data-testid="share-page">{`${authMode}:${routeToken}`}</div>
  ),
}))

import ShareChatPage from "./page-client"

beforeEach(() => {
  navigation.params = { token: "abc" }
  navigation.pathname = "/share/abc"
})

afterEach(cleanup)

describe("ShareChatPage", () => {
  it("reads the share token from the pathname when the static export placeholder is in params", () => {
    navigation.params = { token: "__shell__" }
    navigation.pathname = "/share/abc"

    render(<ShareChatPage />)

    expect(screen.getByTestId("share-page")).toHaveTextContent("share:abc")
  })

  it("falls back to the route param when the pathname does not match", () => {
    navigation.params = { token: "abc" }
    navigation.pathname = "/settings"

    render(<ShareChatPage />)

    expect(screen.getByTestId("share-page")).toHaveTextContent("share:abc")
  })
})
