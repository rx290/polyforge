# Robot wiring through limbs and joints: findings

Scope: how open-source legged and armed robots get wires from body to limb, general practice numbers, and sizing rules for 3D-printed SG90 / MG996R quadrupeds and a small biped. Every claim carries a URL. Where a source did not give a number, this doc says so and the machine file (`src/polyforge/robot/parts/wires.json`) uses null. Items marked (derived) are my own arithmetic or engineering judgment, not a sourced fact.

## 1. Per design

| Design | Body to limb path | Reported problems | Sources |
|-|-|-|-|
| Petoi Nybble / Bittle | Wires run inside the body, around the standoff columns, then plug into the servo pins. The frame has built-in slots "designed as wire organizer". Lower-leg servos sit in a window and the wire goes through a notch on the inner edge; fold direction is shown only in a video. | Plug orientation (reversed plug can burn the chip). Cable length is a product spec: short cables for neck, tail and shoulders, long cables for head tilt and knees. Wires must not get between plugs and frame. | https://nybble.petoi.com/chapter5 , https://bittle.petoi.com/4-connect-the-wires/nyboard , https://guide.petoi.com/product/bittle-x/quick-start-guide/assembling |
| InMoov bicep / shoulder | Bicep servo pots are extended by cutting and soldering extra wire (not desoldering from the servo PCB); cables run in the gap of the servo holder; "tuck down the cable along the frame ... this will avoid pinching the cable during actuations". Cables about 25/30 cm. Builder routing: forearm cables up through the bicep, out the back, through slots in the pivot part, between upper torso parts, then out a torso slot to the controller; leave slack for movement. A 14/16-wire ribbon harness is also used ("no need for heavy gauge wires"). | Pinching during actuation; extra-length cables need a larger opening cut with a knife. | https://inmoov.fr/bicep/ , https://synthiam.com/Community/Questions/3171 |
| Poppy Humanoid / Ergo Jr | Dynamixel daisy chain: servos share one bus, so only one cable goes limb to limb. Poppy biped leg subassembly lists a 250 mm 3-pin cable per MX-28. Ergo Jr: XL-320 chain. Exact in-joint routing is in the Poppy docs/videos and was not retrievable as text. | Each servo needs a unique ID before chaining; reversed chain direction was a reported mistake in a related OpenHand guide. No cable-fatigue report found. | https://github.com/poppy-project/Poppy-lightweight-biped-legs/blob/master/doc/subassemblies/left_thigh_assembly_instructions.md , https://robotis.us/robotis-ir-pr-blog/the-ultimate-dynamixel-daisy-chaining-guide , https://github.com/christopheKJU/poppy-ergo-jr/blob/master/README.md |
| OpenDog (James Bruton) | Repo is CAD and code per episode (Part1 to Part17). The README gives no wiring detail; I found no text source on leg cable routing. Treat as unknown. | None found in text sources. | https://github.com/XRobots/openDog |
| SpotMicro / SpotMicroAI | Docs defer to the GitLab basic repo; no wiring text on the docs page. Community ESP32 variants list four servo extension cables for the lower legs, about 10 to 15 cm each. | Extensions add connectors (a premade extension adds four contact points vs one or two for a splice), so crimp quality matters. | https://spotmicroai.readthedocs.io/en/latest/ , https://github.com/michaelkubina/SpotMicroESP32 , https://github.com/hugogarrix/SpotMicroESP32-Hugo , https://www.rctech.net/forum/showthread.php?p=15627935 |
| EEZYbotARM Mk2 | Listing states internal cable routing in the main big arms. Step-level routing not retrievable. | None found. | https://www.myminifactory.com/object/3d-print-eezybotarm-mk2-46620 |
| Otto DIY | Each foot's wires go through the gap in its leg, then through the leg hole and body slots, then feet are fixed from the back. Servo pins: brown ground, orange signal. | None specific found. | https://www.instructables.com/OttoDIY-Robot , https://www.hackster.io/webotricks/otto-diy-build-your-own-robot-in-one-hour-af637c |
| SunFounder PiDog (related) | Servo wires routed along the legs. Owner worried leg motion would cut them; moderator said length and slack are enough, loosen routing if tight. | Fear of cuts from constant leg motion, no actual breakage described. | https://forum.sunfounder.com/t/servo-wires-breaking/4835 |

Pattern across designs: hobby builds use (a) a body-side wire organizer, (b) a notch or gap at each limb entry, (c) a loop of slack, and (d) longer-cable servos where the limb is far. Daisy-chain servos (Dynamixel) cut the wire count through each joint to one cable.

## 2. Techniques catalogue

