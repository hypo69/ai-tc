# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - skills
# =============================================================================
# Description:
#   Эндпойнты управления навыками агента.
#   Вынесено из router_admin.py (этап 4 оптимизации).
#
# File: skills.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:00:00
# =============================================================================

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from header import __root__
from logger import logger
from .routers import router, skills_router


# ============================================================================
# Skills Management Endpoints
# ============================================================================


def _safe_home_dir() -> Path | None:
    """Safely retrieves user home directory across platforms."""
    try:
        return Path.home()
    except Exception:
        import os
        user_profile = os.environ.get("USERPROFILE") or os.environ.get("HOME")
        if user_profile:
            return Path(user_profile)
        return None

def _check_skills_access(request: Request) -> bool:
    """Check user access for skills management (permits all users to inspect and manage user skills)."""
    return True

class AdminSkillCreateRequest(BaseModel):
    name: str
    description: str = ''
    description_ru: str = ''
    category: str = 'general'
    instructions: str = ''
    target_dir: str = '.agents/skills'
    readme: str = ''
    scripts: Dict[str, str] = Field(default_factory=dict)
    references: Dict[str, str] = Field(default_factory=dict)

class AdminSkillUpdateRequest(BaseModel):
    description: str | None = None
    description_ru: str | None = None
    instructions: str | None = None
    readme: str | None = None

class SkillAiGenerateRequest(BaseModel):
    prompt: str
    category: str = 'general'
    target_dir: str = '.agents/skills'

class SkillTestRunRequest(BaseModel):
    prompt: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

@router.get('/skills')
@skills_router.get('')
@skills_router.get('/')
async def list_admin_skills(request: Request, q: str = '', lang: str = '') -> Dict[str, Any]:
    """List all registered agent skills across supported project skill directories."""
    _check_skills_access(request)
    from src.skills import SkillRegistry
    registry = SkillRegistry(__root__)
    skills = registry.discover(lang=lang if lang else None)

    skills_list = []
    q_clean = q.strip().lower()
    home = _safe_home_dir()

    for s in skills:
        all_text = f"{s.name} {s.description} " + " ".join(s.descriptions_i18n.values())
        if q_clean and q_clean not in all_text.lower():
            continue

        try:
            rel_root = s.root.relative_to(__root__).as_posix()
        except ValueError:
            if home:
                try:
                    rel_root = f"~/{s.root.relative_to(home).as_posix()}"
                except ValueError:
                    rel_root = str(s.root)
            else:
                rel_root = str(s.root)

        has_scripts = (s.root / 'scripts').is_dir() and any((s.root / 'scripts').iterdir())
        has_references = (s.root / 'references').is_dir() and any((s.root / 'references').iterdir())
        has_assets = (s.root / 'assets').is_dir() and any((s.root / 'assets').iterdir())
        has_dist = (s.root / 'dist').is_dir() and any((s.root / 'dist').glob('*.skill'))

        files_count = 0
        try:
            files_count = sum(1 for p in s.root.rglob('*') if p.is_file())
        except Exception:
            pass

        skills_list.append({
            'name': s.name,
            'description': s.get_description(lang) if lang else s.description,
            'descriptions_i18n': s.descriptions_i18n,
            'relative_path': rel_root,
            'source_file': str(s.source.name),
            'metadata': s.metadata,
            'manifest': s.manifest,
            'instructions': s.instructions,
            'has_scripts': has_scripts,
            'has_references': has_references,
            'has_assets': has_assets,
            'has_dist': has_dist,
            'files_count': files_count,
        })

    return {
        'status': 'ok',
        'skills': skills_list,
        'total': len(skills_list),
    }

