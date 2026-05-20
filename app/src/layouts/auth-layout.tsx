import { Logo } from "@/components/brand/logo";
import { ThemeControl } from "@/features/theme/theme-control";

export const AuthLayout = ({ children }: { children: React.ReactNode }) => (
  <main
    id="main"
    className="relative flex min-h-screen flex-col items-center justify-center bg-background px-6 py-16"
  >
    <div className="absolute top-4 right-4">
      <ThemeControl />
    </div>
    <div className="mb-8">
      <Logo />
    </div>
    {children}
  </main>
);
