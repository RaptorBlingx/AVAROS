---
applyTo: "**/*.py"
---
# Code Quality Standards

> **Purpose:** SOLID, DRY, Clean Code principles with examples for AVAROS project.

---

## Philosophy

**Code is read 10x more than it's written.** Optimize for readability, not cleverness.

**Every line of code is a liability.** Less code = less bugs = less maintenance.

**Code quality is not optional.** It's the difference between a maintainable system and technical debt hell.

---

## SOLID Principles

### S - Single Responsibility Principle

**Principle:** A class should have only one reason to change.

#### ✅ GOOD: Single responsibility

```python
# Each class has ONE job
class KPIFetcher:
    """Fetches KPI data. That's it."""
    def fetch(self, metric: str) -> KPIResult:
        return self.adapter.get_kpi(metric)

class KPIFormatter:
    """Formats KPI for display. That's it."""
    def format(self, result: KPIResult) -> str:
        return f"{result.value} {result.unit}"

class KPIResponseBuilder:
    """Builds voice responses. That's it."""
    def build(self, formatted_kpi: str, context: str) -> str:
        return f"Your {context} is {formatted_kpi}"
```

#### ❌ BAD: Multiple responsibilities

```python
class KPIManager:
    """Does EVERYTHING - violates SRP"""
    def handle_kpi_request(self, utterance: str):
        # Responsibility 1: Parse utterance
        metric = self._parse(utterance)
        
        # Responsibility 2: Fetch data
        result = self.adapter.get_kpi(metric)
        
        # Responsibility 3: Format
        formatted = f"{result.value} {result.unit}"
        
        # Responsibility 4: Log
        self.logger.info(f"Returned {metric}")
        
        # Responsibility 5: Speak
        self.speak(formatted)
        
        # 5 reasons to change = 5 responsibilities = BAD
```

---

### O - Open/Closed Principle

**Principle:** Open for extension, closed for modification.

#### ✅ GOOD: Extend via new classes

```python
# Base interface
class ManufacturingAdapter(ABC):
    @abstractmethod
    def get_kpi(self, metric: str) -> KPIResult:
        pass

# Extend with new implementations (no modification needed)
class RENERYOAdapter(ManufacturingAdapter):
    def get_kpi(self, metric: str) -> KPIResult:
        # RENERYO-specific implementation
        pass

class SAPAdapter(ManufacturingAdapter):
    def get_kpi(self, metric: str) -> KPIResult:
        # SAP-specific implementation
        pass

# Adding new adapter doesn't modify existing code
class SiemensAdapter(ManufacturingAdapter):
    def get_kpi(self, metric: str) -> KPIResult:
        # Siemens-specific implementation
        pass
```

#### ❌ BAD: Modify for each new case

```python
class AdapterManager:
    def get_kpi(self, platform: str, metric: str) -> KPIResult:
        if platform == "reneryo":
            # RENERYO logic
            pass
        elif platform == "sap":
            # SAP logic
            pass
        elif platform == "siemens":  # ❌ Modified class to add new platform
            # Siemens logic
            pass
        # Every new platform = modify this class = BAD
```

---

### L - Liskov Substitution Principle

**Principle:** Subtypes must be substitutable for their base types.

#### ✅ GOOD: Subtypes work the same way

```python
def process_kpi(adapter: ManufacturingAdapter, metric: str):
    """Works with ANY adapter implementation."""
    result = adapter.get_kpi(metric)  # Same interface
    return result.value

# All these work identically
process_kpi(RENERYOAdapter(), "energy_per_unit")
process_kpi(SAPAdapter(), "energy_per_unit")
process_kpi(MockAdapter(), "energy_per_unit")
```

#### ❌ BAD: Subtypes behave differently

```python
class BrokenAdapter(ManufacturingAdapter):
    def get_kpi(self, metric: str) -> KPIResult:
        # ❌ Returns None instead of raising exception
        return None  # Violates contract!

# Now this breaks:
def process_kpi(adapter: ManufacturingAdapter, metric: str):
    result = adapter.get_kpi(metric)
    return result.value  # ❌ Crashes if result is None
```

**Fix:** Follow the contract. If base class raises exception, all subtypes must too.

---

### I - Interface Segregation Principle

**Principle:** Clients shouldn't depend on methods they don't use.

#### ✅ GOOD: Focused interfaces

