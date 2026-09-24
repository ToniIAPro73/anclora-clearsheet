import io
import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models import get_db, SourceFile, User
from auth import get_current_user_required
from storage import storage

router = APIRouter(tags=["samples"])

@router.get("/samples/{sample_type}")
def get_sample_data(
    sample_type: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Generates realistic messy ERP/CRM/Bank datasets for immediate one-click testing in UI.
    """
    if sample_type == "erp":
        # Realistic Messy ERP export: title banner, european decimal with dot thousands and comma decimal, mixed dates
        rows = [
            ["INFORME DE VENTAS MENSUAL ERP - SAGE / SAP", "", "", "", ""],
            ["Generado el:", "01/02/2026", "Departamento:", "Finanzas", ""],
            ["", "", "", "", ""],
            ["Fecha Factura", "ID Cliente", "Cliente", "Importe Neto", "IVA 21%"],
            ["01/05/2026", "CLI-9012", "Acme Iberica SL", "1.250,50", "262,60"],
            ["02/05/2026", "CLI-4431", "Logistica Global", "3.400,00", "714,00"],
            ["2026-05-03", "CLI-8821", "Tecnologias Sur", "850,75", "178,65"],
            ["15/05/2026", "CLI-1120", "Construcciones Alfa", "12.800,20", "2.688,04"],
            ["", "", "", "", ""],
            ["18.05.2026", "CLI-9012", "Acme Iberica SL", "540,00", "113,40"],
            ["22/05/2026", "CLI-7732", "Distribuidora Norte", "2.100,90", "441,18"]
        ]
        filename = "02_erp_ventas_messy.xlsx"
    elif sample_type == "bank":
        # Bank statement with title rows and European decimals
        rows = [
            ["BANCO SANTANDER - EXTRACTO DE CUENTA", "", "", ""],
            ["IBAN: ES91 2100 0418 4502 0005 1332", "Divisa: EUR", "", ""],
            ["", "", "", ""],
            ["Fecha", "Concepto", "Importe", "Saldo"],
            ["01/02/2026", "NOMINA EMPRESA", "2.450,00", "5.120,50"],
            ["03/02/2026", "RECIBO LUZ ENDESA", "-124,50", "4.996,00"],
            ["05/02/2026", "TRANSFERENCIA RECIBIDA", "800,00", "5.796,00"],
            ["08/02/2026", "SUPERMERCADO MERCADONA", "-78,35", "5.717,65"],
            ["12/02/2026", "CUOTA HIPOTECA", "-650,00", "5.067,65"]
        ]
        filename = "03_bank_extract_messy.xlsx"
    else:
        # CRM leads with empty columns and unstandardized dates
        rows = [
            ["CRM EXPORT LEADS Q1", "", "", "", ""],
            ["Nombre", "Email", "Vacio", "Fecha Registro", "Valor Estimado"],
            ["Carlos Perez", "carlos@acme.com", "", "01/04/2026", "5.000,00"],
            ["Maria Gomez", "maria@tech.es", "", "2026-04-02", "12.500,00"],
            ["Juan Lopez", "juan@corp.com", "", "03.04.2026", "3.200,50"],
            ["", "", "", "", ""],
            ["Elena Ruiz", "elena@global.com", "", "05/04/2026", "8.900,00"]
        ]
        filename = "04_crm_leads_messy.xlsx"

    # Save to temp file and return as uploaded file
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False, header=False)
    buf.seek(0)

    storage_key = storage.save_file(buf, "xlsx")
    source_file = SourceFile(
        user_id=user.id,
        original_name=filename,
        file_type="xlsx",
        file_size=buf.getbuffer().nbytes,
        storage_path=storage_key,
        metadata_json={"sheets": ["Sheet1"]}
    )
    db.add(source_file)
    db.commit()
    db.refresh(source_file)

    return {
        "file_id": source_file.id,
        "filename": filename,
        "file_type": "xlsx",
        "sheets": ["Sheet1"],
        "default_sheet": "Sheet1"
    }
