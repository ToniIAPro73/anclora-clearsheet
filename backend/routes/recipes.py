from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import yaml
import pandas as pd

from models import get_db, Recipe, SourceFile, User
from auth import get_current_user_required
from storage import storage
from engine import NormalizationPlanner
from schema_validator import SchemaCompatibilityService

router = APIRouter(prefix="/recipes", tags=["recipes"])

class SaveRecipeRequest(BaseModel):
    name: str
    description: Optional[str] = None
    recipe_yaml: str
    structure_fingerprint: Optional[str] = None
    source_format: Optional[str] = "xlsx"

class UpdateRecipeAliasesRequest(BaseModel):
    canonical_column: str
    alias: str

class RemoveRecipeAliasRequest(BaseModel):
    canonical_column: str
    alias: str

class ReapplyRecipeRequest(BaseModel):
    recipe_id: str
    file_id: str

@router.post("")
def create_recipe(
    req: SaveRecipeRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    recipe = Recipe(
        user_id=user.id,
        name=req.name,
        description=req.description,
        recipe_version="1.0",
        definition_yaml=req.recipe_yaml,
        structure_fingerprint=req.structure_fingerprint,
        source_format=req.source_format
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe

@router.get("")
def list_recipes(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    recipes = db.query(Recipe).filter(Recipe.user_id == user.id).order_by(Recipe.updated_at.desc()).all()
    return recipes

@router.get("/{recipe_id}")
def get_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada o no autorizada.")
    return recipe

@router.delete("/{recipe_id}")
def delete_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada.")
    db.delete(recipe)
    db.commit()
    return {"message": "Receta eliminada correctamente."}

@router.get("/{recipe_id}/aliases")
def get_recipe_aliases(
    recipe_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Retrieves canonical columns and configured aliases for a recipe.
    """
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada o no autorizada.")

    recipe_dict = yaml.safe_load(recipe.definition_yaml)
    canonical_columns = list(recipe_dict.get("columns", {}).keys())
    aliases_map = recipe_dict.get("column_aliases", {})

    return {
        "recipe_id": recipe.id,
        "recipe_name": recipe.name,
        "canonical_columns": canonical_columns,
        "aliases": aliases_map
    }

@router.post("/{recipe_id}/aliases")
def add_recipe_alias(
    recipe_id: str,
    req: UpdateRecipeAliasesRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Phase 1: Adds a validated column alias to the recipe definition.
    Validations:
    - Non-empty alias
    - Canonical column must exist in recipe
    - Canonical column cannot be its own alias
    - Alias cannot already be assigned to another canonical column (no collisions)
    - Duplicate alias rejected
    """
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada o no autorizada.")

    canonical = req.canonical_column.strip()
    alias = req.alias.strip()

    if not alias:
        raise HTTPException(status_code=400, detail="El nombre del alias no puede estar vacío.")

    recipe_dict = yaml.safe_load(recipe.definition_yaml)
    canonical_cols = recipe_dict.get("columns", {})

    if canonical not in canonical_cols:
        raise HTTPException(
            status_code=400,
            detail=f"La columna canónica '{canonical}' no existe en esta receta. Columnas disponibles: {list(canonical_cols.keys())}"
        )

    if alias.lower() == canonical.lower():
        raise HTTPException(
            status_code=400,
            detail=f"La columna canónica '{canonical}' no puede ser su propio alias."
        )

    column_aliases = recipe_dict.get("column_aliases", {})

    # Check if alias is already assigned anywhere else
    for c_col, a_list in column_aliases.items():
        if alias.lower() in [a.lower() for a in a_list]:
            if c_col == canonical:
                raise HTTPException(status_code=400, detail=f"El alias '{alias}' ya está asignado a '{canonical}'.")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Conflicto de alias: '{alias}' ya está asignado a otra columna canónica ('{c_col}'). No se permiten aliases ambiguos."
                )

    # Append alias safely
    existing = column_aliases.get(canonical, [])
    existing.append(alias)
    column_aliases[canonical] = list(dict.fromkeys(existing)) # Preserve order without duplicates
    recipe_dict["column_aliases"] = column_aliases

    # Increment version explicitly
    old_version = recipe.recipe_version or "1.0"
    try:
        parts = old_version.split(".")
        new_version = f"{parts[0]}.{int(parts[1]) + 1}"
    except Exception:
        new_version = "1.1"

    recipe.recipe_version = new_version
    recipe.definition_yaml = yaml.dump(recipe_dict, sort_keys=False, allow_unicode=True)
    recipe.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(recipe)

    return {
        "message": f"Alias '{alias}' añadido exitosamente a '{canonical}'.",
        "recipe_version": recipe.recipe_version,
        "canonical_column": canonical,
        "aliases": column_aliases
    }

@router.delete("/{recipe_id}/aliases")
def remove_recipe_alias(
    recipe_id: str,
    req: RemoveRecipeAliasRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Phase 1: Removes an alias from the canonical column specification.
    """
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada o no autorizada.")

    canonical = req.canonical_column.strip()
    alias = req.alias.strip()

    recipe_dict = yaml.safe_load(recipe.definition_yaml)
    column_aliases = recipe_dict.get("column_aliases", {})

    if canonical in column_aliases:
        column_aliases[canonical] = [a for a in column_aliases[canonical] if a.lower() != alias.lower()]
        if not column_aliases[canonical]:
            del column_aliases[canonical]
        recipe_dict["column_aliases"] = column_aliases

        recipe.definition_yaml = yaml.dump(recipe_dict, sort_keys=False, allow_unicode=True)
        recipe.updated_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "message": f"Alias '{alias}' eliminado.",
        "aliases": column_aliases
    }

@router.post("/validate-compatibility")
def validate_compatibility(
    req: ReapplyRecipeRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == req.recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada.")

    source_file = db.query(SourceFile).filter(SourceFile.id == req.file_id, SourceFile.user_id == user.id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o no autorizado.")

    recipe_dict = yaml.safe_load(recipe.definition_yaml)

    # Load candidate file headers
    file_path = storage.get_file_path(source_file.storage_path)
    if source_file.file_type.lower() in ["xlsx", "xls"]:
        df = pd.read_excel(file_path, header=None)
    else:
        df = pd.read_csv(file_path, header=None, sep=None, engine="python")
    raw_rows = df.fillna("").values.tolist()

    analysis = NormalizationPlanner.plan(raw_rows)

    # Use unified SchemaCompatibilityService
    drift_eval = SchemaCompatibilityService.evaluate(recipe_dict, analysis)

    compatibility = {
        "status": "compatible" if drift_eval["status"] == "compatible" else ("compatible_with_warnings" if drift_eval["status"] == "warning" else "incompatible"),
        "score": drift_eval["match_ratio"],
        "message_es": "Esquema compatible" if drift_eval["status"] == "compatible" else ("Advertencias de drift detectadas" if drift_eval["status"] == "warning" else "Drift bloqueante: columnas requeridas ausentes"),
        "message_en": "Compatible schema" if drift_eval["status"] == "compatible" else ("Drift warnings detected" if drift_eval["status"] == "warning" else "Blocking drift: missing required columns"),
        "drift_eval": drift_eval
    }

    return {
        "recipe_id": recipe.id,
        "recipe_name": recipe.name,
        "file_id": source_file.id,
        "filename": source_file.original_name,
        "compatibility": compatibility,
        "drift_analysis": drift_eval,
        "proposed_rules": recipe_dict.get("rules", {})
    }
