import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import { GitHubIcon, SponsorIcon } from "@/components/icons";

function BigRAGLogo() {
  return (
    <svg
      aria-hidden="true"
      className="size-6 text-primary"
      fill="none"
      viewBox="0 0 32 32"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect fill="currentColor" height="32" rx="8" width="32" />
      <path d="M8 12L16 6L24 12V20L16 26L8 20V12Z" fill="white" opacity="0.9" />
      <path d="M16 6L24 12L16 18L8 12L16 6Z" fill="white" />
    </svg>
  );
}

export function baseOptions(): BaseLayoutProps {
  return {
    links: [
      {
        icon: <GitHubIcon className="size-5" />,
        label: "GitHub",
        text: "GitHub",
        type: "icon",
        url: "https://github.com/bigint/bigrag",
      },
      {
        icon: <SponsorIcon className="size-5" />,
        label: "Sponsor",
        text: "Sponsor",
        type: "icon",
        url: "https://github.com/sponsors/bigint",
      },
    ],
    nav: {
      title: (
        <div className="flex items-center gap-2">
          <BigRAGLogo />
          <span className="font-semibold tracking-tight">bigRAG</span>
        </div>
      ),
      transparentMode: "top",
    },
  };
}