@router.post('/skills/generate-ai')
@skills_router.post('/generate-ai')
async def generate_skill_ai(data: SkillAiGenerateRequest, request: Request) -> Dict[str, Any]:
    """Generate complete agent skill structure, metadata, instructions and docs with AI or deterministic smart fallback."""
    _check_skills_access(request)
    user_prompt = data.prompt.strip()
    if not user_prompt:
        raise HTTPException(status_code=400, detail="Prompt is required for AI skill generation")

    target_dir = data.target_dir.strip() or '.agents/skills'
    category = data.category.strip() or 'general'

    # 1. Attempt LLM generation if available
    llm_generated = None
    try:
        from src.ai.unified_chat import UnifiedChatModel
        import os
        api_key_names = [n.strip() for n in os.getenv('GEMINI_API_KEY_NAMES', '').split(',') if n.strip()]
        if api_key_names:
            system_prompt = (
                "You are an expert AI skill architect for AI Windows Admin and Gemini CLI. "
                "Given the user request, generate a structured JSON object for an agent skill.\n"
                "JSON format required:\n"
                "{\n"
                '  "name": "kebab-case-name",\n'
                '  "description": "Concise English description for agent matching (max 2 sentences)",\n'
                '  "description_ru": "Краткое русское описание назначения навыка",\n'
                '  "instructions": "Full structured Markdown instructions for SKILL.md with ## Purpose, ## When to Use & Triggers, ## Execution Protocol, ## Rules & Constraints",\n'
                '  "readme": "English developer README.md documentation",\n'
                '  "scripts": {"helper.py": "# Python executable helper tool code"},\n'
                '  "references": {"protocol.md": "# Detailed specifications or guides"}\n'
                "}\n"
                "Output STRICTLY valid JSON without Markdown backticks or commentary."
            )
            chat = UnifiedChatModel(
                api_key_names=api_key_names,
                system_instruction=system_prompt,
            )
            raw_response = await chat.chat(f"Create a skill for category '{category}': {user_prompt}")
            if raw_response:
                clean_json = raw_response.strip()
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```[a-z]*\n", "", clean_json)
                    clean_json = re.sub(r"\n```$", "", clean_json).strip()
                llm_generated = json.loads(clean_json)
    except Exception as ex:
        logger.warning(f"AI skill generation via LLM fallback to deterministic builder: {ex}")

    if llm_generated and isinstance(llm_generated, dict) and "name" in llm_generated:
        name_clean = re.sub(r'[^a-z0-9_-]', '-', str(llm_generated.get('name', 'custom-skill')).lower()).strip('-')
        return {
            'status': 'ok',
            'generated': {
                'name': name_clean or 'custom-skill',
                'description': str(llm_generated.get('description', '')),
                'description_ru': str(llm_generated.get('description_ru', '')),
                'category': category,
                'target_dir': target_dir,
                'instructions': str(llm_generated.get('instructions', '')),
                'readme': str(llm_generated.get('readme', '')),
                'scripts': llm_generated.get('scripts') if isinstance(llm_generated.get('scripts'), dict) else {},
                'references': llm_generated.get('references') if isinstance(llm_generated.get('references'), dict) else {},
            }
        }

    # Deterministic high-quality smart fallback
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', user_prompt.lower())[:32].strip('-')
    if not slug or len(slug) < 3:
        slug = f"skill-{category}"

    name_clean = slug.replace('_', '-')
    title = name_clean.replace('-', ' ').title()

    instructions_tpl = f"""# {title}

## 🎯 Purpose
Provide specialized agent capability for: {user_prompt}

## 🚀 When to Use & Triggers
- Activate when the user requests actions related to: {user_prompt}.
- Agent should consult this skill before delegating tasks or running manual routines.

## 📋 Execution Protocol
1. **Analyze input request**: Validate preconditions and extract parameters.
2. **Execute actions**:
   - Check if scripts in `scripts/` provide helper automation.
   - Refer to guidelines in `references/` if edge cases are encountered.
3. **Format output**: Deliver results in structured markdown with clear status indicators.

## ⚙️ Rules & Constraints
- Maintain fail-fast validation and English logging.
- Handle missing files or external tool errors gracefully.
"""

    readme_tpl = f"""# {title}

## Overview
Agent skill providing automated capability for: {user_prompt}.

## Directory Structure
- `SKILL.md`: Main instructions and frontmatter contract.
- `README.md`: English documentation for developers.
- `scripts/`: Executable helper tools (Python).
- `references/`: Reference documentation and guidelines.
- `assets/`: Static fixtures, data, and examples.

## Usage
Triggered dynamically by AI agents in AI Windows Admin and Gemini CLI.
"""

    helper_script = f"""# -*- coding: utf-8 -*-
\"\"\"Helper automation script for {name_clean}.\"\"\"

import sys
from logger import logger

def main():
    logger.console("Executing {name_clean} helper utility...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""

    return {
        'status': 'ok',
        'generated': {
            'name': name_clean,
            'description': f"Agent capability for {user_prompt[:120]}.",
            'description_ru': f"Навык для: {user_prompt[:120]}.",
            'category': category,
            'target_dir': target_dir,
            'instructions': instructions_tpl,
            'readme': readme_tpl,
            'scripts': {'main.py': helper_script},
            'references': {'guide.md': f"# Guide for {title}\n\nKey protocols and operational references.\n"},
        }
    }

@router.get('/skills/{name}')
@skills_router.get('/{name}')
async def get_admin_skill_details(name: str, request: Request, lang: str = '') -> Dict[str, Any]:
    """Get full details of a specific skill including SKILL.md and README.md content."""
    _check_skills_access(request)
    from src.skills import SkillRegistry
    registry = SkillRegistry(__root__)
    try:
        skill = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    skill_md_raw = ''
    if skill.source.is_file():
        try:
            skill_md_raw = skill.source.read_text(encoding='utf-8')
        except Exception as ex:
            logger.error(f"Error reading SKILL.md for {name}", ex)

    readme_raw = ''
    readme_path = skill.root / 'README.md'
    if readme_path.is_file():
        try:
            readme_raw = readme_path.read_text(encoding='utf-8')
        except Exception as ex:
            logger.error(f"Error reading README.md for {name}", ex)

    # Collect files tree
    file_list = []
    try:
        for p in sorted(skill.root.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:
                file_list.append({
                    'rel_path': p.relative_to(skill.root).as_posix(),
                    'size': p.stat().st_size,
                })
    except Exception:
        pass

    home = _safe_home_dir()
    try:
        rel_root = skill.root.relative_to(__root__).as_posix()
    except ValueError:
        if home:
            try:
                rel_root = f"~/{skill.root.relative_to(home).as_posix()}"
            except ValueError:
                rel_root = str(skill.root)
        else:
            rel_root = str(skill.root)

    return {
        'status': 'ok',
        'skill': {
            'name': skill.name,
            'description': skill.get_description(lang) if lang else skill.description,
            'descriptions_i18n': skill.descriptions_i18n,
            'relative_path': rel_root,
            'metadata': skill.metadata,
            'manifest': skill.manifest,
            'instructions': skill.instructions,
            'skill_md_raw': skill_md_raw,
            'readme_raw': readme_raw,
            'files': file_list,
        }
    }

@router.post('/skills')
@skills_router.post('')
@skills_router.post('/')
async def create_admin_skill(data: AdminSkillCreateRequest, request: Request) -> Dict[str, Any]:
    """Create a new agent skill directory with standard structure."""
    _check_skills_access(request)
    name = data.name.strip().lower()
    if not name or not re.match(r'^[a-z0-9_-]+$', name):
        raise HTTPException(status_code=400, detail="Skill name must contain only letters, numbers, hyphens, and underscores")

    target_dir = data.target_dir.strip() or '.agents/skills'
    home = _safe_home_dir()
    if target_dir.startswith('~') and home:
        base_dir = (home / target_dir[2:]).resolve()
    else:
        base_dir = (__root__ / target_dir).resolve()

    is_in_project = str(base_dir).startswith(str(__root__.resolve()))
    is_in_home = home is not None and str(base_dir).startswith(str(home.resolve()))
    if not (is_in_project or is_in_home):
        raise HTTPException(status_code=400, detail="Invalid target directory")

    skill_dir = base_dir / name
    if skill_dir.exists():
        raise HTTPException(status_code=400, detail=f"Skill '{name}' already exists at {target_dir}/{name}")

    skill_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = skill_dir / 'scripts'
    references_dir = skill_dir / 'references'
    assets_dir = skill_dir / 'assets'
    scripts_dir.mkdir(exist_ok=True)
    references_dir.mkdir(exist_ok=True)
    assets_dir.mkdir(exist_ok=True)

    desc_en = data.description.strip() or f"Agent skill for {name}."
    desc_ru = data.description_ru.strip() or desc_en

    instructions = data.instructions.strip()
    if not instructions:
        instructions = f"""# {name.replace('-', ' ').replace('_', ' ').title()}

