import { describe, expect, it, vi } from "vitest"
import { readFileSync } from "node:fs"

import {
  resolveDynamicTranslation,
  resolveTranslation,
  translations,
} from "./translations"

function isTranslationBranch(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

// The one leaf allowed to be empty: a plural suffix that deliberately renders
// nothing for one of the plural categories (see the "delete failed" alert).
const INTENTIONALLY_EMPTY_LEAF = "translations.en.userManagement.list.alerts.delete_failed_suffix"

function assertTranslationLeavesNonEmpty(
  value: unknown,
  path: string,
): void {
  expect(isTranslationBranch(value), `${path} must be an object`).toBe(true)
  if (!isTranslationBranch(value)) return

  for (const [key, child] of Object.entries(value)) {
    const childPath = `${path}.${key}`
    if (isTranslationBranch(child)) {
      assertTranslationLeavesNonEmpty(child, childPath)
      continue
    }
    expect(typeof child, `${childPath} must be a string`).toBe("string")
    if (childPath === INTENTIONALLY_EMPTY_LEAF) continue
    expect((child as string).trim(), `${childPath} must be non-empty`).not.toBe("")
  }
}

describe("translations", () => {
  it("ships exactly one locale tree", () => {
    expect(Object.keys(translations)).toEqual(["en"])
  })

  it("has no empty leaves anywhere in the tree", () => {
    assertTranslationLeavesNonEmpty(translations.en, "translations.en")
  })

  it("does not describe the basic tool category with tools it does not control", () => {
    const basic =
      translations.en.builds.configForm.tools.categoryDescriptions.basic
    expect(basic).not.toContain("date/time retrieval")
  })

  it("describes the admin account label and searchable identities", () => {
    expect(translations.en.userManagement.list).toEqual(
      expect.objectContaining({
        search_placeholder: "Search email or username...",
        table: expect.objectContaining({ account: "Account" }),
      }),
    )
  })

  it("describes deployment configuration failure without a browser fallback", () => {
    expect(translations.en.deployment_config.messages.load_failed).toBe(
      "Failed to load deployment configuration. Retry before copying deployment details.",
    )
  })

  it("keeps MCP runtime translations non-empty", () => {
    assertTranslationLeavesNonEmpty(
      translations.en.tools.mcp.runtime,
      "translations.en.tools.mcp.runtime",
    )
  })

  it("resolves a typed translation key", () => {
    expect(resolveTranslation("en", "tools.mcp.runtime.title")).toBe(
      "Runtime Inputs",
    )
  })

  it("provides localized Agent delete dependency copy", () => {
    const english = (translations.en.builds.list as Record<string, unknown>).deleteDialog

    expect(english).toEqual(expect.objectContaining({
      blockedTitle: expect.any(String),
      hiddenReferences: expect.any(String),
      readyToRetry: expect.any(String),
      retryDelete: expect.any(String),
      discardNotAllowed: expect.any(String),
      discardHasRuns: expect.any(String),
    }))
  })

  it("keeps publication failure copy neutral, exact, and fully migrated", () => {
    expect(translations.en.builds.publication).toEqual({
      publishFailed: "Failed to publish agent",
      unpublishFailed: "Failed to unpublish agent",
    })
    expect(translations.en.builds.editor.error as Record<string, unknown>).not.toHaveProperty(
      "publishFailed",
    )
    expect(translations.en.builds.editor.error as Record<string, unknown>).not.toHaveProperty(
      "unpublishFailed",
    )

    const buildPage = readFileSync(`${process.cwd()}/src/app/build/page.tsx`, "utf8")
    const agentBuilder = readFileSync(
      `${process.cwd()}/src/components/build/agent-builder.tsx`,
      "utf8",
    )
    const localeSource = readFileSync(
      `${process.cwd()}/src/i18n/locales/en.ts`,
      "utf8",
    )

    expect(buildPage.match(/builds\.publication\.publishFailed/g)).toHaveLength(1)
    expect(buildPage.match(/builds\.publication\.unpublishFailed/g)).toHaveLength(1)
    expect(agentBuilder.match(/builds\.publication\.publishFailed/g)).toHaveLength(2)
    expect(agentBuilder.match(/builds\.publication\.unpublishFailed/g)).toHaveLength(1)

    for (const source of [buildPage, agentBuilder, localeSource]) {
      expect(source).not.toContain("builds.editor.error.publishFailed")
      expect(source).not.toContain("builds.editor.error.unpublishFailed")
    }
  })

  it("provides localized Widget Session lifecycle copy", () => {
    assertTranslationLeavesNonEmpty(
      translations.en.widgetSession,
      "translations.en.widgetSession",
    )
  })

  it("reports a missing dynamic key and uses its explicit fallback", () => {
    const onMissing = vi.fn()

    expect(
      resolveDynamicTranslation(
        "en",
        "tools.mcp.runtime.missing",
        "Unavailable",
        undefined,
        {
          onMissing,
        },
      ),
    ).toBe("Unavailable")
    expect(onMissing).toHaveBeenCalledWith("tools.mcp.runtime.missing")
  })

  // Pins a PR review finding: the onboarding Done step composes these
  // prefix/<b>value</b>/suffix strings in JSX (page.tsx) with no space of
  // its own between them, so each string must carry its OWN spacing - the
  // prefix needs a trailing space and the suffixes a leading one, or the
  // rendered summary line runs words together.
  it("gives the onboarding Done step's composed summary lines their own inter-word spacing", () => {
    const prefixes = [
      resolveTranslation("en", "onboarding.done.workingInPrefix"),
      resolveTranslation("en", "onboarding.done.briefedPrefix"),
      resolveTranslation("en", "onboarding.done.writingInPrefix"),
      resolveTranslation("en", "onboarding.done.willConnectPrefix"),
    ]
    for (const prefix of prefixes) {
      expect(prefix.endsWith(" ")).toBe(true)
    }
    const suffixes = [
      resolveTranslation("en", "onboarding.done.briefedSuffixOne"),
      resolveTranslation("en", "onboarding.done.briefedSuffixOther"),
      resolveTranslation("en", "onboarding.done.writingInSuffix"),
      resolveTranslation("en", "onboarding.done.willConnectSuffix"),
    ]
    for (const suffix of suffixes) {
      expect(suffix.startsWith(" ")).toBe(true)
    }
  })

  // Pins the same convention for the team step's "N other matches" subtitle:
  // the em-dash-led extra-matches phrase is appended directly after the base
  // sentence in JSX, so it must bring its own leading space.
  it("gives the team step's 'other matches' subtitle a leading space before the em dash", () => {
    expect(resolveTranslation("en", "onboarding.team.subtitleExtraOne").startsWith(" ")).toBe(true)
    expect(resolveTranslation("en", "onboarding.team.subtitleExtraMany").startsWith(" ")).toBe(true)
  })

  // The welcome heading's closing punctuation is owned by the locale tree
  // rather than hardcoded in JSX (page.tsx).
  it("gives the welcome heading locale-appropriate closing punctuation", () => {
    expect(resolveTranslation("en", "onboarding.welcome.titleSuffix")).toBe(".")
  })
})
