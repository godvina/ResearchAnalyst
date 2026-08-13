# AI Language Learning App — Concept & Architecture

## The Idea
An AI-powered language learning app where you have real conversations with an AI persona — audio-first, eventually video, eventually AR glasses. The AI corrects pronunciation in real-time, scores your accent, adapts to your level, and uses creative memorization techniques to cement vocabulary.

Not flashcards. Not drills. A patient, infinitely available conversation partner who happens to be an expert language teacher.

---

## Core Modes

### Mode 1: Conversation Practice
- Open-ended conversation with AI persona in target language
- AI adapts complexity to your level (A1-C2 CEFR framework)
- Personas: "Parisian café waiter," "Tokyo business meeting," "Berlin taxi driver," "Mexican market vendor"
- AI naturally introduces new vocabulary in context, circles back to check retention

### Mode 2: Pronunciation Drill
- Say the word in English → AI says it in target language → you repeat
- Real-time phoneme-level scoring (per syllable, per sound)
- If wrong: AI demonstrates again slower, exaggerates the tricky sound, explains mouth position
- Gamified: "Your French 'r' just went from 62% to 78% — three more and you unlock the next level"

### Mode 3: Vocabulary Builder (50 words at a time)
- Creative memorization games (see below)
- Spaced repetition based on YOUR scores
- Words introduced in thematic batches (restaurant, directions, emotions, business)

### Mode 4: Immersive AR (Meta Glasses / Future)
- See objects in real world → glasses overlay the word in target language
- Point at a door: "la porte" appears. Say it. Get scored.
- Full conversation mode but you see the AI avatar in your peripheral vision

---

## Creative Ways to Memorize 50 Words at a Time

### 1. Story Chain Method
AI generates a ridiculous story using all 50 words. The more absurd, the better memory anchoring.
- "The RED cat (le chat ROUGE) sat on a CHAIR (une chaise) eating BREAD (du pain) while the DOCTOR (le médecin) sang about RAIN (la pluie)..."
- You repeat the story, filling in the foreign words. AI scores each one.

### 2. Memory Palace (Spatial Audio)
- AI walks you through YOUR house (you describe it once)
- Places 50 words in specific locations: "In your kitchen, on the counter, is une pomme (apple). Next to the fridge is du lait (milk)..."
- Recall test: "Walk me through your kitchen — what's on the counter?"
- Audio-spatial memory is 10x stronger than visual flashcards

### 3. Song/Rhythm Method
- AI generates a simple rhyming song with the 50 words
- Melody makes recall automatic (same reason you remember ad jingles)
- You sing along. AI scores pronunciation.

### 4. Word Association Battles
- AI gives you a word. You have 3 seconds to say the translation.
- Streak counter. Personal records. Daily challenges.
- Miss one → it goes into your "revenge list" (comes back 1 hour, 1 day, 3 days later — spaced repetition)

### 5. Context Sentence Building
- You get 5 new words. Build a sentence using all 5.
- AI judges grammar + pronunciation + creativity
- Bonus points for humor. ("The tired elephant dances slowly in the rain" uses 5 words and is memorable)

### 6. Picture Describe (with video mode)
- AI shows you an image (or camera sees real scene)
- Describe it in target language. AI scores vocabulary range + grammar + pronunciation
- Progressive: start with "I see a dog" → advance to "The brown dog is running toward the old man near the blue car"