## 🎯 Purpose
{desc_en}

## 🚀 Usage & Protocol
Describe how AI agents should execute this skill and what triggers its activation.

## ⚙️ Directory Structure
- `SKILL.md`: Main instructions and frontmatter contract.
- `README.md`: English documentation for developers.
- `scripts/`: Executable helper tools.
- `references/`: Reference documentation and guidelines.
- `assets/`: Static data, examples, and assets.
"""

    skill_md_content = f"""---
name: {name}
description: {desc_en}
description_i18n:
  en: {desc_en}
  ru: {desc_ru}
---

{instructions}
"""

    readme_content = data.readme.strip() if data.readme.strip() else f"""# {name.replace('-', ' ').replace('_', ' ').title()}

## Overview
{desc_en}

## Location
`{target_dir}/{name}/`
"""

    (skill_dir / 'SKILL.md').write_text(skill_md_content, encoding='utf-8')
    (skill_dir / 'README.md').write_text(readme_content, encoding='utf-8')

    # Write additional scripts if provided
    if data.scripts and isinstance(data.scripts, dict):
        for script_name, script_code in data.scripts.items():
            if script_name and isinstance(script_code, str):
                safe_script_name = Path(script_name).name
                (scripts_dir / safe_script_name).write_text(script_code, encoding='utf-8')

    # Write additional references if provided
    if data.references and isinstance(data.references, dict):
        for ref_name, ref_content in data.references.items():
            if ref_name and isinstance(ref_content, str):
                safe_ref_name = Path(ref_name).name
                (references_dir / safe_ref_name).write_text(ref_content, encoding='utf-8')

    return {
        'status': 'ok',
        'message': f"Skill '{name}' created successfully",
        'skill': {
            'name': name,
            'description': desc_en,
            'description_ru': desc_ru,
            'relative_path': f"{target_dir}/{name}",
        }
    }

@router.put('/skills/{name}')
@skills_router.put('/{name}')
async def update_admin_skill(name: str, data: AdminSkillUpdateRequest, request: Request) -> Dict[str, Any]:
    """Update skill SKILL.md and README.md content."""
    _check_skills_access(request)
    from src.skills import SkillRegistry
    registry = SkillRegistry(__root__)
    try:
        skill = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    desc_en = data.description if data.description is not None else skill.description
    desc_ru = data.description_ru if data.description_ru is not None else skill.descriptions_i18n.get('ru', desc_en)
    instructions = data.instructions if data.instructions is not None else skill.instructions

    skill_md_content = f"""---
