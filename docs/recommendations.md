# Trip Recommendations & Sharing

Libertas supports three ways to share travel plans and recommendations.

## Share formats

| Format | URL | Best for |
|--------|-----|----------|
| **Itinerary** | `/<link>.html` | Scheduled trips with dates, times, day-by-day view |
| **Recommendation** | `/r/<link>` | Ideas collection grouped by city and category |
| **Write-up** | `/w/<link>` | AI-generated narrative with links and map |

All three are public pages, no account needed to view. Recipients can save recommendations to their own trips.

## Building recommendations

The typical flow:

1. **Explore tab**, search for restaurants, hotels, activities
2. **Pin a trip**, click `+ Trip` on a venue card, pick or create a trip
3. **Add notes**, optional note on each item ("best cocktails in the area")
4. **Add tips**, general advice in the tips section ("weather can be cold in April")
5. **Fill links**, click "Fill Missing Links" to resolve real website URLs via AI
6. **Share**, use the share modal to copy a link or generate a write-up

## How it works under the hood

### Data model

Recommendations are regular trips with `trip_type = 'recommendation'`. The itinerary data includes:

```json
{
  "ideas": [
    {
      "title": "White Mountain Cider Co",
      "category": "meal",
      "location": "Jackson, NH",
      "notes": "best dinner in the area, great cocktails",
      "website": "https://www.whitemountaincider.com",
      "google_maps_link": "https://www.google.com/maps/search/...",
      "latitude": 44.0534,
      "longitude": -71.1826
    }
  ],
  "tips": [
    "Weather can be cold in April, bring layers"
  ],
  "days": [],
  "chatHistory": []
}
```

### AI write-up generation

`POST /api/trips/<link>/writeup` calls Claude Sonnet via [fiat-lux-agents](https://github.com/aabtzu/fiat-lux-agents) to generate a narrative. The prompt includes:

- All items with their notes, locations, and website URLs
- General tips
- Instruction to group by area, be opinionated, include hyperlinks

The write-up is rendered as markdown (bold, headers, links) on both the `/w/` page and in the trip editor.

### Link resolution

`POST /api/trips/<link>/fill-links` resolves missing website URLs:

1. Adds Google Maps search links for items without map links
2. Sends venue names to Claude to look up real website URLs
3. Clears Google search fallback URLs (replaced with real ones or left empty)

### Explore → Trip pipeline

When adding a venue from Explore to a trip:

- Location includes city, state, country (prevents geocoding to wrong state)
- Google Maps link built from coordinates or name
- Website URL from curated DB or LLM response (no Google search fallback)
- All data preserved through edit/save cycles (coordinates, links)

### Sharing

The share modal (My Trips page) offers:

- **Itinerary Link**, `/<link>.html` (day-by-day view)
- **Recommendation Link**, `/r/<link>` (grouped ideas)
- **Write-up Link**, `/w/<link>` (AI narrative)
- **Generate & Copy Write-up**, generates inline, copies text

All options make the trip public first if needed.

### "Save to my trips" (recipient side)

Public recommendation and write-up pages include a "Save to my trips" button. When clicked:

- If not logged in → redirects to register with return URL
- If logged in → styled modal to pick a trip or create new one
- `POST /api/trips/clone-ideas` copies all ideas from source to target trip