### 7. Rapid Fire Rounds
- 30 seconds. As many words as possible. English → Target Language.
- Leaderboard against yourself (yesterday's score)
- After: review misses, AI pronounces them correctly, you repeat

### 8. Fill-the-Gap Dialogues
- AI speaks a full sentence with one word BEEPED out
- You supply the missing word (tests listening comprehension + vocabulary recall simultaneously)

---

## Video Capability — Is It Possible?

**Yes.** Two approaches:

### Approach A: AI Avatar (Generated Video)
- Use Amazon Bedrock + a video avatar service (D-ID, HeyGen, or build with Stable Diffusion)
- AI avatar lip-syncs to the Polly voice output
- User sees a "person" speaking to them
- Adds visual cues (mouth shape for pronunciation) which helps enormously for sounds like French 'u' or Spanish rolled 'r'

### Approach B: Camera-Based (Computer Vision)
- User's camera is on
- App uses Amazon Rekognition or custom model to:
  - Read mouth shape (for pronunciation feedback)
  - Detect objects in scene for vocabulary (see a cup → "How do you say cup?")
  - Read facial expressions (confused? slow down. smiling? increase difficulty)

### Approach C: Both
- AI avatar on one side, you on the other — like a video call with an AI tutor
- The most natural UX. Feels like a real tutoring session.

---

## Meta Glasses / AR Integration

**Absolutely possible.** Meta Quest has:
- Passthrough (see real world with digital overlay)
- Built-in microphone + speakers
- Hand tracking
- Eye tracking

**Language learning on Meta Glasses:**
1. Walk through a city → see labels on everything in target language
2. Look at a menu → instant translation overlay with pronunciation button
3. AI avatar walks beside you, practices conversation while you're on a walk
4. "Look at that sign — what does it say?" → you read it aloud → scored
5. Social mode: practice with another person wearing glasses, AI mediates and corrects both

**Technical path:**
- Meta has an SDK for passthrough AR overlays
- Speech-to-text works via on-device model or cloud (Transcribe)
- You'd build a Unity/Unreal app or use Meta's Horizon OS
- MVP: audio-only on glasses first (already works perfectly), add visual overlay in v2

---

## Technical Architecture (AWS)

| Component | Service | Purpose |
|-----------|---------|---------|
| Speech-to-Text | Amazon Transcribe | Convert user speech to text + pronunciation scores |
| AI Brain | Amazon Bedrock (Claude) | Conversation, correction, story generation, adaptation |
| Text-to-Speech | Amazon Polly (Neural) | Speak back in native accent (30+ languages) |
| Pronunciation Scoring | Transcribe + custom model | Phoneme-level accuracy scoring |
| User Progress DB | DynamoDB | Track words learned, scores, streaks, weak areas |
| Spaced Repetition Engine | Lambda | Calculate when to resurface each word |
| Audio Streaming | WebSocket API Gateway | Real-time audio back-and-forth |
| Video Avatar | D-ID API or Bedrock + custom | Generate lip-synced avatar video |
| AR Overlay | Meta SDK + Unity | Object detection, label overlay, spatial audio |
| Analytics | Kinesis + QuickSight | Learning velocity, retention rates, dropout prediction |

---

## Cost Model

| Usage | Cost Per User/Month | Notes |
|-------|-------------------|-------|
| 10 min/day conversation | ~$9 | Transcribe + Polly + Bedrock |
| 5 min/day vocabulary games | ~$2 | Mostly Bedrock (text) |
| Video avatar (optional) | ~$5 | D-ID or similar |
| Storage + compute | ~$1 | DynamoDB, Lambda |
| **Total** | **~$12-17** | |
| **Suggested price** | **$24.99/month** | ~50% margin |

At scale (10K users): bulk pricing drops costs to ~$6-8/user → 70% margin.

---

## Competitive Landscape

| Competitor | What They Do | What This Does Better |
|-----------|-------------|----------------------|
| Duolingo | Gamified flashcards + text exercises | Real conversation, pronunciation scoring, audio-first |
| Babbel | Structured courses with some speech | Adaptive AI that responds to YOUR level in real-time |
| Pimsleur | Audio-only spaced repetition | Interactive (AI responds), not just listen-repeat |
| italki | Human tutors ($15-30/hour) | Available 24/7, $0.83/day, no scheduling, no embarrassment |
| ChatGPT Voice | General AI conversation | Purpose-built for language with scoring, progression, pedagogy |

**The gap in the market:** No one does PRONUNCIATION SCORING + ADAPTIVE CONVERSATION + GAMIFIED MEMORIZATION in one audio-first package. Everyone is either text-first (Duolingo/Babbel) or conversation-only-no-scoring (ChatGPT voice).

---

## MVP Roadmap

### Phase 1 (2-3 weeks): Audio Conversation Only
- Transcribe → Bedrock → Polly loop
- One language (French or Spanish)
- Web app with microphone
- Basic pronunciation scoring (word-level confidence from Transcribe)

### Phase 2 (2-3 weeks): Vocabulary Games
- Story chain generator
- Rapid fire mode
- Spaced repetition engine
- Progress dashboard

### Phase 3 (4 weeks): Mobile App
- React Native or Flutter
- Push notifications for daily practice
- Offline mode for vocabulary review

### Phase 4 (4-6 weeks): Video Avatar
- D-ID or similar integration
- Lip-sync to Polly output
- Mouth shape visualization for pronunciation help

### Phase 5 (8+ weeks): Meta Glasses AR
- Unity SDK integration
- Object detection + label overlay
- Spatial audio conversation partner
- Walking mode (practice while moving)

---

## How to Make It Better (Ideas Beyond MVP)

1. **Cultural context** — Don't just teach words, teach WHEN to use them. "In France you'd never say 'tu' to your boss. Here's why..."
2. **Emotional memory anchoring** — Words learned during funny/surprising moments stick 5x better. AI should be entertaining, not robotic.
3. **Social challenges** — "You and 3 friends are all learning French. This week's challenge: describe your morning routine. Vote on best pronunciation."
4. **Travel mode** — "You're going to Paris in 2 weeks. Here are the 100 words you actually need for restaurants, metro, and hotels."
5. **Accent choice** — "Learn Parisian French" vs "Learn Québécois French" vs "Learn Senegalese French" — different Polly voices, different vocabulary
6. **Proficiency certification** — Generate a CEFR-style score from your conversation data. "You're B1 in listening, A2 in speaking, B2 in reading."
7. **Dream mode** — Fall asleep listening to gentle conversation in target language (passive absorption is real — proven in sleep learning studies for vocabulary)
8. **Karaoke mode** — Sing popular songs in target language. Lyrics shown, pronunciation scored per line.

---

*Created: 2026-08-09*
*Status: Concept/Idea stage*
*Potential: High — gap in market between cheap apps (Duolingo) and expensive tutors (italki)*
