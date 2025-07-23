# Voyager T800 – AI Travel Assistant

**Voyager T800** is a multimodal AI-powered travel planning assistant developed by Data Science interns during a 12-week generative AI internship. The application helps users generate personalized itineraries by combining their travel preferences (text) and inspiration images. The app integrates image analysis, retrieval-augmented generation (RAG), and large language model (LLM) orchestration to create rich, grounded trip plans.

---

## Key Features

- **Multimodal Input**: Accepts both user-uploaded images and textual preferences.
- **Image Understanding**: Uses computer vision to extract meaning from photos (e.g., landmarks or activities).
- **Knowledge-Driven Recommendations**: Retrieves verified data from a vector database of curated travel facts.
- **RAG Integration**: Grounds LLM output in local, relevant information.
- **Conversational UX**: Generates friendly, day-by-day itineraries with options for follow-up refinement.

---

## Tech Stack

- **Frontend**: Streamlit / React (AI-assisted UI generation)
- **Backend**: FastAPI
- **Orchestration**: LangChain / LangGraph
- **Embeddings & Vector Search**: FAISS / Chroma / Pinecone
- **LLMs**: OpenAI GPT / Anthropic Claude via AWS Bedrock
- **Vision APIs**: AWS Rekognition, CLIP, or equivalent

---

## Project Structure

```

/app/
├── main.py             # API entry point
├── itinerary/          # Core LLM generation logic
├── image\_analysis/     # Vision tools for extracting meaning from images
├── retrieval/          # Vector DB setup and search
├── prompts/            # Prompt templates
└── frontend/           # Streamlit or React app

/docs/                    # Technical documentation
/tests/                   # Unit & integration tests

```

---

## Contributing Guidelines

We follow a structured Git workflow to keep development smooth and collaborative.

### General Git Flow

1. Clone the repo and create your own feature branch from `main`.
2. Make sure to follow naming conventions below.
3. Commit frequently with clear, concise messages.
4. Push to remote and open a Pull Request (PR).
5. Wait for at least **3 code review approvals** before merging to `main`.

### Branch Naming Convention

Branch names should follow this format:

```

issue-\<ISSUE\_NUMBER>-<short-task-summary>

```

Examples:
```
- `issue-23-add-multimodal-upload`
- `issue-17-fix-langchain-vectorbug`
- `issue-12-improve-prompt-formatting`
```

> _Tip: Reference the GitHub Issue in your PR for context._

---

## Pull Request Guidelines

- Always link the related issue (e.g., "Closes #17").
- Add a clear title and description of your changes.
- Include screenshots or examples if UI-related.
- Run all tests before submitting a PR.
- Mark as **"Ready for Review"** only when complete.

---

## Weekly Focus

Each branch or contribution should align with the current module or sprint. See `/docs/sprints/` for a breakdown of weekly goals and accepted contributions.

---

## Code of Conduct

Please respect your team members. This is a learning space — ask questions, document your decisions, and be constructive in code reviews.

---

## Credits

This project was developed as part of the **Generative AI Internship Program** under the mentorship of **SoftServe Academy** mentors. We gratefully acknowledge the tools and APIs provided by OpenAI, Anthropic, AWS, and LangChain.

---

## License

[MIT License](LICENSE)