```python
# Split into focused interfaces
class KPIProvider(ABC):
    @abstractmethod
    def get_kpi(self, metric: str) -> KPIResult:
        pass

class TrendProvider(ABC):
    @abstractmethod
    def get_trend(self, metric: str) -> TrendResult:
        pass

class ComparisonProvider(ABC):
    @abstractmethod
    def compare(self, entities: list, metric: str) -> ComparisonResult:
        pass

# Adapters implement only what they support
class RENERYOAdapter(KPIProvider, TrendProvider, ComparisonProvider):
    """RENERYO supports all features."""
    pass

class BasicAdapter(KPIProvider):
    """Basic adapter only provides KPIs."""
    pass
```

#### ❌ BAD: Fat interface

```python
class ManufacturingAdapter(ABC):
    """Forces ALL adapters to implement EVERYTHING."""
    @abstractmethod
    def get_kpi(self, metric: str) -> KPIResult:
        pass
    
    @abstractmethod
    def get_trend(self, metric: str) -> TrendResult:
        pass
    
    @abstractmethod
    def compare(self, entities: list) -> ComparisonResult:
        pass
    
    @abstractmethod
    def simulate_whatif(self, scenario: dict) -> Simulation:
        pass  # ❌ Not all platforms support this!

# Now this adapter must implement methods it doesn't support
class BasicAdapter(ManufacturingAdapter):
    def simulate_whatif(self, scenario: dict):
        raise NotImplementedError  # ❌ Forced to implement unusable method
```

---

### D - Dependency Inversion Principle

**Principle:** Depend on abstractions, not concretions.

#### ✅ GOOD: Depend on interface

```python
class QueryDispatcher:
    """Depends on adapter INTERFACE, not specific implementation."""
    def __init__(self, adapter: ManufacturingAdapter):  # ✅ Interface type
        self.adapter = adapter
    
    def get_kpi(self, metric: str) -> KPIResult:
        return self.adapter.get_kpi(metric)

# Works with ANY adapter
dispatcher1 = QueryDispatcher(RENERYOAdapter())
dispatcher2 = QueryDispatcher(SAPAdapter())
dispatcher3 = QueryDispatcher(MockAdapter())
```

#### ❌ BAD: Depend on concrete class

```python
class QueryDispatcher:
    """Tightly coupled to RENERYO - can't swap adapters."""
    def __init__(self):
        self.adapter = RENERYOAdapter()  # ❌ Hard-coded dependency
    
    def get_kpi(self, metric: str) -> KPIResult:
        return self.adapter.get_kpi(metric)

# Can't use SAP or Mock adapter without modifying QueryDispatcher
```

---

## DRY Principle (Don't Repeat Yourself)

**Principle:** Every piece of knowledge should have a single, authoritative representation.

### ✅ GOOD: Extract common logic

```python
# Common pattern extracted
def map_to_canonical_metric(platform_metric: str, platform: str) -> str:
    """Single source of truth for metric mapping."""
    mappings = {
        "reneryo": {"seu": "energy_per_unit", "scrap_pct": "scrap_rate"},
        "sap": {"energyPerPiece": "energy_per_unit", "scrapPercentage": "scrap_rate"},
    }
    return mappings[platform].get(platform_metric, platform_metric)

# All adapters use it
class RENERYOAdapter:
    def get_kpi(self, metric: str) -> KPIResult:
        platform_metric = map_to_canonical_metric(metric, "reneryo")
        # ... rest of implementation

class SAPAdapter:
    def get_kpi(self, metric: str) -> KPIResult:
        platform_metric = map_to_canonical_metric(metric, "sap")
        # ... rest of implementation
```

### ❌ BAD: Duplicated logic

```python
# Duplicated in every adapter
class RENERYOAdapter:
    def get_kpi(self, metric: str) -> KPIResult:
        if metric == "energy_per_unit":
            platform_metric = "seu"
        elif metric == "scrap_rate":
            platform_metric = "scrap_pct"
        # ... rest

class SAPAdapter:
    def get_kpi(self, metric: str) -> KPIResult:
        if metric == "energy_per_unit":
            platform_metric = "energyPerPiece"  # Same logic, different names
        elif metric == "scrap_rate":
            platform_metric = "scrapPercentage"
        # ... rest
```

**Problem:** Change the mapping logic? Update in 5 places. Forget one? Bug.

