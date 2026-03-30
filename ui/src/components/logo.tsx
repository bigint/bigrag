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
      <rect fill="#000000" height="512" rx="96" width="512" />
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
