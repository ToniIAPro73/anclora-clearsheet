#!/usr/bin/env python3
"""
Operator CLI for Anclora CleanSheet closed whitelist management.
Commands: add, list, revoke, rotate.
Reuses backend models and security functions.
"""
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from models import SessionLocal, User, AuthWhitelist
from auth import (
    hash_token,
    generate_raw_token,
    record_audit_event,
    AUTH_WHITELIST_TOKEN_TTL_HOURS
)

def cmd_add(args):
    email = args.email.strip().lower()
    if not email or "@" not in email:
        print("ERROR: Correo electrónico inválido.", file=sys.stderr)
        sys.exit(1)

    admin_email = (args.admin_email or "operator_cli").strip().lower()

    db = SessionLocal()
    try:
        existing = db.query(AuthWhitelist).filter(AuthWhitelist.email == email).first()
        if existing and existing.status == "active":
            print(f"ERROR: El correo '{email}' ya cuenta con acceso activo en la whitelist.", file=sys.stderr)
            sys.exit(1)

        raw_token = generate_raw_token()
        t_hash = hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=AUTH_WHITELIST_TOKEN_TTL_HOURS)

        if existing:
            existing.status = "pending"
            existing.token_hash = t_hash
            existing.expires_at = expires_at
            existing.revoked_at = None
            existing.updated_at = now
            entry = existing
        else:
            entry = AuthWhitelist(
                email=email,
                status="pending",
                token_hash=t_hash,
                expires_at=expires_at,
                created_by=admin_email,
                created_at=now,
                updated_at=now
            )
            db.add(entry)

        record_audit_event(
            db, "whitelist_added_cli",
            email=email,
            metadata={"operator": admin_email, "expires_at": expires_at.isoformat()}
        )
        db.commit()
        db.refresh(entry)

        print("-----------------------------------------------------------------")
        print("INVITACIÓN CREADA CORRECTAMENTE (OPERATOR CLI)")
        print("-----------------------------------------------------------------")
        print(f"ID:          {entry.id}")
        print(f"Email:       {entry.email}")
        print(f"Status:      {entry.status}")
        print(f"Expira:      {entry.expires_at.isoformat()}")
        print(f"Token:       {raw_token}")
        print(f"URL:         /activate?token={raw_token}")
        print("-----------------------------------------------------------------")
        print("NOTA: El token se muestra una sola vez. En base de datos sólo")
        print("se almacena su hash SHA-256 no invertible.")
        print("-----------------------------------------------------------------")
    finally:
        db.close()

def cmd_list(args):
    db = SessionLocal()
    try:
        entries = db.query(AuthWhitelist).order_by(AuthWhitelist.created_at.desc()).all()
        if not entries:
            print("No hay entradas en la whitelist.")
            return

        print(f"{'ID':<38} {'EMAIL':<32} {'STATUS':<10} {'EXPIRES_AT':<26} {'USER_ID':<38}")
        print("-" * 150)
        for e in entries:
            exp = e.expires_at.isoformat() if e.expires_at else "-"
            uid = e.user_id or "-"
            print(f"{e.id:<38} {e.email:<32} {e.status:<10} {exp:<26} {uid:<38}")
    finally:
        db.close()

def cmd_revoke(args):
    target = args.target.strip()
    db = SessionLocal()
    try:
        entry = db.query(AuthWhitelist).filter(
            (AuthWhitelist.id == target) | (AuthWhitelist.email == target.lower())
        ).first()

        if not entry:
            print(f"ERROR: Entrada '{target}' no encontrada en la whitelist.", file=sys.stderr)
            sys.exit(1)

        now = datetime.now(timezone.utc)
        entry.status = "revoked"
        entry.token_hash = None
        entry.revoked_at = now
        entry.updated_at = now

        if entry.user_id:
            user = db.query(User).filter(User.id == entry.user_id).first()
            if user:
                user.status = "disabled"

        admin_email = (args.admin_email or "operator_cli").strip().lower()
        record_audit_event(
            db, "whitelist_revoked_cli",
            email=entry.email,
            metadata={"operator": admin_email, "linked_user_id": entry.user_id}
        )
        db.commit()

        print(f"Acceso revocado correctamente para '{entry.email}' (ID: {entry.id}).")
        if entry.user_id:
            print(f"Cuenta de usuario '{entry.user_id}' deshabilitada.")
    finally:
        db.close()

def cmd_rotate(args):
    target = args.target.strip()
    db = SessionLocal()
    try:
        entry = db.query(AuthWhitelist).filter(
            (AuthWhitelist.id == target) | (AuthWhitelist.email == target.lower())
        ).first()

        if not entry:
            print(f"ERROR: Entrada '{target}' no encontrada en la whitelist.", file=sys.stderr)
            sys.exit(1)

        raw_token = generate_raw_token()
        t_hash = hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=AUTH_WHITELIST_TOKEN_TTL_HOURS)

        entry.token_hash = t_hash
        entry.expires_at = expires_at
        entry.status = "pending"
        entry.updated_at = now

        admin_email = (args.admin_email or "operator_cli").strip().lower()
        record_audit_event(
            db, "whitelist_token_rotated_cli",
            email=entry.email,
            metadata={"operator": admin_email}
        )
        db.commit()
        db.refresh(entry)

        print("-----------------------------------------------------------------")
        print("TOKEN ROTADO CORRECTAMENTE (OPERATOR CLI)")
        print("-----------------------------------------------------------------")
        print(f"ID:          {entry.id}")
        print(f"Email:       {entry.email}")
        print(f"Status:      {entry.status}")
        print(f"Expira:      {entry.expires_at.isoformat()}")
        print(f"Nuevo Token: {raw_token}")
        print(f"URL:         /activate?token={raw_token}")
        print("-----------------------------------------------------------------")
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="CleanSheet Operator Whitelist CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    parser_add = subparsers.add_parser("add", help="Añadir correo a la whitelist")
    parser_add.add_argument("--email", required=True, help="Email a invitar")
    parser_add.add_argument("--admin-email", default="operator_cli", help="Email del administrador")
    parser_add.set_defaults(func=cmd_add)

    # list
    parser_list = subparsers.add_parser("list", help="Listar entradas de la whitelist")
    parser_list.set_defaults(func=cmd_list)

    # revoke
    parser_revoke = subparsers.add_parser("revoke", help="Revocar acceso de la whitelist")
    parser_revoke.add_argument("--target", required=True, help="ID o email a revocar")
    parser_revoke.add_argument("--admin-email", default="operator_cli", help="Email del administrador")
    parser_revoke.set_defaults(func=cmd_revoke)

    # rotate
    parser_rotate = subparsers.add_parser("rotate", help="Rotar token de activación")
    parser_rotate.add_argument("--target", required=True, help="ID o email de la entrada")
    parser_rotate.add_argument("--admin-email", default="operator_cli", help="Email del administrador")
    parser_rotate.set_defaults(func=cmd_rotate)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