---

## Clean Code Principles

### 1. Meaningful Names

#### ✅ GOOD: Descriptive names

```python
def calculate_overall_equipment_effectiveness(
    availability: float,
    performance: float,
    quality: float
) -> float:
    """Name explains WHAT it does."""
    return availability * performance * quality

# Usage is self-documenting
oee = calculate_overall_equipment_effectiveness(0.9, 0.95, 0.98)
```

#### ❌ BAD: Cryptic names

```python
def calc_oee(a, p, q):  # What are a, p, q?
    return a * p * q

oee = calc_oee(0.9, 0.95, 0.98)  # What do these numbers mean?
```

### 2. Small Functions

#### ✅ GOOD: Focused functions

```python
def validate_metric(metric: str) -> None:
    """One job: validate metric name."""
    if metric not in SUPPORTED_METRICS:
        raise MetricNotFoundError(metric)

def fetch_kpi_from_adapter(adapter: ManufacturingAdapter, metric: str) -> KPIResult:
    """One job: fetch KPI."""
    return adapter.get_kpi(metric)

def format_kpi_response(result: KPIResult) -> str:
    """One job: format response."""
    return f"{result.value} {result.unit}"

# Compose small functions
def get_kpi_response(metric: str) -> str:
    validate_metric(metric)
    result = fetch_kpi_from_adapter(adapter, metric)
    return format_kpi_response(result)
```

#### ❌ BAD: God function

```python
def get_kpi_response(metric: str) -> str:
    # 100 lines of validation, fetching, parsing, formatting, logging, ...
    # Unmaintainable and untestable
    pass
```

### 3. No Magic Numbers

#### ✅ GOOD: Named constants

```python
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
RATE_LIMIT_PER_MINUTE = 100

def fetch_with_retry(url: str) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            return requests.get(url, timeout=TIMEOUT_SECONDS)
        except Timeout:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
```

#### ❌ BAD: Magic numbers

```python
def fetch_with_retry(url: str) -> dict:
    for attempt in range(3):  # Why 3?
        try:
            return requests.get(url, timeout=30)  # Why 30?
        except Timeout:
            time.sleep(2 ** attempt)  # Why exponential?
```

### 4. Guard Clauses (Early Returns)

#### ✅ GOOD: Early returns

```python
def get_kpi(metric: str, adapter: ManufacturingAdapter) -> KPIResult:
    """Guard clauses reduce nesting."""
    if not metric:
        raise ValueError("Metric required")
    
    if metric not in SUPPORTED_METRICS:
        raise MetricNotFoundError(metric)
    
    if not adapter:
        raise ValueError("Adapter required")
    
    # Happy path at the end, no nesting
    return adapter.get_kpi(metric)
```

#### ❌ BAD: Nested conditions

```python
def get_kpi(metric: str, adapter: ManufacturingAdapter) -> KPIResult:
    """Arrow anti-pattern - too much nesting."""
    if metric:
        if metric in SUPPORTED_METRICS:
            if adapter:
                return adapter.get_kpi(metric)
            else:
                raise ValueError("Adapter required")
        else:
            raise MetricNotFoundError(metric)
    else:
        raise ValueError("Metric required")
```

### 5. Comments Explain WHY, Not WHAT

#### ✅ GOOD: Explain reasoning

```python
# Use exponential backoff because RENERYO rate limits at 100 req/min
for attempt in range(MAX_RETRIES):
    time.sleep(2 ** attempt)

# ISO 50001 requires 12 months of baseline data
MIN_BASELINE_MONTHS = 12
```

#### ❌ BAD: State the obvious

```python
# Loop 3 times
for i in range(3):
    ...

# Get KPI from adapter
result = adapter.get_kpi(metric)
```

**Better:** Make code self-explanatory. If you need a comment to explain WHAT, rename variables/functions.

---

## Code Smells to Avoid

### 1. Long Parameter List

#### ❌ BAD

```python
def create_kpi_result(metric, value, unit, timestamp, source, confidence, metadata):
    # Too many parameters - error-prone
    pass
```

#### ✅ GOOD

```python
@dataclass
class KPIData:
    metric: str
    value: float
    unit: str
    timestamp: datetime
    source: str
    confidence: float
    metadata: dict

def create_kpi_result(data: KPIData) -> KPIResult:
    # Single parameter object
    pass
```

