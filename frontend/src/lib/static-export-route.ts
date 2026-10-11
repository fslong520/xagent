// The placeholder value each dynamic route's static export is prerendered
// under (see the route's page.tsx generateStaticParams). FastAPI serves that
// one shell for every real value.
export const STATIC_EXPORT_SHELL_PARAM = "__shell__"

// Turns a route pattern such as "/agent/:id" into a matcher that captures the
// first dynamic segment. The rest of the pattern is matched literally.
function routePatternToRegex(pattern: string): RegExp {
  const source = pattern
    .split("/")
    .map((segment) =>
      segment.startsWith(":")
        ? "([^/?#]+)"
        : segment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
    )
    .join("/")
  return new RegExp(`^${source}/?$`)
}

// Which value the URL names for one dynamic route segment. The prerendered
// flight payload hardcodes the placeholder for the segment, and Next derives
// useParams() from that payload rather than from the address bar - so on the
// static export (the single-process pip/uvx deployment) useParams() reports
// "__shell__" for a real value and the page never sees the actual one. Read it
// from the pathname, and keep the param as the fallback for the
// Docker/standalone deployment, where the server renders the route under its
// actual value.
export function resolveDynamicRouteParam(
  pathname: string | null | undefined,
  params: unknown,
  paramName: string,
  routePattern: string,
): string | undefined {
  const rawParams =
    params && typeof params === "object"
      ? (params as Record<string, unknown>)[paramName]
      : undefined
  const fromParams = Array.isArray(rawParams) ? rawParams[0] : rawParams
  const match =
    typeof pathname === "string" ? routePatternToRegex(routePattern).exec(pathname) : null
  const fromPath = match ? decodeURIComponent(match[1]) : undefined
  if (fromPath && fromPath !== STATIC_EXPORT_SHELL_PARAM) return fromPath
  if (typeof fromParams === "string" && fromParams !== STATIC_EXPORT_SHELL_PARAM) return fromParams
  return fromPath
}
