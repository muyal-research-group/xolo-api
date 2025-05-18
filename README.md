<div align = center>
<img src='assets/logo.png' width=200/>
</div>
<div align=center>
<a href="https://test.pypi.org/project/mictlanx/"><img src="https://img.shields.io/badge/version-0.0.9--alpha.7-green" alt="build - 0.0.9-alpha.7"></a>
</div>
<div align=center>
	<h1>Xolo Server: <span style="font-weight:normal;"> An extensible framework for security</span></h1>
</div>


**Xolo** is a lightweight and extensible identity and access management system that includes:

- Attribute-Based Access Control (ABAC)
- License management and scoped user assignment
- Role-based permissions (ACL)
- Secure, token-based authentication using JWT

This document describes the **server-side** component of Xolo, including setup, architecture, and usage.

---

## 📦 Project Structure

```
.
├── xoloapi/                  # Main API package
│   ├── controllers/          # FastAPI routers (users, scopes, licenses, policies)
│   ├── services/             # Business logic for each domain
│   ├── repositories/         # DB access layer
│   ├── models/               # Internal domain models (e.g., User, License)
│   ├── dto/                  # Data Transfer Objects (I/O contracts)
│   ├── db/                   # MongoDB connection utilities
│   ├── errors/               # Structured error types
│   └── server.py             # FastAPI server initialization
├── xolo.yml                  # Docker Compose config (MongoDB)
├── run_local.sh             # Local startup script
├── pyproject.toml           # Poetry configuration
└── ...
```

---

## ⚙️ Prerequisites

- Python >= 3.10
- [Poetry](https://python-poetry.org/docs/#installation)
- Poetry Shell Plugin: [poetry-plugin-shell](https://github.com/python-poetry/poetry-plugin-shell)

```bash
pip install poetry
poetry self add poetry-plugin-shell
```

---

## 🚀 Getting Started

### 🛠 Install Dependencies

```bash
poetry install
poetry shell
```

### 🧱 Launch MongoDB Locally

You can use Docker Compose:
```bash
docker volume create xolo-db
docker compose -f xolo.yml up -d xolo-db
```

Or run the helper script:
```bash
bash run_local.sh
```

---

## 🧩 Architecture: CSRM Pattern

Xolo follows a clean **CSRM architecture**:

- **Controller**: FastAPI route handlers (`controllers/`)
- **Service**: Business logic and security validations (`services/`)
- **Repository**: Low-level MongoDB access (`repositories/`)
- **Model/DTO**: Typed schemas for internal logic and I/O (`models/`, `dto/`)

---

## 🔐 Authentication and Authorization

Xolo uses a layered security model:

- **JWT authentication** for stateless access
- **License validation** with expiration handling
- **Scoped access**: users must be assigned to a scope to access it
- **ACL enforcement**: resource-level permissions via roles

---

## 🔑 API Endpoints (Overview)

- `POST /api/v4/users`: Create user
- `POST /api/v4/users/auth`: Authenticate and get access token
- `POST /api/v4/scopes`: Create scope
- `POST /api/v4/scopes/assign`: Assign user to scope
- `POST /api/v4/licenses/`: Assign license
- `DELETE /api/v4/licenses/`: Remove license
- `POST /api/v4/policies`: Add ABAC policies
- `POST /api/v4/policies/prepare`: Detect communities in event graph
- `POST /api/v4/policies/evaluate`: Evaluate access request

---

## 🧪 Running Tests

```bash
poetry run pytest
```

---

## 📦 Publishing

1. Build the distribution:
```bash
poetry build
```
2. Install manually:
```bash
pip install dist/xoloapi-<version>.tar.gz
```
3. Or publish:
```bash
poetry publish --build -r test
```

---

## 🧱 Adding a New Module (CRUD via CSRM)

To integrate a new domain (e.g., `project`):

1. **Model (`models/project.py`)**
```python
from pydantic import BaseModel
class Project(BaseModel):
    id: str
    name: str
    description: str
```

2. **DTO (`dto/project.py`)**
```python
class CreateProjectDTO(BaseModel):
    name: str
    description: str
```

3. **Repository (`repositories/project.py`)**
```python
class ProjectRepository:
    def __init__(self, collection):
        self.collection = collection
    async def create(self, dto):
        return await self.collection.insert_one(dto.dict())
```

4. **Service (`services/project.py`)**
```python
class ProjectService:
    def __init__(self, repository):
        self.repository = repository
    async def create(self, dto):
        return await self.repository.create(dto)
```

5. **Controller (`controllers/project.py`)**
```python
from fastapi import APIRouter, Depends
from xoloapi.dto.project import CreateProjectDTO
from xoloapi.services.project import ProjectService

router = APIRouter()

def get_service():
    return ProjectService(...)

@router.post("/projects")
async def create_project(dto: CreateProjectDTO, service: ProjectService = Depends(get_service)):
    return await service.create(dto)
```

6. Register router in `server.py`:
```python
from xoloapi.controllers.project import router as project_router
app.include_router(project_router)
```

---

## 🤝 Contributing

Feel free to fork the repo, open issues, or suggest features via pull requests.
All contributions are welcome.

---

## 📄 License

This project is licensed under the terms of the [MIT License](LICENSE)

---

## 👤 Author

**Ignacio Castillo**  
[Email](mailto:ignacio.bcastillo@gmail.com)
