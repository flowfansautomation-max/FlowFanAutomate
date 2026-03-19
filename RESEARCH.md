# FlowFanAutomate - Research Report

## Project Goal
Build an automated system to create fan channels of **Flow Church** (Pastors Russell & Vetta Cash, DC Metro area) for TikTok and Instagram, by clipping and posting short-form videos from their long-form content.

- **YouTube:** [@TheresPowerHere](https://www.youtube.com/@TheresPowerHere)
- **Website:** [flow-church.org](https://www.flow-church.org)
- **Content type:** Sermons, worship, relationship/family teaching

---

## Table of Contents
1. [How Others Approach This](#1-how-others-approach-this)
2. [Commercial Tools Landscape](#2-commercial-tools-landscape)
3. [Open-Source Tools on GitHub](#3-open-source-tools-on-github)
4. [Church-Specific Tools & Strategies](#4-church-specific-tools--strategies)
5. [Technical Architecture](#5-technical-architecture)
6. [Common Mistakes & Pitfalls](#6-common-mistakes--pitfalls)
7. [What Makes Sermon Clips Go Viral](#7-what-makes-sermon-clips-go-viral)
8. [Copyright & Legal Considerations](#8-copyright--legal-considerations)
9. [Key Insights from Reddit, Twitter/X, and Hacker News](#9-key-insights-from-reddit-twitterx-and-hacker-news)
10. [Recommendations for This Project](#10-recommendations-for-this-project)

---

## 1. How Others Approach This

### The Standard Pipeline
The dominant workflow across all platforms and tools:

1. **Ingest** -- Download/import long-form video (sermon, podcast, etc.)
2. **Transcribe** -- AI generates timestamped transcript (Whisper is the standard)
3. **Analyze** -- AI (LLM) identifies highlight moments from transcript
4. **Clip** -- FFmpeg cuts video at identified timestamps
5. **Reformat** -- Crop to 9:16 vertical, add captions, add hook text
6. **Post** -- Schedule and publish to TikTok, Instagram Reels, YouTube Shorts

### The "80/20 Rule"
Across Reddit, Twitter/X, and Hacker News, the consensus is clear: **automate to get 80-90% of the way, then let humans do final creative control**. Fully automated posting without human review consistently underperforms.

### The Fan Channel Business Model
- Curate, compile, and repurpose clips from existing creators
- Revenue from ads, affiliate marketing, sponsorships
- No personal presence required ("faceless channels")
- Example: Noah Morris runs 18 faceless YouTube channels with 2.5M subscribers, reportedly making $500K in 90 days
- **Risk:** Copyright strikes are a constant concern for fan channels

---

## 2. Commercial Tools Landscape

### Tier 1: Major Players

| Tool | Price (from) | API? | Auto-Post? | Best For |
|------|-------------|------|------------|----------|
| **OpusClip** | Free / $15/mo | Closed beta (enterprise) | Yes (unreliable) | General clipping, large user base |
| **Vizard.ai** | Free / $14.50/mo | Yes (all paid plans) | Yes | Best all-in-one workflow |
| **Klap** | Free / $29/mo | Yes ($0.32-0.48/op) | Yes | Fast clipping with API |
| **Descript** | Free / $24/mo | Limited | No | Text-based editing, podcasts |
| **CapCut** | Free | No | TikTok only | Budget-friendly, TikTok integration |

### Tier 2: Notable Alternatives

| Tool | Price (from) | API? | Auto-Post? | Best For |
|------|-------------|------|------------|----------|
| **Munch** | Free / $23/mo | No | Yes | Trend analysis + clipping |
| **Quso.ai** (ex-Vidyo.ai) | Free / $19/mo | No | Yes (9 platforms) | Clipping + social management |
| **Submagic** | $12/mo | Yes ($41/mo tier) | No | Best captions/visual polish |
| **Reap** | Subscription | Yes (Automation API) | Yes | Multi-signal detection, dubbing |
| **Flowjin** | $19/mo | No | Yes | Podcasts, audio-only content |
| **Gling** | Free / $15/mo | No | No | YouTuber rough cuts |
| **Spikes Studio** | ~$14/mo | No info | Yes | Long videos (24hr+), 99+ languages |

### OpusClip Deep Dive (Most Discussed)
- **10M+ users, 172M+ clips generated**, SoftBank-backed (~$50M raised)
- Has a **dedicated church vertical** at opus.pro/business/church
- **Pros:** Large community, virality score, animated captions, B-roll insertion
- **Cons:** Trustpilot 2.4/5, unreliable scheduler, AI clip selection is hit-or-miss, billing complaints, built-in editor described as "comically bad" on Reddit
- **Verdict:** Good starting point but expect to discard/tweak 20-40% of clips

### Top 10 Complaints Across ALL Tools
1. AI clip selection misses context, punchlines, and narrative arcs
2. "More time fixing AI than doing it manually" for complex content
3. Black-box AI -- you can't tell it what to look for
4. Workflow stops after clipping (need external editor to finish)
5. Pay-even-when-it-fails credit systems
6. Scheduler/auto-posting drops connections frequently
7. Generic "AI look" with fixed subtitle positioning
8. Only works well for talking-head content
9. Billing/support issues across multiple tools
10. No true semantic/topic-aware clipping

### What's Missing in the Market
- **Guided AI clipping** -- "find clips about topic X"
- **True semantic understanding** of narrative structure
- **Reliable auto-posting** that actually works
- **Risk-free pricing** -- pay only for clips you use
- **Open, self-serve APIs** (most are enterprise-gated)
- **Batch/bulk workflows** with quality control dashboards

---

## 3. Open-Source Tools on GitHub

### Tier 1: Most Relevant for This Project

| Project | Stars | Tech Stack | Key Feature |
|---------|-------|------------|-------------|
| **[ShortGPT](https://github.com/RayVentura/ShortGPT)** | ~6,200-7,100 | Python, GPT-4o-mini, FFmpeg | Largest community, multiple engines |
| **[ViralCutter](https://github.com/RafaelGodoyEbert/ViralCutter)** | 56 | Python, WhisperX, Gemini/GPT/local LLMs | Closest open-source OpusClip alternative |
| **[AI-Youtube-Shorts-Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator)** | -- | Python, GPT-4o-mini, Whisper, OpenCV | Clean pipeline with interactive approval |
| **[AI-Clipping-Software](https://github.com/LikithMeruvu/AI-Clipping-Software)** | -- | Python, AI APIs, FFmpeg | Strong face tracking (keeps pastor centered) |

### Tier 2: Strong Alternatives

| Project | Tech Stack | Key Feature |
|---------|------------|-------------|
| **[yt-short-clipper](https://github.com/jipraks/yt-short-clipper)** | Python, Whisper, FFmpeg | Single-command pipeline with hook generation |
| **[viral-clips-crew](https://github.com/alexfazio/viral-clips-crew)** | Python, CrewAI | Multi-agent AI architecture |
| **[ClipCrafter AI](https://github.com/alexlevy0/clipcrafter-ai)** | Python, AI, FFmpeg | Punchline scoring + self-improving AI loop |
| **[SupoClip](https://github.com/FujiwaraChoki/supoclip)** | Web app (Node.js) | Web UI, AGPL-3.0 licensed |
| **[ai-clips-maker](https://github.com/alperensumeroglu/ai-clips-maker)** | Python, Whisper, FFmpeg | Speaker diarization + scene detection |
| **[clippy-ai-agent](https://github.com/Yacineooak/clippy-ai-agent)** | Python | Privacy-first, offline processing |

### Tier 3: Noteworthy

| Project | Key Feature |
|---------|-------------|
| **[Clip-Anything](https://github.com/SamurAIGPT/Clip-Anything)** | Natural language prompt-based clipping |
| **[PromptClip](https://github.com/video-db/PromptClip)** | LLM-prompt video clip creation via VideoDB |
| **[AWS gen-ai-video-short-form-generator](https://github.com/aws-samples/gen-ai-video-short-form-generator)** | Enterprise-grade, up to 15 clips per video |

### Common Tech Stack Across All Projects
**Python + FFmpeg + OpenAI Whisper + GPT/Gemini/Claude + OpenCV/MediaPipe**

### Church-Specific Finding
No dedicated open-source sermon clipping tool exists on GitHub. The general-purpose tools (especially ViralCutter, AI-Clipping-Software) work well since sermons are essentially long-form talking-head videos.

---

## 4. Church-Specific Tools & Strategies

### Purpose-Built Church Tools

| Tool | Price | Key Feature |
|------|-------|-------------|
| **ChurchSocial.ai** | $15/mo | All-in-one: clips, graphics, carousels, blog posts. 2,000+ churches |
| **Pulpit AI** (Subsplash) | Varies | 1 sermon -> 20+ content pieces |
| **Sermon Shots** | Varies | AI highlights + search-your-sermon-like-a-document |
| **Demtos Clip** | Varies | Religion-aware AI (understands scripture, emotional peaks) |
| **Pastors.ai** | Free tier | Won 2024 AI & Church Hackathon. Auto captions/music/logo |
| **Outreach Social** | Varies | Skips worship segments, centers speaker |
| **Church Posting** | $147/mo | 7 viral clips per sermon, auto-schedule |
| **SocialSermons** | Varies | Human-edited (not AI), writes custom hooks |

### How Megachurches Handle It
- **Transformation Church** -- Partnered with SocialSermons (human editors). First viral post within months.
- **Elevation Church** -- Worship content drives massive organic TikTok engagement (one user's baptism video got 503,800 likes)
- **Life.Church** -- Hosts Church Social Media Roundtable, provides free strategy resources
- **Large churches (800+)** are advised to be on all platforms, post 5-7 times per week

### Church Content Challenges
1. **Length mismatch:** Sermons run 45-90 min; most tools designed for 10-30 min input
2. **Camera framing:** Wide-angle stage shots need AI speaker tracking for vertical crop
3. **Caption accuracy:** Scripture references, theological terms need high accuracy
4. **Context stripping:** 30-second clips can be taken out of context
5. **Copyright on worship music:** Triggers YouTube Content ID. Need CCLI Streaming License
6. **Volunteer burnout:** Manual editing is #1 reason church social media efforts fail

### The Content Funnel
Short clip on TikTok -> Full sermon on YouTube -> Church website -> In-person visit.
**70% of people engage with a church online before ever visiting in person.**

---

## 5. Technical Architecture

### The Standard DIY Pipeline

```
YouTube URL
    |
    v
[yt-dlp] Download video
    |
    v
[FFmpeg] Extract audio (16kHz PCM WAV for best Whisper accuracy)
    |
    v
[Whisper / faster-whisper] Generate timestamped transcript
    |
    v
[LLM: GPT / Claude / Gemini] Analyze transcript, identify highlight timestamps
    |
    v
[FFmpeg] Cut clips at timestamps, crop to 9:16
    |
    v
[Whisper / ASS] Burn in animated captions
    |
    v
[MediaPipe / OpenCV] Face tracking to keep speaker centered
    |
    v
[Upload API / Repurpose.io] Post to TikTok, Instagram Reels, YouTube Shorts
```

### Key Technical Details

**FFmpeg 8.0 Native Whisper Support (Game-Changer)**
- Built-in `whisper` audio filter (`af_whisper`) does ASR directly in FFmpeg
- Includes VAD (Voice Activity Detection) via Silero model
- Can burn subtitles directly onto video
- Single-command transcription eliminates separate Whisper invocation

**Whisper Best Practices**
- Use `faster-whisper-XXL` with `large-v2` model (v3 has known regressions)
- GPU acceleration: 100-200x faster than CPU
- VAD (Silero) to skip silent sections and prevent hallucinated text

**Automation Layer Options**
- **n8n (self-hosted):** Open-source workflow automation with community templates
- **Make.com / Zapier:** Easy but Twitter/X recently cut off Make.com API access
- **Repurpose.io:** Auto-distributes clips across 20+ platforms (official Meta/YouTube/TikTok partner)
- **Upload-Post API:** Single API call publishes to TikTok, YouTube, Instagram, Facebook + 7 more

### Critical Finding: Naive Repurposing Underperforms
From Hacker News (3 months of A/B testing):
- Simply cutting long video into clips and posting everywhere yields poor engagement
- Cost per engaging view: $1.89 to $4.22
- **Platform-specific adaptation, narrative structure, and hook optimization matter more than the cutting itself**

---

## 6. Common Mistakes & Pitfalls

### Content Mistakes
1. **Trusting AI output without review** -- Every tool requires human QA
2. **Clips that don't stand alone** -- "As I said earlier..." fails as standalone content
3. **No hook in first 3 seconds** -- 63% of high-CTR videos hook viewers in that window
4. **Too long** -- Over 90 seconds loses engagement. Sweet spot is 30-60 seconds
5. **Multiple ideas in one clip** -- One clear point per clip
6. **No captions** -- 75-85% of mobile users watch on mute

### Technical Mistakes
7. **Just cropping 16:9 to 9:16** -- Need proper AI reframing or face tracking
8. **Ignoring platform safe zones** -- UI elements cover bottom 10% of vertical video
9. **Using TikTok-licensed music on other platforms** -- Different licensing per platform
10. **Reposting identical videos** -- TikTok flags exact reposts as "unoriginal content"

### Strategy Mistakes
11. **Dumping all clips at once** -- Space them out over days/weeks
12. **Copy-pasting captions across platforms** -- Each platform needs adaptation
13. **Assuming "giving credit" protects from copyright** -- Credit does not equal consent
14. **Fully automated posting without review** -- Consistently underperforms human-curated
15. **Expecting AI virality scores to pick winners** -- Low-scored clips often outperform high-scored ones

---

## 7. What Makes Sermon Clips Go Viral

### Viral Characteristics
- **Strong hook in first 3 seconds** (question, bold statement, surprising stat, relatable pain)
- **15-60 seconds long** (30 seconds is the sweet spot)
- **Authenticity and raw emotion** over polished production
- **Humor, relatability, or inspirational content**
- **Alignment with trending topics/seasons** ("trend-jacking")
- **Single clear point** rather than multiple ideas

### Flop Characteristics
- No hook -- clip starts mid-thought without context
- Over 90 seconds
- Over-produced or overly "churchy" framing
- Multiple points crammed in
- Poor audio quality
- No captions

### Platform Dynamics
**TikTok's algorithm is built for discovery, not just follower distribution.** A clip from a 75-person church has the same viral potential as a megachurch clip.

### Caption Best Practices
- Max 32 characters per line
- 1-3 lines on screen at a time, displayed 3-6 seconds each
- Place within platform "safe zones"
- Animated word-by-word captions ("Hormozi style") perform well
- Accuracy matters more for theological content

---

## 8. Copyright & Legal Considerations

### Key Facts
- **Sermon content is copyrighted** by the church/pastor who created it
- **Fan accounts uploading without permission are technically infringing copyright**
- CCLI licensing covers worship music, NOT the sermon itself
- YouTube Content ID primarily flags music, not spoken sermon content
- **Fair use is a defense, not an exemption** -- educational purpose may help but is not guaranteed
- TikTok enforces a **3-strike system per IP type**; permanent bans possible
- **"Giving credit" in captions is NOT a legal defense**

### Recommendations
- Get explicit permission from Flow Church to create fan channels
- Consider asking the church to provide a Creative Commons license or public statement of permission
- Avoid using copyrighted worship music in clips (or ensure CCLI Streaming License coverage)
- Add commentary/value to clips to strengthen fair use argument
- Be prepared for Content ID claims on any worship music segments

---

## 9. Key Insights from Reddit, Twitter/X, and Hacker News

### Reddit Consensus
- OpusClip is the default starting point but quality has declined
- Vizard.ai preferred for value (half the cost, better accuracy)
- "80/20 approach" -- use AI for first draft, human for final selection
- Consistency beats perfection in posting
- Recycle winning clips with new hooks after 30-60 days

### Twitter/X Insights
- Roberto Blake recommends filming unedited Q&A sessions and running through OpusClip for weeks of content
- n8n + Apify + Claude pipeline costs under $0.50 per video
- Twitter/X recently cut off Make.com API access (use n8n instead)
- Fan channel model is proven: curate, compile, repurpose

### Hacker News Technical Insights
- FFmpeg 8.0 native Whisper is a game-changer for DIY pipelines
- Multimodal indexing (transcript + visual scene analysis) produces better clip boundaries than transcript-only
- Chat UX breaks down for video editing -- node-based or batch workflows are better
- Speaker diarization (Pyannote) important for multi-speaker content
- Proxy workflows: transcode to low-res for AI processing, re-link to originals for export

### The Content Repurposing Fallacy (HN, March 2026)
3 months of A/B testing showed naive repurposing yields poor engagement. Each platform needs:
- Different hooks
- Different pacing
- Different aspect ratios
- Different narrative structures

---

## 10. Recommendations for This Project

### Approach: Custom Pipeline with Human-in-the-Loop

Rather than relying on a single commercial tool, build a custom pipeline that:

1. **Downloads** Flow Church videos automatically (yt-dlp + YouTube API monitoring)
2. **Transcribes** with Whisper (local, free, high accuracy)
3. **Identifies highlights** using an LLM (Claude/GPT) with church-specific prompting
4. **Clips and reformats** with FFmpeg (9:16, face tracking, captions)
5. **Presents clips for human review** via a simple web dashboard
6. **Posts approved clips** to TikTok and Instagram on a schedule

### Why Custom Over Commercial
- **Cost:** Commercial tools charge $15-150/mo per channel; custom runs on free/cheap APIs
- **Control:** Can guide AI with church-specific context ("find moments about faith, family, relationships")
- **API access:** Most commercial APIs are enterprise-gated; DIY has no restrictions
- **Reliability:** Auto-posting on commercial tools is universally unreliable
- **Scalability:** Can process entire back catalog of sermons

### Suggested Tech Stack
- **Python** -- Core language (all open-source tools use it)
- **yt-dlp** -- YouTube video downloading
- **FFmpeg 8.0+** -- Video processing, native Whisper support
- **faster-whisper** (large-v2) -- Transcription with GPU acceleration
- **Claude/GPT API** -- Highlight identification with sermon-aware prompting
- **MediaPipe/OpenCV** -- Face tracking to keep pastor centered
- **n8n or custom scheduler** -- Workflow automation
- **TikTok/Instagram APIs** -- Direct posting (or Repurpose.io as fallback)

### Critical First Step
**Get explicit permission from Flow Church** to create fan channels before building anything. This protects against copyright issues and may open doors to direct collaboration.

### Content Strategy
- Start with 3-4 posts per week
- 30-60 second clips with hooks in first 3 seconds
- Animated captions (essential -- 85% watch on mute)
- One idea per clip, self-contained
- Platform-specific adaptation (don't cross-post identical content)
- Use worship clips alongside sermon clips (worship often performs better)
- Leverage seasonality (Christmas, Easter content has outsized reach)

---

## Sources

### Commercial Tools
- [OpusClip](https://opus.pro) | [OpusClip for Churches](https://www.opus.pro/business/church)
- [Vizard.ai](https://vizard.ai)
- [Klap](https://klap.app) | [Klap API](https://docs.klap.app/pricing)
- [Descript](https://descript.com)
- [Munch](https://getmunch.com)
- [Quso.ai](https://quso.ai)
- [Submagic](https://submagic.co)
- [Reap](https://reap.video)
- [Flowjin](https://flowjin.com)
- [Gling](https://gling.ai)
- [Repurpose.io](https://repurpose.io)

### Church-Specific Tools
- [ChurchSocial.ai](https://www.churchsocial.ai)
- [Pulpit AI / Subsplash](https://www.subsplash.com/blog/how-to-create-sermon-clips)
- [Sermon Shots](https://sermonshots.com)
- [Demtos Clip](https://clip.demtos.com)
- [Pastors.ai](https://pastors.ai)
- [Outreach Social](https://social.outreach.com)
- [SocialSermons](https://www.socialsermons.com)

### Open-Source Projects
- [ShortGPT](https://github.com/RayVentura/ShortGPT) (~6,200+ stars)
- [ViralCutter](https://github.com/RafaelGodoyEbert/ViralCutter)
- [AI-Youtube-Shorts-Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator)
- [AI-Clipping-Software](https://github.com/LikithMeruvu/AI-Clipping-Software)
- [yt-short-clipper](https://github.com/jipraks/yt-short-clipper)
- [viral-clips-crew](https://github.com/alexfazio/viral-clips-crew)
- [ClipCrafter AI](https://github.com/alexlevy0/clipcrafter-ai)
- [SupoClip](https://github.com/FujiwaraChoki/supoclip)
- [Clip-Anything](https://github.com/SamurAIGPT/Clip-Anything)
- [PromptClip](https://github.com/video-db/PromptClip)

### Community Discussions
- [HN: Content Repurposing Fallacy](https://news.ycombinator.com/item?id=47230750)
- [HN: FFmpeg 8.0 Whisper Integration](https://news.ycombinator.com/item?id=44886647)
- [HN: Mosaic YC W25](https://news.ycombinator.com/item?id=45980760)
- [n8n YouTube-to-TikTok Workflow](https://n8n.io/workflows/9867)
- [HackerNoon: DIY AI Video Clipper](https://hackernoon.com/i-built-my-own-ai-video-clipping-tool-because-the-alternatives-were-too-expensive)

### Church Strategy Resources
- [Life.Church Open Network](https://open.life.church/resources/4431-church-social-media-strategy-documents)
- [Churchfluence Guide](https://www.churchfluence.com/learn/church-social-media-management-guide-2025)
- [Missional Marketing Short-Form Guide](https://missionalmarketing.com/a-guide-to-maximizing-short-form-video-for-churches/)

---

*Research compiled on March 19, 2026 from GitHub, Reddit, Twitter/X, Hacker News, and industry sources.*
