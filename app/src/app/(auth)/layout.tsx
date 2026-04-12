import { Logo } from "@/components/brand/logo";

const AuthLayout = ({ children }: { children: React.ReactNode }) => (
  <main
    id="main"
    className="flex min-h-screen flex-col items-center justify-center bg-background px-6 py-16"
  >
    <div className="mb-8">
      <Logo />
    </div>
    {children}
  </main>
);

export default AuthLayout;
