# Ancient Mysteries Field Companion — Mobile PWA Spec

## Concept
A site-centric mobile app for exploring cross-cultural mythology patterns while visiting ancient sites in Ireland. Works fully offline. Each Irish site is a "chapter" that connects to global parallels.

## Navigation Flow
1. Home → List of 13 Irish Sites (cards)
2. Tap a site → Site Detail page
3. Site Detail shows:
   - Site info (date, key facts, what to look for)
   - The deity/deities associated with this site
   - ▶ Audio brief (60s narration)
   - Global parallels (other sites worldwide with same pattern)
   - The dialogue (deity talking to their parallel from another culture)
   - "So What?" investigative insight

## Content Per Site

### Newgrange
- Deity: Dagda, Aengus Óg
- Patterns: Solar Alignment (#6), Underground Retreat (#4), Divine Kingship (#7)
- Global parallels: Eridu (Iraq), Giza (Egypt), Göbekli Tepe (Turkey)
- What to look for: Roofbox above entrance, passage alignment to winter solstice sunrise

### Knowth
- Deity: Associated with lunar calendar (kerbstone K52)
- Patterns: Solar/Lunar Alignment (#6), Pre-Flood Civilization (#5)
- Global parallels: Giza (stellar alignment), Angkor Wat (equinox)
- What to look for: Dual passage (east = equinox sunrise, west = equinox sunset), megalithic art

### Hill of Tara
- Deity: Nuada, Lugh
- Patterns: Divine Kingship (#7)
- Global parallels: Uruk (Anu's throne), Babylon (Marduk's seat), Memphis (Ptah/pharaoh)
- What to look for: Stone of Fal (Lia Fáil), Mound of the Hostages

### Knocknarea
- Deity: Morrigan/Medb
- Patterns: Underground Retreat (#4), Divine Kingship (#7)
- Global parallels: Xibalba entry points (Maya), Knossos (Crete)
- What to look for: Unopened 40,000 ton cairn, all Carrowmore oriented toward it

### Skellig Michael
- Deity: Manannán mac Lir
- Patterns: Underground Retreat (#4)
- Global parallels: Mount Athos (Greece), Potala Palace (Tibet) — liminal sacred sites at world's edge
- What to look for: Michael Line alignment (Skellig → St Michael's Mount → Mont Saint-Michel)

### Loughcrew
- Deity: Brigid, Crom Cruach
- Patterns: Solar Alignment (#6)
- Global parallels: Chichén Itzá (equinox light show), Mnajdra (Malta)
- What to look for: Equinox sunrise illuminates carved backstone in Cairn T

### Carrowmore / Carrowkeel
- Deity: Tuatha Dé Danann (collective)
- Patterns: Pre-Flood Civilization (#5), Underground Retreat (#4)
- Global parallels: Göbekli Tepe (oldest megalithic), Carnac (France)
- What to look for: If 4600 BCE dates valid = oldest megaliths in Ireland

## Global Sites Database (coordinates for "world connection" view)

| Site | Country | Lat | Lng | Pattern |
|------|---------|-----|-----|---------|
| Newgrange | Ireland | 53.6947 | -6.4755 | Solar, Underground |
| Giza Pyramids | Egypt | 29.9792 | 31.1342 | Solar, Construction |
| Göbekli Tepe | Turkey | 37.2231 | 38.9225 | Pre-Flood, Alignment |
| Angkor Wat | Cambodia | 13.4125 | 103.8670 | Solar Alignment |
| Chichén Itzá | Mexico | 20.6843 | -88.5678 | Solar Alignment |
| Puma Punku | Bolivia | -16.5617 | -68.6803 | Precision, Pre-Flood |
| Baalbek | Lebanon | 34.0069 | 36.2048 | Construction |
| Eridu | Iraq | 30.8158 | 45.9945 | Oldest sacred site |
| Stonehenge | England | 51.1789 | -1.8262 | Solar Alignment |
| Carnac | France | 47.5850 | -3.0744 | Megalithic |
| Mnajdra | Malta | 35.8269 | 14.4363 | Solar Alignment |
| Sacsayhuamán | Peru | -13.5094 | -71.9828 | Precision, Construction |
| Easter Island | Chile | -27.1127 | -109.3497 | Megalithic |
| Nan Madol | Micronesia | 6.8435 | 158.3337 | Megalithic, Water |

## Tech Stack
- Static HTML/JS/CSS (no server)
- Service Worker for offline caching
- PWA manifest for "Add to Home Screen"
- Hosted on GitHub Pages (free, auto-deploy on push)
- ~4MB total (including audio)

## Status: Ready to build
