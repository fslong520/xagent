import React from "react"
import { cleanup, render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const navigation = vi.hoisted(() => ({
  params: { name: "demo" } as Record<string, unknown>,
  pathname: "/skill-hub/demo",
}))

const apiRequestMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({
  useParams: () => navigation.params,
  usePathname: () => navigation.pathname,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn() }),
}))

vi.mock("@/lib/api-wrapper", () => ({ apiRequest: apiRequestMock }))

vi.mock("@/lib/utils", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/utils")>()
  return { ...actual, getApiUrl: () => "http://api.local" }
})

vi.mock("@/contexts/i18n-context", () => ({
  useI18n: () => ({ t: (key: string) => key, tDynamic: (_k: string, f: string) => f, locale: "en" }),
}))

import SkillDetailPage from "./page-client"

beforeEach(() => {
  apiRequestMock.mockReset()
  // Keep the page in its loading state: the assertions only concern the URL
  // the page builds from the route, not the loaded detail.
  apiRequestMock.mockReturnValue(new Promise(() => {}))
  navigation.params = { name: "demo" }
  navigation.pathname = "/skill-hub/demo"
})

afterEach(cleanup)

describe("SkillDetailPage", () => {
  it("reads the skill name from the pathname when the static export placeholder is in params", async () => {
    navigation.params = { name: "__shell__" }
    navigation.pathname = "/skill-hub/demo"

    render(<SkillDetailPage />)

    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith(
        "http://api.local/api/skill-hub/installed/demo",
      )
    })
  })

  it("falls back to the route param when the pathname does not match", async () => {
    navigation.params = { name: "demo" }
    navigation.pathname = "/settings"

    render(<SkillDetailPage />)

    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith(
        "http://api.local/api/skill-hub/installed/demo",
      )
    })
  })
})
