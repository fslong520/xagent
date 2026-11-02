import { describe, expect, it } from "vitest"

import { extractBuildPreviewResponse, extractSharedChatResponse } from "./chat-response"

describe("chat-response", () => {
  it("extracts shared chat response from nested metadata payloads", () => {
    const payload = {
      metadata: {
        chat_response: {
          message: "Please specify the target audience",
          interactions: [
            {
              type: "text_input",
              field: "target_user",
              label: "Target audience",
            },
          ],
        },
      },
    }

    expect(extractSharedChatResponse(payload)).toEqual({
      message: "Please specify the target audience",
      interactions: [
        {
          type: "text_input",
          field: "target_user",
          label: "Target audience",
        },
      ],
    })
  })

  it("prefers top-level chat_response from task_completed payloads", () => {
    const payload = {
      type: "task_completed",
      result: "plain result that should not win",
      success: false,
      chat_response: {
        message: "What would you like me to analyze?",
        interactions: [
          {
            type: "text_input",
            field: "analysis_content",
            label: "Enter the content to analyze",
            multiline: true,
          },
        ],
      },
    }

    expect(extractBuildPreviewResponse(payload)).toEqual({
      message: "What would you like me to analyze?",
      interactions: payload.chat_response.interactions,
    })
  })

  it("falls back to structured chat json embedded in result", () => {
    const payload = {
      type: "task_completed",
      result: JSON.stringify({
        type: "chat",
        chat: {
          message: "More information needed",
          interactions: [
            {
              type: "confirm",
              field: "continue",
              label: "Continue?",
            },
          ],
        },
      }),
    }

    expect(extractBuildPreviewResponse(payload)).toEqual({
      message: "More information needed",
      interactions: [
        {
          type: "confirm",
          field: "continue",
          label: "Continue?",
        },
      ],
    })
  })

  it("preserves ordinary json code blocks in non-chat preview results", () => {
    const payload = {
      type: "task_completed",
      result: "Here is the schema:\n```json\n{\"name\":\"demo\"}\n```",
    }

    expect(extractBuildPreviewResponse(payload)).toEqual({
      message: "Here is the schema:\n```json\n{\"name\":\"demo\"}\n```",
    })
  })
})
