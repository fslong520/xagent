"use client"

import React from "react"
import { useParams, usePathname } from "next/navigation"
import { PublicAgentChatPage } from "@/components/widget/public-agent-chat-page"
import { resolveDynamicRouteParam } from "@/lib/static-export-route"

export default function ShareChatPage() {
  const params = useParams()
  const pathname = usePathname()
  const token = resolveDynamicRouteParam(pathname, params, "token", "/share/:token")

  return (
    <PublicAgentChatPage
      authMode="share"
      routeToken={token ?? ""}
    />
  )
}