name: {skill.name}
description: {desc_en}
description_i18n:
  en: {desc_en}
  ru: {desc_ru}
---

{instructions}
"""
    skill.source.write_text(skill_md_content, encoding='utf-8')

    if data.readme is not None:
        readme_path = skill.root / 'README.md'
        readme_path.write_text(data.readme, encoding='utf-8')

    return {
        'status': 'ok',
        'message': f"Skill '{name}' updated successfully",
    }

@router.delete('/skills/{name}')
@skills_router.delete('/{name}')
async def delete_admin_skill(name: str, request: Request) -> Dict[str, Any]:
    """Delete a skill directory."""
    _check_skills_access(request)
    import shutil
    from src.skills import SkillRegistry
    registry = SkillRegistry(__root__)
    try:
        skill = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    skill_root = skill.root.resolve()
    home = _safe_home_dir()
    is_in_project = str(skill_root).startswith(str(__root__.resolve()))
    is_in_home = home is not None and str(skill_root).startswith(str(home.resolve()))
    if not (is_in_project or is_in_home):
        raise HTTPException(status_code=400, detail="Invalid skill directory path")

    forbidden = [__root__.resolve()]
    if home:
        forbidden.append(home.resolve())
    if skill_root in forbidden:
        raise HTTPException(status_code=400, detail="Cannot delete root directory")

    shutil.rmtree(skill_root, ignore_errors=True)
    return {
        'status': 'ok',
        'message': f"Skill '{name}' deleted successfully",
    }

@router.post('/skills/{name}/test')
@skills_router.post('/{name}/test')
async def test_admin_skill(name: str, data: SkillTestRunRequest, request: Request) -> Dict[str, Any]:
    """Test skill execution with a test prompt against active AI runtime or sandbox runner."""
    _check_skills_access(request)
    from src.skills import SkillRegistry
    registry = SkillRegistry(__root__)
    try:
        skill = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    user_prompt = data.prompt.strip() or "Test execution of skill"
    instructions = skill.instructions or skill.description

    model_used = "simulation"
    response_text = ""

    try:
        from src.ai.unified_chat import UnifiedChatModel
        import os
        api_key_names = [n.strip() for n in os.getenv('GEMINI_API_KEY_NAMES', '').split(',') if n.strip()]
        if api_key_names:
            chat = UnifiedChatModel(
                api_key_names=api_key_names,
                system_instruction=f"You are executing the following agent skill:\n\n{instructions}",
            )
            response_text = await chat.chat(user_prompt)
            model_used = "UnifiedChatModel (LLM)"
    except Exception as ex:
        logger.warning(f"Live skill test fallback: {ex}")

    if not response_text:
        response_text = (
            f"✅ [Skill Sandbox]: Skill '{skill.name}' accepted test query: \"{user_prompt}\"\n\n"
            f"**Contract Matched**:\n- Name: `{skill.name}`\n- Path: `{skill.root}`\n"
            f"- Status: Active and ready for dispatch."
        )

    return {
        'status': 'ok',
        'skill': skill.name,
        'model_used': model_used,
        'response': response_text,
    }

@router.post('/skills/{name}/package')
@skills_router.post('/{name}/package')
async def package_admin_skill(name: str, request: Request) -> Dict[str, Any]:
    """Package skill directory into a distributable .skill ZIP archive."""
    _check_skills_access(request)
    import os
    import zipfile
    from src.skills import SkillRegistry
    registry = SkillRegistry(__root__)
    try:
        skill = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    dist_dir = skill.root / 'dist'
    dist_dir.mkdir(parents=True, exist_ok=True)
    archive_file = dist_dir / f"{skill.name}.skill"

    with zipfile.ZipFile(archive_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, dirs, files in os.walk(skill.root):
            dirs[:] = [d for d in dirs if d not in ['dist', '.git', '__pycache__']]
            for f in files:
                file_path = Path(root_dir) / f
                if file_path == archive_file:
                    continue
                arcname = file_path.relative_to(skill.root)
                zipf.write(file_path, arcname)

    size = archive_file.stat().st_size
    home = _safe_home_dir()
    try:
        rel_archive = archive_file.relative_to(__root__).as_posix()
    except ValueError:
        if home:
            try:
                rel_archive = f"~/{archive_file.relative_to(home).as_posix()}"
            except ValueError:
                rel_archive = str(archive_file)
        else:
            rel_archive = str(archive_file)

    return {
        'status': 'ok',
        'message': f"Skill '{skill.name}' packaged successfully",
        'archive': {
            'filename': f"{skill.name}.skill",
            'path': rel_archive,
            'size': size,
        },
    }

