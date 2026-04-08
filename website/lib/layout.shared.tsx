import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import { GitHubIcon, SponsorIcon } from "@/components/icons";

function BigRAGLogo() {
  return (
    <svg
      aria-hidden="true"
      className="size-6"
      fill="none"
      viewBox="0 0 32 32"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect fill="#000000" height="32" rx="8" width="32" />
      <path d="M12 6H20L26 12V20L20 26H12L6 20V12L12 6Z" fill="white" opacity="0.9" />
      <path d="M12 6H20L26 12L20 18H12L6 12L12 6Z" fill="white" />
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
