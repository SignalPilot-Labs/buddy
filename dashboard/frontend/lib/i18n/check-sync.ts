import { en } from "./en";
import { bn } from "./bn";

function collectKeys(obj: Record<string, unknown>, prefix: string): string[] {
  const result: string[] = [];
  for (const key of Object.keys(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    const value = obj[key];
    if (typeof value === "object" && value !== null) {
      result.push(...collectKeys(value as Record<string, unknown>, fullKey));
    } else {
      result.push(fullKey);
    }
  }
  return result;
}

const enKeys = new Set(collectKeys(en as unknown as Record<string, unknown>, ""));
const bnKeys = new Set(collectKeys(bn as unknown as Record<string, unknown>, ""));

const missing = [...enKeys].filter((k) => !bnKeys.has(k));
const extra = [...bnKeys].filter((k) => !enKeys.has(k));

for (const key of missing) {
  console.error(`  MISSING: ${key}`);
}
for (const key of extra) {
  console.warn(`  EXTRA: ${key}`);
}

if (missing.length > 0 || extra.length > 0) {
  console.log(`i18n check: FAILED — ${missing.length} missing, ${extra.length} extra`);
  process.exit(1);
} else {
  console.log(`i18n check: OK (${enKeys.size} keys)`);
}
