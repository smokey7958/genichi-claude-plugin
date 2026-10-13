# Process selection and design-for-manufacture notes

Use this to suggest a process route and point out what drives cost. The figures are typical industry ranges for orientation, not quotes: the factory's quote is what counts, and you should say so when you use them.

## Contents
- Picking a process by quantity and shape
- Tolerances and what they cost
- Materials at a glance
- Finishes and heat treatment
- Design choices that raise cost
- Tooling, lead time and shipping basics

## Picking a process by quantity and shape

| Process | Good for | Typical quantity | Tooling |
|---|---|---|---|
| CNC milling and turning | Precise metal or plastic parts, prototypes | 1 to about 5,000 | None; fixtures only |
| Laser or waterjet cutting plus bending | Flat and bent sheet parts, brackets, enclosures | 1 to about 10,000 | None or simple |
| Metal stamping | Flat or formed sheet parts in volume | from about 5,000 | Progressive or single die |
| Hot or cold forging | Strong parts: wrenches, pliers, hammer heads, shafts | from about 1,000 | Forging dies |
| Investment (lost-wax) casting | Complex steel or stainless shapes near final form | from about 500 | Wax injection mold |
| Die casting | Thin-walled aluminium or zinc housings | from about 5,000 | Steel die |
| Sand casting | Large iron or aluminium parts | from about 50 | Pattern |
| Plastic injection molding | Plastic parts in volume | from about 1,000 | Steel or aluminium mold |
| 3D printing (FDM, SLA, SLS, metal) | Prototypes, fit checks, very small batches | 1 to about 100 | None |

Rules of thumb:

- Low quantity and high precision leans to CNC. High quantity leans to a near-net process (forging, stamping, casting, molding) plus light machining on the critical features.
- Tooling cost is paid once. Spread it over the lifetime volume, not the first order, when comparing routes.
- Hand tools such as pliers, wrenches and screwdrivers are usually forged or cold-headed, heat treated, then machined and ground on the working surfaces. Machining them from bar only makes sense for prototypes.

## Tolerances and what they cost

- A general tolerance class covers everything not called out. ISO 2768-m (for example ±0.1 mm for 3 to 6 mm features, ±0.3 mm for 120 to 400 mm) is a common default for machined parts.
- Typical capabilities: CNC ±0.01 to ±0.05 mm; stamping ±0.05 to ±0.2 mm; forging ±0.3 to ±1 mm before machining; investment casting about ±0.5% of the dimension; injection molding ±0.05 to ±0.2 mm depending on size and resin.
- Put tight tolerances only on features that mate or function. Each extra decimal place on every dimension multiplies inspection time and scrap.

## Materials at a glance

- Carbon steel (S45C, 1045): cheap, strong, needs a coating against rust.
- Alloy tool steels: chrome vanadium (Cr-V) for wrenches and sockets; S2 for screwdriver bits; high-carbon steel for cutting edges of pliers and nippers.
- Stainless steel: 304 is corrosion resistant, not hardenable; 420 and 440C are hardenable for blades and tweezers.
- Aluminium: 6061-T6 general purpose; 7075-T6 high strength; anodize for wear and color.
- Brass (C3604) machines fast and suits fittings; copper for electrical parts.
- Engineering plastics: POM for low-friction parts, PA66-GF30 for stiffness, PP or ABS for housings and handles, TPR or TPE for soft grips.

## Finishes and heat treatment

- Heat treatment: through hardening, induction hardening (for example cutting edges of pliers), carburizing, nitriding. Give the target hardness (HRC) and where it applies.
- Corrosion protection: black oxide (light), zinc plating, nickel or chrome plating, phosphate, powder coating, anodizing (aluminium), passivation (stainless).
- Handles and grips: dip coating, dual-material injection molded grips, insulated grips tested to IEC 60900 for live electrical work.
- Marking: laser engraving is permanent and needs no tooling; pad printing suits colored logos on plastic; stamped or forged-in marks suit high volumes.

## Design choices that raise cost

- Sharp inside corners on milled pockets (cutters are round; allow a radius)
- Deep, narrow pockets and small holes deeper than about 5 times their diameter
- Undercuts in molded or cast parts (need side actions)
- Very thin walls, or uneven wall thickness in plastic parts (sink marks, warping)
- Cosmetic requirements on faces nobody sees
- Many different fasteners or thread sizes on one part
- Hardening after final machining without allowing for distortion

## Tooling, lead time and shipping basics

- Typical lead times, if nothing unusual is involved: machined samples 1 to 3 weeks; forging dies or injection molds 4 to 8 weeks plus sampling; production after sample approval 3 to 8 weeks. Holidays such as Lunar New Year shift schedules.
- The usual sequence is quote, then drawing confirmation, then tooling (if any), then samples for approval, then mass production and inspection.
- Shipping terms: EXW means the buyer arranges everything from the factory; FOB means the seller loads it at the port of export; DDP means the seller delivers with duties paid. State which one the quote should use.
