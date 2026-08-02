# Sky Mirror — TODO / Future Work

## Immediate Fixes Needed (verify after v3 deploy)

- [ ] Confirm stars actually land on pyramid peaks at 10,500 BCE
  - The stereographic projection centers on zenith, not on the pyramids
  - May need to adjust LST (Local Sidereal Time) so Belt stars project exactly onto pyramid coords
  - Test: at 10,500 BCE on Giza, do Belt star canvas positions match pyramid canvas positions?

- [ ] Verify epoch slider causes visible star movement
  - Precession should rotate entire sky ~1° per 72 years
  - Moving slider 1000 years should produce noticeable drift

## Story Mode (P1 — next session)

- [ ] Narrated text walkthrough that appears panel by panel
  - "In 1994, Robert Bauval looked up at Orion's Belt and noticed something..."
  - "The three stars are not perfectly aligned — Mintaka offsets slightly to the east..."
  - "Looking at a satellite photo of Giza, the same offset appears in Menkaure..."
  - "But the match only works at one point in history: 10,500 BCE..."
  - Each step highlights relevant elements on the map (pulse pyramid, highlight star)
  
- [ ] Play/pause button for auto-advance
- [ ] Typewriter text effect (text appears character by character)
- [ ] Each step can auto-set the epoch slider
- [ ] Step indicators (1/7, 2/7, etc.)

## Audio Narration (P2 — after story mode text works)

- [ ] Convert story text to Polly narration (same as documentary system)
- [ ] Sync audio playback with story steps
- [ ] Could reuse existing audio player component from grid-globe.html

## Visual Polish (P2)

- [ ] Animated precession playback (play button sweeps epochs automatically)
- [ ] Star trails — leave fading ghost trail as epoch changes
- [ ] "Mirror ripple" effect when stars lock onto sites (subtle wave animation)
- [ ] More background stars / nebula texture
- [ ] Show actual pyramid photos (small inset) when aligned

## Multi-Site Demo Sequence (P3)

- [ ] "Tour all sites" button that cycles: Giza → Angkor → Teotihuacán → etc.
- [ ] Each site auto-zooms, shows explanation, slides to optimal epoch
- [ ] Cross-site connection lines (e.g., Giza and Angkor both align at 10,500 BCE)
