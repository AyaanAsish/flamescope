// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  formatFlow,
  formatFlowRange,
  formatGravity,
  formatOxygen,
  formatOxygenRange,
  formatPressure,
  formatPressureRange,
  formatSpreadRate,
  fractionToPercent,
  kpaToPsi,
  NOT_AVAILABLE,
  percentToFraction,
  psiToKpa,
} from "@/lib/format";

/** Preset atmospheres of doc 08 section 4.1 as [kPa, psi] pairs. */
const PRESET_PRESSURES: [number, number][] = [
  [101.3, 14.7],
  [70.3, 10.2],
  [56.5, 8.2],
  [29.6, 4.3],
];
const PSI_TOLERANCE = 0.05;
const KPA_TOLERANCE = 0.1;

describe("oxygen: fraction to percent (doc 10 section 2.3 rule 4, doc 05 section 1)", () => {
  it("FR-07: converts the API fraction to the percent shown in the UI and back", () => {
    expect(fractionToPercent(0.34)).toBeCloseTo(34, 10);
    expect(fractionToPercent(1)).toBe(100);
    expect(percentToFraction(30)).toBeCloseTo(0.3, 10);
    expect(percentToFraction(fractionToPercent(0.21))).toBeCloseTo(0.21, 10);
  });

  it("FR-07: oxygen text always carries the percent unit", () => {
    expect(formatOxygen(0.34)).toBe("34 % O₂");
    expect(formatOxygen(0.21)).toBe("21 % O₂");
    expect(formatOxygenRange([0.14, 0.21])).toBe("14 % – 21 %");
  });
});

describe("pressure: kPa and psi toggle (doc 08 section 4.1, doc 10 section 5 Scenario Lab)", () => {
  it.each(PRESET_PRESSURES)("FR-07: %s kPa is %s psi", (kpa, psi) => {
    expect(Math.abs(kpaToPsi(kpa) - psi)).toBeLessThan(PSI_TOLERANCE);
    expect(Math.abs(psiToKpa(psi) - kpa)).toBeLessThan(KPA_TOLERANCE);
    expect(formatPressure(kpa, "psi")).toBe(`${psi} psi`);
  });

  it("FR-07: 14.7 psi is 101.35 kPa within 0.1 and the round trip is lossless", () => {
    expect(Math.abs(psiToKpa(14.7) - 101.35)).toBeLessThan(KPA_TOLERANCE);
    expect(kpaToPsi(psiToKpa(8.2))).toBeCloseTo(8.2, 10);
  });

  it("FR-07: kPa is the default display unit", () => {
    expect(formatPressure(56.5)).toBe("56.5 kPa");
    expect(formatPressureRange([101.3, 101.3])).toBe("101.3 kPa");
    expect(formatPressureRange([50, 101.3])).toBe("50 kPa – 101.3 kPa");
  });
});

describe("numbers with units (doc 10 section 2.3 rule 4)", () => {
  it("FR-06: flow, gravity and spread rate carry their canonical units", () => {
    expect(formatFlow(10)).toBe("10 cm/s");
    expect(formatFlowRange([1, 55])).toBe("1 cm/s – 55 cm/s");
    expect(formatGravity(0.166)).toBe("0.166 g");
    expect(formatGravity(0)).toBe("0 g");
    expect(formatSpreadRate(1.25)).toBe("1.25 mm/s");
  });

  it("FR-02: a half-open range is shown as a bound, never as a point (doc 04 s2)", () => {
    expect(formatOxygenRange([null, 0.85])).toBe("≤ 85 %");
    expect(formatPressureRange([50, null])).toBe("≥ 50 kPa");
    expect(formatFlowRange([null, null])).toBe(NOT_AVAILABLE);
  });

  it("FR-15: unknown (null) values are shown as not available, never as zero", () => {
    expect(formatOxygen(null)).toBe(NOT_AVAILABLE);
    expect(formatPressure(undefined)).toBe(NOT_AVAILABLE);
    expect(formatFlow(null)).toBe(NOT_AVAILABLE);
    expect(formatGravity(null)).toBe(NOT_AVAILABLE);
    expect(formatOxygenRange(null)).toBe(NOT_AVAILABLE);
    expect(NOT_AVAILABLE).not.toMatch(/^0/);
  });
});
