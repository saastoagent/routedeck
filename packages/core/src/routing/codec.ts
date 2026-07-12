import type { DeepLinkPolicy, FrontendContract } from "../contracts/generated";
import { RouteDeckRouteError } from "../client/errors";

export interface RouteDeckRouteLocation {
  nodeId: string;
  params: Readonly<Record<string, string>>;
  policy: DeepLinkPolicy;
  resumeHandle: string | null;
}

export interface RouteDeckRouteContext {
  sessionAvailable: boolean;
  validateResumeCapability?: (
    handle: string,
    nodeId: string,
    params: Readonly<Record<string, string>>,
  ) => boolean;
}

export interface RouteDeckRouteCodec {
  decode(path: string, context?: RouteDeckRouteContext): RouteDeckRouteLocation;
  encode(
    nodeId: string,
    params: Readonly<Record<string, string>>,
    options?: { resumeHandle?: string },
  ): string;
  policyForPath(path: string): DeepLinkPolicy;
  policyForNode(nodeId: string): DeepLinkPolicy;
}

export interface RouteDeckRouteCodecOptions {
  validatePublicRouteKey?: (name: string, value: string) => boolean;
  validateResumeCapability?: RouteDeckRouteContext["validateResumeCapability"];
}

interface CompiledSegment {
  literal: string | null;
  parameter: string | null;
}

interface CompiledRoute {
  nodeId: string;
  policy: DeepLinkPolicy;
  template: string;
  segments: CompiledSegment[];
  parameterNames: string[];
}

export function createRouteDeckRouteCodec(
  contract: FrontendContract,
  options: RouteDeckRouteCodecOptions = {},
): RouteDeckRouteCodec {
  const routes = Object.values(contract.nodes).map((node) =>
    compileRoute(node.id, node.route_template, node.deep_link_policy),
  );
  ensureNoOverlaps(routes);
  const byNode = new Map(routes.map((route) => [route.nodeId, route]));

  function match(path: string): {
    route: CompiledRoute;
    params: Record<string, string>;
    query: string;
  } {
    const { pathOnly, query } = splitLocalPath(path);
    const decodedSegments = pathOnly
      .split("/")
      .filter(Boolean)
      .map((segment) => decodeSegment(segment));
    const matches: Array<{ route: CompiledRoute; params: Record<string, string> }> = [];
    for (const route of routes) {
      if (route.segments.length !== decodedSegments.length) continue;
      const params: Record<string, string> = {};
      let matched = true;
      for (let index = 0; index < route.segments.length; index += 1) {
        const declaration = route.segments[index];
        const value = decodedSegments[index];
        if (declaration === undefined || value === undefined) {
          throw new RouteDeckRouteError(
            "route_invariant",
            "Compiled route segments are inconsistent.",
          );
        }
        if (declaration.literal !== null && declaration.literal !== value) {
          matched = false;
          break;
        }
        if (declaration.parameter !== null) {
          if (!value) {
            matched = false;
            break;
          }
          params[declaration.parameter] = value;
        }
      }
      if (matched) matches.push({ route, params });
    }
    if (matches.length !== 1) {
      throw new RouteDeckRouteError(
        "route_not_found",
        `Path does not identify one declared RouteDeck route: ${path}`,
      );
    }
    const matched = matches[0];
    if (matched === undefined) {
      throw new RouteDeckRouteError("route_invariant", "Route match disappeared.");
    }
    return { ...matched, query };
  }

  return {
    decode(path, context) {
      const { route, params, query } = match(path);
      if (route.policy === "shareable") {
        if (query) {
          throw new RouteDeckRouteError(
            "shareable_query_forbidden",
            "Shareable RouteDeck routes do not accept query bindings.",
          );
        }
        validatePublicParams(route, params, options.validatePublicRouteKey);
        return {
          nodeId: route.nodeId,
          params: Object.freeze({ ...params }),
          policy: route.policy,
          resumeHandle: null,
        };
      }

      if (!context?.sessionAvailable) {
        throw new RouteDeckRouteError(
          "session_required",
          "This RouteDeck route requires the current cookie-backed session.",
        );
      }
      const resumeHandle = decodeResumeQuery(query);
      const validate =
        context.validateResumeCapability ?? options.validateResumeCapability;
      if (!validate || !validate(resumeHandle, route.nodeId, params)) {
        throw new RouteDeckRouteError(
          "capability_mismatch",
          "The RouteDeck resume capability is unavailable or mismatched.",
        );
      }
      return {
        nodeId: route.nodeId,
        params: Object.freeze({ ...params }),
        policy: route.policy,
        resumeHandle,
      };
    },

    encode(nodeId, params, routeOptions = {}) {
      const route = byNode.get(nodeId);
      if (!route) {
        throw new RouteDeckRouteError(
          "route_not_found",
          `Unknown RouteDeck route node: ${nodeId}`,
        );
      }
      requireExactParams(route, params);
      if (route.policy === "shareable") {
        validatePublicParams(route, params, options.validatePublicRouteKey);
      }
      const segments = route.segments.map((segment) => {
        if (segment.literal !== null) return segment.literal;
        const parameter = segment.parameter;
        if (parameter === null) {
          throw new RouteDeckRouteError(
            "route_invariant",
            "Compiled route segment has no declaration.",
          );
        }
        return encodeSegment(parameter, params[parameter]);
      });
      let path = `/${segments.join("/")}`;
      if (route.policy === "session_bound") {
        const handle = routeOptions.resumeHandle;
        if (!handle) {
          throw new RouteDeckRouteError(
            "capability_required",
            "Session-bound RouteDeck links require a resume capability.",
          );
        }
        const validate = options.validateResumeCapability;
        if (validate && !validate(handle, route.nodeId, params)) {
          throw new RouteDeckRouteError(
            "capability_mismatch",
            "The RouteDeck resume capability is unavailable or mismatched.",
          );
        }
        path += `?resume_handle=${encodeURIComponent(handle)}`;
      } else if (routeOptions.resumeHandle !== undefined) {
        throw new RouteDeckRouteError(
          "capability_forbidden",
          "Shareable RouteDeck links do not accept resume capabilities.",
        );
      }
      return path;
    },

    policyForPath(path) {
      return match(path).route.policy;
    },

    policyForNode(nodeId) {
      const route = byNode.get(nodeId);
      if (!route) {
        throw new RouteDeckRouteError(
          "route_not_found",
          `Unknown RouteDeck route node: ${nodeId}`,
        );
      }
      return route.policy;
    },
  };
}

