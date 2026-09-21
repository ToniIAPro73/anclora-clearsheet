import csv
import io
import re
from typing import Dict, Any, List, Optional, Tuple

SUPPORTED_DELIMITERS = [",", ";", "\t", "|"]
BOM_MAP = {
    b"\xef\xbb\xbf": "utf-8-sig",
    b"\xff\xfe": "utf-16-le",
    b"\xfe\xff": "utf-16-be",
}

class CsvDialectDetector:
    """
    Robust CSV dialect and encoding detector:
    - Detects BOM (UTF-8-SIG, UTF-16)
    - Detects Delimiter (comma, semicolon, tab, pipe)
    - Detects Quoting style and quote character
    - Computes structural consistency score across lines
    - Emits confidence score (Alta, Media, Baja) and ambiguity warnings
    - Never picks a silent ambiguous choice without warning
    """

    @classmethod
    def detect_encoding(cls, sample_bytes: bytes) -> Tuple[str, float]:
        for bom, enc in BOM_MAP.items():
            if sample_bytes.startswith(bom):
                return enc, 1.0

        # Try UTF-8 decoding
        try:
            sample_bytes.decode("utf-8")
            return "utf-8", 0.95
        except UnicodeDecodeError:
            pass

        # Try ISO-8859-1 / Latin-1
        try:
            sample_bytes.decode("iso-8859-1")
            return "iso-8859-1", 0.80
        except UnicodeDecodeError:
            return "utf-8", 0.50

    @classmethod
    def analyze(
        cls,
        sample_bytes: bytes,
        manual_override_delimiter: Optional[str] = None,
        manual_override_encoding: Optional[str] = None
    ) -> Dict[str, Any]:
        detected_enc, enc_conf = cls.detect_encoding(sample_bytes[:4096])
        final_enc = manual_override_encoding or detected_enc

        try:
            text = sample_bytes.decode(final_enc, errors="replace")
        except Exception:
            text = sample_bytes.decode("utf-8", errors="replace")

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return {
                "delimiter": manual_override_delimiter or ",",
                "encoding": final_enc,
                "quote_char": '"',
                "confidence": 0.5,
                "confidence_level": "Baja",
                "is_ambiguous": True,
                "ambiguity_warning": "Archivo vacío o sin líneas legibles.",
                "consistency_score": 0.0,
                "sample_line_count": 0
            }

        # If user specified manual delimiter override
        if manual_override_delimiter:
            return {
                "delimiter": manual_override_delimiter,
                "encoding": final_enc,
                "quote_char": '"',
                "confidence": 1.0,
                "confidence_level": "Alta",
                "is_ambiguous": False,
                "ambiguity_warning": None,
                "consistency_score": 1.0,
                "sample_line_count": len(lines[:20])
            }

        # Analyze candidate delimiters over top 25 non-empty lines
        test_lines = lines[:25]
        delim_scores = {}

        for d in SUPPORTED_DELIMITERS:
            counts = []
            for line in test_lines:
                # Count delimiter outside quotes
                try:
                    row = next(csv.reader([line], delimiter=d))
                    counts.append(len(row))
                except Exception:
                    counts.append(line.count(d) + 1)

            if not counts:
                continue

            # Consistency check: how uniform is the column count across lines?
            most_frequent_col_count = max(set(counts), key=counts.count)
            consistent_lines = sum(1 for c in counts if c == most_frequent_col_count)
            consistency = consistent_lines / len(counts)
            avg_cols = sum(counts) / len(counts)

            if most_frequent_col_count >= 2:
                # Weight by consistency (0.8) and column density (0.2)
                score = (consistency * 0.8) + (min(1.0, (avg_cols - 1) / 4) * 0.2)
                delim_scores[d] = {
                    "score": round(score, 3),
                    "consistency": round(consistency, 3),
                    "cols": most_frequent_col_count,
                    "avg_cols": round(avg_cols, 2)
                }

        if not delim_scores:
            # Fallback to standard Sniffer
            try:
                sample_str = "\n".join(test_lines[:10])
                sniffed = csv.Sniffer().sniff(sample_str, delimiters=";,|\t")
                return {
                    "delimiter": sniffed.delimiter,
                    "encoding": final_enc,
                    "quote_char": sniffed.quotechar or '"',
                    "confidence": 0.70,
                    "confidence_level": "Media",
                    "is_ambiguous": False,
                    "ambiguity_warning": None,
                    "consistency_score": 0.70,
                    "sample_line_count": len(test_lines)
                }
            except Exception:
                return {
                    "delimiter": ",",
                    "encoding": final_enc,
                    "quote_char": '"',
                    "confidence": 0.50,
                    "confidence_level": "Baja",
                    "is_ambiguous": True,
                    "ambiguity_warning": "No se pudo determinar el delimitador con suficiente certeza. Se usó coma por defecto; revisa la configuración.",
                    "consistency_score": 0.50,
                    "sample_line_count": len(test_lines)
                }

        # Sort candidates by score
        sorted_delims = sorted(delim_scores.items(), key=lambda x: (x[1]["score"], x[1]["cols"]), reverse=True)
        best_delim, best_stats = sorted_delims[0]

        # Check ambiguity: is there another delimiter with very close score?
        is_ambiguous = False
        ambiguity_warning = None

        if len(sorted_delims) > 1:
            second_delim, second_stats = sorted_delims[1]
            diff = best_stats["score"] - second_stats["score"]
            if diff < 0.15 and second_stats["cols"] >= 2:
                is_ambiguous = True
                ambiguity_warning = (
                    f"Ambigüedad detectada entre delimitador '{best_delim}' ({best_stats['cols']} cols, consistencia {int(best_stats['consistency']*100)}%) "
                    f"y '{second_delim}' ({second_stats['cols']} cols, consistencia {int(second_stats['consistency']*100)}%). "
                    "Verifica o selecciona el delimitador manualmente."
                )

        confidence = best_stats["score"]
        confidence_level = "Alta" if confidence >= 0.80 else ("Media" if confidence >= 0.65 else "Baja")
        if is_ambiguous:
            confidence = min(confidence, 0.65)
            confidence_level = "Media"

        # Quoting detection
        quote_char = '"'
        if any("'" in l for l in test_lines) and not any('"' in l for l in test_lines):
            quote_char = "'"

        return {
            "delimiter": best_delim,
            "encoding": final_enc,
            "quote_char": quote_char,
            "confidence": confidence,
            "confidence_level": confidence_level,
            "is_ambiguous": is_ambiguous,
            "ambiguity_warning": ambiguity_warning,
            "consistency_score": best_stats["consistency"],
            "col_count": best_stats["cols"],
            "sample_line_count": len(test_lines),
            "candidates": delim_scores
        }
