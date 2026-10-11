import React from "react"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const navigation = vi.hoisted(() => ({
  params: { id: "2" } as Record<string, unknown>,
  pathname: "/agent/2",
}))

const apiRequestMock = vi.hoisted(() => vi.fn())
const toastErrorMock = vi.hoisted(() => vi.fn())
const dispatchMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({
  useParams: () => navigation.params,
  usePathname: () => navigation.pathname,
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock("@/lib/api-wrapper", () => ({ apiRequest: apiRequestMock }))

vi.mock("@/lib/utils", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/utils")>()
  return { ...actual, getApiUrl: () => "http://api.local" }
})

vi.mock("@/contexts/i18n-context", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock("@/contexts/app-context-chat", () => ({
  useApp: () => ({ dispatch: dispatchMock, sendMessage: vi.fn() }),
}))

vi.mock("@/components/chat/ChatStartScreen", () => ({
  ChatStartScreen: ({ title }: { title: string }) => <div data-testid="chat-start">{title}</div>,
}))

vi.mock("@/components/ui/sonner", () => ({ toast: { error: toastErrorMock } }))

import AgentChatPage from "./page-client"

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

const agent = {
  id: 2,
  name: "t10-main",
  description: "main agent",
  logo_url: null,
  instructions: null,
  execution_mode: "balanced",
  suggested_prompts: [],
  models: {},
}

beforeEach(() => {
  apiRequestMock.mockReset()
  toastErrorMock.mockReset()
  dispatchMock.mockReset()
  navigation.params = { id: "2" }
  navigation.pathname = "/agent/2"
})

afterEach(cleanup)

describe("AgentChatPage", () => {
  it("reads the agent id from the pathname when the static export placeholder is in params", async () => {
    navigation.params = { id: "__shell__" }
    navigation.pathname = "/agent/2"
    apiRequestMock.mockResolvedValueOnce(jsonResponse(agent))

    render(<AgentChatPage />)

    await waitFor(() => {
      expect(screen.getByTestId("chat-start")).toHaveTextContent("t10-main")
    })
    expect(apiRequestMock).toHaveBeenCalledWith("http://api.local/api/agents/2")
  })

  it("falls back to the route param when the pathname does not match", async () => {
    navigation.params = { id: "2" }
    navigation.pathname = "/settings"
    apiRequestMock.mockResolvedValueOnce(jsonResponse(agent))

    render(<AgentChatPage />)

    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith("http://api.local/api/agents/2")
    })
  })

  it("shows the not-found state when the agent request fails", async () => {
    apiRequestMock.mockResolvedValueOnce(jsonResponse({ detail: "not found" }, 404))

    render(<AgentChatPage />)

    await waitFor(() => {
      expect(screen.getByText("builds.list.chat.notFound")).toBeInTheDocument()
    })
    expect(screen.queryByTestId("chat-start")).not.toBeInTheDocument()
  })
})