function compileRoute(
  nodeId: string,
  template: string,
  policy: DeepLinkPolicy,
): CompiledRoute {
  if (
    !template.startsWith("/") ||
    template.includes("?") ||
    template.includes("#") ||
    (template !== "/" && (template.endsWith("/") || template.includes("//")))
  ) {
    throw new RouteDeckRouteError(
      "route_template_invalid",
      `Invalid RouteDeck route template: ${template}`,
    );
  }
  const parameterNames: string[] = [];
  const segments = template
    .split("/")
    .filter(Boolean)
    .map((value): CompiledSegment => {
      if (value.startsWith("{") && value.endsWith("}")) {
        const name = value.slice(1, -1);
        if (!isIdentifier(name) || parameterNames.includes(name)) {
          throw new RouteDeckRouteError(
            "route_template_invalid",
            `Invalid RouteDeck route parameter in ${template}`,
          );
        }
        parameterNames.push(name);
        return { literal: null, parameter: name };
      }
      if (value.includes("{") || value.includes("}")) {
        throw new RouteDeckRouteError(
          "route_template_invalid",
          `Route parameters must occupy a complete segment: ${template}`,
        );
      }
      return { literal: value, parameter: null };
    });
  return { nodeId, policy, template, segments, parameterNames };
}

function ensureNoOverlaps(routes: readonly CompiledRoute[]): void {
  for (let leftIndex = 0; leftIndex < routes.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < routes.length; rightIndex += 1) {
      const left = routes[leftIndex];
      const right = routes[rightIndex];
      if (left && right && routesOverlap(left, right)) {
        throw new RouteDeckRouteError(
          "route_overlap",
          `Route ${right.nodeId} overlaps route ${left.nodeId}.`,
        );
      }
    }
  }
}

function routesOverlap(left: CompiledRoute, right: CompiledRoute): boolean {
  if (left.segments.length !== right.segments.length) return false;
  for (let index = 0; index < left.segments.length; index += 1) {
    const leftSegment = left.segments[index];
    const rightSegment = right.segments[index];
    if (!leftSegment || !rightSegment) return false;
    if (
      leftSegment.literal !== null &&
      rightSegment.literal !== null &&
      leftSegment.literal !== rightSegment.literal
    ) {
      return false;
    }
  }
  return true;
}

