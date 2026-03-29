import { cn } from "@/lib/utils";

interface LogoProps {
  readonly className?: string;
  readonly size?: number;
}

export const Logo = ({ className, size = 28 }: LogoProps) => {
  return (
    <svg
      className={cn("shrink-0", className)}
      fill="none"
      height={size}
      viewBox="0 0 512 512"
      width={size}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient
          gradientUnits="userSpaceOnUse"
          id="logo-bg"
          x1="0"
          x2="512"
          y1="0"
          y2="512"
        >
          <stop offset="0%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#1d4ed8" />
        </linearGradient>
      </defs>
      <rect fill="url(#logo-bg)" height="512" rx="96" width="512" />
      <rect fill="#ffffff" height="296" rx="28" width="56" x="165" y="108" />
      <circle
        cx="259"
        cy="316"
        fill="none"
        r="66"
        stroke="#ffffff"
        strokeWidth={44}
      />
    </svg>
  );
};
