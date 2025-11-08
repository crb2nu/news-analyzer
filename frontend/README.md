# News Analyzer Frontend

Modern, interactive web interface for the News Analyzer summarizer service.

## Quick Start

### Prerequisites

- Node.js 20.x or later
- npm 10.x or later
- Backend API running at `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open in browser
# Visit http://localhost:5173
```

### Build for Production

```bash
# Build static site
npm run build

# Preview production build
npm run preview
```

## Features

- 📰 **Feed View** - Browse daily articles with filtering and search
- 🔍 **Discover** - Global search across all articles with trending insights
- 📅 **Events** - Community events calendar extracted from articles
- 🌓 **Dark Mode** - Automatic theme switching with manual override
- ♿ **Accessible** - WCAG 2.1 AA compliant with keyboard navigation
- ⚡ **Fast** - Static site generation with smart caching

## Development

```bash
# Type checking
npm run check

# Linting
npm run lint

# Format code
npm run format

# Run tests
npm test
```

## Configuration

Create a `.env` file (copy from `.env.example`):

\`\`\`bash
PUBLIC_API_BASE_URL=http://localhost:8000
PUBLIC_APP_NAME="SW VA News Hub"
\`\`\`

## Project Structure

```
src/
├── routes/              # SvelteKit pages
├── lib/
│   ├── components/     # Reusable components
│   ├── api/           # API client and queries
│   ├── stores/        # State management
│   ├── utils/         # Utility functions
│   └── types/         # TypeScript types
└── app.css            # Global styles
```

## Documentation

See the parent directory for comprehensive documentation:

- [FRONTEND_ARCHITECTURE.md](../FRONTEND_ARCHITECTURE.md) - Complete architecture
- [docs/QUICK_START.md](../docs/QUICK_START.md) - Detailed setup guide
- [docs/API_INTEGRATION_GUIDE.md](../docs/API_INTEGRATION_GUIDE.md) - API integration
- [docs/COMPONENT_EXAMPLES.md](../docs/COMPONENT_EXAMPLES.md) - Component reference

## Technology Stack

- **SvelteKit 2.x** - Meta-framework with static adapter
- **TypeScript 5.x** - Type safety
- **Tailwind CSS 4.x** - Styling
- **TanStack Query** - Data fetching and caching
- **Lucide Svelte** - Icons
- **Vite 5.x** - Build tool

## Deployment

The `build/` directory contains a static site that can be deployed to:

- Netlify
- Vercel
- Cloudflare Pages
- GitHub Pages
- Any static file server

See the architecture documentation for detailed deployment instructions.

## License

[Your License Here]