function splitLocalPath(path: string): { pathOnly: string; query: string } {
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("#")) {
    throw new RouteDeckRouteError(
      "route_invalid",
      "RouteDeck routes must be local paths without fragments.",
    );
  }
  const separator = path.indexOf("?");
  return separator === -1
    ? { pathOnly: path, query: "" }
    : { pathOnly: path.slice(0, separator), query: path.slice(separator + 1) };
}

function decodeResumeQuery(query: string): string {
  const parts = query ? query.split("&") : [];
  if (parts.length !== 1) {
    throw new RouteDeckRouteError(
      "capability_required",
      "Session-bound RouteDeck routes require exactly one resume_handle.",
    );
  }
  const part = parts[0];
  if (part === undefined) {
    throw new RouteDeckRouteError("capability_required", "Missing resume_handle.");
  }
  const separator = part.indexOf("=");
  if (separator < 1) {
    throw new RouteDeckRouteError(
      "capability_malformed",
      "The RouteDeck resume_handle query binding is malformed.",
    );
  }
  const key = decodeSegment(part.slice(0, separator));
  const value = decodeSegment(part.slice(separator + 1));
  if (key !== "resume_handle" || !value) {
    throw new RouteDeckRouteError(
      "capability_required",
      "Session-bound RouteDeck routes require exactly one resume_handle.",
    );
  }
  return value;
}

function validatePublicParams(
  route: CompiledRoute,
  params: Readonly<Record<string, string>>,
  validate: RouteDeckRouteCodecOptions["validatePublicRouteKey"],
): void {
  if (route.parameterNames.length === 0) return;
  if (!validate) {
    throw new RouteDeckRouteError(
      "public_route_validator_required",
      "Parameterized shareable routes require an injected key validator.",
    );
  }
  for (const name of route.parameterNames) {
    const value = params[name];
    encodeSegment(name, value);
    if (!validate(name, value ?? "")) {
      throw new RouteDeckRouteError(
        "public_route_key_invalid",
        `The public RouteDeck route binding is invalid for ${name}.`,
      );
    }
  }
}

function requireExactParams(
  route: CompiledRoute,
  params: Readonly<Record<string, string>>,
): void {
  const actual = Object.keys(params).sort();
  const expected = [...route.parameterNames].sort();
  if (
    actual.length !== expected.length ||
    actual.some((name, index) => name !== expected[index])
  ) {
    throw new RouteDeckRouteError(
      "route_parameters_invalid",
      `Route ${route.nodeId} requires parameters ${expected.join(", ")}.`,
    );
  }
}

function encodeSegment(name: string, value: string | undefined): string {
  if (!value || value.includes("/") || value.includes("\\")) {
    throw new RouteDeckRouteError(
      "route_parameter_invalid",
      `Route parameter ${name} must be non-empty and contain no separator.`,
    );
  }
  return encodeURIComponent(value);
}

function decodeSegment(value: string): string {
  let decoded: string;
  try {
    decoded = decodeURIComponent(value);
  } catch (error) {
    throw new RouteDeckRouteError(
      "route_encoding_invalid",
      "RouteDeck route contains malformed percent encoding.",
      { cause: error },
    );
  }
  if (decoded.includes("/") || decoded.includes("\\")) {
    throw new RouteDeckRouteError(
      "route_parameter_invalid",
      "Decoded RouteDeck route segment contains a separator.",
    );
  }
  return decoded;
}

function isIdentifier(value: string): boolean {
  if (!value) return false;
  const first = value.codePointAt(0);
  if (first === undefined || !isIdentifierStart(first)) return false;
  for (let index = 1; index < value.length; index += 1) {
    const code = value.codePointAt(index);
    if (code === undefined || (!isIdentifierStart(code) && !isDigit(code))) {
      return false;
    }
  }
  return true;
}

function isIdentifierStart(code: number): boolean {
  return code === 95 || (code >= 65 && code <= 90) || (code >= 97 && code <= 122);
}

function isDigit(code: number): boolean {
  return code >= 48 && code <= 57;
}
