---
applyTo: "**/*.py"
---
# Senior Engineer Code Quality Standards

## 🎯 Core Principle
> **Write code as if the next maintainer is a mass murderer who knows where you live.**
>
> Every line must be production-grade, optimized, and maintainable.

## SOLID Principles (MANDATORY)

### S - Single Responsibility
\`\`\`python
# ❌ BAD: Class does too much
class EnergyHandler:
    def get_energy(self): ...
    def format_response(self): ...
    def send_email(self): ...
    def log_to_file(self): ...

# ✅ GOOD: One reason to change
class EnergyQueryHandler:
    def __init__(self, dispatcher, formatter):
        self.dispatcher = dispatcher
        self.formatter = formatter
    
    def handle(self, query: EnergyQuery) -> Response:
        result = self.dispatcher.get_kpi(query)
        return self.formatter.format(result)
\`\`\`

### O - Open/Closed
\`\`\`python
# ✅ GOOD: Extend via new classes, not modifying existing
class ManufacturingAdapter(ABC):
    @abstractmethod
    def get_kpi(self, metric, asset_id, period) -> KPIResult: ...

class ReneryoAdapter(ManufacturingAdapter): ...
class SAPAdapter(ManufacturingAdapter): ...  # New platform = new class
\`\`\`

### L - Liskov Substitution
\`\`\`python
# All adapters must be interchangeable
def process_query(adapter: ManufacturingAdapter):
    # Must work with ANY adapter implementation
    return adapter.get_kpi(metric, asset_id, period)
\`\`\`

### I - Interface Segregation
\`\`\`python
# ❌ BAD: Fat interface
class IEverything:
    def get_kpi(self): ...
    def send_notification(self): ...
    def generate_report(self): ...

# ✅ GOOD: Focused interfaces
class IQueryable(Protocol):
    def get_kpi(self, ...) -> KPIResult: ...

class INotifiable(Protocol):
    def notify(self, ...) -> None: ...
\`\`\`

### D - Dependency Inversion
\`\`\`python
# ❌ BAD: High-level depends on low-level
class IntentHandler:
    def __init__(self):
        self.adapter = ReneryoAdapter()  # Tight coupling!

# ✅ GOOD: Depend on abstractions
class IntentHandler:
    def __init__(self, adapter: ManufacturingAdapter):  # Injected
        self.adapter = adapter
\`\`\`

## Clean Architecture Layers

\`\`\`
┌─────────────────────────────────────────┐
│  Presentation (OVOS Intents, Web API)   │  ← Depends on nothing
├─────────────────────────────────────────┤
│  Application (Use Cases, Handlers)      │  ← Depends on Domain
├─────────────────────────────────────────┤
│  Domain (Entities, Value Objects)       │  ← Pure business logic
├─────────────────────────────────────────┤
│  Infrastructure (Adapters, DB, APIs)    │  ← Implements interfaces
└─────────────────────────────────────────┘
\`\`\`

**Rule**: Dependencies point INWARD. Domain never imports from Infrastructure.

## Optimization Standards

### Performance
\`\`\`python
# Use async for I/O-bound operations
async def get_kpi(...) -> KPIResult:
    async with aiohttp.ClientSession() as session:
        ...

# Use caching for expensive operations
@lru_cache(maxsize=128, ttl=300)
def get_asset_metadata(asset_id: str) -> Asset: ...

# Batch requests when possible
async def get_multiple_kpis(metrics: list[CanonicalMetric]) -> list[KPIResult]:
    return await asyncio.gather(*[self.get_kpi(m) for m in metrics])
\`\`\`

### Memory
\`\`\`python
# Use generators for large datasets
def stream_time_series(start, end) -> Iterator[DataPoint]:
    for chunk in self.fetch_chunks(start, end):
        yield from chunk

# Avoid loading everything into memory
# ❌ BAD: data = list(fetch_all_records())
# ✅ GOOD: for record in fetch_records(): process(record)
\`\`\`

### Database
\`\`\`python
# Use indexes for frequent queries
# Use connection pooling
# Use prepared statements (prevents SQL injection too)
# Batch inserts/updates
\`\`\`

## Error Handling Pattern

\`\`\`python
# Domain-specific exceptions
class AVAROSError(Exception):
    """Base exception for AVAROS"""
    def __init__(self, message: str, code: str, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}

class AdapterError(AVAROSError):
    """Platform adapter errors"""

class ValidationError(AVAROSError):
    """Input validation errors"""

# Structured error handling
try:
    result = await adapter.get_kpi(...)
except aiohttp.ClientError as e:
    raise AdapterError(
        message="Failed to connect to platform",
        code="PLATFORM_UNAVAILABLE",
        details={"original_error": str(e)}
    )
\`\`\`

## Code Style Rules

### Naming
- Classes: \`PascalCase\` (nouns) - \`EnergyQueryHandler\`
- Functions: \`snake_case\` (verbs) - \`get_kpi\`, \`calculate_trend\`
- Constants: \`UPPER_SNAKE\` - \`MAX_RETRIES\`, \`DEFAULT_TIMEOUT\`
- Private: \`_prefix\` - \`_validate_input\`

### Documentation
\`\`\`python
def get_kpi(
    self,
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod
) -> KPIResult:
    """
    Retrieve a KPI value for a specific asset and time period.
    
    Args:
        metric: The canonical metric to query (e.g., ENERGY_PER_UNIT)
        asset_id: Unique identifier of the asset
        period: Time period for aggregation
    
    Returns:
        KPIResult with value, unit, and metadata
    
    Raises:
        AdapterError: If platform API is unavailable
        ValidationError: If asset_id is invalid
    
    Example:
        >>> result = await handler.get_kpi(
        ...     CanonicalMetric.ENERGY_PER_UNIT,
        ...     "compressor-1",
        ...     TimePeriod.last_week()
        ... )
        >>> print(f"{result.value} {result.unit}")
        3.45 kWh/unit
    """
\`\`\`

### Type Hints (MANDATORY)
\`\`\`python
# Every function signature must have type hints
def process(
    data: list[DataPoint],
    options: ProcessOptions | None = None
) -> ProcessResult:
    ...
\`\`\`

## Testing Standards

### Test Coverage Minimum: 80%
\`\`\`python
# Unit tests for all business logic
def test_kpi_calculation():
    result = calculate_energy_per_unit(total=100, units=25)
    assert result == 4.0

# Integration tests for adapters
async def test_reneryo_adapter_connection():
    adapter = ReneryoAdapter(mock_config)
    result = await adapter.get_kpi(...)
    assert isinstance(result, KPIResult)

# Contract tests for interface compliance
def test_adapter_implements_interface():
    adapter = ReneryoAdapter(config)
    assert isinstance(adapter, ManufacturingAdapter)
\`\`\`

## DRY (Don't Repeat Yourself)

\`\`\`python
# ❌ BAD: Duplicated validation
def get_energy(asset_id):
    if not asset_id or len(asset_id) > 50:
        raise ValueError("Invalid asset_id")
    ...

def get_scrap(asset_id):
    if not asset_id or len(asset_id) > 50:
        raise ValueError("Invalid asset_id")
    ...

# ✅ GOOD: Reusable validation
@validated
def get_energy(asset_id: AssetId):  # AssetId is a validated type
    ...
\`\`\`

## Security by Default

- Input validation on ALL external data
- Parameterized queries (no string concatenation)
- Secrets via environment or encrypted storage
- Audit logging for sensitive operations
- Rate limiting on APIs
