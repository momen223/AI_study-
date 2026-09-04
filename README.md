# AI Study Assistant

An intelligent study companion that helps you learn from your PDF documents. Upload your lecture notes, textbooks, or any PDF, and ask questions to get clear, well-explained answers with proper citations.

## What This Does

This is a **smart Q&A system for your study materials**. Instead of reading through hundreds of pages to find answers, you can:

- **Ask questions** about your documents and get accurate, well-explained answers
- **Upload your own PDFs** (lecture notes, textbooks, research papers)
- **Generate quizzes** to test your understanding
- **See exactly where answers come from** - with page citations and source highlighting

## Key Features

- **Works with any subject** - Data Warehousing, Machine Learning, Computer Networks, Database Systems, or your own materials
- **No made-up answers** - If the system can't find the answer in your documents, it says "I don't know" rather than guessing
- **Transparent answers** - See exactly which pages and sections the answer came from
- **Quiz generation** - Automatically create multiple-choice quizzes from your study materials
- **Easy to use** - Modern, clean web interface

## Quick Start

### Prerequisites
- Python 3.10-3.12
- Node.js 18+ (for the web interface)
- An API key for Groq or OpenRouter (or use LM Studio for local AI)

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up your AI provider
```bash
# Copy the example config
cp .env.example .env

# Edit .env and add your API key (from Groq or OpenRouter)
```

### 3. Build the search index and start the server
```bash
python scripts/build_vectorstore.py --all   # Process the demo documents
python app.py                                # Start the API server
```

### 4. Start the web interface
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser and start asking questions!

## How It Works

1. **Upload or select documents** - Choose from the demo libraries or upload your own PDFs
2. **Ask a question** - Type your question in natural language
3. **Get an answer** - The system finds relevant pages, explains the answer, and shows you exactly where it came from

## Project Structure

```
├── src/                    # Core AI logic
│   ├── agents/             # The "brain" - understands and answers questions
│   ├── quizzes/            # Quiz generation system
│   ├── config.py           # Settings (can be changed via environment)
│   └── rag.py              # Main question-answering engine
├── api/                    # Web server (Flask)
├── frontend/               # Web interface (React + TypeScript)
├── tests/                  # Automated tests
├── scripts/                # Helper tools
├── data/                   # Demo documents (included)
└── docs/                   # Documentation
```

## API Endpoints

| Method | Endpoint | What it does |
|--------|----------|--------------|
| `GET` | `/api/health` | Check if the server is running |
| `GET` | `/api/libraries` | List available document libraries |
| `POST` | `/api/chat` | Ask a question |
| `POST` | `/api/documents/upload` | Upload a new PDF |
| `POST` | `/api/quizzes` | Generate a quiz |

## Examples

**Ask a question:**
```json
{
  "question": "What is a fact table?",
  "library": "data_warehousing"
}
```

**Generate a quiz:**
```json
{
  "library": "data_warehousing",
  "question_count": 5,
  "difficulty": "mixed"
}
```

## Documentation

- [Architecture](docs/architecture/ARCHITECTURE.md) - How the system works
- [Testing](docs/testing/TESTING.md) - How we test everything
- [Benchmarks](docs/testing/BENCHMARK.md) - Performance results

## License

MIT License - © 2026 AI Study Assistant