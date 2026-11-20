# Shot Card Sources and Licensing Attribution (48 cards added in 2026-08; 38 preserved after 2026-10 streamlining)

The motion techniques in this batch of shot cards were studied from publicly released product promotional videos and open-source project homepages.
**All implementations are re-implemented from scratch**: the repository contains no original video clips, screenshots, artistic assets, or brand elements. All copy, color palettes, and UI content in the implementations are neutral placeholder templates. Original creators did not participate in this project; card source attributions serve solely as homage and research provenance ("referenced technique only, re-implemented independently").

## Legal Boundaries (Important)

- Abstract motion **techniques/methods** (timing structures, easing approaches, choreography logic) generally fall within the domain of methods and ideas. However, **specific expressions** (the visuals, artwork, copy, brand elements, and recognizable overall audiovisual presentation of original videos) are protected by copyright, trademark, and related rights. This project studies only the former, avoiding copying the latter via full clean-room re-implementation, de-branding, and placeholder substitution.
- "Publicly released" works **do not** imply granting permission for reproduction or derivative works. This table documents research provenance, not licensing credentials. For sources without explicit licenses, we rely on the practice of "technique reference + independent re-implementation, zero original assets", rather than any grant from rights holders.
- If any rights holder believes that the implementation of any card constitutes copying of their specific expression, please open an issue; we will promptly adjust or remove the corresponding content and attribution.

## Source Inventory

Note: The table below records sources by **research batch** (each batch corresponds to one reference video or website, covering several derivative cards). The card files themselves do not carry source annotations; per-card attribution is detailed in the "Per-Card Source Mapping" appendix below.

| Research Batch | Source | Type | Status |
|---|---|---|---|
| anime.js | https://animejs.com/ Official demo (GitHub: juliangarnier/anime) | Open source homepage (MIT project; visual presentation copyright belongs to author) | Technique reference, re-implemented; no code or artwork used |
| remotion-bits.dev | https://remotion-bits.dev/ | Open source example collection | Technique reference, re-implemented; no code used |
| x.com/amirdzm | 2 motion works publicly posted on X (~13s "Storyboard → Result", etc.) | Personal works (publicly posted, no reproduction license granted) | Technique reference, re-implemented; zero original assets |
| x.com/1amanly | Motion works publicly posted on X | Same as above | Same as above |
| x.com/Jerrythe2d | Motion works publicly posted on X (~84s) | Same as above | Same as above |
| x.com/bohdanmotion | Motion works publicly posted on X (~26s) | Same as above | Same as above |
| x.com/thiswillblossom | SaaS concept ad publicly posted on X (~2.1s 4-split grid) | Same as above | Same as above |
| x.com/tvnxty | Firecrawl brand/product promo video (~66s, publicly posted) | Commercial promo video (publicly posted, no reproduction license granted) | Technique reference, re-implemented; zero original assets |
| x.com/aizal_mp4 (individual cards) | Willow Voice product promo video (by motion designer aizal, ~41s) | Commercial promo video (publicly posted, no reproduction license granted) | Technique reference, re-implemented; zero original assets |
| Douyin Guanji She (dy09) | Honor AI concept clip posted by Douyin account "Guanji She" (~22.6s) | Reposted clip; underlying content is brand concept (involves Honor brand elements) | Technique reference, re-implemented; brand logomarks replaced with neutral placeholders |
| Douyin Jiang Jinglian (dy08, individual cards) | Works publicly posted by Douyin account "Jiang Jinglian" (~19.4s vertical video) | Personal works (publicly posted, no reproduction license granted) | Technique reference, re-implemented; zero original assets |
| reference/brand-scan | Custom design based on user-provided reference images | Internal requirement | Original implementation |

> Known precision limitations: X / Douyin sources were recorded by account homepage at the time without retaining specific post URLs (original videos were only retained locally during the research period and not committed to the repo). Identifiable durations and descriptions have been added where possible; refer to the respective accounts for direct searches.

## Per-Card Source Mapping

Mapping between the preserved 38 cards and research batches (from original research timestamp mapping records):

| Source | Cards |
|---|---|
| anime.js official demo | `radial-wave`, `value-stagger-gradient` |
| remotion-bits.dev | `basic-3d-scene`, `blur-slide`, `card-stack`, `carousel-3d`, `cursor-flyover`, `flying-words`, `fracture`, `glitch-cycle`, `gradient-transition`, `list-reveal`, `mosaic-reframe`, `terminal-3d` |
| x.com/1amanly | `avatar-bracket-carousel`, `countdown-arc-scatter`, `pill-chip-slot-cycle-handled`, `radial-ripple-phone-chips` |
| x.com/Jerrythe2d | `bezier-source-converge-merge`, `chip-grid-single-select-blackout`, `doc-park-left-pill-deal`, `picker-carousel-feature-cycle`, `scan-bracket-sweep`, `vertical-word-roll-blur-cycle` |
| x.com/aizal_mp4 (Willow Voice) | `aurora-bloom-bg-flip`, `glass-pill-dictation-typing` |
| x.com/amirdzm (work a) | `brace-expand`, `grain-dissolve` |
| x.com/bohdanmotion | `outline-word-fill`, `word-relay-geometry` |
| x.com/thiswillblossom | `quad-split-parallel-scenes` |
| x.com/tvnxty (Firecrawl promo) | `product-card-progressive-assemble`, `research-card-stack-scroll` |
| Douyin Guanji She | `logo-shrink-wordmark-lockup`, `white-flash-logo-simplify-cut` |
| User reference customization (brand-scan) | `assemble-then-type-flyin`, `scanline-annotate-focus`, `scanline-assemble-flyin` |
