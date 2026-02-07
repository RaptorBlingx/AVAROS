---
name: add-capability
description: Add a new capability to the adapter interface
agent: agent
tools: ['edit/editFiles', 'search']
---
# Add Adapter Capability

Add capability: **${input:capabilityName}**

## Steps

1. **Define method in ABC** (`skill/adapters/base.py`)
   - Add abstract method signature
   - Document parameters and return type
   - Specify if optional (check `supports_capability`)

2. **Update capability enum** if exists

3. **Implement in existing adapters**
   - `skill/adapters/reneryo.py` - full implementation
   - `skill/adapters/mock.py` - mock implementation

4. **Add to YAML configs**
   - Define endpoint in `config/backends/*.yaml`
   - Add response mapping

5. **Create tests**
   - Test the capability in each adapter
   - Test `supports_capability` returns correct value

## Method Signature Template
```python
@abstractmethod
async def {capability_name}(
    self,
    param1: Type1,
    param2: Optional[Type2] = None
) -> ReturnType:
    """
    Description of what this capability does.
    
    Args:
        param1: Description
        param2: Optional description
        
    Returns:
        Description of return value
        
    Raises:
        AdapterError: If the operation fails
        NotSupportedError: If adapter doesn't support this
    """
    pass
```
