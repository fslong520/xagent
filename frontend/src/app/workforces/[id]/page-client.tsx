"use client"

import React from "react"
import { useParams, usePathname } from "next/navigation"
import { WorkforceBuilder } from "@/components/workforce/workforce-builder"
import { resolveDynamicRouteParam } from "@/lib/static-export-route"

export default function WorkforceDetailPage() {
    const params = useParams()
    const pathname = usePathname()
    const id = resolveDynamicRouteParam(pathname, params, "id", "/workforces/:id")

    return <WorkforceBuilder key={id} workforceId={id} />
}
