import type { Source } from '../types';

/**
 * Canned content for mock mode. Everything here is placeholder material written for UI development:
 * document names, pages, chunk IDs and passages are NOT real NASA records.
 */
export interface MockTopic {
  id: string;
  keywords: string[];
  answer: string;
  sources: Omit<Source, 'is_mock'>[];
}

export const MOCK_ERROR_TRIGGER = '/error';

export const mockTopics: MockTopic[] = [
  {
    id: 'instability',
    keywords: ['instability', 'oscillat', 'thermoacoustic', 'rayleigh', 'combustor', 'pressure fluctuation', 'chugging'],
    answer: `## Combustion instability

Combustion instability happens when **unsteady heat release** from the flame couples with the **acoustic modes** of the combustion chamber, forming a self-reinforcing feedback loop.

### Main mechanisms
1. **Flame–acoustic coupling.** Pressure waves perturb the flame, the flame perturbs heat release, and that heat release feeds energy back into the wave. The *Rayleigh criterion* says the oscillation grows when heat release and pressure fluctuate in phase.
2. **Vortex shedding.** Coherent structures shed from flame holders or injectors can burn in bursts at a rhythm that matches a chamber mode.
3. **Equivalence-ratio fluctuations.** Pressure oscillations modulate fuel or air feed rates, so the mixture reaching the flame varies periodically.
4. **Feed-system coupling.** Low-frequency "chugging" can arise when propellant line dynamics interact with chamber pressure.

### Common mitigations
- Acoustic dampers such as baffles, Helmholtz resonators, and acoustic liners
- Injector redesign and fuel staging to shift the heat-release response
- Active control that modulates fuel flow out of phase with measured pressure

> *This is a mock response. The cited passages below are placeholders for UI development.*`,
    sources: [
      {
        document: 'MOCK_Combustion_Instability_Primer.pdf',
        page: 12,
        chunk_id: 'mock_chunk_012',
        content:
          'Self-excited oscillations arise when the unsteady heat release rate is sufficiently in phase with the chamber pressure fluctuation that the net acoustic energy gain exceeds the damping losses in the system.',
      },
      {
        document: 'MOCK_Combustion_Instability_Primer.pdf',
        page: 27,
        chunk_id: 'mock_chunk_031',
        content:
          'Passive control devices such as baffles and quarter-wave or Helmholtz resonators increase acoustic damping and are typically tuned to the dominant tangential or longitudinal mode.',
      },
      {
        document: 'MOCK_Propulsion_Dynamics_Review.pdf',
        page: 5,
        chunk_id: 'mock_chunk_104',
        content:
          'Low-frequency feed-system coupled instabilities involve interaction between propellant line dynamics and chamber pressure, and are distinct from the higher-frequency acoustic modes of the chamber itself.',
      },
    ],
  },
  {
    id: 'flame-spread',
    keywords: ['flame spread', 'spread', 'microgravity', 'gravity', 'buoyan', 'fire safety', 'spacecraft fire'],
    answer: `## Flame spread in microgravity

On Earth, **buoyancy** pulls fresh air toward a flame and carries hot products away. In microgravity that natural convection disappears, so oxidizer reaches the flame mainly by **diffusion** or by whatever **forced flow** exists, such as cabin ventilation.

| Aspect | Normal gravity | Microgravity |
| --- | --- | --- |
| Oxidizer transport | Buoyant convection plus diffusion | Diffusion plus forced flow only |
| Flame shape | Elongated, tilted with gravity | Rounder, more symmetric |
| Low-flow behavior | Buoyant flow keeps a baseline supply | Flame can weaken or extinguish as flow drops |

### Why it matters for safety
- Materials that self-extinguish in a normal-gravity test can sometimes **keep burning** in microgravity at low flow speeds, so ground tests alone may not be conservative.
- Flame spread depends strongly on **flow speed, oxygen concentration, pressure, and sample geometry**, which is why space experiments vary those parameters systematically.

> *This is a mock response. The cited passages below are placeholders for UI development.*`,
    sources: [
      {
        document: 'MOCK_Microgravity_Flammability_Overview.pdf',
        page: 8,
        chunk_id: 'mock_chunk_044',
        content:
          'Without buoyant convection, oxidizer supply to the flame is governed by diffusion and any imposed flow. Flame spread therefore depends strongly on the ambient flow velocity relative to the fuel surface.',
      },
      {
        document: 'MOCK_Microgravity_Flammability_Overview.pdf',
        page: 19,
        chunk_id: 'mock_chunk_058',
        content:
          'Standard normal-gravity flammability screening does not necessarily bound material behavior in low-gravity, low-flow environments, where some samples sustain flames that would extinguish on the ground.',
      },
    ],
  },
  {
    id: 'spherical-flames',
    keywords: ['spherical', 'blue', 'droplet', 'soot', 'cool flame', 'jet flame', 'candle', 'shape'],
    answer: `## Why microgravity flames look different

In normal gravity a candle flame is teardrop-shaped and yellow because buoyant flow stretches it upward and soot particles glow as they heat up.

In microgravity:
- **No buoyant flow** means combustion is diffusion-dominated, so the flame becomes **spherical** (or close to it) around a small fuel source.
- **Less soot** forms in many conditions, so the flame appears **dimmer and bluer**.
- Flames can burn **longer and more steadily** at low heat release, which makes them useful for studying fundamental combustion chemistry.

### A notable finding
Droplet combustion work on the ISS observed **cool flames**: after the visible hot flame went out, large fuel droplets could keep burning at much lower temperatures. This behavior is difficult to isolate on Earth.

> *This is a mock response. The cited passages below are placeholders for UI development.*`,
    sources: [
      {
        document: 'MOCK_Droplet_Combustion_ISS_Summary.pdf',
        page: 3,
        chunk_id: 'mock_chunk_007',
        content:
          'In the absence of buoyancy, an isolated burning droplet develops a nearly spherically symmetric flame, which simplifies comparison with one-dimensional combustion models.',
      },
      {
        document: 'MOCK_Droplet_Combustion_ISS_Summary.pdf',
        page: 14,
        chunk_id: 'mock_chunk_021',
        content:
          'Following radiative extinction of the hot flame, a lower-temperature cool-flame regime was observed to sustain burning of large droplets for an extended period.',
      },
    ],
  },
  {
    id: 'oxygen',
    keywords: ['oxygen', 'flammab', 'limiting', 'extinction', 'loc', 'material', 'atmosphere', 'pressure'],
    answer: `## Oxygen concentration and flammability

The **limiting oxygen concentration (LOC)** is the lowest oxygen level at which a material can sustain a flame under given conditions. It is **not a single fixed number** for a material, since it shifts with flow, pressure, geometry, and gravity.

### Key relationships
- **Higher oxygen** generally raises flame temperature and spread rate, and widens the range of materials that can burn.
- **Lower ambient flow** can force a higher oxygen requirement to sustain a flame, because less oxidizer reaches the reaction zone.
- **Reduced pressure** changes heat and mass transport, so exploration cabin designs that pair lower total pressure with enriched oxygen need dedicated flammability data.

### Practical takeaway
Spacecraft material selection should use test data collected at conditions **close to the intended atmosphere and flow**, not only standard ground-test thresholds.

> *This is a mock response. The cited passages below are placeholders for UI development.*`,
    sources: [
      {
        document: 'MOCK_Material_Flammability_Guide.pdf',
        page: 22,
        chunk_id: 'mock_chunk_066',
        content:
          'The limiting oxygen concentration depends on the test configuration, including ambient pressure, flow velocity, sample thickness, and orientation relative to gravity.',
      },
      {
        document: 'MOCK_Exploration_Atmospheres_Brief.pdf',
        page: 6,
        chunk_id: 'mock_chunk_090',
        content:
          'Proposed exploration atmospheres combine reduced total pressure with elevated oxygen fraction, which requires re-evaluating material flammability under those specific conditions.',
      },
    ],
  },
  {
    id: 'saffire',
    keywords: ['saffire', 'cygnus', 'large-scale', 'large scale'],
    answer: `## Saffire-style large-scale fire experiments

Saffire experiments were designed to study **fire growth at a scale that is not practical inside crewed spacecraft**. They ran in an uncrewed cargo vehicle after it left the station, so a deliberate fire posed no risk to people.

### What they were built to study
- **Flame spread over larger samples** than typical small-scale microgravity tests
- Behavior under **controlled low-speed flow**
- Data to **validate fire models** and to check whether ground-based material tests are adequate for spacecraft use

Instruments typically include cameras, thermocouples, radiometers, and gas sensors, with data returned by telemetry before the vehicle reentered.

> *This is a mock response. The cited passages below are placeholders for UI development.*`,
    sources: [
      {
        document: 'MOCK_Large_Scale_Spacecraft_Fire_Tests.pdf',
        page: 2,
        chunk_id: 'mock_chunk_002',
        content:
          'Conducting fire tests in an uncrewed vehicle allows sample sizes and fire growth that would be unacceptable inside an occupied habitat, providing data to validate numerical fire models.',
      },
    ],
  },
];

export function fallbackAnswer(question: string): string {
  return `## Mock mode

I'm running with **mock data**, so I only have canned answers for a few combustion topics and can't answer *"${question.trim().slice(0, 120)}"* specifically.

Try one of these:
- What causes combustion instability?
- How does microgravity affect flame spread?
- Why do flames look blue and spherical in microgravity?
- How does oxygen concentration influence material flammability?
- What did the Saffire experiments study?

To test the error state, send a message containing \`${MOCK_ERROR_TRIGGER}\`.`;
}
