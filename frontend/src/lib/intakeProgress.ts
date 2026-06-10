import { INTAKE_DOMAINS, type IntakeDomain, type SponsorIntake } from "@/types";

const VALID_DOMAINS = new Set<IntakeDomain>(INTAKE_DOMAINS.map((d) => d.key));

/** Merge domain completion lists — never drop a previously completed domain. */
export function mergeDomainsCompleted(
  existing: IntakeDomain[],
  incoming: IntakeDomain[] | string[] | null | undefined
): IntakeDomain[] {
  const seen = new Set<IntakeDomain>();
  for (const raw of [...existing, ...(incoming ?? [])]) {
    const domain = raw as IntakeDomain;
    if (VALID_DOMAINS.has(domain)) {
      seen.add(domain);
    }
  }
  return INTAKE_DOMAINS.map((d) => d.key).filter((key) => seen.has(key));
}

/** Apply a server intake payload without losing local domain progress. */
export function mergeIntakeSession(
  previous: SponsorIntake | null,
  incoming: SponsorIntake
): SponsorIntake {
  const domains_completed = mergeDomainsCompleted(
    previous?.domains_completed ?? [],
    incoming.domains_completed
  );
  const allComplete = domains_completed.length === INTAKE_DOMAINS.length;
  return {
    ...incoming,
    domains_completed,
    ready_to_compile: incoming.ready_to_compile || allComplete,
    status:
      incoming.status === "COMPILED"
        ? "COMPILED"
        : incoming.ready_to_compile || allComplete
        ? "READY_TO_COMPILE"
        : incoming.status,
  };
}
