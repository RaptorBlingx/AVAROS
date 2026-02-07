---
description: Add a new domain model to AVAROS
---
# New Domain Model Request

Add domain model: {{model_name}}

## Model Fields
{{fields_description}}

## Tasks
1. Create \`domain/{{model_name}}.py\` with dataclass/Pydantic model
2. Zero external dependencies in domain layer
3. Add validation logic as methods
4. Create factory functions if complex initialization needed
5. Add to domain __init__.py exports
6. Write unit tests
