import { FeatureCard, features } from "./feature-card";

export function FeaturesSection() {
  return (
    <section className="relative border-b border-fd-border bg-fd-card/50">
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <div className="mb-14 text-center">
          <p className="mb-3 text-sm font-medium uppercase tracking-widest text-fd-muted-foreground">
            Features
          </p>
          <h2 className="text-3xl font-bold tracking-tight text-fd-foreground md:text-4xl">
            Everything you need for RAG
          </h2>
        </div>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <FeatureCard key={feature.title} {...feature} />
          ))}
        </div>
      </div>
    </section>
  );
}
