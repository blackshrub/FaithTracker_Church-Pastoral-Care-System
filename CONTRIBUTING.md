# Contributing to FaithTracker

Thank you for your interest in contributing to FaithTracker! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- MongoDB 7.0+
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/FaithTracker.git
cd FaithTracker

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

# Frontend setup
cd ../frontend
yarn install
```

### Running Locally

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
uvicorn server:app --reload --port 8001

# Terminal 2: Frontend
cd frontend
yarn start
```

## Development Workflow

### Branch Naming

Use descriptive branch names:

```
feat/add-member-export
fix/dashboard-timezone-bug
refactor/extract-auth-utils
docs/update-api-documentation
test/add-member-crud-tests
```

### Commit Messages

Follow conventional commits format:

```
feat: add member export to CSV
fix: correct timezone handling in dashboard
refactor: extract authentication utilities
docs: update API documentation
test: add member CRUD tests
chore: update dependencies
perf: optimize dashboard queries
```

### Pull Request Process

1. **Create a branch** from `main`
2. **Make changes** following code style guidelines
3. **Write tests** for new functionality
4. **Run tests locally** before pushing
5. **Open PR** with clear description
6. **Address feedback** from code review
7. **Merge** after approval

### PR Description Template

```markdown
## Summary
Brief description of changes

## Changes
- Change 1
- Change 2

## Testing
- [ ] Unit tests pass
- [ ] E2E tests pass (if applicable)
- [ ] Manual testing completed

## Screenshots (if UI changes)
```

## Code Style

### Backend (Python)

- Follow PEP 8
- Use `ruff` for linting and formatting
- Type hints encouraged
- Docstrings for public functions

```bash
# Format code
cd backend
ruff format .

# Check linting
ruff check .
```

### Frontend (JavaScript/React)

- ESLint + Prettier configuration
- Functional components with hooks
- PropTypes for component props

```bash
# Format code
cd frontend
yarn format

# Check linting
yarn lint
```

## Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=. --cov-report=html
```

### Frontend Tests

```bash
cd frontend

# Unit tests
yarn test

# E2E tests
yarn test:e2e
```

### Test Requirements

- New features must include tests
- Bug fixes should include regression tests
- Maintain >80% coverage for critical paths

## Project Structure

```
FaithTracker/
├── backend/
│   ├── server.py          # Main API (monolithic)
│   ├── scheduler.py       # Background jobs
│   ├── tests/             # Pytest tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/         # Page components
│   │   ├── components/    # Reusable components
│   │   ├── hooks/         # Custom hooks
│   │   ├── lib/           # Utilities
│   │   └── context/       # React context
│   ├── e2e/               # Playwright tests
│   └── package.json
└── docker-compose.yml
```

## Key Guidelines

### Backend Development

1. **Multi-tenancy**: Always filter by `campus_id`
2. **Security**: Use `get_current_user()` for auth
3. **Validation**: Use msgspec for request validation
4. **Logging**: Use `logger` for errors and info
5. **Constants**: Add magic numbers to CONSTANTS section

### Frontend Development

1. **State**: Use React Query for server state
2. **Styling**: Use Tailwind CSS classes
3. **Components**: Use Shadcn/UI from `@/components/ui`
4. **i18n**: Add translations to both `en.json` and `id.json`
5. **Accessibility**: Include ARIA labels and keyboard navigation

### Database Changes

1. Add migrations to `migrate.py`
2. Update indexes in `create_indexes.py`
3. Document schema changes

## Common Tasks

### Adding a New API Endpoint

1. Add endpoint to `server.py` in appropriate section
2. Add request/response models if needed
3. Include auth: `current_user = await get_current_user(request)`
4. Filter by campus: `query["campus_id"] = current_user["campus_id"]`
5. Add tests to `tests/`

### Adding a New Page

1. Create page in `frontend/src/pages/`
2. Add route in `App.jsx`
3. Add translations to `locales/en.json` and `locales/id.json`
4. Add navigation link if needed

### Adding Translations

1. Edit `frontend/src/locales/en.json`
2. Edit `frontend/src/locales/id.json`
3. Use in component: `const { t } = useTranslation(); t('key.path')`

## Questions?

- Check existing issues
- Review documentation in CLAUDE.md
- Open a discussion for questions

Thank you for contributing!
