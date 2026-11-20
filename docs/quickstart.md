# Quick Start

## Prerequisites

- Python 3.11+
- Windows 10/11 (Linux/macOS supported via `install.sh`)

## Installation

```powershell
# Clone the repository
git clone https://github.com/hypo69/ai-tc.git
cd ai-tc

# Install dependencies
.\install.ps1

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Start the server
.\run.ps1
```

## First Run

Open `http://localhost:8000` in your browser. On first run, the server auto-creates a local admin user.

## Configuration

All non-secret configuration lives in `config.json`. Secrets go in `.env`.

See User Guide for more details.