**Hollow joints / through-axis passes.** Run the cable through the rotation axis so it only twists, not bends. Good for continuous or large angles. Cost: needs a bore larger than the bundle plus connector. Sources on this are mostly patents (rotary joint cable management: https://eureka.patsnap.com/patent-US10611038B2 ). A coil that behaves like a clock spring (cable never reverse-bends) is described in a fruit-picking robot patent: https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12096733 .

**Service loops (slack).** Sourced numbers are thin. One trolling-motor manual calls for a service loop of at least 25 cm with the rotating joint centred on the loop: https://www8.garmin.com/manuals/webhelp/GUID-9C83E43A-D15D-4D48-9AF6-AF0CBFA49D98/EN-US/GUID-E3B1B7E3-E4BC-4E69-9628-0A0CE54A2471.html . A search snippet from a manipulator patent states the bundle ends up 20 to 50 percent longer than the arm it runs along (I could not open the scanned PDF to verify which patent; treat as unverified; candidates from the search: https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7320264 ). A separate patent says slack is traditionally set by operator experience (https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7773850 ). Servo-scale rule (derived): loop must absorb the arc travel. Extra length at a joint of radius r (cable offset from axis) over angle theta is about r x theta (rad); add the bend-radius allowance. Example: 15 mm offset, 120 degrees (2.09 rad) gives about 31 mm, so give 40 to 50 mm of slack plus a loop with radius >= 10 x OD.

**Clips and channels.** Petoi uses slots in the frame as organizers (see section 1); InMoov uses a servo-holder gap and tucks cable along the frame to avoid pinching. Keep channels open on one side or snap-lid so connectors can be fitted.

**Drag chains (e-chain).** Chain bend radius should be >= the cable's minimum bend radius (https://www.igus.eu/flexible-cable/wiki/structure-and-shielding/bend-radius ). igus reserves 10 percent clearance for electric round cables, 5 to 10 percent for pneumatic, 20 percent for hydraulic and media hoses (https://blog.igus.eu/knowledge-base/tag/filling ). Example small chains: E04 inner height 7 mm, max cable diameter 4.5 mm (https://www.igus.ca/product/series-E04 ); RS listings show chains from W48 x D19 mm with 28 to 48 mm bend radius up to W66 x D50 with 175 mm (https://uk.rs-online.com/web/p/cable-trunkings/7577428/ , https://nz.rs-online.com/web/p/cable-trunking/3825587 ). Chain pitch was not found in sources. Drag chains are overkill for a servo leg; use only for linear travel.

**Slip rings.** Needed only for continuous rotation. Adafruit 1196: 22 mm body, 44 mm flange, 12 wires, 2 A per wire at 240 V, 300 RPM rated, 28 AWG leads about 15 cm: https://www.adafruit.com/product/1196 . A legged robot joint rarely needs one; a service loop covers <= about 270 degrees.

**Strain relief at connectors.** Not found as a quantified rule in sources. (derived) Fix the cable to the part 15 to 20 mm before the connector with a clip, so joint motion bends the cable in the loop and never at the crimp. Extension cables add contact points (see SpotMicro row), so prefer one correct-length lead.

## 3. Wire data and sizing rule

Outer diameters (OD), conductor diameter and chassis current:

| AWG | Bare conductor mm | OD silicone/hookup listing mm | OD PVC mm | Chassis current A (rule of thumb) | Notes |
|-|-|-|-|-|-|
| 22 | 0.645 | 1.6 | null | 7 | Pololu servo extension cables use 22 AWG, 60 strands |
| 24 | 0.511 | 1.4 | null | 3.5 | |
| 26 | 0.404 | 1.5 (Adafruit silicone, +/-0.1; one listing says 1.4) | null | 2.2 | Robu sells 26 AWG servo extensions |
| 28 | 0.320 | 1.2 | null | 1.4 | Adafruit slip-ring leads are 28 AWG |

Sources: conductor diameter and chassis current: https://www.powerstream.com/Wire_Size.htm (their page calls them rules of thumb, not design limits; "power transmission" column is far lower, 0.92 A for 22 AWG). OD for 22, 24, 28 AWG: openelab 1007-type listing (+/-0.2 mm, manual measurement; page titled silicone but spec says 1007 electronic wire, insulation not confirmed): https://openelab.io/a/s/products/22awg-silicone-electrical-wire-cable , https://openelab.io/a/s/products/24awg-silicone-electrical-wire-cable , https://openelab.io/a/s/products/28awg-silicone-electrical-wire-cable . 26 AWG silicone: https://core-electronics.com.au/silicone-cover-stranded-core-wire-25ft-26awg-green.html.plain.md . Caution: a thick-wall silicone 22 AWG (Alpha Wire) is 3.3 mm OD, so OD depends heavily on the product: https://ie.rs-online.com/web/p/hook-up-wire/9043790 . No clean PVC vs silicone side-by-side table was found, so od_pvc is null; measure your actual wire.

Servo cables: SG90 lead about 24 to 25 cm, 3-pin female JR-type plug (https://www.taydaelectronics.com/electromechanical/dc-motor/sg90-servo-motor.html , https://protosupplies.com/product/servo-motor-micro-sg90/ ). SG90 wire gauge and MG996R lead length/gauge: not found in sources (null). Typical extension leads are 26 AWG (https://robu.in/product/60cm-servo-lead-extention-jr-26awg-1pcs ) or 22 AWG (https://www.pololu.com/catalog/product/2185 ). (derived) A flat 3 x 26 AWG lead is about 1.5 x 4.5 mm.

Connectors that must pass a channel: 3-way Dupont-style housing 14.0 x 7.62 x 2.6 mm, wire range 22 to 30 AWG (https://pro.maplin.co.uk/products/3-way-dupont-style-2-54mm-pin-housing ); JR housing is slightly wider than Futaba (forum anecdote: https://discuss.ardupilot.org/t/where-to-buy-female-to-female-futaba-connector-wires/16331 ); JST XHP-3 is 9.8 mm long (ambiguous in listing; XHP-2 is 5.7 x 7.3 mm per https://ph.rs-online.com/web/p/products/8201611 ). JST PH 2.0 dimensions not found.

**Sizing rule (settled):**
1. Fill factor 0.40: channel area >= bundle area / 0.40. Source: NEC Chapter 9 Table 1 allows 40 percent for three or more conductors (53 percent for one, 31 percent for two); via secondary sources https://expertce.com/learn-articles/nec-chapter-9-table-1-conduit-fill/ and https://open-exam-prep.com/study-guides/ct-electrician/raceways-boxes-conduit-fill/conduit-fill-calculations (verify against NFPA 70). Bundle area = sum of pi/4 x OD^2 per wire. igus's 10 percent clearance reserve points the same direction.
2. If connectors must pass: min channel width and height >= largest housing (7.62 x 2.6 mm for 3-pin Dupont, plus 0.5 mm clearance per side (derived)), so 8.6 mm wide by 3.6 mm high minimum, applied to the connector pass-through section only.
3. Bend radius >= 10 x cable OD (igus rule of thumb, https://www.igus.eu/flexible-cable/wiki/structure-and-shielding/bend-radius ). Floor 5 x OD for static, copper hits limits below that (same source).
4. Service loop: slack >= 25 cm class for large rotating joints (Garmin), unverified 20 to 50 percent patent figure; at servo scale use r x theta + 10 x OD (derived).

## 4. Recommendations

Common: 5 V servo power on 22 AWG from the battery/BEC to a rail on the body; never route power over leg servo leads. 2S LiPo (7.4 V) feeding a BEC: 22 AWG is good to 7 A chassis (rule of thumb). Eight to twelve MG996R stall at 2 to 2.5 A each, so use 18 AWG or heavier for the main trunk (derived, not from sources above). Use the servo's own 3 x 26 AWG leads for the last stretch.

**Quadruped (12 servos, SG90 or MG996R):**
- Shoulder (hip abduction) servos sit on the body: use short leads, route inside the body like Petoi (columns, slots).
- Thigh and knee servos: the lead exits the shoulder housing, crosses the hip-pitch axis, and follows the thigh. Do not route through the axis at SG90 scale (horn is about 7 mm boss); use a service loop at the hip pitch joint: 40 to 50 mm of slack, loop radius >= 15 mm (10 x 1.5 mm OD) (derived).
- Knee servo (distal) needs a long lead; Petoi sells long-lead servos for knees. Else add a 100 to 150 mm extension (SpotMicro practice), crimp once, no stacked extensions.
- Channel in thigh and shin: one servo lead (3 x 1.5 mm wires, area about 5.3 mm2 for three round 1.5 mm wires; flat lead about 6.8 mm2) means channel area >= 17 mm2 at 0.40 fill. Use 6 mm wide x 3.5 mm deep slot with a snap lid, widening to 8.6 x 3.6 mm where the connector passes. For two leads (thigh carrying the knee lead), use 8 x 5 mm (40 mm2).
- Clip every 25 to 30 mm, with the last clip 15 to 20 mm from each connector.
- Notch on the entry edge of each limb like Petoi's inner-edge notch.

**Small biped (Otto-style 4 to 6 servos, SG90):**
- Foot servo lead passes through the leg gap and body slot (Otto method); give a 30 to 40 mm loop at the ankle, hidden inside the leg gap, with a 10 mm minimum bend radius.
- Hip servos in the body: leads straight to the board, no loop.
- Channel: 8 x 4 mm per leg (single lead plus connector at the pass section); two-lead legs 8 x 6 mm.
- For a 6 to 12 servo biped, consider a daisy-chain bus servo (Poppy / Dynamixel style) to pass one cable per joint.

Open gaps: no sourced strain-relief rule, no sourced servo-scale service-loop rule, no drag chain pitch, no OpenDog or EEZYbot routing text, no MG996R lead data. Measure real parts before finalizing.
