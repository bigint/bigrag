import {
  CodeSection,
  CtaSection,
  FeaturesSection,
  Footer,
  Hero,
  StatsSection,
} from "@/components/home";

export default function Page() {
  return (
    <main>
      <Hero />
      <FeaturesSection />
      <CodeSection />
      <StatsSection />
      <CtaSection />
      <Footer />
    </main>
  );
}
