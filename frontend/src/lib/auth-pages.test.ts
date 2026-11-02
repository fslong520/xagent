import { describe, expect, it } from "vitest"
import { resolveTranslation } from "@/i18n/translations"

import {
  authMutationUnavailableTranslationKey,
  isAuthPublicPath,
  isChromelessAuthenticatedPath,
  isExternalRoutePath,
} from "./auth-pages"

describe("auth public paths", () => {
  it("allows the OIDC callback route through the auth guard", () => {
    expect(isAuthPublicPath("/auth/oidc/callback")).toBe(true)
  })

  it("classifies widget and share routes as external provider boundaries", () => {
    expect(isExternalRoutePath("/widget/chat/session")).toBe(true)
    expect(isExternalRoutePath("/share/public-token")).toBe(true)
    expect(isExternalRoutePath("/settings")).toBe(false)
    expect(isExternalRoutePath("/widgets")).toBe(false)
    expect(isExternalRoutePath("/widget-admin")).toBe(false)
    expect(isExternalRoutePath("/share-settings")).toBe(false)
  })

  it.each([
    ["storage_unavailable", "Your browser is blocking local storage. Enable storage and try again."],
    ["coordination_unavailable", "Your browser does not support the secure sign-in features this application requires."],
    ["operation_failed", "Your sign-in session could not be updated. Please try again."],
  ] as const)("maps %s to a real localized availability key", (reason, english) => {
    const key = authMutationUnavailableTranslationKey(reason)
    expect(resolveTranslation("en", key)).toBe(english)
  })
})

describe("chromeless authenticated paths", () => {
  it("treats /onboarding as chromeless but still auth-gated", () => {
    expect(isChromelessAuthenticatedPath("/onboarding")).toBe(true)
    expect(isAuthPublicPath("/onboarding")).toBe(false)
  })

  it("does not treat unrelated or null paths as chromeless", () => {
    expect(isChromelessAuthenticatedPath("/settings")).toBe(false)
    expect(isChromelessAuthenticatedPath("/onboarding/extra")).toBe(false)
    expect(isChromelessAuthenticatedPath(null)).toBe(false)
  })
})
