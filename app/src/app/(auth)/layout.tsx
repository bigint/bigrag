import { Logo } from "@/components/brand/logo";

const AuthLayout = ({ children }: { children: React.ReactNode }) => (
  <div className="relative min-h-svh overflow-hidden">
    <div className="absolute inset-0 -z-10 bg-[var(--color-background)]" />
    <div className="absolute inset-0 -z-10 opacity-60 [background:radial-gradient(circle_at_20%_0%,color-mix(in_oklab,var(--color-primary),transparent_80%),transparent_60%),radial-gradient(circle_at_80%_100%,color-mix(in_oklab,var(--color-info),transparent_85%),transparent_55%)]" />
    <main
      id="main"
      className="relative z-10 flex min-h-svh flex-col items-center justify-center px-6 py-16"
    >
      <div className="mb-8">
        <Logo />
      </div>
      {children}
    </main>
  </div>
);

export default AuthLayout;
