---
applyTo: "**/docubot/**,**/rag/**"
---
# DocuBoT Integration Rules (RAG Retrieval Grounding)

## 🎯 Purpose
DocuBoT provides **document-grounded answers** by retrieving relevant content from:
- Procedures & SOPs
- Technical specifications
- Supplier declarations
- Pilot documentation
- LCA factors & emission tables

## Architecture
\`\`\`
User Query → AVAROS Skill → DocuBoT Service
                               ↓
                    Vector Store (embeddings)
                               ↓
                    Retrieved Context + Sources
                               ↓
                    Grounded Answer with Citations
\`\`\`

## Integration Points

### DocuBoT API Endpoints
\`\`\`python
# Query with retrieval
POST /docubot/query
{
    "question": "What's the melting point for PET plastic?",
    "top_k": 5,
    "filters": {"doc_type": "specification"}
}

# Response includes sources
{
    "answer": "The melting point of PET is 250-260°C",
    "sources": [
        {"doc": "material_specs.pdf", "page": 12, "confidence": 0.92}
    ]
}
\`\`\`

### When to Use DocuBoT
- Technical specifications lookups
- Procedure/SOP retrieval
- Regulatory compliance queries
- Supplier documentation search
- Historical pilot learnings

### Skill Integration Pattern
\`\`\`python
async def get_grounded_answer(self, question: str, doc_type: str = None) -> GroundedAnswer:
    """Route through DocuBoT for document-grounded responses"""
    response = await self.docubot_client.query(
        question=question,
        filters={"doc_type": doc_type} if doc_type else None
    )
    return GroundedAnswer(
        text=response["answer"],
        sources=response["sources"],
        confidence=response.get("confidence", 0.0)
    )
```

## Document Indexing
- Index formats: PDF, DOCX, TXT, Markdown
- Metadata: doc_type, asset_id, supplier_id, language
- Multilingual support: EN, DE, TR (per proposal)
- Re-index on document updates

## Rules
1. Always cite sources in responses
2. Flag low-confidence answers (<0.7)
3. Fallback to "I don't have documentation on that"
4. Log all queries for audit trail
