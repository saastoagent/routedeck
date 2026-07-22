import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const base = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export function MenuIcon(props: IconProps) {
  return <svg {...base} {...props}><path d="M4 7h16M4 12h16M4 17h16" /></svg>;
}

export function SearchIcon(props: IconProps) {
  return <svg {...base} {...props}><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg>;
}

export function GitHubIcon(props: IconProps) {
  return <svg {...base} {...props}><path d="M15 22v-4a4.7 4.7 0 0 0-1-3.5c3.3-.4 6.8-1.6 6.8-7.4A5.7 5.7 0 0 0 19.3 3 5.4 5.4 0 0 0 19.1 0S17.9-.4 15 1.5a14.4 14.4 0 0 0-6 0C6.1-.4 4.9 0 4.9 0A5.4 5.4 0 0 0 4.7 3a5.7 5.7 0 0 0-1.5 4.1c0 5.8 3.5 7 6.8 7.4A4.7 4.7 0 0 0 9 18v4" /><path d="M9 19c-3 .9-3-1.5-4.2-2" /></svg>;
}

export function CloseIcon(props: IconProps) {
  return <svg {...base} {...props}><path d="m6 6 12 12M18 6 6 18" /></svg>;
}

export function ArrowIcon(props: IconProps) {
  return <svg {...base} {...props}><path d="M5 12h14M14 7l5 5-5 5" /></svg>;
}

export function ChevronIcon(props: IconProps) {
  return <svg {...base} {...props}><path d="m9 6 6 6-6 6" /></svg>;
}