### 2. Feature Envy

#### ❌ BAD

```python
class ResponseBuilder:
    def build(self, result: KPIResult):
        # Accessing too many properties of KPIResult
        return (
            f"{result.metric} is {result.value} {result.unit} "
            f"at {result.timestamp} from {result.metadata['source']}"
        )
```

#### ✅ GOOD

```python
@dataclass
class KPIResult:
    def to_string(self) -> str:
        """Behavior lives with the data."""
        return (
            f"{self.metric} is {self.value} {self.unit} "
            f"at {self.timestamp} from {self.metadata['source']}"
        )

class ResponseBuilder:
    def build(self, result: KPIResult):
        return result.to_string()  # Delegates to KPIResult
```

### 3. Primitive Obsession

#### ❌ BAD

```python
def calculate_timeframe(start: str, end: str) -> tuple[str, str]:
    # Using strings for dates - error-prone
    pass
```

#### ✅ GOOD

```python
@dataclass
class TimeFrame:
    start: datetime
    end: datetime
    
    def duration_days(self) -> int:
        return (self.end - self.start).days

def calculate_timeframe(timeframe: TimeFrame) -> TimeFrame:
    # Type-safe, clear intent
    pass
```

### 4. Shotgun Surgery

**Problem:** One change requires modifications in many places.

**Solution:** Use DRY principle. Centralize related logic.

---

## Refactoring Patterns

### Extract Method

```python
# Before
def process_kpi(metric):
    if metric not in SUPPORTED_METRICS:
        raise MetricNotFoundError(metric)
    result = adapter.get_kpi(metric)
    if result.value < 0:
        raise ValueError("Negative value")
    return f"{result.value} {result.unit}"

# After (extracted methods)
def validate_metric(metric):
    if metric not in SUPPORTED_METRICS:
        raise MetricNotFoundError(metric)

def validate_result(result):
    if result.value < 0:
        raise ValueError("Negative value")

def format_result(result):
    return f"{result.value} {result.unit}"

def process_kpi(metric):
    validate_metric(metric)
    result = adapter.get_kpi(metric)
    validate_result(result)
    return format_result(result)
```

### Replace Conditional with Polymorphism

```python
# Before
def get_adapter_for_platform(platform: str):
    if platform == "reneryo":
        return RENERYOAdapter()
    elif platform == "sap":
        return SAPAdapter()
    else:
        return MockAdapter()

# After (factory + polymorphism)
ADAPTERS = {
    "reneryo": RENERYOAdapter,
    "sap": SAPAdapter,
}

def get_adapter_for_platform(platform: str):
    adapter_class = ADAPTERS.get(platform, MockAdapter)
    return adapter_class()
```

---

## Performance Considerations

### 1. Avoid Premature Optimization

> "Premature optimization is the root of all evil." - Donald Knuth

**Write clean code first. Optimize only when:**
1. Profiling shows it's a bottleneck
2. User experience is affected
3. Resource costs are high

### 2. Use Appropriate Data Structures

```python
# ✅ GOOD: O(1) lookup
SUPPORTED_METRICS = {"energy_per_unit", "scrap_rate", "oee"}  # Set

if metric in SUPPORTED_METRICS:  # Fast
    ...

# ❌ BAD: O(n) lookup
SUPPORTED_METRICS = ["energy_per_unit", "scrap_rate", "oee"]  # List

if metric in SUPPORTED_METRICS:  # Slow for large lists
    ...
```

### 3. Async for I/O-Bound Operations

```python
# ✅ GOOD: Async for API calls
async def get_kpi(metric: str) -> KPIResult:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return KPIResult.from_dict(data)

# ❌ BAD: Blocking I/O in voice assistant
def get_kpi(metric: str) -> KPIResult:
    response = requests.get(url)  # Blocks the entire app
    return KPIResult.from_dict(response.json())
```

---

## How Agents Use This File

**@quality agent:**
- Reviews code for SOLID violations
- Checks for code smells (long functions, magic numbers, etc.)
- Suggests refactoring patterns
- Ensures clean code standards

**@lead-dev agent:**
- Follows SOLID principles when writing code
- Extracts common patterns (DRY)
- Uses meaningful names
- Writes small, focused functions

**@pr-review agent:**
- Teaches Emre about SOLID violations
- Points out code smells
- Suggests cleaner alternatives
