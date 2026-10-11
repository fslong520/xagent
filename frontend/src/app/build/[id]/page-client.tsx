"use client"

import React from "react"
import { AgentBuilder } from "@/components/build/agent-builder"
import { useParams, usePathname } from "next/navigation"
import { resolveDynamicRouteParam } from "@/lib/static-export-route"

export default function BuildDetailPage() {
  const params = useParams()
  const pathname = usePathname()
  const id = resolveDynamicRouteParam(pathname, params, "id", "/build/:id")

  return <AgentBuilder key={id} agentId={id} />
}
