# Testing Guide

Comprehensive guide for running and writing tests in the Feature Voting System.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Test Files](#test-files)
5. [Writing Tests](#writing-tests)
6. [CI/CD Integration](#cicd-integration)

---

## Quick Start

### Run All Tests

```bash
# From project root
./setup_and_test.sh              # Full setup + comprehensive test suite

# From backend directory
cd backend
source venv/bin/activate
python run_tests.py              # Master test runner (all tests)
```

### Run Specific Test Categories

```bash
cd backend
source venv/bin/activate

# Core functionality tests
pytest tests/ -v

# Integration tests
python test_detailed_features.py
python test_complete_api.py

# Agent tests
pytest tests/test_base_agent.py tests/test_product_analyzer.py -v

# Feature extraction tests
pytest tests/test_feature_extraction.py tests/test_feature_extraction_api.py -v
```

---

## Test Structure

```
backend/
├── tests/                          # Pytest unit/integration tests
│   ├── test_base_agent.py         # Agent framework tests
│   ├── test_product_analyzer.py   # Product analysis tests
│   ├── test_ci_models.py          # CI model tests
│   ├── test_feature_extraction.py # Feature extraction logic
│   ├── test_feature_extraction_api.py # Feature extraction endpoints
│   └── test_llm_service_extended.py   # LLM service tests
│
├── test_detailed_features.py      # Integration: Two-level features
├── test_complete_api.py           # Integration: Complete API workflow
├── test_search.py                 # Integration: Vector search
├── test_llm_service.py            # Unit: LLM service basics
├── test_schemas.py                # Unit: Pydantic schema validation
├── test_password_management.py    # Integration: Password workflows
│
├── scripts/
│   └── test_agent_framework.py    # Agent framework validation
│
└── run_tests.py                   # Master test runner (NEW)
```

---

## Running Tests

### Option 1: Master Test Runner (Recommended)

```bash
cd backend
source venv/bin/activate
python run_tests.py
```

**Features**:
- Runs all test categories in logical order
- Shows progress and timing for each category
- Generates summary report
- Exits with appropriate code for CI/CD
- Optional: Coverage reporting

**Options**:
```bash
python run_tests.py --coverage     # Include coverage report
python run_tests.py --fast         # Skip slow integration tests
python run_tests.py --verbose      # Detailed output
```

### Option 2: Pytest Directly

```bash
cd backend
source venv/bin/activate

# All pytest tests
pytest tests/ -v

# Specific test file
pytest tests/test_base_agent.py -v

# Specific test function
pytest tests/test_base_agent.py::test_agent_initialization -v

# With coverage
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

### Option 3: Individual Integration Tests

```bash
cd backend
source venv/bin/activate

# Two-level feature extraction
python test_detailed_features.py

# Complete API workflow
python test_complete_api.py

# Vector search
python test_search.py

# Password management
python test_password_management.py
```

### Option 4: Shell Script Tests (Legacy)

```bash
cd backend

# Document upload test
./test_document_upload.sh

# API chunk test
./test_chunk2_api.sh

# Dev OTP test
./test_dev_otp.sh
```

**Note**: Shell scripts are legacy but still functional. Prefer pytest or master runner.

---

## Test Files

### Core Unit Tests (`tests/`)

**tests/test_base_agent.py**
- Agent framework initialization
- Context management
- Tool integration
- Error handling

**tests/test_product_analyzer.py**
- Product analysis prompts
- Feature extraction logic
- Schema validation
- Output formatting

**tests/test_ci_models.py**
- Database model creation
- Model relationships
- Cascading deletes
- Data integrity

**tests/test_feature_extraction.py**
- Feature extraction algorithms
- Confidence scoring
- Category assignment
- Deduplication logic

**tests/test_feature_extraction_api.py**
- Feature extraction endpoints
- Session management
- Competitor selection
- Feature retrieval

**tests/test_llm_service_extended.py**
- LLM service initialization
- Prompt formatting
- Response parsing
- Error handling

### Integration Tests (Root Level)

**test_detailed_features.py** (RECOMMENDED)
- **Purpose**: End-to-end test of two-level feature extraction
- **Coverage**:
  - Product creation
  - Product analysis with detailed features
  - Feature storage in database
  - Feature retrieval via API
  - Validation of feature counts and structure
- **Runtime**: ~30 seconds (requires Anthropic API)
- **Usage**:
  ```bash
  python test_detailed_features.py
  ```

**test_complete_api.py**
- **Purpose**: Complete competitive intelligence workflow
- **Coverage**:
  - Product creation and analysis
  - Competitor discovery
  - Feature extraction
  - Session management
  - Differential analysis
- **Runtime**: ~2-3 minutes
- **Usage**:
  ```bash
  python test_complete_api.py
  ```

**test_search.py**
- **Purpose**: Vector search and semantic matching
- **Coverage**:
  - Embedding generation
  - Similarity search
  - Feature matching
  - Performance benchmarks
- **Runtime**: ~10 seconds
- **Usage**:
  ```bash
  python test_search.py
  ```

**test_password_management.py**
- **Purpose**: Password workflows and authentication
- **Coverage**:
  - User creation
  - Password hashing
  - Login/logout
  - Password reset
  - Token management
- **Runtime**: ~5 seconds
- **Usage**:
  ```bash
  python test_password_management.py
  ```

**test_llm_service.py**
- **Purpose**: Basic LLM service functionality
- **Coverage**:
  - Service initialization
  - Simple prompts
  - Response handling
- **Runtime**: ~10 seconds (requires API)
- **Usage**:
  ```bash
  python test_llm_service.py
  ```

**test_schemas.py**
- **Purpose**: Pydantic schema validation
- **Coverage**:
  - Request schemas
  - Response schemas
  - Validation rules
  - Error messages
- **Runtime**: <1 second
- **Usage**:
  ```bash
  python test_schemas.py
  ```

### Shell Script Tests (Legacy)

**test_document_upload.sh**
- Tests file upload endpoints
- PDF and text file processing
- Multi-source document handling

**test_chunk2_api.sh**
- Tests API chunking and pagination
- Large dataset handling

**test_dev_otp.sh**
- Tests development OTP bypass
- Authentication workflows

**Note**: These are functional but not integrated into pytest. Consider migrating to pytest when time allows.

---

## Writing Tests

### Pytest Test Template

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from sqlalchemy.orm import Session

client = TestClient(app)

def test_example_endpoint():
    """Test description."""
    # Arrange
    test_data = {"key": "value"}

    # Act
    response = client.post("/endpoint", json=test_data)

    # Assert
    assert response.status_code == 200
    assert "expected_key" in response.json()
```

### Integration Test Template

```python
import requests

BASE_URL = "http://localhost:8000"

def get_auth_token():
    """Get authentication token."""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin", "password": "password"}
    )
    response.raise_for_status()
    return response.json()["access_token"]

def test_workflow():
    """Test complete workflow."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Create resource
    response = requests.post(
        f"{BASE_URL}/resource",
        headers=headers,
        json={"name": "test"}
    )
    assert response.status_code == 200
    resource_id = response.json()["id"]

    # Step 2: Use resource
    response = requests.get(
        f"{BASE_URL}/resource/{resource_id}",
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "test"

if __name__ == "__main__":
    test_workflow()
    print("✓ All tests passed")
```

### Test Best Practices

**1. Arrange-Act-Assert Pattern**:
```python
def test_feature():
    # Arrange: Set up test data
    data = {"field": "value"}

    # Act: Execute function/endpoint
    result = function_under_test(data)

    # Assert: Verify results
    assert result == expected_value
```

**2. Use Fixtures for Common Setup**:
```python
@pytest.fixture
def auth_headers():
    """Fixture for authenticated headers."""
    token = get_auth_token()
    return {"Authorization": f"Bearer {token}"}

def test_with_auth(auth_headers):
    response = client.get("/protected", headers=auth_headers)
    assert response.status_code == 200
```

**3. Test Error Cases**:
```python
def test_invalid_input():
    response = client.post("/endpoint", json={"invalid": "data"})
    assert response.status_code == 422  # Validation error
    assert "error" in response.json()
```

**4. Mock External Dependencies**:
```python
from unittest.mock import patch

@patch('app.services.llm_service.anthropic.messages.create')
def test_with_mock_llm(mock_create):
    mock_create.return_value = {"content": "mocked response"}
    result = service.analyze()
    assert result == expected_value
```

**5. Clean Up After Tests**:
```python
@pytest.fixture
def clean_database():
    # Setup
    db = get_test_db()
    yield db
    # Teardown
    db.close()
    clean_test_data()
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements.txt

    - name: Run tests
      env:
        ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      run: |
        cd backend
        python run_tests.py --coverage

    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        file: ./backend/coverage.xml
```

### Running Tests in Docker

```dockerfile
FROM python:3.12
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
CMD ["python", "run_tests.py"]
```

```bash
docker build -t voting-tests .
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY voting-tests
```

---

## Test Coverage

### Generate Coverage Report

```bash
cd backend
source venv/bin/activate

# Generate HTML report
pytest tests/ --cov=app --cov-report=html

# Open report
open htmlcov/index.html

# Generate terminal report
pytest tests/ --cov=app --cov-report=term-missing
```

### Coverage Goals

- **Target**: 80% overall coverage
- **Critical paths**: 95%+ (auth, voting, data integrity)
- **New features**: 80%+ before merging

### Viewing Coverage

```bash
# Terminal summary
pytest tests/ --cov=app --cov-report=term

# Detailed HTML report
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# XML for CI
pytest tests/ --cov=app --cov-report=xml
```

---

## Troubleshooting

### Tests Fail with "Connection Refused"

**Cause**: Backend server not running for integration tests

**Solution**:
```bash
# Start server in background
cd backend
source venv/bin/activate
uvicorn app.main:app --reload &
SERVER_PID=$!

# Run tests
python test_detailed_features.py

# Stop server
kill $SERVER_PID
```

**Better**: Use `setup_and_test.sh` which handles this automatically.

### Tests Fail with "Module Not Found"

**Cause**: Virtual environment not activated or dependencies not installed

**Solution**:
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### Tests Fail with "Anthropic API Error"

**Cause**: Invalid or missing API key

**Solution**:
```bash
# Check .env
grep ANTHROPIC_API_KEY backend/.env

# Should output: ANTHROPIC_API_KEY=sk-ant-...

# If missing, add to .env
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> backend/.env
```

### Pytest Not Found

**Cause**: pytest not installed in virtual environment

**Solution**:
```bash
cd backend
source venv/bin/activate
pip install pytest pytest-asyncio pytest-cov
```

---

## Migration from Shell Scripts

To migrate shell script tests to pytest:

1. **Identify test cases** in shell script
2. **Extract API calls** and expected responses
3. **Create pytest file** with equivalent logic
4. **Use TestClient** for synchronous tests
5. **Use pytest-asyncio** for async tests
6. **Add fixtures** for common setup
7. **Remove shell script** after validation

**Example Migration**:

**Before** (`test_example.sh`):
```bash
curl -X POST http://localhost:8000/endpoint \
  -H "Content-Type: application/json" \
  -d '{"key":"value"}'
```

**After** (`tests/test_example.py`):
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_endpoint():
    response = client.post("/endpoint", json={"key": "value"})
    assert response.status_code == 200
```

---

## Additional Resources

**Documentation**:
- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Coverage.py](https://coverage.readthedocs.io/)

**Internal Docs**:
- [SETUP.md](SETUP.md) - Development setup
- [USER_GUIDE.md](../USER_GUIDE.md) - User documentation
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture

---

**End of Testing Guide**

For setup instructions, see [SETUP.md](SETUP.md).
